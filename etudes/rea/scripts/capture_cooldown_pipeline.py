#!/usr/bin/env python
"""Private candidate: real read_current -> cooldown projection -> tactical key.

NOT a production release. No GUI, coach, audio, screenshots or process writes.
The candidate scope is enabled only in this bounded diagnostic process.
"""
from __future__ import annotations

import argparse
import contextlib
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

from etudes.rea.scripts.capture_positions import ReplayTrace, frozen_sources, utc
from etudes.rea.scripts.capture_visibility_pipeline import RecordedClock
from etudes.rea.scripts.capture_dragon_pipeline import PipelineMemory
from hotstate.reader import ProcessBackend
from hotstate.native import NativeUnavailable
from hotstate.native_context import NativeContextProbe
from hotstate import cooldown_packet
from hotstate.live import read_current
from cerveau.state import snapshot as normalize
from cerveau.runner import tactical_key

REAL_CLOCK = time.monotonic
CANDIDATE_SCOPES = (('DragonShire', 'sonya'),)


def take_sample(backend, probe, *, clock=None, native_profile=None):
    memory = PipelineMemory(backend)
    recorded = RecordedClock(REAL_CLOCK if clock is None else clock)
    row = {'status': 'rejected', 'kind': 'candidate_full_local_cooldowns_NOT_RELEASE',
           'wall_before': utc(), 'recorded_non_atomic': memory.recorded_non_atomic,
           'execution_kind': ('fixture_or_historical_NOT_LIVE' if clock is not None or native_profile is not None
                              else 'real_monotonic_record_only')}
    refusals = []
    original = cooldown_packet.LocalCooldowns.read
    def observed(reader, context, **options):
        try:
            return original(reader, context, **options)
        except NativeUnavailable as exc:
            refusals.append(str(exc))
            raise
    def project(raw):
        row['raw'] = raw
        clean = normalize(raw)
        row['normalized'] = clean
        return clean
    def key(clean):
        row['tactical_key'] = tactical_key(clean)
        return row['tactical_key']
    original_resolver = getattr(probe, 'map_resolver', None)
    def resolver(handles):
        result = original_resolver(handles)
        row['map_metadata_observed'] = {k:v for k,v in result.items() if k in ('map', 'map_id')}
        return result
    try:
        if not isinstance(probe, NativeContextProbe):
            raise NativeUnavailable('contexte_natif_cooldowns_pipeline_requis')
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch('time.monotonic', recorded))
            stack.enter_context(patch.object(cooldown_packet, 'VALIDATED_SCOPES', CANDIDATE_SCOPES))
            stack.enter_context(patch.object(cooldown_packet.LocalCooldowns, 'read', observed))
            stack.enter_context(patch.object(probe, 'map_resolver', resolver))
            if native_profile is not None:
                from hotstate import live
                actual_snapshot = live.memory_snapshot
                def fixture_snapshot(memory, mapping, *, context):
                    return actual_snapshot(memory, mapping, context=context, native_profile=native_profile)
                stack.enter_context(patch.object(live, 'memory_snapshot', fixture_snapshot))
            start = time.monotonic()
            clean = read_current(memory, {'triggers': {}}, context=probe, project=project, key=key)
            elapsed = time.monotonic()-start
            packet = clean.get('local_cooldowns')
            if not isinstance(packet, dict) or (row['raw']['meta']['map_id'], packet['hero']) not in CANDIDATE_SCOPES:
                raise NativeUnavailable('cooldowns_pipeline_payload_absent')
            if packet['alive'] and not any(a['cooldown_status'] == 'observed' or a['charges_status'] == 'observed' for a in packet['abilities']):
                raise NativeUnavailable('cooldowns_pipeline_all_unknown')
            if not 0 <= elapsed <= 0.125:
                raise NativeUnavailable('fenetre_pipeline_globale_depassee')
            for hero in clean['heroes']:
                if hero['team'] != clean['ally_team'] and any(k in hero for k in
                        ('health', 'health_max', 'resource', 'resource_max', 'x', 'y', 'cooldowns', 'talents')):
                    raise AssertionError('enemy tactical leak')
            row.update(status='accepted', whole_snapshot_window_s=elapsed,
                       evidence_kind=('observed_local_cooldowns' if packet['alive'] else 'dead_current_no_values'))
    except (NativeUnavailable, ValueError) as exc:
        row['rejected'] = str(exc)
    if 'map_metadata_observed' not in row:
        values = [{k:v for k,v in value.items() if k in ('map', 'map_id')}
                  for value in getattr(probe, 'map_cache', {}).values()]
        if values and all(value == values[0] for value in values):
            row['map_metadata_observed'] = values[0]
    row.update(wall_after=utc(), reads=memory.trace.reads, read_count=len(memory.trace.reads),
               bytes_requested=memory.trace.bytes_requested, wall_clock_calls=recorded.values,
               optional_cooldown_refusals=refusals)
    return row


def replay_sample(row, module_base, probe, *, native_profile=None):
    replay = ReplayTrace(module_base, row['reads'])
    shadow = SimpleNamespace(module_base=module_base, read_memory=replay.read_memory,
                             recorded_non_atomic=row.get('recorded_non_atomic', False))
    times = iter(row['wall_clock_calls'])
    with patch.object(probe, 'map_resolver', lambda _:dict(row.get('map_metadata_observed', {}))), \
         patch.object(probe, 'map_cache', {}):
        actual = take_sample(shadow, probe, clock=lambda:next(times), native_profile=native_profile)
    replay.finish()
    sentinel = object()
    if next(times, sentinel) is not sentinel:
        raise AssertionError('unconsumed cooldown pipeline clock')
    for field in ('status', 'rejected', 'evidence_kind', 'normalized', 'tactical_key', 'whole_snapshot_window_s',
                  'optional_cooldown_refusals', 'bytes_requested', 'read_count'):
        if actual.get(field) != row.get(field):
            raise AssertionError('cooldown pipeline replay differs: '+field)
    actual['execution_kind'] = 'historical_exact_replay_NOT_LIVE'
    return actual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--live', action='store_true')
    parser.add_argument('--candidate-local-cooldowns', action='store_true')
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--pid', type=int)
    parser.add_argument('--duration', type=float, default=4)
    parser.add_argument('--interval', type=float, default=0.25)
    parser.add_argument('--private-player-env', default='HOTS_PLAYER')
    args = parser.parse_args(argv)
    if not 0 < args.duration <= 90 or not 0.25 <= args.interval <= 10:
        parser.error('duration/interval hors bornes')
    if args.live and not args.candidate_local_cooldowns:
        parser.error('--candidate-local-cooldowns explicite requis')
    extra = [Path(__file__).resolve(), ROOT/'etudes/rea/scripts/capture_dragon_pipeline.py',
             ROOT/'etudes/rea/scripts/capture_visibility_pipeline.py', ROOT/'kb/data/map_timings.json']
    extra.extend(sorted((ROOT/'cerveau').glob('*.py')))
    commit, sources = frozen_sources(args.expected_commit, extra_paths=extra)
    if args.preflight:
        print(json.dumps({'commit': commit, 'sources_sha256': sources, 'live_opened': False,
                          'production_released': False, 'png': False, 'candidate_scopes': CANDIDATE_SCOPES}))
        return 0
    if args.out is None or not os.environ.get(args.private_player_env):
        parser.error('--out neuf et identité privée en environnement requis')
    out = args.out.resolve()
    private_root = Path('C:/root/dev/AI/CervHots/out/day-fleet/2026-10-20/private').resolve()
    if not out.is_relative_to(private_root) or out.suffix != '.jsonl':
        parser.error('JSONL privé neuf sous private/ du jour requis')
    probe = NativeContextProbe(os.environ[args.private_player_env])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as output:
        backend = ProcessBackend(args.pid)
        try:
            output.write(json.dumps({'schema': 'cooldown-whole-pipeline-candidate-v1', 'commit': commit,
                'module_base': backend.module_base, 'sources_sha256': sources,
                'candidate_scopes': CANDIDATE_SCOPES, 'production_released': False,
                'duration_s': args.duration, 'interval_s': args.interval})+'\n')
            deadline = REAL_CLOCK()+args.duration
            while REAL_CLOCK() < deadline:
                row = take_sample(backend, probe)
                output.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n');output.flush()
                remaining = min(args.interval, deadline-REAL_CLOCK())
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            backend.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
