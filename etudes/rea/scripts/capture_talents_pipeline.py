#!/usr/bin/env python
"""Finite private talents candidate through read_current/normalizer/tactical_key.

No GUI/images/OCR/coach/audio. The release gate opens in THIS diagnostic
process only. Full acceptance requires nonempty typed talents and whole budget.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
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

from etudes.rea.scripts.capture_positions import TraceMemory, ReplayTrace, frozen_sources, utc
from etudes.rea.scripts.capture_visibility_pipeline import RecordedClock
from etudes.rea.scripts.capture_talents import _cache_rows, _cache, PRIVATE_ROOT
from hotstate.reader import ProcessBackend
from hotstate.native import NativeUnavailable
from hotstate.native_context import NativeContextProbe
from hotstate.talents import NativeTalentChoices
from hotstate.live import read_current
from cerveau.state import snapshot as normalize
from cerveau.runner import tactical_key

REAL_CLOCK = time.monotonic
CANDIDATE_SCOPES = (('DragonShire','sonya'), ('DragonShire','stitches'), ('Volskaya','stitches'))


class PipelineMemory(ProcessBackend):
    def __init__(self, backend):
        self.trace = TraceMemory(backend)
        self.module_base = backend.module_base
        self.recorded_non_atomic = getattr(backend, 'recorded_non_atomic', False)

    def read_memory(self, address, size):
        return self.trace.read_memory(address, size)

    def positions_clock(self):
        return self.trace.positions_clock()


def take_sample(backend, probe, *, clock=None, native_profile=None):
    memory = PipelineMemory(backend)
    recorded = RecordedClock(REAL_CLOCK if clock is None else clock)
    row = {'status':'rejected', 'kind':'candidate_full_talents_NOT_RELEASE',
           'recorded_non_atomic':memory.recorded_non_atomic,
           'execution_kind':'fixture_or_historical_NOT_LIVE' if clock is not None or native_profile is not None
                            else 'real_monotonic_record_only'}
    if not isinstance(probe, NativeContextProbe):
        return dict(row, rejected='talent_context_source_unsupported')
    before = _cache_rows(probe.map_cache)
    refusals = []
    original = NativeTalentChoices.read
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
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch('time.monotonic', recorded))
            stack.enter_context(patch('hotstate.talents.VALIDATED_SCOPES', CANDIDATE_SCOPES))
            stack.enter_context(patch.object(NativeTalentChoices, 'read', observed))
            if native_profile is not None:
                from hotstate import live
                original_snapshot = live.memory_snapshot
                def fixture_snapshot(memory, mapping, *, context):
                    return original_snapshot(memory, mapping, context=context, native_profile=native_profile)
                stack.enter_context(patch.object(live, 'memory_snapshot', fixture_snapshot))
            start = time.monotonic()
            clean = read_current(memory, {'triggers':{}}, context=probe, project=project, key=key)
            elapsed = time.monotonic()-start
            if not clean.get('talents', {}).get('players'):
                raise NativeUnavailable('talents_full_pipeline_absent')
            if not 0 <= elapsed <= 0.125:
                raise NativeUnavailable('fenetre_pipeline_globale_depassee')
            for hero in clean['heroes']:
                if hero['team'] != clean['ally_team'] and any(k in hero for k in
                        ('health','health_max','resource','resource_max','x','y','cooldowns','talents')):
                    raise AssertionError('enemy tactical leak')
            row.update(status='accepted', whole_snapshot_window_s=elapsed)
    except (NativeUnavailable, ValueError) as exc:
        row['rejected'] = str(exc)
    row.update(reads=memory.trace.reads, bytes_requested=memory.trace.bytes_requested,
        wall_clock_calls=recorded.values, optional_talent_refusals=refusals,
        context_map_cache_before=before, context_map_cache_after=_cache_rows(probe.map_cache))
    return row


def replay_sample(row, module_base, probe, *, native_profile=None):
    replay = ReplayTrace(module_base, row['reads'])
    shadow = SimpleNamespace(module_base=module_base, read_memory=replay.read_memory,
                             recorded_non_atomic=row.get('recorded_non_atomic', False))
    times = iter(row['wall_clock_calls'])
    after = _cache(row['context_map_cache_after'])
    replay_probe = NativeContextProbe(probe.player_name, profile=probe.profile,
        map_resolver=lambda handles: dict(after[tuple(handles)]))
    replay_probe.map_cache = _cache(row['context_map_cache_before'])
    actual = take_sample(shadow, replay_probe, clock=lambda:next(times), native_profile=native_profile)
    replay.finish()
    sentinel = object()
    if next(times, sentinel) is not sentinel:
        raise AssertionError('unconsumed talent pipeline clock')
    for field in ('status','rejected','normalized','tactical_key','whole_snapshot_window_s',
                  'optional_talent_refusals','bytes_requested'):
        if actual.get(field) != row.get(field):
            raise AssertionError('Talent pipeline replay differs: '+field)
    return actual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--live', action='store_true')
    parser.add_argument('--candidate-talents', action='store_true')
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--pid', type=int)
    parser.add_argument('--duration', type=float, default=12)
    parser.add_argument('--interval', type=float, default=0.5)
    parser.add_argument('--private-player-env', default='HOTS_PLAYER')
    args = parser.parse_args(argv)
    if not 0 < args.duration <= 30 or not 0.25 <= args.interval <= 10:
        parser.error('duration/interval hors bornes')
    if args.live and not args.candidate_talents:
        parser.error('--candidate-talents explicite requis')
    extra = [Path(__file__).resolve(), ROOT/'etudes/rea/scripts/capture_talents.py',
             ROOT/'etudes/rea/scripts/capture_visibility_pipeline.py', ROOT/'kb/data/map_timings.json']
    extra.extend(sorted((ROOT/'cerveau').glob('*.py')))
    extra.extend(sorted((ROOT/'grocoapi').glob('*.py')))
    commit, sources = frozen_sources(args.expected_commit, extra_paths=extra)
    if args.preflight:
        print(json.dumps({'commit':commit, 'sources_sha256':sources,
                          'live_opened':False, 'release':False, 'png':False}))
        return 0
    if args.out is None:
        parser.error('--out requis')
    out = args.out.resolve()
    if not out.is_relative_to(PRIVATE_ROOT.resolve()) or out.suffix != '.jsonl':
        parser.error('JSONL prive neuf sous day-fleet/2026-10-20/private requis')
    label = os.environ.get(args.private_player_env)
    if not label:
        parser.error('libelle prive requis en variable locale, jamais argv/manifeste')
    probe = NativeContextProbe(label)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        backend = ProcessBackend(args.pid)
        try:
            stream.write(json.dumps({'kind':'candidate_full_talents_NOT_RELEASE','commit':commit,
                'sources_sha256':sources,'module_base':backend.module_base,'wall':utc(),
                'png':False,'coach_audio':False,'heap_scan':False})+'\n')
            stream.flush()
            deadline = REAL_CLOCK()+args.duration
            while REAL_CLOCK() < deadline:
                stream.write(json.dumps(take_sample(backend,probe),allow_nan=False)+'\n')
                stream.flush()
                remaining = min(args.interval,deadline-REAL_CLOCK())
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            backend.close()
    with out.with_suffix('.manifest.json').open('x',encoding='utf-8') as stream:
        json.dump({'file':out.name,'size':out.stat().st_size,'commit':commit,
            'sha256':hashlib.sha256(out.read_bytes()).hexdigest()},stream,indent=2)
    print('Recette candidate talents privee terminee ; aucune activation produit.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
