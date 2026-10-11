#!/usr/bin/env python
"""heap_clock_scan3.py — chrono de jeu par écarts de valeurs (version mémoire-safe).

Même principe que scan2 (écarts exacts entre captures : +382 s puis +427 s,
zéro indépendant), mais :
  - tableaux numpy triés + np.intersect1d au lieu de dicts (le float32 génère
    ~18 M de candidats aléatoires : les flottants couvrent ~2 % des motifs) ;
  - un dump en mémoire à la fois ;
  - pour chaque candidat : hexdump comparé du voisinage (±128 octets) dans les
    3 dumps — c'est là que se révélera la structure d'état.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

BASE = Path(r"C:\Users\Nauss\ghidra-projects")
D23, D34 = 382, 427
STEMS = ("game2", "game3", "game4")
RANGES = {"sec": (0, 3200), "tick16": (0, 3200 * 16), "ms": (0, 3200 * 1000)}


def load(stem):
    m = json.loads((BASE / f"hots_{stem}.heap.json").read_text(encoding="utf-8"))
    data = (BASE / f"hots_{stem}.heap.bin").read_bytes()
    return m["regions"], data


def offset_to_addr(regions, offs):
    starts = np.array([r["offset"] for r in regions], dtype=np.int64)
    sizes = np.array([r["size"] for r in regions], dtype=np.int64)
    addrs = np.array([r["addr"] for r in regions], dtype=np.int64)
    i = np.searchsorted(starts, offs, side="right") - 1
    ic = np.clip(i, 0, len(starts) - 1)
    ok = (i >= 0) & (offs < starts[ic] + sizes[ic])
    out = np.full(offs.shape, -1, dtype=np.int64)
    ii = i[ok]
    out[ok] = addrs[ii] + (offs[ok] - starts[ii])
    return out


def collect(stem):
    """{encodage: (addrs triées, valeurs)} pour un dump."""
    regions, data = load(stem)
    out = {}
    u32 = np.frombuffer(data, dtype="<u4")
    for enc, (lo, hi) in RANGES.items():
        idxs = np.nonzero((u32 >= lo) & (u32 <= hi))[0]
        addrs = offset_to_addr(regions, idxs * 4)
        keep = addrs >= 0
        a = addrs[keep]
        v = u32[idxs[keep]].astype(np.int64)
        order = np.argsort(a)
        out[enc] = (a[order], v[order])
        print(f"   {stem}/{enc}: {len(a)} candidats", flush=True)
    del u32
    fa = np.frombuffer(data, dtype="<f4")
    finite = np.isfinite(fa)
    idxs = np.nonzero(finite & (fa >= 0) & (fa <= 3200))[0]
    addrs = offset_to_addr(regions, idxs * 4)
    keep = addrs >= 0
    a = addrs[keep]
    v = fa[idxs[keep]]
    order = np.argsort(a)
    out["f32"] = (a[order], v[order])
    print(f"   {stem}/f32: {len(a)} candidats", flush=True)
    return out, regions, data


def val_at(entry, addr):
    a, v = entry
    i = np.searchsorted(a, addr)
    return float(v[i]) if i < len(a) and a[i] == addr else None


def hexdump(data, regions, addr, span=128):
    starts = np.array([r["offset"] for r in regions], dtype=np.int64)
    sizes = np.array([r["size"] for r in regions], dtype=np.int64)
    a0 = np.array([r["addr"] for r in regions], dtype=np.int64)
    i = np.searchsorted(a0, addr) - 1
    if i < 0 or addr >= a0[i] + sizes[i]:
        return None
    off = starts[i] + (addr - a0[i])
    lo = max(0, off - span)
    return data[lo:off + span]


def main():
    per, cached = {}, {}
    for stem in STEMS:
        print(f"collecte {stem} …", flush=True)
        per[stem], regions, data = collect(stem)
        cached[stem] = regions
        del data

    results = []
    for enc, scale in (("sec", 1), ("tick16", 16), ("ms", 1000)):
        a2, v2 = per["game2"][enc]
        a3, v3 = per["game3"][enc]
        a4, v4 = per["game4"][enc]
        common = np.intersect1d(np.intersect1d(a2, a3), a4)
        for addr in common.tolist():
            x2, x3, x4 = val_at(per["game2"][enc], addr), val_at(per["game3"][enc], addr), val_at(per["game4"][enc], addr)
            if abs((x3 - x2) - D23 * scale) <= 0 and abs((x4 - x3) - D34 * scale) <= 0:
                results.append((enc, addr, x2, x3, x4))
    a2, _ = per["game2"]["f32"]
    a3, _ = per["game3"]["f32"]
    a4, _ = per["game4"]["f32"]
    common = np.intersect1d(np.intersect1d(a2, a3), a4)
    for addr in common.tolist():
        x2 = val_at(per["game2"]["f32"], addr)
        x3 = val_at(per["game3"]["f32"], addr)
        x4 = val_at(per["game4"]["f32"], addr)
        if abs((x3 - x2) - D23) <= 0.51 and abs((x4 - x3) - D34) <= 0.51:
            results.append(("f32", addr, x2, x3, x4))

    print(f"\n=== {len(results)} candidat(s) chrono ===", flush=True)
    out = []
    for enc, addr, x2, x3, x4 in sorted(results, key=lambda r: r[1])[:30]:
        print(f"  {addr:#x} [{enc}]  {x2} -> {x3} -> {x4}", flush=True)
        out.append({"enc": enc, "addr": hex(addr), "game2": x2, "game3": x3, "game4": x4})

    # voisinages comparés pour les 5 premiers candidats (rechargement par dump)
    top = sorted(results, key=lambda r: r[1])[:5]
    if top:
        for stem in STEMS:
            regions = cached[stem]
            _m, data = load(stem)
            for enc, addr, *_ in top:
                blob = hexdump(data, regions, addr)
                if blob:
                    print(f"  [{stem}] {addr:#x} ({enc}): {blob.hex()}", flush=True)
            del data
    (BASE / "clock_candidates.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("écrit: clock_candidates.json", flush=True)


if __name__ == "__main__":
    main()
