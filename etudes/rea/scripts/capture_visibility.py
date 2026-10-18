#!/usr/bin/env python
"""Finite operator-coordinated RO visibility recipe, publication CLOSED.

No game launch, focus changes, injection, coach, API or audio. PNG only from the
foreground game window; raw requested reads stay in private ignored out/.
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
    TraceMemory, GameWindowState, capture_game_image, frozen_sources, utc,
)
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.visibility import CurrentVisibility
from hotstate.reader import ProcessBackend


def attempt(backend, map_id, *, native_profile=None, visibility_profile=None,
            position_profile=None, hero_ids=None):
    trace = TraceMemory(backend)
    row = {'wall_before': utc(), 'monotonic_before': time.monotonic()}
    try:
        native = NativeReader(trace, profile=native_profile)
        row['visibility'] = CurrentVisibility(native, profile=visibility_profile,
                                             position_profile=position_profile).diagnose(map_id, hero_ids=hero_ids)
    except NativeUnavailable as exc:
        row['rejected'] = str(exc)
    row.update(wall_after=utc(), monotonic_after=time.monotonic(), reads=trace.reads,
               bytes_requested=trace.bytes_requested, core_monotonic=trace.core_monotonic)
    return row


def capture_frame(backend, map_id, *, screenshot=None, **profiles):
    row = {'wall_before': utc(), 'monotonic_before': time.monotonic(),
           'before': attempt(backend, map_id, **profiles)}
    if screenshot is not None:
        image = {'wall_before': utc(), 'monotonic_before': time.monotonic()}
        image.update(screenshot())
        image.update(wall_after=utc(), monotonic_after=time.monotonic())
        row['image'] = image
    row['after'] = attempt(backend, map_id, **profiles)
    row.update(wall_after=utc(), monotonic_after=time.monotonic())
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--pid', type=int)
    parser.add_argument('--map-id', choices=['Volskaya'], default='Volskaya')
    parser.add_argument('--duration', type=float, default=120)
    parser.add_argument('--interval', type=float, default=0.5)
    parser.add_argument('--png', action='store_true')
    args = parser.parse_args(argv)
    if not 0 < args.duration <= 120 or not 0.25 <= args.interval <= 10:
        parser.error('duration/interval hors bornes')
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / 'out') or out.suffix != '.jsonl':
        parser.error('out doit être un JSONL privé sous le out/ ignoré du worktree')
    # Also freezes this collector; the shared helper freezes itself and readers.
    commit, manifest = frozen_sources(args.expected_commit, extra_paths=(Path(__file__).resolve(),))
    grab = None
    if args.png:
        from PIL import ImageGrab
        grab = ImageGrab.grab
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        backend = ProcessBackend(args.pid)
        try:
            window_state = GameWindowState(backend.pid) if grab else None
            stream.write(json.dumps({
                'kind': 'targeted_current_visibility', 'status': 'diagnostic_unreleased',
                'commit': commit, 'sources_sha256': manifest, 'pid': backend.pid,
                'module_base': backend.module_base, 'map_id_requested': args.map_id,
                'wall': utc(), 'monotonic_s': time.monotonic(), 'png': args.png,
                'heap_scan': False, 'coach_or_audio': False,
            }) + '\n'); stream.flush()
            deadline, sequence = time.monotonic() + args.duration, 0
            while time.monotonic() < deadline:
                png = out.with_name(f'{out.stem}-{sequence:05d}.png')
                def screenshot():
                    return capture_game_image(png, window_state, grab)
                row = capture_frame(backend, args.map_id, screenshot=screenshot if grab else None)
                row['sequence'] = sequence
                stream.write(json.dumps(row, allow_nan=False) + '\n'); stream.flush()
                sequence += 1
                delay = min(args.interval, deadline - time.monotonic())
                if delay > 0:
                    time.sleep(delay)
        finally:
            backend.close()
    print(f'Diagnostic privé conservé : {out} ; aucune visibilité publiée.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
