#!/usr/bin/env python
"""Private Dragon candidate through the REAL consumer read_current entrypoint.

No coach, audio, GUI, screen collection or replay production. The release gate
is enabled only inside this diagnostic process. No Full claim without a typed
normalized Dragon objective and tactical key under the whole physical budget.
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

from etudes.rea.scripts.capture_positions import TraceMemory, ReplayTrace, frozen_sources, utc
from etudes.rea.scripts.capture_visibility_pipeline import RecordedClock
from hotstate.reader import ProcessBackend
from hotstate.native import NativeUnavailable
from hotstate.native_context import NativeContextProbe
from hotstate.dragon import DragonObjective
from hotstate.live import read_current
from cerveau.state import snapshot as normalize
from cerveau.runner import tactical_key

REAL_CLOCK = time.monotonic


class PipelineMemory(ProcessBackend):
    def __init__(self, backend):
        self.trace = TraceMemory(backend)
        self.module_base = backend.module_base
        self.recorded_non_atomic = getattr(backend, 'recorded_non_atomic', False)

    def read_memory(self, address, size):
        return self.trace.read_memory(address, size)

    def positions_clock(self):
        return self.trace.positions_clock()


def take_sample(backend, probe, *, clock=None, native_profile=None, candidate_permission=True):
    memory = PipelineMemory(backend)
    recorded = RecordedClock(REAL_CLOCK if clock is None else clock)
    row = {'status':'rejected', 'kind':('candidate_full_dragon_NOT_RELEASE' if candidate_permission else 'qualified_full_dragon_NOT_RELEASE'),
           'candidate_override':candidate_permission, 'wall_before':utc(),
           'recorded_non_atomic':memory.recorded_non_atomic,
           'execution_kind':('fixture_or_historical_NOT_LIVE' if clock is not None or native_profile is not None
                             else 'real_monotonic_record_only')}
    refusals = []
    original = DragonObjective.read
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
        row['map_metadata_observed'] = {k:v for k,v in result.items() if k in ('map','map_id')}
        return result
    try:
        if not isinstance(probe, NativeContextProbe):
            raise NativeUnavailable('contexte_natif_dragon_pipeline_requis')
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch('time.monotonic', recorded))
            if candidate_permission:
                stack.enter_context(patch('hotstate.dragon.VALIDATED_MAPS', ('DragonShire',)))
            stack.enter_context(patch.object(DragonObjective, 'read', observed))
            stack.enter_context(patch.object(probe, 'map_resolver', resolver))
            if native_profile is not None:
                # Literal profile fixtures only; live CLI NEVER uses this path.
                from hotstate import live
                actual_snapshot = live.memory_snapshot
                def fixture_snapshot(memory, mapping, *, context):
                    return actual_snapshot(memory, mapping, context=context, native_profile=native_profile)
                stack.enter_context(patch.object(live, 'memory_snapshot', fixture_snapshot))
            start = time.monotonic()
            clean = read_current(memory, {'triggers':{}}, context=probe, project=project, key=key)
            elapsed = time.monotonic()-start
            if (clean.get('objective', {}).get('map_id') != 'DragonShire'
                    or row.get('raw', {}).get('meta', {}).get('map_id') != 'DragonShire'):
                raise NativeUnavailable('objectif_dragon_pipeline_absent')
            if not 0 <= elapsed <= 0.125:
                raise NativeUnavailable('fenetre_pipeline_globale_depassee')
            for hero in clean['heroes']:
                if hero['team'] != clean['ally_team'] and any(k in hero for k in
                        ('health','health_max','resource','resource_max','x','y','cooldowns','talents')):
                    raise AssertionError('enemy tactical leak')
            row.update(status='accepted', whole_snapshot_window_s=elapsed)
    except (NativeUnavailable, ValueError) as exc:
        row['rejected'] = str(exc)
    # Record immutable-cache metadata even if a later context recheck refused.
    if 'map_metadata_observed' not in row:
        values = [{k:v for k,v in value.items() if k in ('map','map_id')}
                  for value in getattr(probe,'map_cache',{}).values()]
        if values and all(value == values[0] for value in values):
            row['map_metadata_observed'] = values[0]
    row.update(wall_after=utc(), reads=memory.trace.reads, bytes_requested=memory.trace.bytes_requested,
               wall_clock_calls=recorded.values, optional_dragon_refusals=refusals)
    return row


def replay_sample(row, module_base, probe, *, native_profile=None):
    replay = ReplayTrace(module_base, row['reads'])
    shadow = SimpleNamespace(module_base=module_base, read_memory=replay.read_memory,
                             recorded_non_atomic=row.get('recorded_non_atomic',False))
    times = iter(row['wall_clock_calls'])
    with patch.object(probe,'map_resolver',lambda _:dict(row.get('map_metadata_observed',{}))), \
         patch.object(probe,'map_cache',{}):
        actual = take_sample(shadow,probe,clock=lambda:next(times),native_profile=native_profile,
                             candidate_permission=row.get('candidate_override',True))
    replay.finish()
    sentinel = object()
    if next(times,sentinel) is not sentinel:
        raise AssertionError('unconsumed Dragon pipeline clock')
    for field in ('status','rejected','normalized','tactical_key','whole_snapshot_window_s',
                  'optional_dragon_refusals','bytes_requested'):
        if actual.get(field) != row.get(field):
            raise AssertionError('Dragon pipeline replay differs: '+field)
    return actual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight',action='store_true')
    mode.add_argument('--live',action='store_true')
    parser.add_argument('--candidate-dragon',action='store_true')
    parser.add_argument('--expected-commit',required=True)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--pid',type=int)
    parser.add_argument('--duration',type=float,default=12)
    parser.add_argument('--interval',type=float,default=0.25)
    parser.add_argument('--private-player-env',default='HOTS_PLAYER')
    args = parser.parse_args(argv)
    if not 0 < args.duration <= 30 or not 0.25 <= args.interval <= 10:
        parser.error('duration/interval hors bornes')
    if args.live and not args.candidate_dragon:
        parser.error('--candidate-dragon explicite requis')
    extra = [Path(__file__).resolve(), ROOT/'etudes/rea/scripts/capture_visibility_pipeline.py']
    extra.append(ROOT/'kb/data/map_timings.json')
    extra.extend(ROOT/'cerveau'/f for f in ('state.py','runner.py','objectives.py','dragon.py','battlefield.py'))
    commit,sources = frozen_sources(args.expected_commit,extra_paths=extra)
    if args.preflight:
        print(json.dumps({'commit':commit,'sources_sha256':sources,'live_opened':False,'release':False,'png':False}))
        return 0
    if args.out is None:
        parser.error('--out requis')
    out = args.out.resolve()
    if not out.is_relative_to(ROOT/'out') or out.suffix != '.jsonl':
        parser.error('JSONL privé neuf sous out/ du worktree requis')
    label = os.environ.get(args.private_player_env)
    if not label:
        parser.error('libellé privé requis en variable locale, jamais dans argv ou manifeste')
    probe = NativeContextProbe(label)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as stream:
        backend = ProcessBackend(args.pid)
        try:
            stream.write(json.dumps({'kind':'candidate_full_dragon_NOT_RELEASE','commit':commit,
                'sources_sha256':sources,'module_base':backend.module_base,'wall':utc(),
                'png':False,'coach_audio':False,'heap_scan':False})+'\n'); stream.flush()
            deadline = REAL_CLOCK()+args.duration
            while REAL_CLOCK() < deadline:
                stream.write(json.dumps(take_sample(backend,probe),allow_nan=False)+'\n'); stream.flush()
                remaining = min(args.interval,deadline-REAL_CLOCK())
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            backend.close()
    print('Recette candidate Dragon privée terminée ; aucune activation produit.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
