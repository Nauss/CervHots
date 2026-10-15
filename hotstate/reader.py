#!/usr/bin/env python
"""hotstate/reader.py — lecteur LIVE de l'état de jeu (triggers gt_*).

Lit, en lecture seule, les enregistrements de triggers du moteur Storm dans la
mémoire du processus (ou dans un dump, pour les tests) et produit un instantané
au format du contrat hotstate. Voir etudes/rea/ETUDE.md §13.

Sources : les enregistrements nommés `gt_<nom>_Func\0` dans les zones privées
(tas) du processus ; l'état est à `nom-28` (compteur) / `nom-20` (miroir).
Le mapping nom -> champ vient de `triggers_map.json`.

Usage :
  # hors-ligne (tests sur dumps) :
  python reader.py --dump hots_game4.heap.bin hots_game4.heap.json

  # en direct (le jeu tourne) :
  python reader.py --live [--out game_state.json]

Sécurité : lecture seule (PROCESS_VM_READ | PROCESS_QUERY_INFORMATION),
aucune écriture, aucune injection.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import datetime as dt
import json
import re
import struct
from pathlib import Path

PATTERN = re.compile(rb"gt_[A-Za-z0-9_]{3,60}_Func\x00")
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


# --------------------------------------------------------------- backends

class DumpBackend:
    """Lit un dump de tas (hots_gameN.heap.bin/.heap.json)."""

    def __init__(self, heap_bin: Path, heap_json: Path):
        self.regions = json.loads(heap_json.read_text(encoding="utf-8"))["regions"]
        self.data = heap_bin.read_bytes()

    def regions_bytes(self):
        for r in self.regions:
            yield r["addr"], self.data[r["offset"]:r["offset"] + r["size"]]


class ProcessBackend:
    """Lit directement la mémoire du processus (en direct)."""

    def __init__(self, pid: int | None = None, exe_name="HeroesOfTheStorm_x64.exe"):
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        k32.OpenProcess.restype = wt.HANDLE
        k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p,
                                          ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.POINTER(ctypes.c_size_t)]
        k32.ReadProcessMemory.restype = wt.BOOL
        k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p,
                                       ctypes.c_void_p, ctypes.c_size_t]
        k32.VirtualQueryEx.restype = ctypes.c_size_t
        self.k32 = k32
        if pid is None:
            pid = self._find_pid(exe_name)
            if pid is None:
                raise SystemExit(f"processus {exe_name} introuvable")
        self.pid = pid
        self.handle = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                                      False, pid)
        if not self.handle:
            raise SystemExit(f"OpenProcess impossible ({ctypes.get_last_error()})")

    @staticmethod
    def _find_pid(name):
        import subprocess
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}"],
                             check=False, capture_output=True).stdout.decode("latin-1")
        m = re.search(rf"{re.escape(name)}\s+(\d+)", out)
        return int(m.group(1)) if m else None

    def _read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        if not self.k32.ReadProcessMemory(self.handle, ctypes.c_void_p(addr),
                                          buf, size, ctypes.byref(got)):
            return None
        return buf.raw[: got.value]

    def regions_bytes(self):
        class MBI(ctypes.Structure):
            _fields_ = [("BaseAddress", ctypes.c_void_p),
                        ("AllocationBase", ctypes.c_void_p),
                        ("AllocationProtect", wt.DWORD),
                        ("__align", wt.DWORD),
                        ("RegionSize", ctypes.c_size_t),
                        ("State", wt.DWORD),
                        ("Protect", wt.DWORD),
                        ("Type", wt.DWORD)]
        addr, total = 0, 0
        while addr < 0x800000000000 and total < 4 * 1024 ** 3:
            mbi = MBI()
            if not self.k32.VirtualQueryEx(self.handle, ctypes.c_void_p(addr),
                                           ctypes.byref(mbi), ctypes.sizeof(mbi)):
                break
            base = mbi.BaseAddress or 0
            size = mbi.RegionSize or 0x1000
            if (mbi.State == 0x1000 and mbi.Type == 0x20000
                    and not (mbi.Protect & 0x100) and (mbi.Protect & 0xFF) != 0x01):
                data = self._read(base, size)
                if data:
                    total += len(data)
                    yield base, data
            addr = base + size


# --------------------------------------------------------------- extraction

def scan_triggers(backend, wanted: dict):
    """Cherche les enregistrements gt_* et extrait les états demandés."""
    found = {}
    for base, data in backend.regions_bytes():
        for m in PATTERN.finditer(data):
            name = m.group()[:-1].decode("latin-1")
            if name not in wanted:
                continue
            off = m.start()
            if off < 0x20:
                continue
            rec = {
                "addr": base + off,
                "flag": struct.unpack_from("<I", data, off - 32)[0],
                "compteur": struct.unpack_from("<I", data, off - 28)[0],
                "m24": struct.unpack_from("<I", data, off - 24)[0],
                "m20": struct.unpack_from("<I", data, off - 20)[0],
            }
            # signature du record vivant (validée sur 3 compteurs x 3 dumps) :
            # flag 1 à nom-32 ; compteur à nom-28 ; miroir en nom-24 OU nom-20
            # (l'autre vaut 0). Les records de gabarit ont flag != 1.
            s1, s2, s3 = rec["compteur"], rec["m24"], rec["m20"]
            rec["vivant"] = (rec["flag"] == 1
                             and ((s2 == s1 and s3 == 0) or (s3 == s1 and s2 == 0)))
            rec["miroir"] = s2 or s3
            found.setdefault(name, []).append(rec)
    return found


def snapshot(backend, mapping: dict, debug: bool = False) -> dict:
    triggers = mapping["triggers"]
    found = scan_triggers(backend, triggers)
    state = {
        "meta": {
            "source": "live" if isinstance(backend, ProcessBackend) else "dump",
            "t": dt.datetime.now().isoformat(timespec="seconds"),
        },
        "stats": {},
    }
    if debug:
        state["triggers_bruts"] = {}
    for name, spec in triggers.items():
        recs = found.get(name, [])
        if debug:
            state["triggers_bruts"][name] = recs
        if not recs:
            continue
        vivants = [r for r in recs if r["vivant"]]
        if not vivants:
            continue  # Une sentinelle de gabarit n'est jamais une observation de jeu.
        off = spec.get("offset_fiable", -28)
        vals = [r["compteur"] if off == -28 else r["miroir"] for r in vivants]
        state["stats"][spec["field"]] = max(vals)
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", nargs=2, metavar=("HEAP_BIN", "HEAP_JSON"))
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--map", type=Path,
                    default=Path(__file__).parent / "triggers_map.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--debug", action="store_true",
                    help="ajoute la trace des instances (triggers_bruts)")
    args = ap.parse_args()

    mapping = json.loads(args.map.read_text(encoding="utf-8"))
    if args.dump:
        backend = DumpBackend(Path(args.dump[0]), Path(args.dump[1]))
    elif args.live:
        backend = ProcessBackend(args.pid)
    else:
        raise SystemExit("--dump HEAP BIN JSON ou --live")

    state = snapshot(backend, mapping, debug=args.debug)
    text = json.dumps(state, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"écrit : {args.out.resolve()}")
    print(f"source : {state['meta']['source']}  ({state['meta']['t']})")
    for field, value in state["stats"].items():
        print(f"  {field:24s} = {value}")
    missing = [n for n in mapping["triggers"] if n not in state.get("triggers_bruts", {})
               or not state["triggers_bruts"][n]]
    if args.debug and missing:
        print("triggers introuvables :", ", ".join(missing))


if __name__ == "__main__":
    main()
