#!/usr/bin/env python
"""heap_clock_scan5.py — chrono : tolérance de dérive + doubles + image.

Corrections vs scan4 :
  - la simulation dérive légèrement du temps réel (chargement, GC) : les écarts
    sont testés avec tolérance (sec ±8, ticks ±128, ms ±8000, f32/f64 ±2 s) ;
  - encodages supplémentaires : float64 ;
  - les dumps d'IMAGE sont aussi fouillés (les singletons moteur vivent dans
    .data, pas seulement dans le tas) — adresses vivantes (base 0x7ff62bd00000).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

BASE = Path(r"C:\Users\Nauss\ghidra-projects")
IMAGE_BASE = 0x7FF62BD00000
D23, D34 = 382, 427
STEMS = ("game2", "game3", "game4")
SCALES = (("sec", 1, 8), ("tick16", 16, 128), ("ms", 1000, 8000))


def regions_of(stem):
    """Régions (addr, offset, size) : tas + image mappée en une région."""
    regs = json.loads((BASE / f"hots_{stem}.heap.json").read_text(encoding="utf-8"))["regions"]
    return regs


def main():
    files = {}
    for s in STEMS:
        files[("heap", s)] = np.memmap(BASE / f"hots_{s}.heap.bin",
                                       dtype=np.uint8, mode="r")
        files[("img", s)] = np.memmap(BASE / f"hots_{s}.bin",
                                      dtype=np.uint8, mode="r")

    man = {s: regions_of(s) for s in STEMS}
    idx = {s: {r["addr"]: r for r in man[s]} for s in STEMS}
    heap_addrs = sorted(set(idx["game2"]) & set(idx["game3"]) & set(idx["game4"]))

    # travail par segments homogènes : (nom, {stem: (offset, size)}, addr_de_base)
    segments = []
    for addr in heap_addrs:
        r2, r3, r4 = idx["game2"][addr], idx["game3"][addr], idx["game4"][addr]
        size = min(r2["size"], r3["size"], r4["size"]) // 8 * 8
        if size >= 16:
            segments.append(("heap", addr,
                             {"game2": (r2["offset"], size),
                              "game3": (r3["offset"], size),
                              "game4": (r4["offset"], size)}))
    img_size = min(len(files[("img", s)]) for s in STEMS) // 8 * 8
    segments.append(("img", IMAGE_BASE,
                     {s: (0, img_size) for s in STEMS}))
    print(f"segments : {len(segments)} (dont image {img_size / 1e6:.1f} Mo)",
          flush=True)

    results = []
    for n, (kind, addr, spec) in enumerate(segments):
        views = {}
        for s in STEMS:
            off, size = spec[s]
            views[s] = files[(kind, s)][off:off + size]
        u2 = np.frombuffer(views["game2"], dtype="<u8")
        u3 = np.frombuffer(views["game3"], dtype="<u8")
        u4 = np.frombuffer(views["game4"], dtype="<u8")
        # u32 (paires / impaires d'octets couvertes via vues u4 décalées)
        for shift in (0, 4):
            w2 = np.frombuffer(views["game2"][shift:], dtype="<u4")[: len(u2) * 2]
            w3 = np.frombuffer(views["game3"][shift:], dtype="<u4")[: len(u3) * 2]
            w4 = np.frombuffer(views["game4"][shift:], dtype="<u4")[: len(u4) * 2]
            for enc, k, tol in SCALES:
                mask = ((np.abs(w3.astype(np.int64) - w2.astype(np.int64) - D23 * k) <= tol)
                        & (np.abs(w4.astype(np.int64) - w3.astype(np.int64) - D34 * k) <= tol))
                for pos in np.nonzero(mask)[0].tolist():
                    results.append((enc, addr + shift + pos * 4,
                                    int(w2[pos]), int(w3[pos]), int(w4[pos])))
        for dt, enc in (("<f4", "f32"), ("<f8", "f64")):
            f2 = np.frombuffer(views["game2"], dtype=dt)
            f3 = np.frombuffer(views["game3"], dtype=dt)
            f4 = np.frombuffer(views["game4"], dtype=dt)
            with np.errstate(invalid="ignore", over="ignore"):
                mask = ((np.abs((f3 - f2) - D23) <= 2.0)
                        & (np.abs((f4 - f3) - D34) <= 2.0)
                        & np.isfinite(f2) & np.isfinite(f3) & np.isfinite(f4))
            for pos in np.nonzero(mask)[0].tolist():
                results.append((enc, addr + pos * (8 if dt == "<f8" else 4),
                                float(f2[pos]), float(f3[pos]), float(f4[pos])))
        if n % 2000 == 0:
            print(f"   … {n}/{len(segments)}, {len(results)} candidats", flush=True)

    print(f"\n=== {len(results)} candidat(s) ===", flush=True)
    results.sort(key=lambda r: r[1])
    for enc, addr, x2, x3, x4 in results[:60]:
        print(f"  {addr:#x} [{enc}]  {x2} -> {x3} -> {x4}", flush=True)

    out = [{"enc": e, "addr": hex(a), "game2": v2, "game3": v3, "game4": v4}
           for e, a, v2, v3, v4 in results]
    (BASE / "clock_candidates.json").write_text(json.dumps(out, indent=1),
                                                encoding="utf-8")
    print("écrit: clock_candidates.json", flush=True)


if __name__ == "__main__":
    main()
