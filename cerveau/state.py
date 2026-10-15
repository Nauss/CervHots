"""Adaptation des DEUX sorties hotstate : triggers mémoire et replay temporel."""
from __future__ import annotations

import math

VALIDATED_COUNTERS = ("deaths_total", "respawns_total", "globes_total")


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def snapshot(raw: dict, *, at: float | None = None, team: int = 0,
             map_name: str | None = None, allies: list[str] | None = None,
             enemies: list[str] | None = None) -> dict:
    if not isinstance(raw, dict):
        raise TypeError("hotstate doit être un objet JSON")
    meta = raw.get("meta", {})
    if not isinstance(meta, dict):
        raise TypeError("meta doit être un objet JSON")
    is_replay = meta.get("source") == "replay" or "timeline" in raw
    clock = at if is_replay else meta.get("t_s")
    if is_replay and not _number(clock):
        raise ValueError("un replay exige --at SECONDES (aucune lecture du futur)")
    if clock is not None and not _number(clock):
        raise ValueError("temps de jeu invalide")
    if is_replay and _number(meta.get("duration_s")) and clock > meta["duration_s"]:
        raise ValueError("--at dépasse la durée du replay")
    result = {"meta": {"source": meta.get("source", "memory")}, "stats": {}}
    if clock is not None:
        result["meta"]["t_s"] = clock
    if map_name or meta.get("map"):
        result["meta"]["map"] = map_name or meta["map"]
    players = raw.get("players", [])
    if not isinstance(players, list) or not all(isinstance(p, dict) for p in players):
        raise TypeError("players doit être une liste d'objets")
    result["composition"] = {
        "allies": allies if allies is not None else [
            p["hero"] for p in players if p.get("team") == team and p.get("hero")],
        "enemies": enemies if enemies is not None else [
            p["hero"] for p in players if p.get("team") in (0, 1)
            and p["team"] != team and p.get("hero")],
    }
    result["ally_team"] = team
    if not is_replay:
        stats = raw.get("stats", raw)
        if not isinstance(stats, dict):
            raise TypeError("stats doit être un objet JSON")
        result["stats"] = {key: stats[key] for key in VALIDATED_COUNTERS
                           if type(stats.get(key)) is int and stats[key] >= 0}
        if not result["stats"]:
            raise ValueError("aucun compteur mémoire validé disponible")
        return result

    roster = {p.get("name", str(i)): {"hero": p["hero"], "team": p.get("team")}
              for i, p in enumerate(players) if p.get("hero")}
    events = []
    timeline = raw.get("timeline", {})
    for kind in ("hero_events", "stat_events", "structure_events"):
        for event in timeline.get(kind, []):
            if (not _number(event.get("t")) or event["t"] > clock
                    or event.get("name", "").startswith("EndOfGame")):
                continue
            member = roster.get(event.get("player"))
            if member is not None:
                if event.get("type") in ("spawn", "respawn", "death"):
                    member["alive"] = event["type"] != "death"
                if event.get("name") == "LevelUp":
                    level = event.get("data", {}).get("Level")
                    if type(level) is int and level > 0:
                        member["level"] = level
            # Noms des joueurs, chat, score et résultat finaux ne partent pas vers le LLM.
            clean = {k: v for k, v in event.items()
                     if k in ("t", "type", "name", "hero", "team", "upgrade", "pos")}
            if member is not None:
                clean["team"] = member["team"]
            data = dict(event.get("data", {}))
            fixed_team = data.pop("TeamID", None)
            if fixed_team in (4096, 8192):
                clean["team"] = fixed_team // 4096 - 1
            for key in list(data):
                if (key in ("PlayerID", "KillingPlayer", "GameTime", "PreviousGameTime",
                            "PositionX", "PositionY") or key.endswith("XP")):
                    del data[key]
            if data:
                clean["data"] = data
            events.append(clean)
    result["heroes"] = list(roster.values())
    result["events"] = sorted(events, key=lambda e: e["t"])[-24:]
    result["stats"]["deaths_total"] = sum(e.get("type") == "death" for e in events)
    positions = [p for p in raw.get("position_snapshots", [])
                 if _number(p.get("t")) and p["t"] <= clock]
    if positions:
        latest = max(positions, key=lambda p: p["t"])
        result["positions"] = {
            "t": latest["t"],
            "heroes": [{"hero": roster[name]["hero"], "team": roster[name]["team"],
                        "x": pos["x"] / 4, "y": pos["y"] / 4}
                       for name, pos in latest["positions"].items() if name in roster],
        }
    return result
