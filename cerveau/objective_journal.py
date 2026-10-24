"""Minimised objective export. Historical journal rows never grant a receipt.

age_s is measured at normalization, not renewed at journal flush or replay.
Only Dragon values are selected here; other families keep qualification only.
"""
from __future__ import annotations

import math

from hotstate.diagnostics import refusal


def _number(value, maximum):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum


def _enum(*values):
    return lambda value: type(value) is str and value in values


def _team(value):
    return value is None or type(value) is int and value in (0, 1)


def _select(value, schema):
    """Closed recursive selection; extra input fields are never copied."""
    if type(schema) is dict:
        if type(value) is not dict:
            raise ValueError('invalid_objective_export')
        return {key: _select(value[key], check) for key, check in schema.items()}
    if type(schema) is list:
        if type(value) is not list or len(value) != len(schema):
            raise ValueError('invalid_objective_export')
        return [_select(row, check) for row, check in zip(value, schema)]
    if not schema(value):
        raise ValueError('invalid_objective_export')
    return value


_TIMER = {'remaining_s': lambda v: v is None or _number(v, 600),
          'paused': lambda v: type(v) is bool}
_SHRINE = {'owner': lambda v: _team(v) or v == 'neutral',
           'state': _enum('unknown', 'disabled', 'contested', 'paused', 'neutral',
                          'captured', 'reverting', 'capturing'),
           'contested': lambda v: v is None or type(v) is bool}
_DRAGON = {
    'phase': _enum('waiting', 'warning', 'shrines', 'dragon', 'unknown'),
    'shrines': [dict(_SHRINE, id=_enum(name)) for name in ('sun', 'moon')],
    'statue': {'state': _enum('capturable', 'inactive', 'unknown'), 'team': _team,
               'channeling': lambda v: v is None or type(v) is bool},
    'dragon': {'state': _enum('inactive', 'active', 'ended', 'unknown'), 'team': _team,
               'remaining_s': lambda v: v is None or _number(v, 600)},
    'start': _TIMER, 'respawn': _TIMER, 'warning': _TIMER,
}


def objective_summary(state):
    """Export already-normalized public values, not a producer or a permission."""
    q = state.get('objective_qualification')
    q = q if type(q) is dict else {}
    status = q.get('status')
    status = status if status in ('normalized', 'refused', 'rejected', 'not_attempted') else 'unknown'
    reason = q.get('reason')
    result = {'status': status,
              'reason': None if reason is None else refusal(reason.get('code') if type(reason) is dict else None),
              'source': 'native_player' if q.get('source') == 'native_player' else 'unknown',
              'source_mission_t_s': None, 'age_s': None, 'read_window_s': None,
              'family': None, 'value_status': 'unavailable', 'value': None}
    if status != 'normalized':
        return result
    try:
        if (result['source'] != 'native_player' or reason is not None
                or not _number(q.get('source_mission_t_s'), 21600)
                or not _number(q.get('age_s'), 1)
                or not _number(q.get('read_window_s'), .125)):
            raise ValueError('invalid_objective_export')
        packet = state['objective']
        if type(packet) is not dict or packet.get('t') != q['source_mission_t_s']:
            raise ValueError('invalid_objective_export')
        result.update({key: q[key] for key in ('source_mission_t_s', 'age_s', 'read_window_s')})
        if packet.get('map_id') != 'DragonShire':
            result['value_status'] = 'not_selected'
            return result
        value = _select(packet, _DRAGON)
    except (KeyError, TypeError, ValueError):
        result.update(status='rejected', reason=refusal('objective_packet_rejected'),
                      source_mission_t_s=None, age_s=None, read_window_s=None)
        return result
    result.update(family='dragon', value_status='exported', value=value)
    return result


def replay(path, emit):
    """Read a bounded journal for inspection only, never issue or renew receipts.

    A journal is not authenticated native evidence. The label is unconditional,
    even for a row whose recorded qualification says normalized.
    """
    import json
    result = {'lines': 0, 'observations': 0, 'exported_values': 0}
    total = 0
    with path.open('rb') as stream:
        while True:
            line = stream.readline(65537)
            if not line:
                break
            total += len(line)
            result['lines'] += 1
            if len(line) > 65536 or total > 4 * 2**20 or result['lines'] > 10000:
                raise ValueError('journal_limit')
            row = json.loads(line)
            if type(row) is not dict:
                raise ValueError('invalid_journal')
            if row.get('event') != 'observation':
                continue
            stored = row.get('objective')
            stored = stored if type(stored) is dict else {}
            state = {'objective_qualification': stored}
            value = stored.get('value')
            if stored.get('family') == 'dragon' and type(value) is dict:
                state['objective'] = dict(value, map_id='DragonShire',
                                          t=stored.get('source_mission_t_s'))
            elif stored.get('value_status') == 'not_selected':
                state['objective'] = {'map_id': None, 't': stored.get('source_mission_t_s')}
            clean = objective_summary(state)
            emit({'event': 'objective_replay', 'mode': 'historical_not_current', 'objective': clean})
            result['observations'] += 1
            result['exported_values'] += int(clean['value_status'] == 'exported')
    return result


def main(argv=None):
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', required=True, type=Path, help='recorded events.jsonl; never current state')
    args = parser.parse_args(argv)

    def emit(row):
        print(json.dumps(row, ensure_ascii=True, allow_nan=False), flush=True)

    try:
        summary = replay(args.journal, emit)
    except (OSError, ValueError, TypeError, RecursionError):
        emit({'event': 'objective_replay_error', 'mode': 'historical_not_current',
              'code': 'invalid_or_unavailable_journal'})
        return 1
    emit(dict(summary, event='objective_replay_summary', mode='historical_not_current'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
