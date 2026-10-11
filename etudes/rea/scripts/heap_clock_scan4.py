#!/usr/bin/env python
"""heap_clock_scan4.py — chrono de jeu par comparaison vectorisée par région.

Le tas de jeu est plein de petites valeurs (600 M+ de « candidats » par plage) :
les dictionnaires ne passent pas. Ici, pour chaque région présente dans les
3 dumps (même adresse, même taille), on compare les u32/f32 **élément par
élément** et on garde les positions où :
    v3 == v2 + 382*k   et   v4 == v3 + 427*k   (k = 1, 16, 1000 — secondes,
    ticks 1/16 s, ms)  ou l'équivalent float32 (±0,5).
Mémoire : fichiers en mmap, zéro copie.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

BASE = Path(r"C:\Users\Nauss\ghidra-projects")
D23, D34 = 382, 427
STEMS = ("game2", "game3", "game4")


def load_manifest(stem):
    return json.loads((BASE / f"hots_{stem}.heap.json").read_text(encoding="utf-8"))["regions"]


def main():
    man = {s: load_manifest(s) for s in STEMS}
    mm = {s: np.memmap(BASE / f"hots_{s}.heap.bin", dtype=np.uint8, mode="r")
          for s in STEMS}
    idx = {s: {r["addr"]: r for r in man[s]} for s in STEMS}

    addrs = sorted(set(idx["game2"]) & set(idx["game3"]) & set(idx["game4"]))
    print(f"régions communes aux 3 dumps : {len(addrs)}", flush=True)

    results = []
    for n, addr in enumerate(addrs):
        r2, r3, r4 = idx["game2"][addr], idx["game3"][addr], idx["game4"][addr]
        size = min(r2["size"], r3["size"], r4["size"]) // 4 * 4
        if size < 8:
            continue
        a2 = mm["game2"][r2["offset"]:r2["offset"] + size]
        a3 = mm["game3"][r3["offset"]:r3["offset"] + size]
        a4 = mm["game4"][r4["offset"]:r4["offset"] + size]
        u2 = np.frombuffer(a2, dtype="<u4")
        u3 = np.frombuffer(a3, dtype="<u4")
        u4 = np.frombuffer(a4, dtype="<u4")
        for k, enc in ((1, "sec"), (16, "tick16"), (1000, "ms")):
            mask = (u3 == u2 + D23 * k) & (u4 == u3 + D34 * k)
            for pos in np.nonzero(mask)[0].tolist():
                results.append((enc, addr + pos * 4,
                                int(u2[pos]), int(u3[pos]), int(u4[pos])))
        f2 = np.frombuffer(a2, dtype="<f4")
        f3 = np.frombuffer(a3, dtype="<f4")
        f4 = np.frombuffer(a4, dtype="<f4")
        mask = ((np.abs((f3 - f2) - D23) <= 0.51)
                & (np.abs((f4 - f3) - D34) <= 0.51)
                & np.isfinite(f2) & np.isfinite(f3) & np.isfinite(f4))
        for pos in np.nonzero(mask)[0].tolist():
            results.append(("f32", addr + pos * 4,
                            float(f2[pos]), float(f3[pos]), float(f4[pos])))
        if n % 2000 == 0:
            print(f"   … {n}/{len(addrs)} régions, {len(results)} candidats",
                  flush=True)

    print(f"\n=== {len(results)} candidat(s) chrono ===", flush=True)
    results.sort(key=lambda r: r[1])
    for enc, addr, x2, x3, x4 in results[:40]:
        print(f"  {addr:#x} [{enc}]  {x2} -> {x3} -> {x4}", flush=True)

    out = [{"enc": e, "addr": hex(a), "game2": v2, "game3": v3, "game4": v4}
           for e, a, v2, v3, v4 in results]
    (BASE / "clock_candidates.json").write_text(json.dumps(out, indent=1),
                                                encoding="utf-8")

    # voisinages comparés (±128 octets) pour les 8 premiers candidats
    for enc, addr, *_ in results[:8]:
        print(f"\n--- voisinage {addr:#x} ({enc}) ---", flush=True)
        for stem in STEMS:
            r = idx[stem][addr]
            off = r["offset"] + (addr - r["addr"])
            lo = max(r["offset"], off - 128)
            hi = min(r["offset"] + r["size"], off + 128)
            blob = bytes(mm[stem][lo:hi])
            print(f"  [{stem}] {blob.hex()}", flush=True)
    print("écrit: clock_candidates.json", flush=True)


if __name__ == "__main__":
    main()
