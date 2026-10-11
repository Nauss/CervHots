#!/usr/bin/env python
"""anchors_offline.py — chasse aux ancres RTTI sur le PE brut (sans Ghidra).

Dans un PE, les pointeurs de vtable et les RVA du CompleteObjectLocator sont
stockés tels quels (base préférée 0x140000000) : on peut donc trouver les
vtables et leurs méthodes directement dans le fichier, avant toute analyse.

Sortie : anchors_offline.json — {classe: {col, vtable, methods[VA], ...}}
Usage : python anchors_offline.py <HeroesOfTheStorm_x64.exe> [--out anchors.json]
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

CLASSES = [
    "CTimerFrame", "CTimerWindow",
    "CUnitStatusHealth", "CUnitStatusHealthLabel", "CUnitStatusShieldedHealthBar",
    "CTeamHeroLevelFrame", "CPlayerHeroLevelFrame", "CUnitStatusLevel",
    "CPlayerDeathIndicatorFrame",
    "CHeroState",
    "CMinimap", "CMinimapUnitStatusPanel",
    "CGameStatsPanel", "CPlayerScoreResultFrame",
]


class PE:
    def __init__(self, path: Path):
        self.data = path.read_bytes()
        e_lfanew = struct.unpack_from("<I", self.data, 0x3C)[0]
        assert self.data[e_lfanew:e_lfanew + 4] == b"PE\0\0"
        nsec = struct.unpack_from("<H", self.data, e_lfanew + 6)[0]
        opt_size = struct.unpack_from("<H", self.data, e_lfanew + 20)[0]
        self.image_base = struct.unpack_from("<Q", self.data, e_lfanew + 24 + 24)[0]
        self.sections = []
        off = e_lfanew + 24 + opt_size
        for i in range(nsec):
            s = off + i * 40
            name = self.data[s:s + 8].rstrip(b"\0").decode("ascii", "replace")
            vsize, va, rsize, raw = struct.unpack_from("<IIII", self.data, s + 8)
            self.sections.append((name, va, vsize, raw, rsize))

    def rva2off(self, rva: int) -> int | None:
        for _n, va, vsize, raw, rsize in self.sections:
            if va <= rva < va + max(vsize, rsize):
                return raw + (rva - va)
        return None

    def off2va(self, off: int) -> int | None:
        for _n, va, vsize, raw, rsize in self.sections:
            if raw <= off < raw + rsize:
                return self.image_base + va + (off - raw)
        return None

    def text_va_range(self):
        for n, va, _vs, _r, _rs in self.sections:
            if n == ".text":
                return self.image_base + va, self.image_base + va + _vs
        return 0, 0


def find_all(data: bytes, needle: bytes, limit: int = 50):
    out, i = [], 0
    while len(out) < limit:
        j = data.find(needle, i)
        if j < 0:
            break
        out.append(j)
        i = j + 1
    return out


def hunt(pe: PE, cls: str) -> dict:
    data = pe.data
    name = (".?AV%s@@" % cls).encode("ascii")
    hits = find_all(data, name, limit=4)
    if not hits:
        return {"error": "chaine RTTI absente"}
    out = {"string_off": hex(hits[0])}
    td_va = pe.off2va(hits[0]) - 16   # TypeDescriptor = pVFTable + spare (2×8 octets)
    rva_td = td_va - pe.image_base
    out["typedesc_va"] = hex(td_va)

    needle = struct.pack("<I", rva_td)
    col_va = None
    for hit in find_all(data, needle, limit=200):
        col = hit - 12
        if col < 0:
            continue
        sig, off, cd, rva_chd = struct.unpack_from("<IIII", data, col)
        if sig == 1 and off < 0x10000 and cd < 0x10000 and 0 < rva_chd < 0x20000000:
            col_va = pe.off2va(col)
            out["col_va"] = hex(col_va)
            break
    if col_va is None:
        out["error"] = "CompleteObjectLocator introuvable"
        return out

    # vtable : le pointeur 8 octets vers la COL précède les pointeurs de méthodes
    needle8 = struct.pack("<Q", col_va)
    lo, hi = pe.text_va_range()
    for hit in find_all(data, needle8, limit=20):
        methods = []
        cursor = hit + 8
        while True:
            val = struct.unpack_from("<Q", data, cursor)[0]
            if not (lo <= val < hi):
                break
            methods.append(hex(val))
            cursor += 8
            if len(methods) >= 48:
                break
        if methods:
            out["vtable_col_ptr_off"] = hex(hit)
            out["first_method_va"] = hex(struct.unpack_from("<Q", data, hit + 8)[0])
            out["methods"] = methods
            break
    if "methods" not in out:
        out["error"] = "vtable introuvable"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--out", type=Path, default=Path("anchors_offline.json"))
    args = ap.parse_args()

    pe = PE(args.exe)
    print("image base:", hex(pe.image_base), "| sections:",
          [(n, hex(va)) for n, va, *_ in pe.sections[:8]])
    results = {}
    for cls in CLASSES:
        results[cls] = hunt(pe, cls)
        r = results[cls]
        summary = r.get("error") or ("vtable %s, %d méthodes" % (r.get("first_method_va"), len(r.get("methods", []))))
        print("%-32s %s" % (cls, summary))
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("écrit:", args.out.resolve())


if __name__ == "__main__":
    main()
