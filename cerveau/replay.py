"""Player-facing replay projection, NOT an omniscient tracker view.

No visibility history is produced by hotstate.extract: enemy XY and event XY
are therefore unconditionally absent. Diagnostic extraction remains separate.
Only catalogued strings and newly constructed, typed values cross this seam.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_HERO_IDS = json.loads((ROOT / 'hotstate/hero_ids.json').read_text(encoding='utf-8'))
HEROES = {s.casefold(): s for s in (*_HERO_IDS.values(), *_HERO_IDS)}
_MAPS = json.loads((ROOT / 'kb/data/map_timings.json').read_text(encoding='utf-8'))['maps']
MAPS = {s.casefold(): name for name, row in _MAPS.items()
        for s in (name, row['slug'], *row.get('aliases_fr', []))}
# Public, global announcements actually inventoried in events_par_carte.json.
# Do NOT use the whole inventory: it also contains private loot/endgame events.
PUBLIC_OBJECTIVES = frozenset((
    'TributeCollected', 'RavenCurseActivated', 'DragonKnightActivated',
    'VolskayaCapturePointSpawned', 'VolskayaCapturePointComplete',
    'BraxisHoldoutMapEventComplete', 'SkyTempleActivated', 'SkyTempleCaptured',
    'SkyTempleShotsFired', 'GhostShipCaptured', 'HauntedMinesGolemsSpawned',
    'SoulEatersSpawned', 'Boss Duel Started', 'Immortal Defeated',
    'Infernal Shrine Captured', 'Punisher Killed', 'Altar Captured',
    'Town Captured', 'Six Town Event Start', 'Six Town Event End',
))
LIFE_EVENTS = ('spawn', 'respawn', 'death')
MAX_TIME_S = 21600  # same engineering ceiling as the native consumer
MAX_POSITION_AGE_S = 1  # no interpolation across the ~15s tracker cadence
MAX_RAW_XY = 2048  # extract multiplies by 4; consumer outer envelope is 512


def _number(value, maximum):
    return (type(value) in (int, float) and 0 <= value <= maximum
            and (type(value) is int or math.isfinite(value)))


def _known(value, vocabulary):
    return vocabulary.get(value.casefold()) if type(value) is str and len(value) <= 80 else None


def _rows(value):
    return value if isinstance(value, list) else []


def project(raw, *, at, team, map_name=None, allies=None, enemies=None):
    """Single normalized coach contract; explicit team or coherent local slot.

    Explicit team selects a hypothetical offline player's side, not a verified
    human identity. It NEVER grants enemy coordinates. No omniscient option.
    """
    meta = raw['meta'] if isinstance(raw.get('meta'), dict) else {}
    if not _number(at, MAX_TIME_S):
        raise ValueError('un replay exige --at SECONDES borné (aucune lecture du futur)')
    if _number(meta.get('duration_s'), MAX_TIME_S) and at > meta['duration_s']:
        raise ValueError('--at dépasse la durée du replay')
    players = raw.get('players', [])
    if not isinstance(players, list) or not all(isinstance(p, dict) for p in players):
        raise TypeError("players doit être une liste d'objets")
    if len(players) > 10:
        raise ValueError('composition replay ambiguë')
    members, roster, ambiguous, seen_names = [], {}, set(), set()
    for player in players:
        name = player.get('name')
        if type(name) is str and 0 < len(name) <= 256:
            if name in seen_names:
                ambiguous.add(name)
            seen_names.add(name)
        hero, side = _known(player.get('hero'), HEROES), player.get('team')
        if hero is None or type(side) is not int or side not in (0, 1):
            continue
        member = {'hero': hero, 'team': side}
        members.append((player, member))
        if type(name) is str and 0 < len(name) <= 256:
            roster[name] = member
    for name in ambiguous:
        roster.pop(name, None)
    local = raw.get('local_player')
    if local is not None:
        if not isinstance(local, dict) or type(local.get('id')) is not int:
            raise ValueError('identité locale replay invalide')
        matched = [member for player, member in members
                   if type(player.get('id')) is int and player['id'] == local['id']]
        if (len(matched) != 1 or type(local.get('team')) is not int
                or local['team'] != matched[0]['team']
                or _known(local.get('hero'), HEROES) != matched[0]['hero']):
            raise ValueError('identité locale replay observateur ou ambiguë')
        if team is None:
            team = local['team']
        if team != local['team']:
            raise ValueError('équipe replay contradictoire')
    if type(team) is not int or team not in (0, 1):
        raise ValueError('un replay exige une équipe joueur explicite')
    result = {'meta': {'source': 'replay', 't_s': at, 'clock_kind': 'mission'},
              'stats': {}, 'ally_team': team}
    map_id = _known(map_name if map_name is not None else meta.get('map'), MAPS)
    if map_id is not None:
        result['meta']['map'] = map_id
    result['composition'] = {}
    for key, override, side in (('allies', allies, team), ('enemies', enemies, 1 - team)):
        result['composition'][key] = (
            [hero for value in _rows(override)[:5] if (hero := _known(value, HEROES)) is not None]
            if override is not None else [m['hero'] for _, m in members if m['team'] == side])
    timeline = raw.get('timeline')
    timeline = timeline if isinstance(timeline, dict) else {}
    hero_rows = timeline.get('hero_events')
    life_complete = (isinstance(hero_rows, list)
                     and all(isinstance(e, dict) and _number(e.get('t'), MAX_TIME_S)
                             and (e['t'] > at or (type(e.get('type')) is str
                                  and e['type'] in (*LIFE_EVENTS, 'upgrade')))
                             for e in hero_rows))
    pending = []
    for family in ('hero_events', 'stat_events'):
        for event in _rows(timeline.get(family)):
            if isinstance(event, dict) and _number(event.get('t'), at):
                pending.append((event['t'], family, event))
    events, life_times, life_values = [], {}, {}
    for t, family, event in sorted(pending, key=lambda item: item[0]):
        kind, name = event.get('type'), event.get('name')
        is_life = family == 'hero_events' and type(kind) is str and kind in LIFE_EVENTS
        is_stat = (family == 'stat_events' and type(name) is str
                   and (name == 'LevelUp' or name in PUBLIC_OBJECTIVES))
        if not is_life and not is_stat:
            continue
        clean = {'t': t, 'type': kind} if is_life else {'t': t, 'name': name}
        player = event.get('player')
        member = roster.get(player) if type(player) is str else None
        hero = _known(event.get('hero'), HEROES)
        conflicting_hero = (member is not None and event.get('hero') is not None
                            and hero != member['hero'])
        if is_life and (member is None or conflicting_hero):
            # An unbound/contradictory transition is not evidence that everyone
            # stayed alive. Invalidate the whole life family; never join by hero.
            life_complete = False
            continue
        if member is not None:
            if conflicting_hero:
                continue
            clean.update(hero=member['hero'], team=member['team'])
            if is_life:
                key, alive = id(member), kind != 'death'
                if life_times.get(key) == t and life_values.get(key) != alive:
                    member.pop('alive', None)
                    life_values[key] = None
                else:
                    member['alive'] = alive
                    life_values[key] = alive
                life_times[key] = t
        elif hero is not None:
            clean['hero'] = hero
        data = event.get('data')
        data = data if isinstance(data, dict) else {}
        fixed_team = data.get('TeamID')
        if is_stat and type(fixed_team) is int and fixed_team in (4096, 8192):
            side = fixed_team // 4096 - 1
            if member is not None and side != member['team']:
                continue
            clean['team'] = side
        if name == 'LevelUp':
            level = data.get('Level')
            if type(level) is int and 1 <= level <= 30:
                clean['data'] = {'Level': level}
                if member is not None:
                    member['level'] = level
        # pos/unit/upgrade/name on life events, arbitrary data and all personal
        # keys are never copied, at ANY nesting depth. No raw value survives.
        events.append(clean)
    if not life_complete:
        for _, member in members:
            member.pop('alive', None)
    result['heroes'] = [dict(member) for _, member in members]
    result['events'] = events[-24:]
    if life_complete:
        result['stats']['deaths_total'] = sum(e.get('type') == 'death' for e in events)
    sample_rows = _rows(raw.get('position_snapshots'))
    dated_samples = all(isinstance(p, dict) and _number(p.get('t'), MAX_TIME_S)
                        for p in sample_rows)
    samples = [p for p in sample_rows
               if isinstance(p, dict) and _number(p.get('t'), at)]
    if samples and dated_samples:
        latest = max(samples, key=lambda p: p['t'])
        if sum(p['t'] == latest['t'] for p in samples) != 1:
            return result  # ambiguous latest observation, never select by input order
        positions = latest.get('positions')
        clean = []
        if at - latest['t'] <= MAX_POSITION_AGE_S and isinstance(positions, dict):
            for player, pos in positions.items():
                member = roster.get(player)
                if (member is None or member['team'] != team or member.get('alive') is not True
                        or life_times[id(member)] > latest['t'] or not isinstance(pos, dict)
                        or not all(_number(pos.get(k), MAX_RAW_XY) for k in ('x', 'y'))):
                    continue
                clean.append({'hero': member['hero'], 'team': team,
                              'x': pos['x'] / 4, 'y': pos['y'] / 4})
        if clean:
            result['positions'] = {'t': latest['t'], 'heroes': clean}
    return result
