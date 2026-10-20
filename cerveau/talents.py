"""Allied selected talent boundary, never enemy/possessions/offered options."""
from __future__ import annotations

import re
from hotstate.acquisition import fresh


def _number(value):
    return type(value) in (int, float) and -float('inf') < value < float('inf')


def project_talents(raw, local, team):
    from hotstate.talents import qualified_map, qualified_for
    p, meta, perspective = raw.get('talents'), raw.get('meta', {}), raw.get('perspective')
    if (not isinstance(local, dict) or type(team) is not int or team != local.get('team')
            or not isinstance(p, dict) or not isinstance(perspective, dict)
            or meta.get('source') != 'live' or meta.get('native_build') != 98348
            or meta.get('context_source') != 'initdata_native_fields'
            or p.get('status') != 'validated' or p.get('scope') != 'allied_selected_talents'
            or not fresh(p) or not fresh(perspective)
            or not qualified_map(p.get('map_id'))
            or p.get('map_id') != meta.get('map_id')
            or not isinstance(meta.get('match_id'), str)
            or not re.fullmatch('[0-9a-f]{64}', meta['match_id'])
            or not isinstance(p.get('native_session'), str)
            or not re.fullmatch('[0-9a-f]{64}', p['native_session'])
            or type(p.get('generation')) is not int or not 0 <= p['generation'] <= 0x3fffff
            or type(p.get('local_id')) is not int or p['local_id'] != local.get('id')
            or type(p.get('team')) is not int or p['team'] != team
            or p.get('local_hero') != local.get('hero')
            or p.get('match_id') != meta['match_id']
            or perspective.get('local_generation') != p['generation']
            or perspective.get('heroes') != raw.get('heroes')):
        return None
    for key in ('match_id', 'local_id', 'team', 'local_hero', 'native_session'):
        if p.get(key) != perspective.get(key):
            return None
    for packet in (p, perspective):
        if (not _number(packet.get('mission_t_s')) or not _number(meta.get('t_s'))
                or not 0 <= packet['mission_t_s'] <= 21600
                or not 0 <= meta['t_s']-packet['mission_t_s'] <= 1
                or not _number(packet.get('read_window_s')) or not 0 <= packet['read_window_s'] <= 0.125):
            return None
    rows, generations = p.get('players'), perspective.get('allied_generations')
    if not isinstance(rows, list) or len(rows) != 5 or not isinstance(generations, dict):
        return None
    roster = {h['id']:h for h in raw.get('heroes', []) if h.get('team') == team}
    if len(roster) != 5 or set(generations) != {str(i) for i in roster}:
        return None
    players, seen, observed = [], set(), False
    for row in rows:
        if not isinstance(row, dict) or type(row.get('id')) is not int:
            return None
        ident = row['id']
        member = roster.get(ident)
        if (member is None or ident in seen or row.get('hero') != member.get('hero')
                or not isinstance(row.get('hero'), str)
                or not re.fullmatch('[a-z][a-z0-9_-]{0,79}', row['hero'])
                or type(row.get('generation')) is not int or not 0 <= row['generation'] <= 0x3fffff
                or type(generations.get(str(ident))) is not int
                or row['generation'] != generations[str(ident)]):
            return None
        if ident == local['id'] and row['generation'] != p['generation']:
            return None
        seen.add(ident)
        status = row.get('status')
        if status == 'unknown':
            if row.get('tiers') is not None:
                return None
            tiers = None
        elif status == 'observed':
            if not qualified_for(p['map_id'], row['hero'], local=ident == local['id']):
                return None
            tiers = _project_tiers(row.get('tiers'), member.get('level'))
            if tiers is None:
                return None
            observed = True
        else:
            return None
        players.append({'id':ident, 'hero':row['hero'], 'status':status, 'tiers':tiers})
    if not observed:
        return None
    return {'t':p['mission_t_s'], 'map_id':p['map_id'], 'players':sorted(players, key=lambda r:r['id'])}


def _project_tiers(rows, hero_level):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 31:
        return None
    if type(hero_level) is not int or not 1 <= hero_level <= 30:
        return None
    tiers, seen, ids = [], set(), set()
    for row in rows:
        if not isinstance(row, dict):
            return None
        tier, level, status = row.get('tier'), row.get('required_level'), row.get('status')
        slot, identifier = row.get('slot'), row.get('catalog_id')
        if (type(tier) is not int or not 1 <= tier <= 31 or tier in seen
                or type(level) is not int or not 1 <= level <= 30
                or status not in ('selected', 'unselected', 'unknown')):
            return None
        seen.add(tier)
        if status == 'selected':
            if (type(slot) is not int or not 1 <= slot <= 32 or not isinstance(identifier, str)
                    or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,127}', identifier)
                    or identifier in ids or level > hero_level):
                return None
            ids.add(identifier)
        elif slot is not None or identifier is not None:
            return None
        tiers.append({'tier':tier, 'required_level':level, 'status':status,
                      'slot':slot, 'catalog_id':identifier})
    return sorted(tiers, key=lambda r:r['tier'])


def talents_key(packet):
    if not isinstance(packet, dict):
        return None
    return {'map_id':packet['map_id'], 'players':packet['players']}
