#!/usr/bin/env python
"""heap_clock_scan.py — trouve le chrono de jeu dans les dumps de tas.

Principe (value scanning classique) : on connaît l'instant de chaque capture
depuis le replay (vérité terrain). Toute valeur mémoire qui « suit » le chrono
(527 s @ dump2, 909 s @ dump3, 1336 s @ dump4) doit passer par ces valeurs dans
les trois dumps, à la même adresse. On cherche donc les adresses communes.

Encodages testés : entiers secondes, ticks 1/16 s (boucles de jeu), ms,
float32 secondes. Sortie : candidats + contexte mémoire autour.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

BASE = Path(r"C:\Users\Nauss\ghidra-projects")

# instants de capture (s depuis le début de partie) — calés sur le replay
# (début = 19:16:31 - 1321 s = 18:54:30 ; captures à 19:03:17 / 19:09:39 / 19:16:46)
TIMES = {"game2": 527, "game3": 909, "game4": 1336}


def load(stem: str):
    manifest = json.loads((BASE / f"hots_{stem}.heap.json").read_text(encoding="utf-8"))
    data = (BASE / f"hots_{stem}.heap.bin").read_bytes()
    return manifest["regions"], data


def variants(t: int):
    out = {}
    for v in range(t - 3, t + 4):
        out[f"int:{v}"] = struct.pack("<I", v)
    for k in range(-3, 4):
        v = (t + k) * 16
        out[f"tick16:{v}"] = struct.pack("<I", v)
    for k in range(-3, 4):
        v = (t + k) * 1000
        out[f"ms:{v}"] = struct.pack("<I", v)
    for k in (-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0):
        out[f"f32:{t + k}"] = struct.pack("<f", t + k)
    return out


def find_all(data: bytes, needle: bytes, limit: int = 400):
    res, i = [], 0
    while len(res) < limit:
        j = data.find(needle, i)
        if j < 0:
            break
        res.append(j)
        i = j + 4
    return res


def addr_map(regions, off: int):
    # recherche binaire simple sur les offsets cumulés
    lo, hi = 0, len(regions)
    while lo < hi:
        mid = (lo + hi) // 2
        r = regions[mid]
        if off < r["offset"]:
            hi = mid
        elif off >= r["offset"] + r["size"]:
            lo = mid + 1
        else:
            return r["addr"] + (off - r["offset"])
    return None


def scan(stem: str):
    regions, data = load(stem)
    t = TIMES[stem]
    hits = {}
    for name, pat in variants(t).items():
        for off in find_all(data, pat):
            addr = addr_map(regions, off)
            if addr is not None:
                hits.setdefault(name, set()).add(addr)
    return hits


print("scan des trois dumps…")
h2, h3, h4 = scan("game2"), scan("game3"), scan("game4")

common = {}
for name2, a2 in h2.items():
    for name3, a3 in h3.items():
        for name4, a4 in h4.items():
            if name2.split(":")[0] != name3.split(":")[0] or name3.split(":")[0] != name4.split(":")[0]:
                continue
            inter = a2 & a3 & a4
            for addr in inter:
                common.setdefault(addr, set()).update([name2, name3, name4])

print("adresses communes aux 3 dumps :", len(common))
for addr, names in sorted(common.items())[:25]:
    print(f"   {addr:#x}  {sorted(names)}")

out = {hex(a): sorted(n) for a, n in common.items()}
(BASE / "clock_candidates.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("écrit: clock_candidates.json")
