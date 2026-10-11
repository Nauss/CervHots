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
LIST_MODULES_ALL = 0x03
DEFAULT_BASE = 0x140000000


def find_module(pid: int, exe_name: str):
    """Retourne (base, taille) du module exe_name dans le processus (ASLR-safe)."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    k32.OpenProcess.restype = wt.HANDLE
    psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE),
                                          wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
    psapi.GetModuleFileNameExW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]
    psapi.GetModuleInformation.argtypes = [wt.HANDLE, wt.HMODULE,
                                          ctypes.c_void_p, wt.DWORD]
    handle = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                             False, pid)
    if not handle:
        raise OSError(f"OpenProcess: {ctypes.get_last_error()}")
    try:
        arr = (wt.HMODULE * 4096)()
        needed = wt.DWORD()
        if not psapi.EnumProcessModulesEx(handle, arr,
                                          ctypes.sizeof(arr),
                                          ctypes.byref(needed),
                                          LIST_MODULES_ALL):
            raise OSError(f"EnumProcessModulesEx: {ctypes.get_last_error()}")
        n = needed.value // ctypes.sizeof(wt.HMODULE)
        for i in range(n):
            name = ctypes.create_unicode_buffer(260)
            psapi.GetModuleFileNameExW(handle, arr[i], name, 260)
            if name.value.lower().endswith(exe_name.lower()):
                info = type("MODULEINFO", (ctypes.Structure,), {
                    "_fields_": [("lpBaseOfDll", wt.LPVOID),
                                 ("SizeOfImage", wt.DWORD),
                                 ("EntryPoint", wt.LPVOID)]})()
                psapi.GetModuleInformation(handle, arr[i], ctypes.byref(info),
                                           ctypes.sizeof(info))
                return info.lpBaseOfDll, info.SizeOfImage
    finally:
        k32.CloseHandle(handle)
    return None


def dump_heap(k32, handle, out_bin, out_json, max_bytes):
    """Dump les zones privées committées (tas) — c'est là que vit l'état de jeu."""
    import json

    class MBI(ctypes.Structure):
        _fields_ = [("BaseAddress", ctypes.c_void_p),
                    ("AllocationBase", ctypes.c_void_p),
                    ("AllocationProtect", wt.DWORD),
                    ("__align", wt.DWORD),
                    ("RegionSize", ctypes.c_size_t),
                    ("State", wt.DWORD),
                    ("Protect", wt.DWORD),
                    ("Type", wt.DWORD)]

    k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p,
                                   ctypes.c_void_p, ctypes.c_size_t]
    k32.VirtualQueryEx.restype = ctypes.c_size_t

    regions, addr, total = [], 0, 0
    with out_bin.open("wb") as fh:
        while addr < 0x800000000000 and total < max_bytes:
            mbi = MBI()
            if not k32.VirtualQueryEx(handle, ctypes.c_void_p(addr),
                                      ctypes.byref(mbi), ctypes.sizeof(mbi)):
                break
            base = mbi.BaseAddress or 0
            size = mbi.RegionSize or 0x1000
            readable = (mbi.State == 0x1000 and mbi.Type == 0x20000
                        and not (mbi.Protect & 0x100)
                        and (mbi.Protect & 0xFF) != 0x01)
            if readable:
                try:
                    data = read_mem(k32, handle, base, size)
                    fh.write(data)
                    regions.append({"addr": base, "size": size,
                                    "offset": total, "protect": mbi.Protect})
                    total += len(data)
                except OSError:
                    pass
            addr = base + size
    out_json.write_text(
        json.dumps({"regions": regions, "total": total}, indent=1),
        encoding="utf-8")
    print(f"heap : {len(regions)} zones, {total / 1e6:.1f} Mo -> {out_bin.name}")


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
    ap.add_argument("--base", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--heap", action="store_true",
                    help="dump aussi les zones privées (tas) dans <out>.heap.bin")
    ap.add_argument("--heap-max", type=int, default=3 * 1024 * 1024 * 1024,
                    help="taille max du dump heap (défaut 3 Go)")
    args = ap.parse_args()

    pid = args.pid
    if pid is None:
        pid = find_pid("HeroesOfTheStorm_x64.exe")
        if pid is None:
            raise SystemExit("Processus HeroesOfTheStorm_x64.exe introuvable "
                             "(le jeu doit tourner).")
    print("PID:", pid)

    mod = find_module(pid, "HeroesOfTheStorm_x64.exe")
    if mod is None:
        raise SystemExit("Module HeroesOfTheStorm_x64.exe introuvable dans le processus.")
    base, mod_size = mod
    if args.base is not None:
        base = args.base
    print(f"base réelle : {base:#x} — taille module : {mod_size:#x}")

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    k32.OpenProcess.restype = wt.HANDLE
    k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    k32.ReadProcessMemory.restype = wt.BOOL
    k32.CloseHandle.argtypes = [wt.HANDLE]
    handle = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                             False, pid)
    if not handle:
        raise SystemExit(f"OpenProcess impossible (erreur {ctypes.get_last_error()}).")

    try:
        head = read_mem(k32, handle, base, 4096)
        if head[:2] != b"MZ":
            raise SystemExit(f"Pas de MZ @ {base:#x} — mauvaise base ?")
        e_lfanew = struct.unpack_from("<I", head, 0x3C)[0]
        if head[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            raise SystemExit("En-tête PE introuvable.")
        size_of_image = struct.unpack_from("<I", head, e_lfanew + 24 + 56)[0]
        print(f"image @ {base:#x} — SizeOfImage = {size_of_image:#x} "
              f"({size_of_image / 1e6:.1f} Mo)")

        chunk = 1 << 20
        written = 0
        with args.out.open("wb") as fh:
            for off in range(0, size_of_image, chunk):
                n = min(chunk, size_of_image - off)
                try:
                    fh.write(read_mem(k32, handle, base + off, n))
                    written += n
                except OSError as exc:
                    print(f"  trou @ {off:#x}: {exc} — comblé de zéros")
                    fh.write(b"\0" * n)
        print(f"écrit : {args.out.resolve()} ({written / 1e6:.1f} Mo)")
        if args.heap:
            dump_heap(k32, handle, args.out.with_suffix(".heap.bin"),
                      args.out.with_suffix(".heap.json"), args.heap_max)
    finally:
        k32.CloseHandle(handle)


if __name__ == "__main__":
    main()
