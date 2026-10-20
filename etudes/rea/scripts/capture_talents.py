#!/usr/bin/env python
"""Operator-only finite selected talent diagnostic. No GUI/PNG/OCR/audio/coach.

Readsets contain private context bytes: ignored private storage ONLY. This
research collector is not a Full producer and grants no hero/map coverage.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etudes.rea.scripts.capture_positions import TraceMemory, ReplayTrace, frozen_sources, utc
from hotstate.talents import diagnose
from hotstate.native_context import NativeContextProbe
from hotstate.reader import ProcessBackend

PRIVATE_ROOT = ROOT.parents[1]/'out/day-fleet/2026-10-20/private'


def _cache_rows(cache):
    return [{'handles': [h.hex() for h in key], 'result': copy.deepcopy(value)}
            for key, value in cache.items()]


def _cache(rows):
    return {tuple(bytes.fromhex(h) for h in row['handles']): copy.deepcopy(row['result'])
            for row in rows}


def attempt(backend, probe, *, native_profile=None, clock=None):
    trace = TraceMemory(backend)
    if clock is not None:
        trace.backend = type('ClockBackend', (), {
            'read_memory': staticmethod(backend.read_memory), 'positions_clock': staticmethod(clock)})()
    before = _cache_rows(probe.map_cache)
    row = diagnose(trace, probe, clock=trace.positions_clock, native_profile=native_profile)
    return dict(row, reads=trace.reads, core_monotonic=trace.core_monotonic,
                context_map_cache_before=before, context_map_cache_after=_cache_rows(probe.map_cache))


def replay_attempt(base, packet, probe, *, native_profile=None):
    backend = ReplayTrace(base, packet['reads'], packet['core_monotonic'])
    cache_after = _cache(packet['context_map_cache_after'])
    replay_probe = NativeContextProbe(probe.player_name, profile=probe.profile,
        map_resolver=lambda handles: copy.deepcopy(cache_after[tuple(handles)]))
    replay_probe.map_cache = _cache(packet['context_map_cache_before'])
    actual = attempt(backend, replay_probe, native_profile=native_profile)
    backend.finish()
    for key in ('status', 'reason', 'source', 'coverage', 'hero', 'map_id', 'local_id', 'team', 'match_id',
                'generation', 'level', 'tree', 'mission_interval_s', 'elapsed_s',
                'read_count', 'bytes_requested'):
        if actual.get(key) != packet.get(key):
            raise AssertionError('Talent strict replay differs: '+key)
    return actual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--live', action='store_true')
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--pid', type=int)
    parser.add_argument('--duration', type=float, default=12)
    parser.add_argument('--interval', type=float, default=0.5)
    parser.add_argument('--private-player-env', default='HOTS_PLAYER')
    args = parser.parse_args(argv)
    if not 0 < args.duration <= 30 or not 0.25 <= args.interval <= 10:
        parser.error('duration/interval hors bornes')
    commit, sources = frozen_sources(args.expected_commit, extra_paths=(Path(__file__).resolve(),))
    if args.preflight:
        print(json.dumps({'commit': commit, 'sources_sha256': sources,
            'live_opened': False, 'release': False, 'png': False, 'mode': 'diagnostic_NOT_PRODUCT'}))
        return 0
    if args.out is None:
        parser.error('--out requis')
    out = args.out.resolve()
    if not out.is_relative_to(PRIVATE_ROOT.resolve()) or out.suffix != '.jsonl':
        parser.error('out doit être un JSONL privé neuf sous day-fleet/2026-10-20/private')
    label = os.environ.get(args.private_player_env)
    if not label:
        parser.error('libellé privé requis par variable locale, jamais dans commande/manifeste')
    probe = NativeContextProbe(label)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        backend = ProcessBackend(args.pid)
        try:
            stream.write(json.dumps({'kind': 'native_selected_talents_diagnostic_NOT_PRODUCT',
                'commit': commit, 'sources_sha256': sources, 'module_base': backend.module_base,
                'wall': utc(), 'png': False, 'coach_audio': False, 'heap_scan': False})+'\n')
            stream.flush()
            deadline = time.monotonic()+args.duration
            while time.monotonic() < deadline:
                stream.write(json.dumps(attempt(backend, probe), allow_nan=False)+'\n')
                stream.flush()
                remaining = min(args.interval, deadline-time.monotonic())
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            backend.close()
    manifest = {'file': out.name, 'sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
                'size': out.stat().st_size, 'commit': commit, 'kind': 'private_diagnostic_NOT_PRODUCT'}
    with out.with_suffix('.manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
    print('Diagnostic talents privé terminé ; aucune publication produit.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
