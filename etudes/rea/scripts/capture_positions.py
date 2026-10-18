#!/usr/bin/env python
"""Finite private RO positions recipe; no GUI control, coach, audio or heap scan.

Only the operator may invoke --live in the coordinated private match. PNG is an
explicit opt-in and imports Pillow lazily. Both sides run AlliedPositions' SAME
_observe core with the release gate CLOSED (diagnostic_unreleased).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hotstate.native import NativeReader, NativeUnavailable
from hotstate.positions import AlliedPositions
from hotstate.reader import ProcessBackend


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class TraceMemory:
    """Every requested read, including failures; fixed upper bounds, no cache."""
    def __init__(self, backend):
        self.backend = backend
        self.module_base = backend.module_base
        self.recorded_non_atomic = getattr(backend, 'recorded_non_atomic', False)
        self.reads = []
        self.bytes_requested = 0
        self.core_monotonic = []

    def positions_clock(self):
        clock = getattr(self.backend, 'positions_clock', time.monotonic)
        value = clock()
        self.core_monotonic.append(value)
        return value

    def read_memory(self, address, size):
        if len(self.reads) >= 8192 or not 0 < size <= 65536 or self.bytes_requested + size > 2**20:
            raise NativeUnavailable('budget_trace_positions_depasse')
        self.bytes_requested += size
        before, wall = time.monotonic(), utc()
        data = self.backend.read_memory(address, size)
        self.reads.append({'order': len(self.reads), 'address': address, 'size': size,
                           'monotonic_before': before, 'monotonic_after': time.monotonic(),
                           'wall_before': wall, 'wall_after': utc(),
                           'hex': data.hex() if data is not None else None})
        return data


def attempt(backend, map_id, *, native_profile=None, position_profile=None, hero_ids=None):
    trace = TraceMemory(backend)
    row = {'wall_before': utc(), 'monotonic_before': time.monotonic()}
    try:
        native = NativeReader(trace, profile=native_profile)
        row['positions'] = AlliedPositions(native, profile=position_profile).diagnose(map_id, hero_ids=hero_ids)
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


class ReplayTrace:
    """Exact ordered playback; any unconsumed or divergent read is an error."""
    def __init__(self, module_base, reads, core_monotonic=()):
        self.module_base, self.reads, self.cursor = module_base, reads, 0
        self.core_monotonic, self.clock_cursor = core_monotonic, 0

    def positions_clock(self):
        if self.clock_cursor >= len(self.core_monotonic):
            raise AssertionError('core clock trace exhausted')
        value = self.core_monotonic[self.clock_cursor]
        self.clock_cursor += 1
        return value

    def read_memory(self, address, size):
        if self.cursor >= len(self.reads):
            raise AssertionError('trace exhausted')
        expected = self.reads[self.cursor]
        if (expected['order'], expected['address'], expected['size']) != (self.cursor, address, size):
            raise AssertionError('read sequence differs')
        self.cursor += 1
        return None if expected['hex'] is None else bytes.fromhex(expected['hex'])

    def finish(self):
        if self.cursor != len(self.reads):
            raise AssertionError('unconsumed trace')
        if self.clock_cursor != len(self.core_monotonic):
            raise AssertionError('unconsumed clock trace')


def frozen_sources(expected_commit):
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != expected_commit or subprocess.call(['git', 'diff', '--quiet', 'HEAD'], cwd=ROOT):
        raise ValueError('commit différent ou fichiers suivis modifiés')
    paths = [Path(__file__).resolve(), *sorted((ROOT / 'hotstate').glob('*.py')),
             *sorted((ROOT / 'hotstate/profiles').glob('*.json')), ROOT / 'hotstate/hero_ids.json']
    manifest = {}
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        recorded = subprocess.check_output(['git', 'show', f'{commit}:{relative}'], cwd=ROOT)
        data = path.read_bytes()
        # Git worktrees can use CRLF; compare canonical text, hash actual bytes.
        if data.replace(b'\r\n', b'\n') != recorded.replace(b'\r\n', b'\n'):
            raise ValueError(f'source non gelée : {relative}')
        manifest[relative] = hashlib.sha256(data).hexdigest()
    return commit, manifest


def save_png_exclusive(image, path):
    with path.open('xb') as stream:
        image.save(stream, format='PNG')
    return {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'size': list(image.size)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--out', type=Path, required=True, help='new private JSONL under this worktree out/')
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--map-id', choices=['Volskaya'], default='Volskaya')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--duration', type=float, default=60)
    parser.add_argument('--interval', type=float, default=0.5)
    parser.add_argument('--png', action='store_true', help='operator-coordinated desktop PNG between RO reads')
    args = parser.parse_args(argv)
    if not 0 < args.duration <= 120 or not 0.25 <= args.interval <= 10:
        parser.error('duration/interval hors bornes')
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / 'out') or out.suffix != '.jsonl':
        parser.error('out doit être un JSONL privé sous le out/ ignoré du worktree')
    try:
        commit, manifest = frozen_sources(args.expected_commit)
    except (ValueError, subprocess.CalledProcessError) as exc:
        parser.error(f'capture non gelée : {exc}')
    grab = None
    if args.png:
        from PIL import ImageGrab
        grab = ImageGrab.grab
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        backend = ProcessBackend(args.pid)
        try:
            header = {'kind': 'targeted_allied_positions', 'status': 'diagnostic_unreleased',
                      'commit': commit, 'sources_sha256': manifest, 'worktree': str(ROOT), 'pid': backend.pid,
                      'module_base': backend.module_base, 'map_id_requested': args.map_id,
                      'wall': utc(), 'monotonic_s': time.monotonic(),
                      'png': args.png, 'heap_scan': False, 'coach_or_audio': False}
            # Public path MUST refuse absent identity even with a real native root.
            try:
                AlliedPositions(NativeReader(backend)).read({'local_player': None})
            except NativeUnavailable as exc:
                header['absent_context_refusal'] = str(exc)
            else:
                raise AssertionError('absent identity unexpectedly accepted')
            stream.write(json.dumps(header) + '\n'); stream.flush()
            deadline = time.monotonic() + args.duration
            sequence = 0
            while time.monotonic() < deadline:
                png_path = out.with_name(f'{out.stem}-{sequence:05d}.png')
                def screenshot():
                    image = grab()
                    return save_png_exclusive(image, png_path)
                row = capture_frame(backend, args.map_id, screenshot=screenshot if grab else None)
                row['sequence'] = sequence
                stream.write(json.dumps(row, allow_nan=False) + '\n'); stream.flush()
                sequence += 1
                # Bounded cadence, never catch up with a read storm.
                delay = min(args.interval, deadline - time.monotonic())
                if delay > 0:
                    time.sleep(delay)
        finally:
            backend.close()
    print(f'Diagnostic privé conservé : {out} ; publication toujours fermée.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
