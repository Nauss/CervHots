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
import bisect
import ctypes
import ctypes.wintypes as wt
import datetime as dt
import json
import mmap
import re
import struct
from pathlib import Path

PATTERN = re.compile(rb"gt_[A-Za-z0-9_]{3,60}_Func\x00")
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
VALIDATED_FIELDS = {"deaths_total", "respawns_total", "globes_total"}


# --------------------------------------------------------------- backends

class DumpBackend:
    """Lit un dump de tas (hots_gameN.heap.bin/.heap.json)."""

    recorded_non_atomic = True

    def __init__(self, heap_bin: Path, heap_json: Path, *, image: Path | None = None,
                 module_base: int | None = None):
        self.regions = sorted(json.loads(heap_json.read_text(encoding="utf-8"))["regions"],
                              key=lambda r: r["addr"])
        self.starts = [r["addr"] for r in self.regions]
        self.stream = heap_bin.open("rb")
        self.data = mmap.mmap(self.stream.fileno(), 0, access=mmap.ACCESS_READ) if heap_bin.stat().st_size else b""
        self.image = image.read_bytes() if image is not None else None
        self.module_base = module_base
        if self.image is not None and self.module_base is None:
            from hotstate.native import module_base_from_image
            try:
                self.module_base = module_base_from_image(self.image)
            except ValueError:
                self.close()
                raise

    def close(self):
        if isinstance(self.data, mmap.mmap):
            self.data.close()
        self.data = b""
        self.stream.close()

    def read_memory(self, address, size):
        if (self.image is not None and self.module_base is not None
                and self.module_base <= address
                and address + size <= self.module_base + len(self.image)):
            offset = address - self.module_base
            return self.image[offset:offset + size]
        chunks = []
        while size > 0:
            index = bisect.bisect_right(self.starts, address) - 1
            if index < 0:
                return None
            region = self.regions[index]
            available = region["addr"] + region["size"] - address
            if available <= 0:
                return None
            count = min(size, available)
            offset = region["offset"] + address - region["addr"]
            chunk = self.data[offset:offset + count]
            if len(chunk) != count:
                return None
            chunks.append(chunk)
            address, size = address + count, size - count
        return b"".join(chunks)

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
        k32.CloseHandle.argtypes = [wt.HANDLE]
        k32.CloseHandle.restype = wt.BOOL
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
        self.module_base, self.module_size = self._module_info(exe_name)

    def _module_info(self, exe_name):
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE),
                                               wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
        psapi.EnumProcessModulesEx.restype = wt.BOOL
        psapi.GetModuleFileNameExW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]
        psapi.GetModuleFileNameExW.restype = wt.DWORD
        psapi.GetModuleInformation.argtypes = [wt.HANDLE, wt.HMODULE, ctypes.c_void_p, wt.DWORD]
        psapi.GetModuleInformation.restype = wt.BOOL

        class ModuleInfo(ctypes.Structure):
            _fields_ = [("base", wt.LPVOID), ("size", wt.DWORD), ("entry", wt.LPVOID)]

        modules, needed = (wt.HMODULE * 4096)(), wt.DWORD()
        if not psapi.EnumProcessModulesEx(self.handle, modules, ctypes.sizeof(modules),
                                          ctypes.byref(needed), 3):
            return None, 0
        for index in range(min(len(modules), needed.value // ctypes.sizeof(wt.HMODULE))):
            name = ctypes.create_unicode_buffer(32768)
            if not psapi.GetModuleFileNameExW(self.handle, modules[index], name, len(name)):
                continue
            if Path(name.value).name.casefold() != exe_name.casefold():
                continue
            info = ModuleInfo()
            if psapi.GetModuleInformation(self.handle, modules[index], ctypes.byref(info),
                                           ctypes.sizeof(info)):
                return info.base, info.size
        return None, 0

    def close(self):
        if self.handle:
            self.k32.CloseHandle(self.handle)
            self.handle = None

    def read_memory(self, address, size):
        return self._read(address, size)

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

def scan_triggers(backend, wanted: dict, *, observe_region=None):
    """Cherche les enregistrements gt_* et extrait les états demandés."""
    found = {}
    for base, data in backend.regions_bytes():
        if observe_region is not None:
            observe_region(base, data)
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


def snapshot(backend, mapping: dict, debug: bool = False, *, context=None) -> dict:
    triggers = mapping["triggers"]
    if context is not None:
        context.begin()
    found = scan_triggers(backend, triggers,
                          observe_region=context.feed if context is not None else None)
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
        if spec["field"] not in VALIDATED_FIELDS:
            continue  # Un compteur d'appels expérimental n'est pas un état d'objectif.
        if not recs:
            continue
        vivants = [r for r in recs if r["vivant"]]
        if not vivants:
            continue  # Une sentinelle de gabarit n'est jamais une observation de jeu.
        off = spec.get("offset_fiable", -28)
        vals = [r["compteur"] if off == -28 else r["miroir"] for r in vivants]
        state["stats"][spec["field"]] = max(vals)
    if context is not None:
        extra = context.finish()
        state["meta"].update({k: v for k, v in extra.get("meta", {}).items()
                              if k in ("map", "map_id", "match_id", "context_source")})
        state.update({k: v for k, v in extra.items()
                      if k in ("players", "local_player", "composition_complete")})
        if isinstance(context.reason, str):
            state["meta"]["context_status"] = context.reason
    if getattr(backend, "module_base", None) is not None:
        from hotstate.native import NativeReader, NativeUnavailable
        if "local_player" not in state:
            state["meta"]["native_status"] = "contexte_requis"
        else:
            try:
                native = NativeReader(backend).read_state(state)
            except NativeUnavailable as exc:
                state["meta"]["native_status"] = str(exc)
            else:
                state["meta"].update(native["meta"])
                state.update({k: v for k, v in native.items() if k != "meta"})
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", nargs=2, metavar=("HEAP_BIN", "HEAP_JSON"))
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--player", help="joueur local pour identifier le contexte initData")
    ap.add_argument("--image", type=Path, help="module capturé avec le dump, pour les champs natifs")
    ap.add_argument("--map", type=Path,
                    default=Path(__file__).parent / "triggers_map.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--debug", action="store_true",
                    help="ajoute la trace des instances (triggers_bruts)")
    args = ap.parse_args()
    if args.image is not None and not args.dump:
        ap.error("--image nécessite --dump")

    mapping = json.loads(args.map.read_text(encoding="utf-8"))
    from hotstate.context import make_probe
    context = make_probe(args.player, live=args.live and not args.dump)
    if args.dump:
        backend = DumpBackend(Path(args.dump[0]), Path(args.dump[1]), image=args.image)
    elif args.live:
        backend = ProcessBackend(args.pid)
    else:
        raise SystemExit("--dump HEAP BIN JSON ou --live")

    try:
        state = snapshot(backend, mapping, debug=args.debug, context=context)
    finally:
        backend.close()
    text = json.dumps(state, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"écrit : {args.out.resolve()}")
    print(f"source : {state['meta']['source']}  ({state['meta']['t']})")
    for field, value in state["stats"].items():
        print(f"  {field:24s} = {value}")
    if "native_status" in state["meta"]:
        print("natif :", state["meta"]["native_status"])
    if "heroes" in state:
        print("horloge de mission (préparation incluse) :", state["meta"]["t_s"], "s")
        for hero in state["heroes"]:
            print(f"  {hero['hero']:18s} équipe {hero['team']} niveau {hero['level']} vivant={hero['alive']}")
    missing = [n for n in mapping["triggers"] if n not in state.get("triggers_bruts", {})
               or not state["triggers_bruts"][n]]
    if args.debug and missing:
        print("triggers introuvables :", ", ".join(missing))


if __name__ == "__main__":
    main()
