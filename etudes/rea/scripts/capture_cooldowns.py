#!/usr/bin/env python
"""Operator-only finite RO cooldown diagnostic. Never Full/coach/GUI/PNG."""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etudes.rea.scripts.capture_positions import TraceMemory, ReplayTrace, frozen_sources, utc
from hotstate.cooldowns import observe
from hotstate.native_context import NativeContextProbe
from hotstate.reader import ProcessBackend


class Clock:
    def __init__(self, values=None):
        self.replay = values
        self.values = []

    def __call__(self):
        value = time.monotonic() if self.replay is None else self.replay[len(self.values)]
        self.values.append(value)
        return value


def take_sample(backend, probe, *, extended_sources=False):
    trace, clock = TraceMemory(backend), Clock()
    before = utc()
    cache_before = encode_cache(probe.map_cache)
    result = observe(trace, probe, clock=clock, extended_sources=extended_sources)
    return {'kind': 'local_unit_cooldown_diagnostic_NOT_PRODUCT', 'wall_before': before,
            'wall_after': utc(), 'observation': result, 'reads': trace.reads,
            'clock_values': clock.values, 'bytes_requested': trace.bytes_requested,
            'recorded_non_atomic': trace.recorded_non_atomic,
            'extended_sources': extended_sources,
            'map_cache_before': cache_before, 'map_cache_after': encode_cache(probe.map_cache)}


def encode_cache(cache):
    return [{'handles': [h.hex() for h in handles], 'metadata': copy.deepcopy(metadata)}
            for handles, metadata in cache.items()]


def decode_cache(entries):
    return {tuple(bytes.fromhex(h) for h in entry['handles']): copy.deepcopy(entry['metadata'])
            for entry in entries}


def replay_sample(row, module_base, probe):
    trace = ReplayTrace(module_base, row['reads'])
    trace.recorded_non_atomic = row['recorded_non_atomic']
    clock = Clock(row['clock_values'])
    after = decode_cache(row['map_cache_after'])
    def resolve(handles):
        if tuple(handles) not in after:
            raise AssertionError('unrecorded map resolution')
        return copy.deepcopy(after[tuple(handles)])
    isolated = NativeContextProbe(probe.player_name, profile=probe.profile, map_resolver=resolve)
    isolated.map_cache = decode_cache(row['map_cache_before'])
    actual = observe(trace, isolated, clock=clock, extended_sources=row.get('extended_sources', False))
    trace.finish()
    if (clock.values != row['clock_values'] or actual != row['observation']
            or encode_cache(isolated.map_cache) != row['map_cache_after']):
        raise AssertionError('cooldown diagnostic replay differs')
    return actual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--live', action='store_true')
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--duration', type=float, default=25)
    parser.add_argument('--interval', type=float, default=0.25)
    parser.add_argument('--private-player-env', default='HOTS_PLAYER')
    parser.add_argument('--active-storage-diagnostic', action='store_true')
    args = parser.parse_args(argv)
    if not 0 < args.duration <= 120 or not 0.25 <= args.interval <= 10:
        parser.error('duration/interval hors bornes')
    commit, sources = frozen_sources(args.expected_commit, extra_paths=(Path(__file__).resolve(),))
    if args.preflight:
        print(json.dumps({'commit': commit, 'sources_sha256': sources,
                          'live_opened': False, 'product': False, 'png': False}))
        return 0
    if args.out is None:
        parser.error('--out requis')
    out = args.out.resolve()
    private_root = Path('C:/root/dev/AI/CervHots/out/day-fleet/2026-10-20/private').resolve()
    if not out.is_relative_to(private_root) or out.suffix != '.jsonl':
        parser.error('JSONL privé neuf sous private/ du jour requis')
    label = os.environ.get(args.private_player_env)
    if not label:
        parser.error('libellé privé requis en variable locale, jamais dans argv/manifeste')
    probe = NativeContextProbe(label)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        backend = ProcessBackend()
        try:
            stream.write(json.dumps({'kind': 'local_unit_cooldown_diagnostic_NOT_PRODUCT',
                'commit': commit, 'sources_sha256': sources, 'module_base': backend.module_base,
                'extended_sources': args.active_storage_diagnostic,
                'wall': utc(), 'png': False, 'coach_audio': False, 'heap_scan': False})+'\n')
            stream.flush()
            deadline = time.monotonic()+args.duration
            while time.monotonic() < deadline:
                stream.write(json.dumps(take_sample(backend, probe, extended_sources=args.active_storage_diagnostic), allow_nan=False)+'\n')
                stream.flush()
                remaining = min(args.interval, deadline-time.monotonic())
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            backend.close()
    print('Diagnostic CD privé terminé ; aucun produit/coach/audio/image.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
