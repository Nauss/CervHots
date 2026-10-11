#!/usr/bin/env python
"""gt_catalog.py — catalogue des triggers de jeu (gt_*_Func) dans la mémoire vive.

Le moteur Storm maintient, pour la map, un registre de triggers nommés
(gt_*_Func) dont les enregistrements contiennent l'état courant. Trois d'entre
eux ont été validés contre la vérité terrain replay :
  gt_KillLogOnHeroUnitDies_Func                  = morts héros cumulées
  gt_PlayerRegenGlobeImpactScoreTracking_Func    = globules ramassés
  gt_HeroDeathwingRespawn_Func                   = respawns
Layout vérifié : compteur u32 à (nom - 0x1C), miroir à (nom - 0x14).

Usage : python gt_catalog.py <hots_game4.heap.bin> <hots_game4.heap.json> [--out gt_catalog.json]
"""
from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

import numpy as np

PATTERN = re.compile(rb"gt_[A-Za-z0-9_]{3,60}_Func\x00")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("heap_bin", type=Path)
    ap.add_argument("heap_json", type=Path)
    ap.add_argument("--out", type=Path, default=Path("gt_catalog.json"))
    args = ap.parse_args()

    regs = json.loads(args.heap_json.read_text(encoding="utf-8"))["regions"]
    mm = np.memmap(args.heap_bin, dtype=np.uint8, mode="r")
    data = bytes(mm)
    print(f"tas : {len(data) / 1e6:.0f} Mo, {len(regs)} régions", flush=True)

    def region_of(off):
        lo, hi = 0, len(regs)
        while lo < hi:
            mid = (lo + hi) // 2
            r = regs[mid]
            if off < r["offset"]:
                hi = mid
            elif off >= r["offset"] + r["size"]:
                lo = mid + 1
            else:
                return r
        return None

    rows = []
    for m in PATTERN.finditer(data):
        off = m.start()
        name = m.group()[:-1].decode("latin-1")
        r = region_of(off)
        addr = (r["addr"] + (off - r["offset"])) if r else None
        if off < 0x20:
            continue
        rows.append({
            "name": name,
            "addr": hex(addr) if addr else None,
            "compteur": struct.unpack_from("<I", data, off - 0x1C)[0],
            "miroir": struct.unpack_from("<I", data, off - 0x14)[0],
            "flag": struct.unpack_from("<I", data, off - 0x20)[0],
        })

    rows.sort(key=lambda r: r["name"])
    args.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"{len(rows)} triggers catalogués -> {args.out.resolve()}", flush=True)

    # les plus parlants pour le coach
    mots = ("Kill", "Death", "Core", "Capture", "Objective", "Talent", "Level",
            "XP", "Globe", "Siege", "Boss", "Cavalry", "GameOver", "Timer")
    print("\n=== triggers pertinents pour le coach ===", flush=True)
    for r in rows:
        if any(k.lower() in r["name"].lower() for k in mots):
            print(f"  {r['name'][:58]:58s} {r['compteur']}", flush=True)


if __name__ == "__main__":
    main()
