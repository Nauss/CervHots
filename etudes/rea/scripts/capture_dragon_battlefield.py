#!/usr/bin/env python
"""Private finite Dragon camps/structures diagnostic: no GUI/PNG/coach/audio.

No public packet, complete initial catalogue or live consumer qualification is
claimed. Readsets are private and must not be included in Git or model prompts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etudes.rea.scripts.capture_positions import TraceMemory, ReplayTrace, frozen_sources, utc
from hotstate.dragon_battlefield import DragonBattlefield
from hotstate.live import LiveBudget
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.native_context import NativeContextProbe
from hotstate.reader import ProcessBackend


def attempt(backend, probe, *, native_profile=None, battlefield_profile=None):
    trace = TraceMemory(backend)
    row = {'wall_before': utc(), 'status': 'rejected'}
    budget = LiveBudget(trace, clock=trace.positions_clock)
    try:
        native = NativeReader(budget, profile=native_profile)
        sample = DragonBattlefield(native, profile=battlefield_profile).diagnose(probe, clock=trace.positions_clock)
        budget.check()
        row.update(status='accepted_diagnostic_NOT_PRODUCT', battlefield=sample)
    except NativeUnavailable as exc:
        row['rejected'] = str(exc)
    row.update(wall_after=utc(), reads=trace.reads, bytes_requested=trace.bytes_requested,
               core_monotonic=trace.core_monotonic)
    return row


def replay_attempt(base, packet, probe, **profiles):
    backend = ReplayTrace(base, packet['reads'], packet['core_monotonic'])
    actual = attempt(backend, probe, **profiles)
    backend.finish()
    for key in ('status', 'battlefield', 'rejected', 'bytes_requested'):
        if actual.get(key) != packet.get(key):
            raise AssertionError('Dragon battlefield replay differs: '+key)
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
    parser.add_argument('--interval', type=float, default=0.25)
    parser.add_argument('--private-player-env', default='HOTS_PLAYER')
    args = parser.parse_args(argv)
    if not 0 < args.duration <= 30 or not 0.25 <= args.interval <= 10:
        parser.error('duration/interval hors bornes')
    commit, sources = frozen_sources(args.expected_commit, extra_paths=(Path(__file__).resolve(),))
    if args.preflight:
        print(json.dumps({'commit': commit, 'sources_sha256': sources,
                          'live_opened': False, 'release': False, 'png': False}))
        return 0
    if args.out is None:
        parser.error('--out requis')
    out = args.out.resolve()
    if not out.is_relative_to(ROOT/'out') or out.suffix != '.jsonl':
        parser.error('out doit être un JSONL privé neuf sous out/ du worktree')
    label = os.environ.get(args.private_player_env)
    if not label:
        parser.error('libellé privé requis par variable locale, jamais dans la commande ou le manifeste')
    probe = NativeContextProbe(label)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        backend = ProcessBackend(args.pid)
        try:
            stream.write(json.dumps({'kind': 'native_dragon_battlefield_diagnostic_NOT_PRODUCT',
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
    print('Diagnostic camps/structures Dragon privé terminé ; publication fermée.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
