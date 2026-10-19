"""Typed current-objective boundary, never an event/replay reconstruction."""
from __future__ import annotations

import math
import re

from hotstate.acquisition import fresh


def _number(value):
    return type(value) is int or type(value) is float and math.isfinite(value)


def project_objective(raw, local, team):
    from hotstate.objectives import VALIDATED_MAPS

    p, meta = raw.get('objective'), raw['meta']
    if (not isinstance(p, dict) or not isinstance(local, dict) or team != local.get('team')
            or meta.get('source') != 'live' or meta.get('native_build') != 98348
            or meta.get('context_source') != 'initdata_memory'
            or p.get('status') != 'validated' or not fresh(p)
            or p.get('map_id') not in VALIDATED_MAPS or p.get('map_id') != meta.get('map_id')
            or not isinstance(meta.get('match_id'), str)
            or not re.fullmatch('[0-9a-f]{64}', meta['match_id'])
            or p.get('match_id') != meta['match_id']
            or type(p.get('local_id')) is not int or p['local_id'] != local.get('id')
            or type(p.get('team')) is not int or p['team'] != team
            or p.get('local_hero') != local.get('hero')
            or not _number(p.get('mission_t_s')) or not _number(meta.get('t_s'))
            or not 0 <= p['mission_t_s'] <= 21600
            or not 0 <= meta['t_s'] - p['mission_t_s'] <= 1
            or not _number(p.get('read_window_s')) or not 0 <= p['read_window_s'] <= 0.125
            or p.get('phase') not in ('waiting', 'warning', 'active', 'protector', 'unknown')):
        return None
    phase, current = p['phase'], p.get('current_point')
    if current is not None and (type(current) is not int or current not in (1, 2, 3)):
        return None
    point, clean_point = p.get('point'), None
    if phase == 'active':
        if (not isinstance(point, dict) or type(point.get('index')) is not int
                or point['index'] not in (1, 2, 3) or point['index'] != current
                or point.get('active') is not True
                or not (point.get('owner') == 'neutral'
                        or type(point.get('owner')) is int and point['owner'] in (0, 1))
                or point.get('state') not in ('capturing', 'contested', 'empty', 'resetting')
                or type(point.get('contested')) is not bool
                or point['contested'] != (point['state'] == 'contested')
                or type(point.get('overtime')) is not bool):
            return None
        progress = point.get('victory_percent')
        if (not isinstance(progress, list) or len(progress) != 2
                or any(type(v) is not int or not 0 <= v <= 100 for v in progress)):
            return None
        remaining = point.get('overtime_remaining_s')
        if point['overtime']:
            if not _number(remaining) or not 0 <= remaining <= 5:
                return None
        elif remaining is not None:
            return None
        clean_point = {k: point[k] for k in ('index', 'owner', 'state', 'contested',
                        'victory_percent', 'overtime', 'overtime_remaining_s')}
    elif point is not None:
        return None
    protector = p.get('protector')
    if not isinstance(protector, dict) or protector.get('state') not in ('active', 'absent', 'destroyed', 'unknown'):
        return None
    state = protector['state']
    if state == 'active':
        if (phase != 'protector' or type(protector.get('team')) is not int
                or protector['team'] not in (0, 1)
                or not _number(protector.get('health_percent'))
                or not 0 <= protector['health_percent'] <= 100
                or not _number(protector.get('remaining_s'))
                or not 0 <= protector['remaining_s'] <= 600):
            return None
    elif (phase == 'protector' or protector.get('health_percent') is not None
            or protector.get('remaining_s') is not None):
        return None
    elif state in ('absent', 'unknown') and protector.get('team') is not None:
        return None
    elif state == 'destroyed' and (type(protector.get('team')) is not int or protector['team'] not in (0, 1)):
        return None
    timers = {}
    for key in ('cooldown', 'warning'):
        value = p.get(key)
        if not isinstance(value, dict) or type(value.get('paused')) is not bool:
            return None
        remaining = value.get('remaining_s')
        if remaining is not None and (not _number(remaining) or not 0 <= remaining <= 600):
            return None
        timers[key] = {'remaining_s': remaining, 'paused': value['paused']}
    if phase == 'warning' and (current is None or not timers['warning']['remaining_s'] or timers['warning']['paused']):
        return None
    return {'t': p['mission_t_s'], 'map_id': p['map_id'], 'phase': phase,
            'point': clean_point, 'warning_point': current if phase == 'warning' else None,
            'protector': {k: protector.get(k) for k in ('state', 'team', 'health_percent', 'remaining_s')},
            **timers}


def objective_key(packet):
    """Cancel on tactical changes, not every tick of a public countdown."""
    if not isinstance(packet, dict):
        return None
    point, protector = packet.get('point'), packet['protector']

    def band(value, cutoffs):
        return None if value is None else sum(value > c for c in cutoffs)

    return {'phase': packet['phase'], 'warning_point': packet['warning_point'],
            'point': None if point is None else {
                'index': point['index'], 'owner': point['owner'], 'state': point['state'],
                'contested': point['contested'], 'overtime': point['overtime'],
                'progress_bands': [band(x, (24, 49, 74, 98)) for x in point['victory_percent']]},
            'protector': {'state': protector['state'], 'team': protector['team'],
                'health_band': band(protector['health_percent'], (25, 50, 75)),
                'remaining_band': band(protector['remaining_s'], (10, 30))},
            'warning_band': band(packet['warning']['remaining_s'], (10,))}
