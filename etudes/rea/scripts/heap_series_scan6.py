#!/usr/bin/env python
"""heap_series_scan6.py — chercher les SÉRIES connues (vérité terrain) en mémoire.

Au lieu de dériver des candidats par écarts, on cherche directement les champs
dont les valeurs aux 3 captures égalent les séries réelles du replay :
  morts (8,16,21) · respawns (8,14,20) · talents (40,60,70) ·
  LevelUp (110,175,220) · globules (64,128,170) · structures (0,3,6) ·
  chrono ticks (8224,14436,21160) · compteurs de score (dégâts finaux connus).

Encodages : u32, u64 (dword haut nul). Image + tas.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

BASE = Path(r"C:\Users\Nauss\ghidra-projects")
IMAGE_BASE = 0x7FF62BD00000
STEMS = ("game2", "game3", "game4")

SERIES = {
    "morts": (8, 16, 21),
    "respawns": (8, 14, 20),
    "talents": (40, 60, 70),
    "levelup": (110, 175, 220),
    "globules": (64, 128, 170),
    "structures": (1, 3, 6),        # +1 : évite les zéros parasites
    "chrono_ticks": (8224, 14436, 21160),
    "chrono_sec": (514, 902, 1322),
}


def segments():
    man = {s: json.loads((BASE / f"hots_{s}.heap.json").read_text())["regions"]
           for s in STEMS}
    idx = {s: {r["addr"]: r for r in man[s]} for s in STEMS}
    common = sorted(set(idx["game2"]) & set(idx["game3"]) & set(idx["game4"]))
    segs = []
    for addr in common:
        r2, r3, r4 = idx["game2"][addr], idx["game3"][addr], idx["game4"][addr]
        size = min(r2["size"], r3["size"], r4["size"]) // 8 * 8
        if size >= 16:
            segs.append(("heap", addr,
                         {"game2": (r2["offset"], size),
                          "game3": (r3["offset"], size),
                          "game4": (r4["offset"], size)}))
    img = min((BASE / f"hots_{s}.bin").stat().st_size for s in STEMS) // 8 * 8
    segs.append(("img", IMAGE_BASE, {s: (0, img) for s in STEMS}))
    return segs, idx


def main():
    segs, idx = segments()
    print(f"segments : {len(segs)}", flush=True)
    mm = {("heap", s): np.memmap(BASE / f"hots_{s}.heap.bin", dtype=np.uint8, mode="r")
          for s in STEMS}
    mm.update({("img", s): np.memmap(BASE / f"hots_{s}.bin", dtype=np.uint8, mode="r")
               for s in STEMS})

    hits = []
    for n, (kind, addr, spec) in enumerate(segs):
        views = {s: mm[(kind, s)][spec[s][0]:spec[s][0] + spec[s][1]] for s in STEMS}
        for shift, width in ((0, "<u4"), (0, "<u8"), (4, "<u4")):
            arrs = {s: np.frombuffer(views[s][shift:], dtype=width)
                    for s in STEMS}
            ln = min(len(a) for a in arrs.values())
            a2, a3, a4 = (arrs[s][:ln] for s in STEMS)
            for name, (v2, v3, v4) in SERIES.items():
                if width == "<u8":
                    mask = (a2 == v2) & (a3 == v3) & (a4 == v4)
                else:
                    mask = (a2 == v2) & (a3 == v3) & (a4 == v4)
                for pos in np.nonzero(mask)[0].tolist():
                    hits.append((name, addr + shift + pos * (8 if width == "<u8" else 4),
                                 width, int(a2[pos])))
        if n % 3000 == 0:
            print(f"   … {n}/{len(segs)}, {len(hits)} hits", flush=True)

    print(f"\n=== {len(hits)} hit(s) ===", flush=True)
    by_name = {}
    for name, addr, width, v in hits:
        by_name.setdefault(name, []).append((addr, width))
    for name, lst in sorted(by_name.items()):
        print(f"  {name:14s} {len(lst)} adresse(s)", flush=True)
        for addr, width in lst[:15]:
            print(f"      {addr:#x}  [{width}]", flush=True)

    (BASE / "series_candidates.json").write_text(json.dumps(
        {k: [{"addr": hex(a), "enc": w} for a, w in v] for k, v in by_name.items()},
        indent=1), encoding="utf-8")
    print("écrit: series_candidates.json", flush=True)


if __name__ == "__main__":
    main()
