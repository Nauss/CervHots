#!/usr/bin/env python
"""Finite, targeted RO clock capture. Run ONLY in a coordinated existing game.

Does not start a match, move focus, capture the desktop, send advice or play
sound. Pair its UTC/monotonic/mission brackets with a separately coordinated
HUD sampler. Raw packets are private memory evidence and must stay out of Git.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hotstate.gameplay import GameplayClock
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.reader import ProcessBackend


class RecordingBackend:
    """Record only the bounded reads requested by the production clock reader."""
    def __init__(self, backend):
        self.backend = backend
        self.module_base = backend.module_base
        self.recorded_non_atomic = getattr(backend, "recorded_non_atomic", False)
        self.reads = []

    def read_memory(self, address, size):
        before = time.monotonic()
        data = self.backend.read_memory(address, size)
        self.reads.append({"address": address, "size": size, "before": before,
                           "after": time.monotonic(),
                           "hex": data.hex() if data is not None else None})
        return data


def capture_one(reader):
    """One complete production attempt, including rejections and both passes."""
    packet = {"wall_before": dt.datetime.now(dt.timezone.utc).isoformat(),
              "monotonic_before": time.monotonic()}
    reader.native.memory.reads.clear()
    try:
        packet["clock"] = reader.read()
    except NativeUnavailable as exc:
        packet["rejected"] = str(exc)
    packet.update(wall_after=dt.datetime.now(dt.timezone.utc).isoformat(),
                  monotonic_after=time.monotonic(), reads=reader.native.memory.reads.copy())
    return packet


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True,
                        help="explicitly authorize this coordinated read-only sampling run")
    parser.add_argument("--out", type=Path, required=True, help="new private .jsonl file under out/")
    parser.add_argument("--duration", type=float, default=60, help="seconds, >0 and <=120")
    parser.add_argument("--interval", type=float, default=0.2, help="seconds, >=0.125 and <=10")
    args = parser.parse_args(argv)
    if not 0 < args.duration <= 120 or not 0.125 <= args.interval <= 10:
        parser.error("duration/interval hors bornes")
    output = args.out.resolve()
    if not output.is_relative_to(ROOT / "out") or output.suffix != ".jsonl":
        parser.error("la capture privée doit être un .jsonl dans le out/ ignoré du worktree")
    # Exclusive creation prevents overwriting evidence. Opening a process is RO.
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        backend = ProcessBackend()
        try:
            recording = RecordingBackend(backend)
            native = NativeReader(recording)
            reader = GameplayClock(native)
            stream.write(json.dumps({"kind": "targeted_clock_reads", "build": 98348,
                                     "module_base": native.base, "pid": backend.pid,
                                     "hud_captured": False, "not_a_rolling_heap_dump": True}) + "\n")
            start, deadline = time.monotonic(), time.monotonic() + args.duration
            sequence = 0
            while time.monotonic() < deadline:
                packet = capture_one(reader)
                packet["sequence"] = sequence
                stream.write(json.dumps(packet, allow_nan=False) + "\n")
                stream.flush()
                sequence += 1
                target = min(start + sequence * args.interval, deadline)
                delay = target - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                elif time.monotonic() < deadline:
                    # Skip missed scheduling slots, never create a catch-up read storm.
                    start = time.monotonic() - sequence * args.interval
        finally:
            backend.close()
    print(f"Capture ciblée conservée : {output} ; aucune validation HUD automatique.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
