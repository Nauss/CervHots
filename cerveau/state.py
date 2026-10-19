"""Adaptation des DEUX sorties hotstate : triggers mémoire et replay temporel."""
from __future__ import annotations

import math
import re

VALIDATED_COUNTERS = ("deaths_total", "respawns_total", "globes_total")


def _number(value) -> bool:
    return ((type(value) is int and value >= 0)
            or (type(value) is float and math.isfinite(value) and value >= 0))


def validated_gameplay_clock(meta):
    """Typed HUD allowlist; never reinterpret mission/replay time as HUD time."""
    clock = meta.get("gameplay_clock")
    if not isinstance(clock, dict) or meta.get("source") == "replay":
        return None
    seconds, phase = clock.get("t_s"), clock.get("phase")
    mission, window = clock.get("mission_t_s"), clock.get("read_window_s")
    if (clock.get("status") != "validated" or phase not in ("preparation", "playing")
            or type(seconds) not in (int, float) or not -3600 <= seconds <= 21600
            or (phase == "preparation" and not -600 <= seconds < 0)
            or type(clock.get("timer_paused")) is not bool
            or not _number(window) or window > 0.125
            or not _number(mission) or mission > 21600
            or not _number(meta.get("t_s")) or meta["t_s"] > 21600
            or not 0 <= meta["t_s"] - mission <= 1):
        return None
    return {key: clock[key] for key in ("status", "t_s", "phase", "timer_paused",
                                        "read_window_s", "mission_t_s")}


def _native_positions(raw, heroes, local, team):
    """Fail closed at the model boundary, independently of the native producer."""
    from hotstate import positions
    from hotstate.acquisition import fresh

    packet, meta = raw.get("positions"), raw["meta"]
    if (not isinstance(packet, dict) or local is None or team != local["team"]
            or meta.get("source") != "live" or meta.get("native_build") != 98348
            or packet.get("status") != "validated"
            or not fresh(packet)
            or packet.get("map_id") not in positions.VALIDATED_MAPS
            or packet.get("map_id") != meta.get("map_id")
            or meta.get("context_source") not in ("initdata_memory", "initdata_native_fields")
            or not isinstance(meta.get("match_id"), str)
            or not re.fullmatch("[0-9a-f]{64}", meta["match_id"])
            or packet.get("match_id") != meta["match_id"]
            or type(packet.get("local_id")) is not int or packet["local_id"] != local["id"]
            or type(packet.get("team")) is not int or packet["team"] != team
            or not _number(packet.get("mission_t_s")) or packet["mission_t_s"] > 21600
            or not _number(meta.get("t_s")) or meta["t_s"] > 21600
            or not 0 <= meta["t_s"] - packet["mission_t_s"] <= 1
            or not _number(packet.get("read_window_s")) or packet["read_window_s"] > 0.125):
        return None
    bounds = packet.get("bounds")
    if (not isinstance(bounds, list) or len(bounds) != 4
            or bounds != positions.playable_bounds(packet["map_id"])
            or any(type(value) is not int for value in bounds)
            or not -256 <= bounds[0] < bounds[2] <= 512
            or not -256 <= bounds[1] < bounds[3] <= 512):
        return None
    samples = packet.get("heroes")
    if not isinstance(samples, list) or len(samples) > 5:
        return None
    roster = {h["id"]: h for h in heroes}
    clean, seen = [], set()
    xmin, ymin, xmax, ymax = bounds
    for sample in samples:
        if not isinstance(sample, dict) or type(sample.get("id")) is not int:
            return None
        member = roster.get(sample["id"])
        if (member is None or member["team"] != team or not member["alive"]
                or sample["id"] in seen or sample.get("hero") != member["hero"]
                or type(sample.get("x")) not in (int, float)
                or type(sample.get("y")) not in (int, float)
                or not xmin <= sample["x"] <= xmax or not ymin <= sample["y"] <= ymax):
            return None
        seen.add(sample["id"])
        x, y = sample["x"], sample["y"]
        clean.append({"id": sample["id"], "hero": member["hero"], "team": team,
                      "x": x, "y": y, "u": (x - xmin) / (xmax - xmin),
                      "v": 1 - (y - ymin) / (ymax - ymin)})
    return {"t": packet["mission_t_s"], "map_id": packet["map_id"],
            "heroes": sorted(clean, key=lambda h: h["id"])}


def _native_visibility(raw, heroes, local, team):
    """Boolean current sight only. Never a permission for enemy tactical fields."""
    from hotstate import visibility
    from hotstate.acquisition import fresh

    p, meta = raw.get('visibility'), raw['meta']
    if (not isinstance(p, dict) or local is None or team != local['team']
            or meta.get('source') != 'live' or meta.get('native_build') != 98348
            or meta.get('context_source') not in ('initdata_memory', 'initdata_native_fields')
            or p.get('status') != 'validated' or not fresh(p)
            or p.get('map_id') not in visibility.VALIDATED_MAPS
            or p.get('map_id') != meta.get('map_id')
            or not isinstance(meta.get('match_id'), str)
            or not re.fullmatch('[0-9a-f]{64}', meta['match_id'])
            or p.get('match_id') != meta['match_id']
            or type(p.get('local_id')) is not int or p['local_id'] != local['id']
            or type(p.get('team')) is not int or p['team'] != team
            or p.get('local_hero') != local['hero']
            or not _number(p.get('mission_t_s')) or not _number(meta.get('t_s'))
            or not 0 <= meta['t_s'] - p['mission_t_s'] <= 1
            or not _number(p.get('read_window_s')) or p['read_window_s'] > 0.125):
        return None
    samples = p.get('heroes')
    if not isinstance(samples, list) or len(samples) != 10:
        return None
    roster = {h['id']: h for h in heroes}
    clean, seen = [], set()
    for sample in samples:
        if not isinstance(sample, dict) or type(sample.get('id')) is not int:
            return None
        member = roster.get(sample['id'])
        if (member is None or sample['id'] in seen or sample.get('hero') != member['hero']
                or 'visible' not in sample
                or (sample['visible'] is not None and type(sample['visible']) is not bool)
                or (not member['alive'] and sample['visible'] is not None)):
            return None
        seen.add(sample['id'])
        clean.append({'id': sample['id'], 'hero': member['hero'], 'visible': sample['visible']})
    return {'t': p['mission_t_s'], 'map_id': p['map_id'],
            'heroes': sorted(clean, key=lambda h: h['id'])}


def _native_heroes(raw, players, local, team):
    heroes = raw.get("heroes")
    if (local is None or len(players) != 10 or not isinstance(heroes, list) or len(heroes) != 10
            or not all(type(p.get("id")) is int and type(p.get("team")) is int
                       and p["team"] in (0, 1) for p in players)
            or {p["id"] for p in players} != set(range(10))
            or any(sum(p["team"] == t for p in players) != 5 for t in (0, 1))):
        raise ValueError("composition native incomplète")
    roster = {p["id"]: p for p in players}
    if (local["id"] not in roster
            or any(roster[local["id"]].get(k) != local[k] for k in ("hero", "team"))):
        raise ValueError("identité locale native incohérente")
    from hotstate.acquisition import fresh
    packet, meta = raw.get('perspective'), raw.get('meta', {})
    vitals_permitted = (
        isinstance(packet, dict) and fresh(packet)
        and meta.get('source') == 'live' and meta.get('native_build') == 98348
        and meta.get('context_source') in ('initdata_memory', 'initdata_native_fields')
        and isinstance(meta.get('match_id'), str)
        and re.fullmatch('[0-9a-f]{64}', meta['match_id']) is not None
        and packet.get('match_id') == meta['match_id']
        and packet.get('local_id') == local['id'] and packet.get('team') == team == local['team']
        and packet.get('local_hero') == local['hero'] and packet.get('heroes') == heroes
        and _number(packet.get('mission_t_s')) and _number(meta.get('t_s'))
        and 0 <= meta['t_s'] - packet['mission_t_s'] <= 1
        and _number(packet.get('read_window_s')) and packet['read_window_s'] <= 0.125)
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
        if vitals_permitted and hero["team"] == team == local["team"]:
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
            positions = _native_positions(raw, result["heroes"], local, team)
            if positions is not None and (map_name is None or map_name == meta.get("map")):
                result["positions"] = positions
            visibility = _native_visibility(raw, result['heroes'], local, team)
            if visibility is not None and (map_name is None or map_name == meta.get('map')):
                result['visibility'] = visibility
            from .objectives import project_objective
            objective = project_objective(raw, local, team)
            if objective is not None and (map_name is None or map_name == meta.get('map')):
                result['objective'] = objective
            result["meta"]["native_status"] = "valide"
            gameplay_clock = validated_gameplay_clock(meta)
            if gameplay_clock is not None:
                result["meta"]["gameplay_clock"] = gameplay_clock
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
        if meta.get("context_source") in ("initdata_memory", "initdata_native_fields"):
            result["meta"]["context_source"] = meta["context_source"]
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
            data = event.get("data", {})
            if not isinstance(data, dict):
                data = {}
            member = roster.get(event.get("player"))
            if member is not None:
                if event.get("type") in ("spawn", "respawn", "death"):
                    member["alive"] = event["type"] != "death"
                if event.get("name") == "LevelUp":
                    level = data.get("Level")
                    if type(level) is int and 1 <= level <= 30:
                        member["level"] = level
            # Noms des joueurs, chat, score et résultat finaux ne partent pas vers le LLM.
            clean = {k: v for k, v in event.items()
                     if k in ("t", "type", "name", "hero", "team", "upgrade", "pos")}
            if member is not None:
                clean["team"] = member["team"]
            fixed_team = data.get("TeamID")
            if type(fixed_team) is int and fixed_team in (4096, 8192):
                clean["team"] = fixed_team // 4096 - 1
            # Typed allowlist: never forward arbitrary strings, nested values,
            # account identifiers or unknown future tracker fields. Event kind,
            # hero, team, upgrade and positions still carry tactical facts.
            level = data.get("Level")
            if event.get("name") == "LevelUp" and type(level) is int and 1 <= level <= 30:
                clean["data"] = {"Level": level}
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
