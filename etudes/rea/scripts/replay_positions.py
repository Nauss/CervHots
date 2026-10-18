"""Offline exact recipe replay. Private captures never become live observations.

Supply the private JSONL recorded by capture_positions.py. This verifies ordered
bytes AND recorded core clocks, including refusals. An optional public-path
replay exercises the released reader against the same trace; it does not claim
that replaying historical acquisitions is fresh production data.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from capture_positions import AlliedPositions, NativeReader, NativeUnavailable, ReplayTrace, attempt


def audit(path, *, public=False, options=None):
    options = options or {}
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    header, rows = rows[0], rows[1:]
    assert header['kind'] == 'targeted_allied_positions'
    assert header['status'] == 'diagnostic_unreleased'
    counts, windows, pairs = Counter(), [], []
    # All identities used for context replay come from native accepted samples,
    # not invented enemy heroes, replay events or a desired output.
    identities = {}
    for row in rows:
        for side in ('before', 'after'):
            for h in row[side].get('positions', {}).get('heroes', []):
                assert identities.setdefault(h['id'], h['hero']) == h['hero']
    for sequence, row in enumerate(rows):
        assert row['sequence'] == sequence
        for side in ('before', 'after'):
            original = row[side]
            for i, read in enumerate(original['reads']):
                assert read['order'] == i
                assert read['monotonic_before'] <= read['monotonic_after']
            replay = ReplayTrace(header['module_base'], original['reads'], original['core_monotonic'])
            reproduced = attempt(replay, header['map_id_requested'], **options)
            replay.finish()
            assert original.get('rejected') == reproduced.get('rejected'), (sequence, side)
            assert original.get('positions') == reproduced.get('positions'), (sequence, side)
            counts['exact_replayed_attempts'] += 1
            p = original.get('positions')
            if p:
                assert p['status'] == 'diagnostic_unreleased'
                assert 'acquisition' not in p and 'match_id' not in p
                counts['accepted'] += 1
                windows.append(p['read_window_s'])
                counts['local_alive' if any(h['id'] == p['local_id'] for h in p['heroes']) else 'local_absent'] += 1
            else:
                counts['rejection:' + original['rejected']] += 1
            if public:
                # Use an accepted native perspective from this series for the
                # refused attempts too. _identity must independently re-prove it.
                reference = p or next(r[s]['positions'] for r in rows for s in ('before', 'after') if 'positions' in r[s])
                allied_ids = set(identities)
                assert len(allied_ids) == 5
                context = {'meta': {'map_id': header['map_id_requested'], 'match_id': 'a' * 64,
                                    'context_source': 'initdata_memory'},
                           'local_player': {'id': reference['local_id'], 'team': reference['team'],
                                            'hero': identities[reference['local_id']]},
                           'players': [{'id': i, 'team': reference['team'] if i in allied_ids else 1-reference['team'],
                                        'hero': identities.get(i)} for i in range(10)]}
                replay = ReplayTrace(header['module_base'], original['reads'], original['core_monotonic'])
                native = NativeReader(replay, profile=options.get('native_profile'))
                try:
                    result = AlliedPositions(native, profile=options.get('position_profile')).read(
                        context, hero_ids=options.get('hero_ids'))
                except NativeUnavailable as exc:
                    assert str(exc) == original.get('rejected'), (sequence, side, str(exc))
                else:
                    assert p is not None
                    assert result.pop('status') == 'validated'
                    result.pop('acquisition')
                    result.pop('match_id')
                    assert result == {k: v for k, v in p.items() if k != 'status'}
                replay.finish()
                counts['public_core_replayed_attempts'] += 1
        image = row.get('image', {})
        assert row['before']['monotonic_after'] <= image.get('monotonic_before', row['after']['monotonic_before'])
        assert image.get('monotonic_after', row['before']['monotonic_after']) <= row['after']['monotonic_before']
        if 'file' in image:
            assert Path(image['file']).name == image['file']
            png = path.parent / image['file']
            assert hashlib.sha256(png.read_bytes()).hexdigest() == image['sha256']
            assert image['hwnd'] == image['foreground']
            counts['png_verified'] += 1
            a, b = row['before'].get('positions'), row['after'].get('positions')
            if a and b and a['native_session'] == b['native_session'] and a['local_id'] == b['local_id']:
                counts['png_double_accepted'] += 1
                pairs.append(row['after']['monotonic_after'] - row['before']['monotonic_before'])
    return {'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'commit': header['commit'],
            'rows': len(rows), 'counts': dict(counts),
            'max_accepted_read_window_s': max(windows, default=None),
            'max_accepted_png_pair_window_s': max(pairs, default=None),
            'public_replay_context': 'native identities plus synthetic match label; not a captured initData packet',
            'historical_not_fresh_live': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--public', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.input.resolve(), public=args.public)
    with args.out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
