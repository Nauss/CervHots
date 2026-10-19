#!/usr/bin/env python
"""Private bounded battlefield diagnostic. Operator-only RO process access.

No game launch, GUI control, coach/API, sound, replay producer or public packet.
Unknown/torn memory is a refusal, not a ready/zero/destroyed observation.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from etudes.rea.scripts.capture_positions import (
    TraceMemory, ReplayTrace, GameWindowState, capture_game_image, frozen_sources, utc,
)
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.battlefield import VolskayaBattlefield
from hotstate.reader import ProcessBackend


def attempt(backend, *, native_profile=None, battlefield_profile=None,
            position_profile=None, match_profile=None, section='inventory'):
    trace = TraceMemory(backend)
    row = {'wall_before': utc(), 'monotonic_before': time.monotonic(),'requested_section':section}
    try:
        n = NativeReader(trace, profile=native_profile)
        row['battlefield'] = VolskayaBattlefield(n, profile=battlefield_profile,
            position_profile=position_profile, match_profile=match_profile).diagnose('Volskaya',section=section)
    except NativeUnavailable as exc:
        row['rejected'] = str(exc)
    row.update(wall_after=utc(), monotonic_after=time.monotonic(), reads=trace.reads,
               bytes_requested=trace.bytes_requested, core_monotonic=trace.core_monotonic)
    return row


def capture_frame(backend, *, screenshot=None, **profiles):
    row = {'wall_before': utc(), 'monotonic_before': time.monotonic(),
           'before': attempt(backend, **profiles)}
    if screenshot is not None:
        image = {'wall_before': utc(), 'monotonic_before': time.monotonic()}
        image.update(screenshot())
        image.update(wall_after=utc(), monotonic_after=time.monotonic())
        row['image'] = image
    row['after'] = attempt(backend, **profiles)
    row.update(wall_after=utc(), monotonic_after=time.monotonic())
    return row


def replay_attempt(base, packet, **profiles):
    profiles.setdefault('section',packet.get('requested_section','inventory'))
    backend = ReplayTrace(base, packet['reads'], packet['core_monotonic'])
    actual = attempt(backend, **profiles)
    backend.finish()
    for key in ('battlefield', 'rejected', 'bytes_requested'):
        if actual.get(key) != packet.get(key):
            raise AssertionError(f'battlefield replay differs: {key}')
    return actual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--preflight', action='store_true')
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--pid', type=int)
    parser.add_argument('--duration', type=float, default=120)
    parser.add_argument('--interval', type=float, default=1)
    parser.add_argument('--png', action='store_true')
    parser.add_argument('--section',choices=('inventory','camps','structures'),default='inventory')
    args = parser.parse_args(argv)
    if not 0 < args.duration <= 300 or not 0.25 <= args.interval <= 10:
        parser.error('duration/interval hors bornes')
    commit, manifest = frozen_sources(args.expected_commit, extra_paths=(Path(__file__).resolve(),))
    if args.preflight:
        print(json.dumps({'commit': commit, 'sources_sha256': manifest, 'live_opened': False}))
        return 0
    if args.out is None:
        parser.error('--out requis pour --live')
    out = args.out.resolve()
    if not out.is_relative_to(ROOT/'out') or out.suffix != '.jsonl':
        parser.error('out doit être un JSONL privé neuf sous out/ du worktree')
    grab = None
    if args.png:
        from PIL import ImageGrab
        grab = ImageGrab.grab
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        backend = ProcessBackend(args.pid)
        try:
            state = GameWindowState(backend.pid) if grab else None
            stream.write(json.dumps({'kind': 'targeted_current_battlefield', 'status': 'diagnostic_unreleased',
                'commit': commit, 'sources_sha256': manifest, 'pid': backend.pid, 'module_base': backend.module_base,
                'map_id_requested': 'Volskaya', 'wall': utc(), 'monotonic_s': time.monotonic(),
                'png': args.png, 'heap_scan': False, 'coach_or_audio': False,'section':args.section})+'\n')
            stream.flush()
            deadline, sequence = time.monotonic()+args.duration, 0
            while time.monotonic() < deadline:
                png = out.with_name(f'{out.stem}-{sequence:05d}.png')
                def screenshot():
                    return capture_game_image(png, state, grab)
                row = capture_frame(backend, screenshot=screenshot if grab else None,section=args.section)
                row['sequence'] = sequence
                stream.write(json.dumps(row, allow_nan=False)+'\n')
                stream.flush()
                sequence += 1
                delay = min(args.interval, deadline-time.monotonic())
                if delay > 0:
                    time.sleep(delay)
        finally:
            backend.close()
    print(f'Diagnostic champ de bataille privé : {out} ; publication fermée.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
