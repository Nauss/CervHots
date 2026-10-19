"""Typed Dragon objective boundary; no counters, raw refs or hidden channels."""
from __future__ import annotations

import re

from hotstate.acquisition import fresh
from .objectives import _number


def project_dragon(raw, local, team):
    from hotstate.dragon import VALIDATED_MAPS

    p, meta = raw.get('objective'), raw['meta']
    if (not isinstance(p, dict) or not isinstance(local, dict) or type(team) is not int
            or team != local.get('team') or meta.get('source') != 'live' or meta.get('native_build') != 98348
            or meta.get('context_source') not in ('initdata_memory', 'initdata_native_fields')
            or p.get('status') != 'validated' or not fresh(p)
            or p.get('map_id') != 'DragonShire' or p['map_id'] not in VALIDATED_MAPS
            or p['map_id'] != meta.get('map_id') or not isinstance(meta.get('match_id'), str)
            or not re.fullmatch('[0-9a-f]{64}', meta['match_id']) or p.get('match_id') != meta['match_id']
            or type(p.get('local_id')) is not int or p['local_id'] != local.get('id')
            or type(p.get('team')) is not int or p['team'] != team or p.get('local_hero') != local.get('hero')
            or not _number(p.get('mission_t_s')) or not _number(meta.get('t_s'))
            or not 0 <= p['mission_t_s'] <= 21600 or not 0 <= meta['t_s']-p['mission_t_s'] <= 1
            or not _number(p.get('read_window_s')) or not 0 <= p['read_window_s'] <= 0.125
            or p.get('phase') not in ('waiting', 'warning', 'shrines', 'dragon', 'unknown')):
        return None
    phase, rows = p['phase'], p.get('shrines')
    if not isinstance(rows, list) or len(rows) != 2:
        return None
    shrines = []
    for ident, row in zip(('sun', 'moon'), rows):
        if not isinstance(row, dict) or row.get('id') != ident:
            return None
        state, owner, contested = row.get('state'), row.get('owner'), row.get('contested')
        if state not in ('unknown', 'disabled', 'contested', 'paused', 'neutral', 'captured', 'reverting', 'capturing'):
            return None
        if state == 'unknown':
            if owner is not None or contested is not None:
                return None
        else:
            if not (owner == 'neutral' or type(owner) is int and owner in (0, 1)):
                return None
            if state == 'disabled':
                if contested is not None:
                    return None
            elif type(contested) is not bool or contested != (state == 'contested'):
                return None
        shrines.append({'id': ident, 'owner': owner, 'state': state, 'contested': contested})
    dragon, statue = p.get('dragon'), p.get('statue')
    if not isinstance(dragon, dict) or not isinstance(statue, dict):
        return None
    ds, dt, remaining = dragon.get('state'), dragon.get('team'), dragon.get('remaining_s')
    if ds not in ('inactive', 'active', 'ended', 'unknown'):
        return None
    if ds in ('active', 'ended'):
        if type(dt) is not int or dt not in (0, 1) or phase != 'dragon':
            return None
        if ds == 'active':
            if not _number(remaining) or not 0 < remaining <= 600:
                return None
        elif remaining is not None:
            return None
    elif dt is not None or remaining is not None or phase == 'dragon':
        return None
    ss, st = statue.get('state'), statue.get('team')
    if ss not in ('capturable', 'inactive', 'unknown'):
        return None
    if ss == 'capturable':
        if (phase != 'shrines' or type(st) is not int or st not in (0, 1)
                or any(s['owner'] != st or s['state'] in ('unknown', 'disabled') for s in shrines)):
            return None
    elif st is not None:
        return None
    channeling = None
    if statue.get('current_visible') is True:
        candidate = statue.get('channeling')
        if ss == 'capturable' and type(candidate) is bool:
            channeling = candidate
    # Visibility never grants positions, vitals, pilot identity or cooldowns.
    timers = {}
    for key in ('start', 'respawn', 'warning'):
        timer = p.get(key)
        if not isinstance(timer, dict) or type(timer.get('paused')) is not bool:
            return None
        value = timer.get('remaining_s')
        if value is not None and (not _number(value) or not 0 <= value <= 600):
            return None
        timers[key] = {'remaining_s': value, 'paused': timer['paused']}
    return {'t': p['mission_t_s'], 'map_id': 'DragonShire', 'phase': phase, 'shrines': shrines,
            'statue': {'state': ss, 'team': st, 'channeling': channeling},
            'dragon': {'state': ds, 'team': dt, 'remaining_s': remaining}, **timers}


def dragon_key(packet):
    def band(value):
        return None if value is None else sum(value > c for c in (10, 30))
    return {'map_id': 'DragonShire', 'phase': packet['phase'], 'shrines': packet['shrines'],
            'statue': packet['statue'], 'dragon': {'state': packet['dragon']['state'],
                'team': packet['dragon']['team'], 'remaining_band': band(packet['dragon']['remaining_s'])},
            'timers': {key: {'remaining_band': band(packet[key]['remaining_s']), 'paused': packet[key]['paused']}
                       for key in ('start', 'respawn', 'warning')}}
