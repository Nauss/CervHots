"""Closed allied-position export shared by passive and Coach journals.

These are recorded normalized values, never a native packet or a new receipt.
Age is preserved from normalization, not recalculated when writing to disk.
"""
from __future__ import annotations

import math

from hotstate.diagnostics import refusal


def _number(value, maximum, minimum=0):
    return (type(value) in (int, float) and minimum <= value <= maximum
            and math.isfinite(value))


def _allies(state):
    """Require a complete typed roster and its actual local team binding."""
    team, local, heroes = state.get('ally_team'), state.get('local_player'), state.get('heroes')
    if (type(team) is not int or team not in (0, 1) or type(local) is not dict
            or type(local.get('id')) is not int or type(local.get('team')) is not int
            or local['team'] != team or type(heroes) is not list or len(heroes) != 10):
        return None
    roster = {}
    for row in heroes:
        if (type(row) is not dict or type(row.get('id')) is not int or not 0 <= row['id'] < 10
                or row['id'] in roster or type(row.get('team')) is not int or row['team'] not in (0, 1)):
            return None
        roster[row['id']] = row
    allies = {slot: row for slot, row in roster.items() if row['team'] == team}
    if (len(allies) != 5 or local['id'] not in allies
            or allies[local['id']].get('hero') != local.get('hero')
            or any(type(row.get('alive')) is not bool for row in allies.values())):
        return None
    return allies


def positions_summary(state):
    """Select only complete, already-normalized living allies; unknown is not zero."""
    q = state.get('positions_qualification')
    q = q if type(q) is dict else {}
    meta = state.get('meta')
    meta = meta if type(meta) is dict else {}
    status, reason = q.get('status'), q.get('reason')
    result = {
        'status': status if status in ('normalized', 'refused', 'rejected', 'not_selected', 'not_attempted') else 'unknown',
        'reason': None if reason is None else refusal(reason.get('code') if type(reason) is dict else None),
        'source': 'native_player' if meta.get('source') == 'live'
            and meta.get('context_source') in ('initdata_memory', 'initdata_native_fields') else 'unknown',
        'source_mission_t_s': None, 'age_s': None, 'read_window_s': None, 'map_validation': None,
        'allies_expected': None, 'allies_alive': None, 'positions_acquired': None, 'value': None,
    }
    allies = _allies(state)
    if allies is not None:
        result.update(allies_expected=len(allies), allies_alive=sum(h['alive'] for h in allies.values()))
    if meta.get('collection') in ('core', 'talents'):
        result.update(status='not_selected', reason=None)
        return result
    if result['status'] != 'normalized':
        return result
    try:
        from hotstate.positions import PROFILE, map_validation, valid_bounds
        if (allies is None or result['source'] != 'native_player' or meta.get('native_status') != 'valide'
                or type(meta.get('native_build')) is not int or meta['native_build'] != PROFILE['build']
                or reason is not None or not _number(q.get('age_s'), 1)
                or not _number(q.get('read_window_s'), .125)):
            raise ValueError('invalid_positions_export')
        packet = state['positions']
        map_id, sampled = packet['map_id'], packet['t']
        validation = map_validation(map_id)
        if (validation is None or map_id != meta.get('map_id')
                or packet.get('map_validation') != validation or q.get('map_validation') != validation
                or not valid_bounds(map_id, packet.get('bounds'))
                or not _number(sampled, 21600) or not _number(meta.get('t_s'), 21600)
                or not 0 <= meta['t_s'] - sampled <= 1
                or type(packet.get('heroes')) is not list or len(packet['heroes']) > 5):
            raise ValueError('invalid_positions_export')
        left, bottom, right, top = packet['bounds']
        rows, seen = [], set()
        for row in packet['heroes']:
            slot = row['id']
            if (type(slot) is not int or slot not in allies or slot in seen
                    or allies[slot]['alive'] is not True or type(row.get('team')) is not int
                    or row['team'] != state['ally_team'] or row.get('hero') != allies[slot].get('hero')
                    or not _number(row.get('x'), right, left) or not _number(row.get('y'), top, bottom)
                    or not _number(row.get('u'), 1) or not _number(row.get('v'), 1)
                    or abs(row['u'] - (row['x']-left)/(right-left)) > 1e-9
                    or abs(row['v'] - (top-row['y'])/(top-bottom)) > 1e-9):
                raise ValueError('invalid_positions_export')
            seen.add(slot)
            rows.append(dict(slot=slot, **{key: row[key] for key in ('team', 'x', 'y', 'u', 'v')}))
        if seen != {slot for slot, hero in allies.items() if hero['alive']}:
            raise ValueError('invalid_positions_export')
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        result['status'] = 'rejected'
        return result
    result.update(source_mission_t_s=sampled, age_s=q['age_s'], read_window_s=q['read_window_s'],
                  map_validation=validation,
                  positions_acquired=len(rows), value=dict(map_id=map_id, t=sampled,
                      bounds=list(packet['bounds']), map_validation=validation,
                      team=state['ally_team'], heroes=rows))
    return result
