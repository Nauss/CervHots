"""Local selected talent allowlist boundary, never possessions or offered options."""
from __future__ import annotations

import re
from hotstate.acquisition import fresh


def _number(value):
    return type(value) in (int, float) and -float('inf') < value < float('inf')


def project_talents(raw, local, team):
    from hotstate.talents import VALIDATED_SCOPES
    p, meta, perspective = raw.get('talents'), raw.get('meta', {}), raw.get('perspective')
    if (not isinstance(local, dict) or type(team) is not int or team != local.get('team')
            or not isinstance(p, dict) or not isinstance(perspective, dict)
            or meta.get('source') != 'live' or meta.get('native_build') != 98348
            or meta.get('context_source') != 'initdata_native_fields'
            or p.get('status') != 'validated' or p.get('scope') != 'local_selected_talents'
            or not fresh(p) or not fresh(perspective)
            or (p.get('map_id'), p.get('local_hero')) not in VALIDATED_SCOPES
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
    rows = p.get('tiers')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 31:
        return None
    local_heroes = [h for h in raw.get('heroes', []) if h.get('id') == local['id']]
    if len(local_heroes) != 1 or type(local_heroes[0].get('level')) is not int:
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
                    or identifier in ids or level > local_heroes[0]['level']):
                return None
            ids.add(identifier)
        elif slot is not None or identifier is not None:
            return None
        tiers.append({'tier':tier, 'required_level':level, 'status':status,
                      'slot':slot, 'catalog_id':identifier})
    return {'t':p['mission_t_s'], 'map_id':p['map_id'],
            'players':[{'id':local['id'], 'hero':local['hero'], 'tiers':sorted(tiers, key=lambda r:r['tier'])}]}


def talents_key(packet):
    if not isinstance(packet, dict):
        return None
    return {'map_id':packet['map_id'], 'players':packet['players']}
