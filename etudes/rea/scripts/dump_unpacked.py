#!/usr/bin/env python
"""dump_unpacked.py — dump la zone déchiffrée du client HotS en mémoire.

Le .text de HeroesOfTheStorm_x64.exe est chiffré sur le disque (entropie ~8) ;
le protecteur le déchiffre au lancement. Ce script copie l'image mémoire du
processus (code en clair + données) vers un fichier importable dans Ghidra —
la RE statique devient alors possible pour de vrai.

Pré-requis : le jeu lancé (le menu suffit, pas besoin de partie).
Usage : python dump_unpacked.py [PID] [--out hots_unpacked.bin]

Sécurité : lecture seule (PROCESS_VM_READ | PROCESS_QUERY_INFORMATION),
aucune injection, aucune écriture dans le processus.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import re
import struct
import subprocess
from pathlib import Path

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
DEFAULT_BASE = 0x140000000


def find_pid(name: str) -> int | None:
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}"],
                         capture_output=True).stdout.decode("latin-1")
    m = re.search(rf"{re.escape(name)}\s+(\d+)", out)
    return int(m.group(1)) if m else None


def read_mem(kernel32, handle, addr, size) -> bytes:
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size,
                                    ctypes.byref(read))
    if not ok:
        raise OSError(f"ReadProcessMemory a échoué @ {addr:#x} "
                      f"(erreur {ctypes.get_last_error()})")
    return buf.raw[: read.value]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pid", type=int, nargs="?", default=None)
    ap.add_argument("--out", type=Path, default=Path("hots_unpacked.bin"))
    ap.add_argument("--base", type=lambda s: int(s, 0), default=DEFAULT_BASE)
    args = ap.parse_args()

    pid = args.pid
    if pid is None:
        pid = find_pid("HeroesOfTheStorm_x64.exe")
        if pid is None:
            raise SystemExit("Processus HeroesOfTheStorm_x64.exe introuvable "
                             "(le jeu doit tourner).")
    print("PID:", pid)

    k32 = ctypes.windll.kernel32
    handle = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                             False, pid)
    if not handle:
        raise SystemExit(f"OpenProcess impossible (erreur {ctypes.get_last_error()}).")

    try:
        head = read_mem(k32, handle, args.base, 4096)
        if head[:2] != b"MZ":
            raise SystemExit(f"Pas de MZ @ {args.base:#x} — mauvaise base ?")
        e_lfanew = struct.unpack_from("<I", head, 0x3C)[0]
        if head[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            raise SystemExit("En-tête PE introuvable.")
        size_of_image = struct.unpack_from("<I", head, e_lfanew + 24 + 56)[0]
        print(f"image @ {args.base:#x} — SizeOfImage = {size_of_image:#x} "
              f"({size_of_image / 1e6:.1f} Mo)")

        chunk = 1 << 20
        written = 0
        with args.out.open("wb") as fh:
            for off in range(0, size_of_image, chunk):
                n = min(chunk, size_of_image - off)
                try:
                    fh.write(read_mem(k32, handle, args.base + off, n))
                    written += n
                except OSError as exc:
                    print(f"  trou @ {off:#x}: {exc} — comblé de zéros")
                    fh.write(b"\0" * n)
        print(f"écrit : {args.out.resolve()} ({written / 1e6:.1f} Mo)")
    finally:
        k32.CloseHandle(handle)


if __name__ == "__main__":
    main()
