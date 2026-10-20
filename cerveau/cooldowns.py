"""Allowlisted local cooldown projection and discrete tactical transitions.

No diagnostic table is a publishable packet. The source's release scope is
closed until a real whole-path recipe; JSON cannot renew its in-process seal.
"""
from __future__ import annotations

import math
import re

from hotstate.acquisition import fresh


def _number(value, upper):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= upper


def project_local_cooldowns(raw, local, team):
    from hotstate.cooldown_packet import VALIDATED_SCOPES
    return _project(raw, local, team, scopes=VALIDATED_SCOPES)


def _project(raw, local, team, *, scopes=()):
    if not isinstance(raw, dict):
        return None
    meta, p = raw.get('meta', {}), raw.get('local_cooldowns')
    if (not isinstance(meta, dict) or not isinstance(p, dict) or not isinstance(local, dict)
            or type(local.get('id')) is not int or not 0 <= local['id'] <= 9
            or type(team) is not int or team not in (0, 1)
            or type(local.get('team')) is not int or local.get('team') != team
            or not isinstance(local.get('hero'), str)
            or meta.get('source') != 'live' or meta.get('native_status') != 'valide'
            or type(meta.get('native_build')) is not int or meta['native_build'] != 98348
            or meta.get('context_source') != 'initdata_native_fields'
            or p.get('status') != 'validated' or not fresh(p)
            or (meta.get('map_id'), local.get('hero')) not in scopes
            or p.get('map_id') != meta.get('map_id') or p.get('local_hero') != local.get('hero')
            or type(p.get('local_id')) is not int or p['local_id'] != local['id']
            or type(p.get('team')) is not int or p['team'] != team
            or not isinstance(meta.get('match_id'), str) or not re.fullmatch('[0-9a-f]{64}', meta['match_id'])
            or p.get('match_id') != meta['match_id'] or type(p.get('alive')) is not bool
            or not _number(p.get('mission_t_s'), 21600) or not _number(meta.get('t_s'), 21600)
            or not 0 <= meta['t_s']-p['mission_t_s'] <= 1
            or not _number(p.get('read_window_s'), 0.125)):
        return None
    heroes = raw.get('heroes')
    if not isinstance(heroes, list) or not all(isinstance(h, dict) for h in heroes):
        return None
    owners = [h for h in heroes if h.get('id') == local['id']]
    if (len(owners) != 1 or owners[0].get('hero') != local.get('hero')
            or type(owners[0].get('id')) is not int or type(owners[0].get('team')) is not int
            or owners[0].get('team') != team or type(owners[0].get('alive')) is not bool
            or owners[0]['alive'] != p['alive']):
        return None
    abilities = p.get('abilities')
    if not isinstance(abilities, list) or len(abilities) > 64 or (not p['alive'] and abilities):
        return None
    clean, slots = [], set()
    for a in abilities:
        if (not isinstance(a, dict) or not isinstance(a.get('ability'), str)
                or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,127}', a['ability'])
                or type(a.get('instance_slot')) is not int or not 0 <= a['instance_slot'] < 64
                or a['instance_slot'] in slots or a.get('slot_kind') != 'native_instance_NOT_HUD_button'
                or a.get('cast_legality') != 'unknown'
                or a.get('cooldown_status') not in ('observed', 'unknown')
                or a.get('charges_status') not in ('observed', 'unknown', 'not_applicable_current_max_zero')):
            return None
        slots.add(a['instance_slot'])
        row = {k:a[k] for k in ('ability', 'instance_slot', 'slot_kind', 'cooldown_status', 'charges_status', 'cast_legality')}
        if a['cooldown_status'] == 'observed':
            if (not _number(a.get('remaining_s'), 3600) or type(a.get('cooldown_ready')) is not bool
                    or a['cooldown_ready'] != (a['remaining_s'] == 0)):
                return None
            row.update(remaining_s=a['remaining_s'], cooldown_ready=a['cooldown_ready'])
        elif any(k in a for k in ('remaining_s', 'cooldown_ready')):
            return None
        charge_fields = ('charges_max', 'charges_used', 'charges_available', 'charge_regen_s')
        if a['charges_status'] == 'observed':
            if (not all(_number(a.get(k), 1024 if k != 'charge_regen_s' else 3600) for k in charge_fields)
                    or a['charges_max'] <= 0
                    or a['charges_available'] != max(0, a['charges_max']-a['charges_used'])):
                return None
            row.update({k:a[k] for k in charge_fields})
        elif any(k in a for k in charge_fields):
            return None
        clean.append(row)
    return {'t': p['mission_t_s'], 'map_id': p['map_id'], 'local_id': local['id'],
            'hero': local['hero'], 'alive': p['alive'], 'abilities': sorted(clean, key=lambda a:a['instance_slot'])}


def cooldown_key(packet):
    if not isinstance(packet, dict):
        return None
    return (packet['map_id'], packet['local_id'], packet['hero'], packet['alive'],
            tuple((a['instance_slot'], a['ability'], a['cooldown_status'], a.get('cooldown_ready'),
                   a['charges_status'], a.get('charges_max'), a.get('charges_available')) for a in packet['abilities']))
