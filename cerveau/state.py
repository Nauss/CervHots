"""Adaptation des DEUX sorties hotstate : triggers mémoire et replay temporel."""
from __future__ import annotations

import math
import re

VALIDATED_COUNTERS = ("deaths_total", "respawns_total", "globes_total")


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _native_heroes(raw, players, local, team):
    heroes = raw.get("heroes")
    if (local is None or len(players) != 10 or not isinstance(heroes, list) or len(heroes) != 10
            or not all(type(p.get("id")) is int and type(p.get("team")) is int
                       and p["team"] in (0, 1) for p in players)
            or {p["id"] for p in players} != set(range(10))
            or any(sum(p["team"] == t for p in players) != 5 for t in (0, 1))):
        raise ValueError("composition native incomplète")
    roster = {p["id"]: p for p in players}
    if any(roster[local["id"]].get(k) != local[k] for k in ("hero", "team")):
        raise ValueError("identité locale native incohérente")
    observed, seen = [], set()
    for hero in heroes:
        if (not isinstance(hero, dict) or type(hero.get("id")) is not int
                or hero["id"] not in roster or hero["id"] in seen
                or any(hero.get(k) != roster[hero["id"]].get(k) for k in ("hero", "team"))
                or type(hero.get("alive")) is not bool or type(hero.get("level")) is not int
                or not 1 <= hero["level"] <= 30):
            raise ValueError("état de héros natif invalide")
        seen.add(hero["id"])
        clean = {k: hero[k] for k in ("id", "hero", "team", "alive", "level")}
        if not hero["alive"] and _number(hero.get("respawn_s")) and hero["respawn_s"] <= 600:
            clean["respawn_s"] = hero["respawn_s"]
        if hero["team"] == team == local["team"]:
            for value, maximum in (("health", "health_max"), ("resource", "resource_max")):
                if (_number(hero.get(value)) and _number(hero.get(maximum))
                        and 0 < hero[maximum] and hero[value] <= hero[maximum]):
                    clean.update({value: hero[value], maximum: hero[maximum]})
        observed.append(clean)
    return observed


def snapshot(raw: dict, *, at: float | None = None, team: int | None = None,
             map_name: str | None = None, allies: list[str] | None = None,
             enemies: list[str] | None = None) -> dict:
    if not isinstance(raw, dict):
        raise TypeError("hotstate doit être un objet JSON")
    meta = raw.get("meta", {})
    if not isinstance(meta, dict):
        raise TypeError("meta doit être un objet JSON")
    local = raw.get("local_player")
    if local is not None:
        if (not isinstance(local, dict) or type(local.get("team")) is not int
                or local["team"] not in (0, 1) or type(local.get("id")) is not int
                or not 0 <= local["id"] < 16 or not isinstance(local.get("hero"), str)
                or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", local["hero"])):
            raise ValueError("identité locale invalide")
        local = {k: local[k] for k in ("id", "team", "hero")}
    if team is None:
        team = local["team"] if local is not None else 0
    if type(team) is not int or team not in (0, 1):
        raise ValueError("équipe alliée invalide")
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
    if is_replay or meta.get("native_status") == "valide":
        result["meta"]["clock_kind"] = "mission"
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
        if meta.get("native_status") == "valide":
            result["heroes"] = _native_heroes(raw, players, local, team)
            result["meta"]["native_status"] = "valide"
            if type(meta.get("native_build")) is int:
                result["meta"]["native_build"] = meta["native_build"]
        if not result["stats"] and "heroes" not in result:
            raise ValueError("aucun compteur mémoire validé disponible")
        if local is not None:
            result["local_player"] = local
        if "composition_complete" in raw:
            result["composition_complete"] = (
                raw["composition_complete"] is True and len(players) == 10
                and all(isinstance(p.get("hero"), str) and p["hero"] for p in players)
                and all(sum(p.get("team") == t for p in players) == 5 for t in (0, 1)))
        if meta.get("context_source") == "initdata_memory":
            result["meta"]["context_source"] = "initdata_memory"
            match_id = meta.get("match_id")
            if isinstance(match_id, str) and re.fullmatch(r"[0-9a-f]{64}", match_id):
                result["meta"]["match_id"] = match_id
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
