#!/usr/bin/env python
"""Valider un contexte dans un dump CONTRE le replay correspondant, sans son.

Le replay est la vérité terrain seulement ; ses champs ne sont jamais fusionnés
avec l'observation capturée envoyée en option à Groco.
"""
from __future__ import annotations

import argparse
import json
import mmap
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from cerveau.brain import Coach
from cerveau.runner import knowledge_for
from cerveau.state import snapshot as normalize
from hotstate.context import ContextProbe
from hotstate.extract import extract
from hotstate.reader import snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--heap", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--replay", required=True, type=Path)
    parser.add_argument("--player", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--api", action="store_true", help="vrai appel Groco, sans TTS ni Mumble")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    regions = json.loads(args.manifest.read_text(encoding="utf-8"))["regions"]
    mapping = json.loads((Path(__file__).resolve().parents[3]
                          / "hotstate/triggers_map.json").read_text(encoding="utf-8"))
    with args.heap.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        class MappedCapture:
            def regions_bytes(self):
                for region in regions:
                    yield region["addr"], data[region["offset"]:region["offset"] + region["size"]]

        context = ContextProbe(args.player)
        observed = snapshot(MappedCapture(), mapping, context=context)
    clean = normalize(observed)
    truth = extract(args.replay)
    expected = next(p for p in truth["players"] if p["name"] == args.player)
    local = observed.get("local_player", {})
    owner_ok = all(local.get(k) == expected[k] for k in ("id", "team", "hero"))
    teams_ok = len(observed.get("players", [])) == 10 and all(
        next(p for p in truth["players"] if p["id"] == q["id"])["team"] == q["team"]
        for q in observed["players"])
    # Vérifier l'identité de partie par seed+cache initData, sans envoyer le replay au modèle.
    import mpyq

    from hotstate.protocols import load_protocol

    archive = mpyq.MPQArchive(str(args.replay))
    init = load_protocol().decode_replay_initdata(archive.read_file("replay.initData"))
    identity = (init["m_syncLobbyState"]["m_lobbyState"]["m_randomSeed"],
                tuple(init["m_syncLobbyState"]["m_gameDescription"]["m_cacheHandles"]))
    match_ok = identity in context.contexts
    report = {"source": "dump_captured_during_game", "context_status": context.reason,
              "local_player_matches_replay": owner_ok, "ten_teams_match_replay": teams_ok,
              "match_identity_matches_replay": match_ok,
              "context": clean,
              "unknown": ["game_clock", "team_levels", "heroes_alive", "respawn_timers",
                          "AI_hero_choices_after_lobby"], "audio_played": False}
    (args.out / "observed.json").write_text(json.dumps(observed, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    if not (owner_ok and teams_ok and match_ok):
        (args.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
        raise SystemExit("Le contexte ne correspond pas au replay : aucun appel API")
    if args.api:
        from grocoapi import GrocoClient
        from grocoapi.client import _load_env_file

        requests, responses = [], []
        client = GrocoClient()

        class AuditedGateway:
            def chat(self, messages, **options):
                requests.append({"messages": messages, "model": options.get("model")})
                response = client.chat(messages, **options)
                responses.append(response["choices"][0]["message"]["content"])
                return response

        decision = Coach(AuditedGateway(), _load_env_file().get("GROCO_MODEL")).decide(
            clean, knowledge_for(clean))
        report["api"] = {"request_count": len(requests), "response_count": len(responses),
                         "decision": asdict(decision)}
        (args.out / "groco-trace.json").write_text(json.dumps(
            {"requests": requests, "responses": responses}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        if len(responses) != 1:
            raise RuntimeError("aucune réponse Groco réelle ; voir la trace")
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    (args.out / "report.json").write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
