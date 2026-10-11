#!/usr/bin/env python
"""heap_clock_scan2.py — chrono de jeu par ÉCARTS de valeurs (zéro indépendant).

Entre les captures : game2 -> game3 = +382 s, game3 -> game4 = +427 s
(calés sur le replay). Toute mémoire qui suit le chrono doit présenter ces
écarts exacts à la même adresse, quel que soit l'encodage (secondes, ticks
1/16 s, ms, float32). Le filtre des écarts tue les faux positifs.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

BASE = Path(r"C:\Users\Nauss\ghidra-projects")
D23, D34 = 382, 427          # écarts temporels entre captures (s)
STEMS = ("game2", "game3", "game4")
RANGES = {                  # encodage -> (min, max, échelle)
    "sec": (0, 3200, 1),
    "tick16": (0, 3200 * 16, 16),
    "ms": (0, 3200 * 1000, 1000),
}


def load(stem):
    m = json.loads((BASE / f"hots_{stem}.heap.json").read_text(encoding="utf-8"))
    data = (BASE / f"hots_{stem}.heap.bin").read_bytes()
    return m["regions"], data


def offset_to_addr(regions, offs: np.ndarray):
    starts = np.array([r["offset"] for r in regions], dtype=np.int64)
    sizes = np.array([r["size"] for r in regions], dtype=np.int64)
    addrs = np.array([r["addr"] for r in regions], dtype=np.int64)
    i = np.searchsorted(starts, offs, side="right") - 1
    ok = (i >= 0) & (offs < starts[np.clip(i, 0, len(starts) - 1)]
                     + sizes[np.clip(i, 0, len(starts) - 1)])
    out = np.full(offs.shape, -1, dtype=np.int64)
    ii = i[ok]
    out[ok] = addrs[ii] + (offs[ok] - starts[ii])
    return out


def scan_all(stem):
    """Un seul chargement par dump : tous les encodages d'un coup."""
    regions, data = load(stem)
    out = {}
    arr = np.frombuffer(data, dtype="<u4")
    for enc, (lo, hi, _scale) in RANGES.items():
        idxs = np.nonzero((arr >= lo) & (arr <= hi))[0]
        vals = arr[idxs].astype(np.int64)
        addrs = offset_to_addr(regions, idxs * 4)
        keep = addrs >= 0
        out[enc] = dict(zip(addrs[keep].tolist(), vals[keep].tolist()))
    del arr
    fa = np.frombuffer(data, dtype="<f4")
    idxs = np.nonzero(np.isfinite(fa) & (fa >= 0) & (fa <= 3200))[0]
    addrs = offset_to_addr(regions, idxs * 4)
    keep = addrs >= 0
    out["f32"] = dict(zip(addrs[keep].tolist(),
                          [float(x) for x in fa[idxs][keep]]))
    return out


def check(v2, v3, v4, scale, tol):
    return (abs((v3 - v2) - D23 * scale) <= tol
            and abs((v4 - v3) - D34 * scale) <= tol)


def main():
    per = {s: scan_all(s) for s in STEMS}
    results = []
    for enc, scale in (("sec", 1), ("tick16", 16), ("ms", 1000)):
        m2, m3, m4 = per["game2"][enc], per["game3"][enc], per["game4"][enc]
        print(f"{enc}: candidats {len(m2)} / {len(m3)} / {len(m4)}")
        for a in set(m2) & set(m3) & set(m4):
            if check(m2[a], m3[a], m4[a], scale, 0):
                results.append((enc, a, m2[a], m3[a], m4[a]))
    f2, f3, f4 = per["game2"]["f32"], per["game3"]["f32"], per["game4"]["f32"]
    print(f"f32: candidats {len(f2)} / {len(f3)} / {len(f4)}")
    for a in set(f2) & set(f3) & set(f4):
        if check(f2[a], f3[a], f4[a], 1.0, 0.51):
            results.append(("f32", a, round(f2[a], 2), round(f3[a], 2), round(f4[a], 2)))

    print(f"\n=== {len(results)} candidat(s) chrono ===")
    for enc, a, v2, v3, v4 in sorted(results, key=lambda r: r[1])[:40]:
        print(f"   {a:#x}  [{enc}]  {v2} -> {v3} -> {v4}")
    (BASE / "clock_candidates.json").write_text(
        json.dumps([{"enc": e, "addr": hex(a), "game2": v2, "game3": v3, "game4": v4}
                    for e, a, v2, v3, v4 in results], indent=1), encoding="utf-8")
    print("écrit: clock_candidates.json")


if __name__ == "__main__":
    main()
