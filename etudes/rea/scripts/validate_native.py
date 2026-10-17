#!/usr/bin/env python
"""Validate native memory against its own replay; optional real Groco call, no audio.

Replay data is used only as a reference. Only the anonymized captured observation
is passed to the coach. No process is opened by this script.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from cerveau.brain import Coach
from cerveau.runner import knowledge_for
from cerveau.state import snapshot as normalize
from hotstate.context import ContextProbe
from hotstate.extract import extract
from hotstate.protocols import load_protocol
from hotstate.reader import DumpBackend, snapshot
from kb.briefing import DB, resolve_hero


def reference_aliases(truth, archive):
    """Resolve localized names from independent tracker unit births, not the observation."""
    hero_ids = json.loads((Path(__file__).resolve().parents[3] / "hotstate/hero_ids.json").read_text())
    players = {p["id"] + 1: p["hero"] for p in truth["players"]}
    aliases = {}
    for event in load_protocol().decode_replay_tracker_events(archive.read_file("replay.tracker.events")):
        if not event.get("_event", "").endswith("SUnitBornEvent"):
            continue
        owner = event.get("m_controlPlayerId")
        unit = event.get("m_unitTypeName", b"").decode("ascii", "replace")
        token = unit.removeprefix("Hero")
        if owner in players and unit.startswith("Hero") and token in hero_ids:
            aliases.setdefault(players[owner], hero_ids[token])
    return aliases


def validate(observed, truth, aliases):
    with sqlite3.connect(DB) as connection:
        def canonical(hero):
            return aliases[hero] if hero in aliases else resolve_hero(hero, connection)

        expected = normalize(truth, at=observed["meta"]["t_s"])
        reference = {}
        for hero in expected["heroes"]:
            reference.setdefault((canonical(hero["hero"]), hero["team"]), []).append(hero)
        original_players = {p["id"]: p for p in truth["players"]}
        rows = []
        for hero in observed["heroes"]:
            original = original_players[hero["id"]]
            candidates = reference.get((hero["hero"], hero["team"]), [])
            fact = candidates[0] if len(candidates) == 1 else {}
            rows.append({"id": hero["id"], "hero": hero["hero"],
                         "team_matches": hero["team"] == original["team"],
                         "choice_matches": hero["hero"] == canonical(original["hero"]),
                         "level_matches": hero["level"] == fact.get("level"),
                         "alive_matches": hero["alive"] == fact.get("alive")})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("image", "heap", "manifest", "replay", "out"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--player", required=True)
    parser.add_argument("--api", action="store_true", help="one real Groco request; no TTS or Mumble")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    mapping = json.loads((Path(__file__).resolve().parents[3] / "hotstate/triggers_map.json").read_text())
    probe = ContextProbe(args.player)
    backend = DumpBackend(args.heap, args.manifest, image=args.image)
    try:
        observed = snapshot(backend, mapping, context=probe)
    finally:
        backend.close()
    (args.out / "observed.json").write_text(json.dumps(observed, indent=2), encoding="utf-8")
    if observed["meta"].get("native_status") != "valide":
        raise SystemExit("Native observation rejected: " + str(observed["meta"].get("native_status")))
    clean = normalize(observed)
    (args.out / "api-state.json").write_text(json.dumps(clean, indent=2), encoding="utf-8")
    truth = extract(args.replay)
    import mpyq

    archive = mpyq.MPQArchive(str(args.replay))
    rows = validate(observed, truth, reference_aliases(truth, archive))
    init = load_protocol().decode_replay_initdata(archive.read_file("replay.initData"))
    identity = (init["m_syncLobbyState"]["m_lobbyState"]["m_randomSeed"],
                tuple(init["m_syncLobbyState"]["m_gameDescription"]["m_cacheHandles"]))
    owner = next(p for p in truth["players"] if p["name"] == args.player)
    local = observed["local_player"]
    checks = {"native_profile_accepted": True, "match_identity": identity in probe.contexts,
              "local_id_and_team": all(local[k] == owner[k] for k in ("id", "team")),
              "ten_hero_choices": len(rows) == 10 and all(r["choice_matches"] for r in rows),
              "ten_teams": len(rows) == 10 and all(r["team_matches"] for r in rows),
              "ten_levels": len(rows) == 10 and all(r["level_matches"] for r in rows),
              "ten_alive_flags": len(rows) == 10 and all(r["alive_matches"] for r in rows)}
    dead = [hero for hero in observed["heroes"] if not hero["alive"]]
    report = {"source": "native_memory_captured_during_game", "clock_s": clean["meta"]["t_s"],
              "checks": checks, "heroes": rows, "audio_played": False,
              "respawn_real_case_present": bool(dead),
              "respawn_timers_observed": sum("respawn_s" in hero for hero in dead),
              "not_collected": ["objective_state", "camp_state", "structure_state",
                                "positions_and_visibility", "ability_cooldowns"]}
    report_path = args.out / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not all(checks.values()):
        raise SystemExit("Capture/replay checks failed: no API request sent")
    if args.api:
        from grocoapi import GrocoClient
        from grocoapi.client import _load_env_file

        calls, answers = [], []
        client = GrocoClient()

        class AuditedGateway:
            def chat(self, messages, **options):
                calls.append({"messages": messages, "model": options.get("model")})
                response = client.chat(messages, **options)
                answers.append(response["choices"][0]["message"]["content"])
                return response

        decision = Coach(AuditedGateway(), _load_env_file().get("GROCO_MODEL")).decide(
            clean, knowledge_for(clean))
        report["api"] = {"requests": len(calls), "responses": len(answers),
                         "decision": asdict(decision)}
        (args.out / "groco-trace.json").write_text(json.dumps(
            {"requests": calls, "responses": answers}, indent=2, ensure_ascii=False), encoding="utf-8")
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        if len(calls) != 1 or len(answers) != 1:
            raise SystemExit("No real Groco response; inspect the trace")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
