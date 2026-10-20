#!/usr/bin/env python
"""Private Dragon battlefield candidate through read_current→normalizer→key.

No diagnostic trace is promoted. Candidate permission is local to this bounded
process, public gates stay closed on disk. No coach/GUI/audio/PNG or heap scan.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etudes.rea.scripts import capture_dragon_pipeline as objective_capture
from hotstate.dragon_battlefield import DragonBattlefield
from hotstate.native import NativeUnavailable
from hotstate.native_context import NativeContextProbe
from hotstate.reader import ProcessBackend
from cerveau.runner import tactical_key

BASE_SAMPLE = objective_capture.take_sample
REAL_CLOCK = objective_capture.REAL_CLOCK


def take_sample(backend, probe, *, clock=None, native_profile=None):
    refusals = []
    original_read = DragonBattlefield.read

    def observed(reader, context, **options):
        try:
            return original_read(reader, context, **options)
        except NativeUnavailable as exc:
            refusals.append(str(exc))
            raise

    def require_battlefield(clean):
        battlefield = clean.get('battlefield')
        if (not isinstance(battlefield, dict)
                or len(battlefield.get('camps', {}).get('entries', [])) != 5
                or len(battlefield.get('structures', {}).get('entries', [])) != 90):
            raise NativeUnavailable('champ_bataille_dragon_pipeline_absent')
        # Runs INSIDE read_current's whole attempt, never posthoc acceptance.
        return tactical_key(clean)

    with patch('hotstate.dragon_battlefield.VALIDATED_MAPS', ('DragonShire',)), \
         patch.object(DragonBattlefield, 'read', observed), \
         patch.object(objective_capture, 'tactical_key', require_battlefield):
        result = BASE_SAMPLE(backend, probe, clock=clock, native_profile=native_profile)
    result['kind'] = 'candidate_full_dragon_battlefield_NOT_RELEASE'
    result['optional_battlefield_refusals'] = refusals
    return result


def replay_sample(row, module_base, probe, *, native_profile=None):
    replay = objective_capture.ReplayTrace(module_base, row['reads'])
    shadow = SimpleNamespace(module_base=module_base, read_memory=replay.read_memory,
                             recorded_non_atomic=row.get('recorded_non_atomic', False))
    times = iter(row['wall_clock_calls'])
    with patch.object(probe, 'map_resolver', lambda _:dict(row.get('map_metadata_observed', {}))), \
         patch.object(probe, 'map_cache', {}):
        actual = take_sample(shadow, probe, clock=lambda:next(times), native_profile=native_profile)
    replay.finish()
    sentinel = object()
    if next(times, sentinel) is not sentinel:
        raise AssertionError('unconsumed Dragon battlefield pipeline clock')
    for field in ('status', 'rejected', 'normalized', 'tactical_key', 'whole_snapshot_window_s',
                  'optional_dragon_refusals', 'optional_battlefield_refusals', 'bytes_requested'):
        if actual.get(field) != row.get(field):
            raise AssertionError('Dragon battlefield pipeline replay differs: '+field)
    return actual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--live', action='store_true')
    parser.add_argument('--candidate-battlefield', action='store_true')
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--pid', type=int)
    parser.add_argument('--duration', type=float, default=12)
    parser.add_argument('--interval', type=float, default=0.25)
    parser.add_argument('--private-player-env', default='HOTS_PLAYER')
    args = parser.parse_args(argv)
    if not 0 < args.duration <= 30 or not 0.25 <= args.interval <= 10:
        parser.error('duration/interval hors bornes')
    if args.live and not args.candidate_battlefield:
        parser.error('--candidate-battlefield explicite requis')
    extras = [Path(__file__).resolve(), Path(objective_capture.__file__).resolve(),
              ROOT/'etudes/rea/scripts/capture_visibility_pipeline.py', ROOT/'kb/data/map_timings.json']
    extras.extend(ROOT/'cerveau'/name for name in ('state.py', 'runner.py', 'objectives.py', 'dragon.py', 'battlefield.py'))
    commit, sources = objective_capture.frozen_sources(args.expected_commit, extra_paths=extras)
    if args.preflight:
        print(json.dumps({'commit':commit, 'sources_sha256':sources, 'live_opened':False,
                          'release':False, 'png':False, 'mode':'candidate_full_battlefield'}))
        return 0
    if args.out is None:
        parser.error('--out requis')
    out = args.out.resolve()
    day_private = ROOT.parents[1]/'out/day-fleet/2026-10-20/private/t_de084111'
    if (not (out.is_relative_to(ROOT/'out') or out.is_relative_to(day_private))
            or out.suffix != '.jsonl'):
        parser.error('JSONL privé neuf sous out/ worktree ou private/t_de084111 du jour requis')
    label = os.environ.get(args.private_player_env)
    if not label:
        parser.error('libellé privé requis en variable locale, jamais dans argv/manifeste')
    probe = NativeContextProbe(label)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        backend = ProcessBackend(args.pid)
        try:
            stream.write(json.dumps({'kind':'candidate_full_dragon_battlefield_NOT_RELEASE',
                'commit':commit, 'sources_sha256':sources, 'module_base':backend.module_base,
                'wall':objective_capture.utc(), 'png':False, 'coach_audio':False, 'heap_scan':False})+'\n')
            stream.flush()
            deadline = REAL_CLOCK()+args.duration
            while REAL_CLOCK() < deadline:
                stream.write(json.dumps(take_sample(backend, probe), allow_nan=False)+'\n')
                stream.flush()
                remaining = min(args.interval, deadline-REAL_CLOCK())
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            backend.close()
    print('Recette candidate camps/structures Dragon terminée ; publication fermée.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
