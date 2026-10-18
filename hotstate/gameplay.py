"""HUD clock from the active Galaxy VM, strictly limited to build 98348.

No heap/name scan, client call, mission-time subtraction, or wall-time
extrapolation. The compiler's unowned metadata copies are not used. Saved
rolling dumps can be inspected explicitly, never published as synchronized.
"""
from __future__ import annotations

import hashlib
import json
import struct
import time
from pathlib import Path

from .native import NativeUnavailable

MAX_WINDOW_S = 0.125
FIXED = 4096
GLOBAL_DATA = 0x3D0C920
GAME_TIMER = 0xC988
GATES_TIMER = 0x19E67
GAME_STARTED = 0x19E77
DEBUG_DELTA = 0x10E56F


class GameplayClock:
    def __init__(self, native, *, profile=None):
        self.native = native
        self.profile = profile if profile is not None else json.loads(
            (Path(__file__).parent / "profiles/98348-clock.json").read_text(encoding="utf-8"))

    def _verify_code(self):
        n, p = self.native, self.profile
        read_set = []

        def read(address, size):
            data = n.read(address, size)
            read_set.append((address, data))
            return data

        def value(address):
            return struct.unpack('<I', read(address, 4))[0]

        pe = n.base + value(n.base + 0x3C)
        if (p.get("build") != 98348 or n.profile.get("build") != 98348
                or value(pe + 8) != p["pe_timestamp"]
                or value(pe + 24 + 56) != p["image_size"]
                or not p.get("signatures") or len(p.get("functions", [])) != 3):
            raise NativeUnavailable("profil_chrono_non_pris_en_charge")
        for signature in p["signatures"]:
            code = read(n.base + signature["rva"], signature["size"])
            if hashlib.sha256(code).hexdigest() != signature["sha256"]:
                raise NativeUnavailable("signature_chrono_invalide")
        return read_set

    @staticmethod
    def _pointer(pointer):
        if not 0x10000 <= pointer < 0x800000000000 or pointer % 8:
            raise NativeUnavailable("pointeur_chrono_invalide")
        return pointer

    def _sample(self):
        n = self.native
        read_set = []

        def read(address, size):
            data = n.read(address, size)
            read_set.append((address, data))
            return data

        def value(address, fmt="I"):
            return struct.unpack("<" + fmt, read(address, struct.calcsize("<" + fmt)))[0]

        if value(n.base + 0x35C8CD9, "B") != 1:
            raise NativeUnavailable("aucune_simulation_active")
        count = value(n.base + 0x2FA70F0)
        table = self._pointer(value(n.base + 0x3B8C5C8, "Q"))
        code_size = value(n.base + 0x3B8C904)
        if (not 4217 < count <= 65536 or not 4 <= code_size <= 0x180000
                or value(n.base + 0x2FA7100, "Q") != table):
            raise NativeUnavailable("racine_vm_chrono_invalide")
        for spec in self.profile["functions"]:
            index = spec["index"]
            if not 0 <= index < count:
                raise NativeUnavailable("index_vm_chrono_invalide")
            record = self._pointer(value(table + index * 8, "Q"))
            offset = value(record + 8)
            if (value(record + 0x50) != index or offset < 4
                    or offset + spec["length"] > code_size):
                raise NativeUnavailable("borne_vm_chrono_invalide")
            length, flags = struct.unpack("<II", read(record + 0x58, 8))
            if length >> 2 != len(spec["name"]):
                raise NativeUnavailable("nom_vm_chrono_invalide")
            string = self._pointer(value(record + 0x60, "Q")) if flags & 2 else record + 0x60
            if read(string, length >> 2) != spec["name"].encode("ascii"):
                raise NativeUnavailable("nom_vm_chrono_invalide")
            code = read(n.base + 0x3B8C920 + offset, spec["length"])
            if hashlib.sha256(code).hexdigest() != spec["sha256"]:
                raise NativeUnavailable("script_vm_chrono_invalide")
        # The exact bytecode fingerprints prove these operands in the active VM:
        # HeroesGameTime: ref-global gates -> remaining; otherwise game elapsed
        # + call(4217)*fixed(60). DebugGameTimeDelta: fixed global 0x10e56f.
        # GatesOpen writes byte global 0x19e77 before TimerStart(game, -1, game).
        started = value(n.base + GLOBAL_DATA + GAME_STARTED, "B")
        if started not in (0, 1):
            raise NativeUnavailable("phase_chrono_invalide")
        delta = value(n.base + GLOBAL_DATA + DEBUG_DELTA, "i")
        slots = value(n.base + 0x4020970, "Q")
        # This build's registry has all 65536 ushort-indexed 16-byte slots in
        # the image. Its live pointer must designate that registry, not a copy.
        if slots != n.base + 0x4020980:
            raise NativeUnavailable("registre_timers_chrono_invalide")
        timer_count = value(n.base + 0x2F72670)
        if not 2 <= timer_count <= 8192:
            raise NativeUnavailable("nombre_timers_chrono_hors_budget")
        timer_list = self._pointer(value(n.base + 0x2F72680, "Q"))
        registered = struct.unpack("<" + "I" * timer_count, read(timer_list, timer_count * 4))

        def timer(global_offset):
            reference = value(n.base + GLOBAL_DATA + global_offset)
            index, generation = reference & 65535, reference >> 16
            if index <= 1 or generation == 0 or registered.count(reference) != 1:
                raise NativeUnavailable("reference_timer_chrono_invalide")
            slot = read(slots + index * 16, 16)
            gen, _, refs, kind, _, pointer = struct.unpack("<HHHBBQ", slot)
            if gen != generation or kind != 19 or refs == 0:
                raise NativeUnavailable("generation_ou_type_timer_chrono_invalide")
            pointer = self._pointer(pointer)
            data = read(pointer, 40)
            vtable, owner = struct.unpack_from("<QI", data)
            repeat, paused, expired, reserved = data[16:20]
            clock, elapsed, deadline = struct.unpack_from("<Iii", data, 20)
            if (vtable != n.base + 0x26B4F18 or owner != reference
                    or any(flag not in (0, 1) for flag in (repeat, paused, expired))
                    or repeat or reserved or clock not in (0, 1, 2)
                    or not 0 <= elapsed <= 21600 * FIXED):
                raise NativeUnavailable("objet_timer_chrono_invalide")
            return clock, elapsed, deadline, paused, expired

        game, gates = timer(GAME_TIMER), timer(GATES_TIMER)
        clock, elapsed, deadline, paused, expired = gates
        remaining = deadline - elapsed
        if remaining > 0:
            if (started or clock != 0 or expired or not 0 < deadline <= 600 * FIXED
                    or game[1] != 0 or game[2] != 0):
                raise NativeUnavailable("preparation_chrono_incoherente")
            ticks, phase = -remaining, "preparation"
        else:
            clock, elapsed, deadline, paused, expired = game
            if (not started or clock != 0 or deadline != -FIXED or expired
                    or gates[0] != 0 or not 0 < gates[2] <= 600 * FIXED
                    or not gates[2] <= gates[1] <= gates[2] + FIXED or gates[4] != 1):
                raise NativeUnavailable("debut_gameplay_non_prouve")
            ticks, phase = elapsed + delta * 60, "playing"
        if not -3600 * FIXED <= ticks <= 21600 * FIXED:
            raise NativeUnavailable("temps_gameplay_hors_bornes")
        return {"t_s": ticks / FIXED, "phase": phase, "timer_paused": bool(paused)}, read_set

    def inspect_saved(self):
        """Offline structural evidence only; no temporal-validity claim."""
        self._verify_code()
        sample, _ = self._sample()
        return dict(sample, status="offline_non_atomic")

    def read(self):
        n = self.native
        if getattr(n.memory, "recorded_non_atomic", False):
            raise NativeUnavailable("capture_chrono_non_atomique")
        started_wall = time.monotonic()
        started_mission = n.read_clock()
        code_reads = self._verify_code()
        sample, read_set = self._sample()
        # Exact second pass: changes in roots, code, generations, globals or
        # timer bytes reject the whole clock, even if the displayed integer is
        # unchanged. No retries hide an intervening match/phase transition.
        for address, data in code_reads + read_set:
            if n.read(address, len(data)) != data:
                raise NativeUnavailable("lecture_chrono_dechiree")
        finished_mission = n.read_clock()
        window = time.monotonic() - started_wall
        if not (0 <= finished_mission - started_mission <= MAX_WINDOW_S
                and 0 <= window <= MAX_WINDOW_S):
            raise NativeUnavailable("fenetre_chrono_trop_large")
        return dict(sample, status="validated", read_window_s=window,
                    mission_t_s=finished_mission)
