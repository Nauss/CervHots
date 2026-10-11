#!/usr/bin/env python
"""hotstate/extract.py — .StormReplay -> état de jeu (contrat hotstate).

Extrait d'un replay HotS toutes les stats utiles à l'agent de décision :
joueurs/héros, timeline (naissances, morts, respawns, talents, structures,
pings, chat), instantanés de positions, score final.

Usage:
    python extract.py <replay.StormReplay> [--out game_state.json] [--summary]

Décodeur : Blizzard heroprotocol (officiel). Les builds récents non listés par
heroprotocol sont décodés avec le dernier protocole connu (shim documenté dans
le README) — vérifié fonctionnel sur les replays 97xxx/98xxx.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

import mpyq
from heroprotocol import versions

LOOPS_PER_SECOND = 16.0  # boucles de jeu HotS par seconde
FILETIME_EPOCH = 11644473600  # 1601 -> 1970, en secondes
HERO_PREFIX = "Hero"


# ---------------------------------------------------------------- utilitaires

def to_str(v):
    """bytes -> str (UTF-8, repli latin-1), récursif ; JSON-safe partout."""
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.decode("latin-1", errors="replace")
    if isinstance(v, dict):
        return {to_str(k): to_str(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [to_str(x) for x in v]
    return v


def t_sec(gameloop):
    return round(gameloop / LOOPS_PER_SECOND, 2)


def filetime_to_iso(ft):
    if not ft:
        return None
    try:
        ts = ft / 1e7 - FILETIME_EPOCH
        return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def load_protocol(archive):
    """Header -> protocole. Shim : build inconnu -> dernier protocole connu."""
    latest = versions.latest()
    header = to_str(latest.decode_replay_header(
        archive.header["user_data_header"]["content"]))
    base_build = header["m_version"]["m_baseBuild"]
    shim = False
    try:
        proto = versions.build(base_build)
    except Exception:
        proto, shim = versions.latest(), True
    return proto, header, base_build, shim


def decode_positions(ev):
    """SUnitPositionsEvent -> {unitIndex: (x, y)} (cf. README heroprotocol)."""
    out, unit_index = {}, ev.get("m_firstUnitIndex", 0)
    items = ev.get("m_items") or []
    for i in range(0, len(items), 3):
        unit_index += items[i + 0]
        out[unit_index] = (items[i + 1] * 4, items[i + 2] * 4)
    return out


# ------------------------------------------------------------------- extraction

def extract(replay_path: Path) -> dict:
    archive = mpyq.MPQArchive(str(replay_path))
    proto, header, base_build, shim = load_protocol(archive)

    details = to_str(proto.decode_replay_details(archive.read_file("replay.details")))
    players_raw = details.get("m_playerList") or []

    players = []
    for i, p in enumerate(players_raw):
        players.append({
            "id": p.get("m_workingSetSlotId", i),
            "index": i,
            "name": p.get("m_name"),
            "hero": p.get("m_hero"),
            "team": p.get("m_teamId"),
            "result": p.get("m_result"),
        })

    def player_by_ctrl(pid):
        """m_controlPlayerId (tracker) -> joueur ; slot+1 en priorité."""
        for pl in players:
            if pl["id"] is not None and pl["id"] + 1 == pid:
                return pl
        if isinstance(pid, int) and 1 <= pid <= len(players):
            return players[pid - 1]
        return None

    hero_tags = {}   # unitTag -> player
    hero_events, structure_events, stat_events, comms, snapshots = [], [], [], [], []
    stat_names = Counter()
    score_event = None

    for ev in proto.decode_replay_tracker_events(archive.read_file("replay.tracker.events")):
        name = ev.get("_event", "")
        t = t_sec(ev.get("_gameloop", 0))
        short = name.rsplit(".", 1)[-1]

        if short == "SUnitBornEvent":
            unit = to_str(ev.get("m_unitTypeName", ""))
            pl = player_by_ctrl(ev.get("m_controlPlayerId"))
            tag = proto.unit_tag(ev.get("m_unitTagIndex", 0), ev.get("m_unitTagRecycle", 0))
            if unit.startswith(HERO_PREFIX) and pl:
                hero_tags[tag] = pl
                hero_events.append({
                    "t": t, "type": "spawn", "player": pl["name"], "hero": pl["hero"],
                    "pos": [ev.get("m_x"), ev.get("m_y")],
                })
            elif unit.startswith("Town") or unit.startswith("Moonwell") or "Gate" in unit:
                structure_events.append({
                    "t": t, "type": "structure_born", "unit": unit,
                    "team": pl["team"] if pl else None,
                    "pos": [ev.get("m_x"), ev.get("m_y")],
                })

        elif short == "SUnitDiedEvent":
            tag = proto.unit_tag(ev.get("m_unitTagIndex", 0), ev.get("m_unitTagRecycle", 0))
            killer = player_by_ctrl(ev.get("m_killerPlayerId"))
            if tag in hero_tags:
                pl = hero_tags[tag]
                hero_events.append({
                    "t": t, "type": "death", "player": pl["name"], "hero": pl["hero"],
                    "pos": [ev.get("m_x"), ev.get("m_y")],
                    "killer": killer["name"] if killer else None,
                })
            else:
                # structure / unit : ne garder que les cibles structurantes
                pass

        elif short == "SUnitRevivedEvent":
            tag = proto.unit_tag(ev.get("m_unitTagIndex", 0), ev.get("m_unitTagRecycle", 0))
            if tag in hero_tags:
                pl = hero_tags[tag]
                hero_events.append({
                    "t": t, "type": "respawn", "player": pl["name"], "hero": pl["hero"],
                    "pos": [ev.get("m_x"), ev.get("m_y")],
                })

        elif short == "SUpgradeEvent":
            up = to_str(ev.get("m_upgradeTypeName", ""))
            pl = player_by_ctrl(ev.get("m_playerId"))
            if up and up not in ("CreepColor",):
                hero_events.append({
                    "t": t, "type": "upgrade", "player": pl["name"] if pl else None,
                    "hero": pl["hero"] if pl else None, "upgrade": up,
                    "count": ev.get("m_count"),
                })

        elif short == "SStatGameEvent":
            ev_name = to_str(ev.get("m_eventName", ""))
            stat_names[ev_name] += 1
            data = {}
            for src in ("m_intData", "m_stringData", "m_fixedData"):
                for e in (ev.get(src) or []):
                    k, v = to_str(e.get("m_key")), to_str(e.get("m_value"))
                    if k in data:
                        if not isinstance(data[k], list):
                            data[k] = [data[k]]
                        data[k].append(v)
                    else:
                        data[k] = v
            entry = {"t": t, "name": ev_name, "data": data}
            pid = data.get("PlayerID")
            if isinstance(pid, int):
                pl = player_by_ctrl(pid)
                if pl:
                    entry["player"] = pl["name"]
                    entry["hero"] = pl["hero"]
            stat_events.append(entry)

        elif short == "SUnitPositionsEvent":
            raw = decode_positions(ev)
            pos = {}
            for tag, pl in hero_tags.items():
                idx = proto.unit_tag_index(tag)
                if idx in raw:
                    pos[pl["name"]] = {"x": raw[idx][0], "y": raw[idx][1]}
            if pos:
                snapshots.append({"t": t, "positions": pos})

        elif short == "SScoreResultEvent":
            score_event = ev

        elif short in ("SUnitOwnerChangeEvent", "SUnitTypeChangeEvent"):
            pass  # utile plus tard (camps de mercenaires, objectifs de map)

    for ev in proto.decode_replay_message_events(archive.read_file("replay.message.events")):
        short = ev.get("_event", "").rsplit(".", 1)[-1]
        t = t_sec(ev.get("_gameloop", 0))
        uid = ev.get("_userid", {}).get("m_userId") if isinstance(ev.get("_userid"), dict) else None
        pl = players[uid] if isinstance(uid, int) and 0 <= uid < len(players) else None
        if short == "SPingMessage":
            pt = ev.get("m_point") or {}
            comms.append({
                "t": t, "type": "ping",
                "player": pl["name"] if pl else None,
                "pos": [pt.get("x"), pt.get("y")],
            })
        elif short == "SChatMessage":
            comms.append({
                "t": t, "type": "chat",
                "player": pl["name"] if pl else None,
                "text": to_str(ev.get("m_string")),
            })

    final_score = {}
    if score_event is not None:
        for inst in score_event.get("m_instanceList") or []:
            stat = to_str(inst.get("m_name"))
            vals = []
            for i, series in enumerate(inst.get("m_values") or []):
                if i < len(players) and series:
                    last = series[-1]
                    vals.append({"player": players[i]["name"], "value": last.get("m_value"),
                                 "t": t_sec(last.get("m_time", 0))})
            final_score[stat] = vals

    hero_events.sort(key=lambda e: e["t"])
    duration = t_sec(header.get("m_elapsedGameLoops", 0))

    return {
        "meta": {
            "source": "replay",
            "file": replay_path.name,
            "map": details.get("m_title"),
            "date_utc": filetime_to_iso(details.get("m_timeUTC")),
            "build": base_build,
            "protocol": proto.__name__,
            "protocol_shim": shim,
            "duration_s": duration,
        },
        "players": players,
        "timeline": {
            "hero_events": hero_events,
            "stat_events": stat_events,
            "structure_events": structure_events,
            "comms": comms,
        },
        "position_snapshots": snapshots,
        "final_score": final_score,
        "available": {"stat_event_names": dict(stat_names)},
    }


# ----------------------------------------------------------------------- CLI

def print_summary(state: dict):
    m = state["meta"]
    print(f"Partie : {m['map']}  |  {m['date_utc']}  |  {m['duration_s']:.0f} s")
    print(f"Build {m['build']} (protocole {m['protocol']}{', SHIM' if m['protocol_shim'] else ''})")
    for p in state["players"]:
        res = {1: "victoire", 2: "défaite"}.get(p["result"], p["result"])
        print(f"  [{p['team']}] {p['name']:<22} {p['hero']:<14} {res}")
    he = state["timeline"]["hero_events"]
    counts = Counter(e["type"] for e in he)
    print("Événements héros :", dict(counts))
    deaths = [e for e in he if e["type"] == "death"]
    if deaths:
        print("Morts :", ", ".join(f"{e['player']}@{e['t']:.0f}s" for e in deaths[:8]), "...")
    snaps = state["position_snapshots"]
    print(f"Instantanés de positions : {len(snaps)}"
          + (f" (premier à {snaps[0]['t']} s)" if snaps else ""))
    if state["final_score"]:
        for stat in ("Takedowns", "Deaths", "HeroDamage", "SiegeDamage", "Healing"):
            if stat in state["final_score"]:
                vals = ", ".join(f"{v['player']}={v['value']}" for v in state["final_score"][stat][:5])
                print(f"{stat} : {vals}")
    print("Stat events disponibles :", dict(state["available"]["stat_event_names"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("replay", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()

    state = extract(args.replay)
    out = args.out or args.replay.with_suffix(".hotstate.json")
    out.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"écrit : {out}")
    if args.summary:
        print_summary(state)


if __name__ == "__main__":
    main()
