"""Minimised selected talents; saved rows never grant current permission.

No display-name catalog is qualified here: catalog_id is NOT a translated label.
The original receipt age is captured by snapshot, never renewed by persistence.
"""
from __future__ import annotations

import math
import re

from .talents import _project_tiers


def _number(value, maximum):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum


def _value(packet):
    """Closed schema for historical/public values, not receipt authentication."""
    from hotstate.talents import qualified_map, qualified_for
    if (type(packet) is not dict or type(packet.get('build')) is not int or packet['build'] != 98348
            or not qualified_map(packet.get('map_id'))
            or type(packet.get('team')) is not int or packet['team'] not in (0, 1)
            or type(packet.get('local_slot')) is not int
            or type(packet.get('players')) is not list or len(packet['players']) != 5):
        raise ValueError('invalid_talents_export')
    players, seen, observed = [], set(), False
    for row in packet['players']:
        if type(row) is not dict:
            raise ValueError('invalid_talents_export')
        slot, hero, level = row.get('slot'), row.get('hero'), row.get('level')
        if (type(slot) is not int or not 0 <= slot < 10 or slot in seen
                or type(hero) is not str or not re.fullmatch('[a-z][a-z0-9_-]{0,79}', hero)
                or type(level) is not int or not 1 <= level <= 30):
            raise ValueError('invalid_talents_export')
        seen.add(slot)
        status, tiers = row.get('status'), row.get('tiers')
        if status == 'observed':
            if not qualified_for(packet['map_id'], hero, local=slot == packet['local_slot']):
                raise ValueError('invalid_talents_export')
            tiers = _project_tiers(tiers, level)
            if tiers is None:
                raise ValueError('invalid_talents_export')
            # Never guess a label from a different hero/build, KB or offered tree.
            tiers = [dict(t, label=None, label_status='unknown', label_provenance=None) for t in tiers]
            observed = True
        elif status != 'unknown' or tiers is not None:
            raise ValueError('invalid_talents_export')
        players.append({'slot': slot, 'hero': hero, 'level': level, 'status': status, 'tiers': tiers})
    if not observed or packet['local_slot'] not in seen:
        raise ValueError('invalid_talents_export')
    return {'build': 98348, 'map_id': packet['map_id'], 'team': packet['team'],
            'local_slot': packet['local_slot'], 'players': sorted(players, key=lambda r: r['slot'])}


def talents_summary(state):
    """Select normalized allied data only; never copy offered catalogs or receipts."""
    q = state.get('talents_qualification')
    q = q if type(q) is dict else {}
    status = q.get('status')
    result = {'status': status if status in ('normalized', 'refused', 'rejected', 'not_attempted') else 'unknown',
              'source': 'native_player' if q.get('source') == 'native_player' else 'unknown',
              'source_mission_t_s': None, 'age_s': None, 'read_window_s': None, 'value': None}
    if result['status'] != 'normalized':
        return result
    try:
        meta, local, team = state['meta'], state['local_player'], state['ally_team']
        if (result['source'] != 'native_player' or meta.get('source') != 'live'
                or meta.get('native_status') != 'valide' or meta.get('native_build') != 98348
                or meta.get('context_source') != 'initdata_native_fields'
                or type(team) is not int or team not in (0, 1) or local.get('team') != team
                or not _number(q.get('source_mission_t_s'), 21600)
                or not _number(q.get('age_s'), 1) or not _number(q.get('read_window_s'), .125)):
            raise ValueError('invalid_talents_export')
        packet = state['talents']
        if packet['t'] != q['source_mission_t_s']:
            raise ValueError('invalid_talents_export')
        roster = {h['id']: h for h in state['heroes'] if h.get('team') == team}
        if len(roster) != 5 or roster[local['id']]['hero'] != local['hero']:
            raise ValueError('invalid_talents_export')
        players = []
        for row in packet['players']:
            member = roster[row['id']]
            if member['hero'] != row['hero']:
                raise ValueError('invalid_talents_export')
            players.append({'slot': row['id'], 'hero': row['hero'], 'level': member['level'],
                            'status': row['status'], 'tiers': row['tiers']})
        value = _value({'build': meta['native_build'], 'map_id': packet['map_id'],
                        'team': team, 'local_slot': local['id'], 'players': players})
    except (KeyError, TypeError, ValueError, AttributeError):
        result['status'] = 'rejected'
        return result
    result.update({key: q[key] for key in ('source_mission_t_s', 'age_s', 'read_window_s')})
    result['value'] = value
    return result


def replay(path, emit):
    """Bounded, re-sanitized inspection only; no issuance or live normalizer."""
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
            stored = row.get('talents')
            stored = stored if type(stored) is dict else {}
            clean = talents_summary({'talents_qualification': stored})
            if stored.get('status') == 'normalized':
                try:
                    if (stored.get('source') != 'native_player'
                            or not _number(stored.get('source_mission_t_s'), 21600)
                            or not _number(stored.get('age_s'), 1)
                            or not _number(stored.get('read_window_s'), .125)):
                        raise ValueError('invalid_talents_export')
                    value = _value(stored.get('value'))
                except (KeyError, TypeError, ValueError):
                    pass  # clean already says rejected, no values or apparent renewed age
                else:
                    clean.update(status='normalized', value=value,
                                 **{key: stored[key] for key in (
                                     'source_mission_t_s', 'age_s', 'read_window_s')})
            emit({'event': 'talents_replay', 'mode': 'historical_not_current', 'talents': clean})
            result['observations'] += 1
            result['exported_values'] += int(clean['value'] is not None)
    return result


def main(argv=None):
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', required=True, type=Path,
                        help='recorded events.jsonl; never current state')
    args = parser.parse_args(argv)

    def emit(row):
        print(json.dumps(row, ensure_ascii=True, allow_nan=False), flush=True)

    try:
        result = replay(args.journal, emit)
    except (OSError, ValueError, TypeError, RecursionError):
        emit({'event': 'talents_replay_error', 'mode': 'historical_not_current',
              'code': 'invalid_or_unavailable_journal'})
        return 1
    emit(dict(result, event='talents_replay_summary', mode='historical_not_current'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
