"""Synthetic VM/timer fixtures. These are NOT measurements of saved captures."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from test_native import NativeMemory
from hotstate.native import NativeReader, NativeUnavailable

PROFILE = Path(__file__).resolve().parents[1] / "hotstate/profiles/98348-clock.json"


class ClockMemory(NativeMemory):
    def __init__(self, base=0x40000000):
        super().__init__(base)
        self.clock_profile = json.loads(PROFILE.read_text())
        self.clock_profile["pe_timestamp"] = self.profile["pe_timestamp"]
        self.clock_profile["signatures"] = copy.deepcopy(self.profile["signatures"])
        self.table, self.slots = 0x200000, base + 0x4020980
        self.pack(base + 0x3B8C5C8, "Q", self.table)
        self.pack(base + 0x2FA7100, "Q", self.table)
        self.pack(base + 0x2FA70F0, "I", 5000)
        self.pack(base + 0x3B8C904, "I", 800000)
        self.pack(base + 0x4020970, "Q", self.slots)
        self.pack(base + 0x2F72670, "I", 2)
        self.pack(base + 0x2F72680, "Q", 0x650000)
        self.pack(0x650000, "II", (3 << 16) | 5, (3 << 16) | 6)
        for ordinal, spec in enumerate(self.clock_profile["functions"]):
            record = 0x300000 + ordinal * 4096
            self.pack(self.table + spec["index"] * 8, "Q", record)
            self.pack(record + 8, "I", ordinal * 1024 + 4)
            self.pack(record + 0x50, "I", spec["index"])
            name = spec["name"].encode("ascii")
            self.pack(record + 0x58, "IIQ", len(name) << 2, 2, record + 256)
            self.put(record + 256, name)
            # Deliberately synthetic bytecode fingerprints, not claimed client instructions.
            code = bytes([ordinal + 1]) * spec["length"]
            self.put(base + 0x3B8C920 + ordinal * 1024 + 4, code)
            spec["sha256"] = hashlib.sha256(code).hexdigest()
        self.phase("playing")

    def timer(self, index, elapsed, deadline, *, paused=0, expired=0, clock=0):
        pointer, reference = 0x600000 + index * 4096, (3 << 16) | index
        self.pack(self.slots + index * 16, "HHHBBQ", 3, 0, 1, 19, 0, pointer)
        self.pack(pointer, "QII4BIiiiI", self.module_base + 0x26B4F18, reference, 0,
                  0, paused, expired, 0, clock, int(elapsed * 4096), int(deadline * 4096),
                  123 * 4096, 0)
        return reference

    def phase(self, phase, *, seconds=12.5, delta=0):
        prep = phase == "preparation"
        game = self.timer(5, 0 if prep else seconds, 0 if prep else -1,
                          paused=1 if prep else 0, clock=1 if prep else 0)
        gates = self.timer(6, 7 if prep else 35, 35, expired=0 if prep else 1)
        self.pack(self.module_base + 0x3D0C920 + 0xC988, "I", game)
        self.pack(self.module_base + 0x3D0C920 + 0x19E67, "I", gates)
        self.pack(self.module_base + 0x3D0C920 + 0x19E77, "B", 0 if prep else 1)
        self.pack(self.module_base + 0x3D0C920 + 0x10E56F, "i", int(delta * 4096))

    def reader(self):
        from hotstate.gameplay import GameplayClock
        return GameplayClock(NativeReader(self, profile=self.profile), profile=self.clock_profile)


class GameplayClockTests(unittest.TestCase):
    def test_native_clock_code_changed_after_verification_is_rejected(self):
        m = ClockMemory(); reader = m.reader(); original = m.read_memory; fired = False
        def changing(address, size):
            nonlocal fired
            data = original(address, size)
            if not fired and address == m.module_base + 0x200:
                fired = True; m.put(address, b'CORRUPT')
            return data
        m.read_memory = changing
        with self.assertRaisesRegex(NativeUnavailable, 'lecture_chrono_dechiree'):
            reader.read()

    def test_preparation_and_proven_zero_and_elapsed_debug_delta(self):
        for phase, seconds, delta, expected in (("preparation", 0, 9, -28),
                                               ("playing", 0, 0, 0),
                                               ("playing", 12.5, 2, 132.5),
                                               ("playing", 12.5, -1, -47.5)):
            with self.subTest(phase=phase, seconds=seconds, delta=delta):
                memory = ClockMemory()
                memory.phase(phase, seconds=seconds, delta=delta)
                result = memory.reader().read()
                self.assertEqual(result["t_s"], expected)
                self.assertEqual(result["phase"], phase)
                self.assertEqual(result["status"], "validated")
                self.assertNotIn("pointer", str(result))
                self.assertNotIn("reference", str(result))

    def test_ambiguous_initial_zero_zero_is_not_gameplay_zero(self):
        memory = ClockMemory()
        memory.phase("preparation")
        memory.timer(6, 0, 0, paused=1, clock=1)
        with self.assertRaises(NativeUnavailable):
            memory.reader().read()

    def test_bad_profile_root_bounds_name_script_tag_generation_owner_and_clock_refused(self):
        for change in ("build", "signature", "root", "alias", "count", "code_bounds", "index",
                       "name", "bytecode", "tag", "generation", "owner", "clock", "started",
                       "deadline", "null_handle", "null_timer", "refcount", "flags"):
            with self.subTest(change=change):
                m = ClockMemory()
                base = m.module_base
                if change == "build": m.clock_profile["build"] = 999
                elif change == "signature": m.put(base + 0x200, b"BAD")
                elif change == "root": m.pack(base + 0x3B8C5C8, "Q", 0)
                elif change == "alias": m.pack(base + 0x2FA7100, "Q", m.table + 8)
                elif change == "count": m.pack(base + 0x2FA70F0, "I", 1)
                elif change == "code_bounds": m.pack(0x300000 + 8, "I", 800000)
                elif change == "index": m.pack(0x300000 + 0x50, "I", 0)
                elif change == "name": m.put(0x300000 + 256, b"dead")
                elif change == "bytecode": m.put(base + 0x3B8C920 + 4, b"BAD")
                elif change == "tag": m.pack(m.slots + 5 * 16 + 6, "B", 18)
                elif change == "generation": m.pack(m.slots + 5 * 16, "H", 2)
                elif change == "owner": m.pack(0x605000 + 8, "I", 0)
                elif change == "clock": m.pack(0x605000 + 20, "I", 2)
                elif change == "started": m.pack(base + 0x3D0C920 + 0x19E77, "B", 0)
                elif change == "deadline": m.pack(0x605000 + 28, "i", 0)
                elif change == "null_handle": m.pack(base + 0x3D0C920 + 0xC988, "I", 0)
                elif change == "null_timer": m.pack(m.slots + 5 * 16 + 8, "Q", 0)
                elif change == "refcount": m.pack(m.slots + 5 * 16 + 4, "H", 0)
                else: m.pack(0x605000 + 16, "B", 2)
                with self.assertRaises(NativeUnavailable): m.reader().read()

    def test_timer_pause_resume_has_no_wall_clock_extrapolation(self):
        m = ClockMemory()
        reader = m.reader()
        m.pack(0x605000 + 17, "B", 1)
        one = reader.read()
        two = reader.read()
        self.assertTrue(one["timer_paused"])
        self.assertEqual(one["t_s"], two["t_s"])
        m.pack(0x605000 + 17, "B", 0)
        m.pack(0x605000 + 24, "i", 14 * 4096)
        self.assertEqual(reader.read()["t_s"], 14)

    def test_only_registered_timers_are_accepted_and_expiry_may_overshoot_one_tick(self):
        m = ClockMemory()
        m.timer(6, 35.0625, 35, expired=1)
        self.assertEqual(m.reader().read()["t_s"], 12.5)
        m.pack(0x650000, "I", 0)
        with self.assertRaises(NativeUnavailable): m.reader().read()

    def test_reset_re_resolves_and_does_not_reuse_old_gameplay(self):
        m = ClockMemory()
        reader = m.reader()
        self.assertEqual(reader.read()["t_s"], 12.5)
        m.phase("preparation")
        self.assertEqual(reader.read()["t_s"], -28)
        m.pack(m.module_base + 0x35C8CD9, "B", 0)
        with self.assertRaises(NativeUnavailable): reader.read()

    def test_torn_timer_and_reset_during_read_are_rejected(self):
        for target in (0x605000 + 24, 0x100000 + 0x68):
            m = ClockMemory()
            original = m.read_memory
            def torn(address, size):
                data = original(address, size)
                if address == 0x606000:
                    m.pack(target, "i", 0)
                return data
            m.read_memory = torn
            with self.assertRaises(NativeUnavailable): m.reader().read()

    def test_read_window_is_bounded_in_both_mission_and_monotonic_time(self):
        m = ClockMemory()
        with patch("hotstate.gameplay.time.monotonic", side_effect=[1.0, 1.2]):
            with self.assertRaises(NativeUnavailable): m.reader().read()

    def test_rolling_dump_is_not_validated_by_fast_rereads(self):
        m = ClockMemory()
        m.recorded_non_atomic = True
        with self.assertRaises(NativeUnavailable): m.reader().read()
        # Explicit offline diagnostics may inspect bytes but cannot claim publication.
        sample = m.reader().inspect_saved()
        self.assertNotEqual(sample["status"], "validated")
        self.assertEqual(sample["t_s"], 12.5)

    def test_torn_root_bytecode_generation_and_owner_are_rejected(self):
        for change in ("root", "bytecode", "generation", "owner"):
            m = ClockMemory()
            original = m.read_memory
            def torn(address, size):
                data = original(address, size)
                if address == 0x606000 and size == 40:
                    if change == "root": m.pack(m.module_base + 0x3B8C5C8, "Q", m.table + 8)
                    elif change == "bytecode": m.put(m.module_base + 0x3B8C920 + 4, b"BAD")
                    elif change == "generation": m.pack(m.slots + 5 * 16, "H", 9)
                    else: m.pack(0x605000 + 8, "I", 7)
                return data
            m.read_memory = torn
            with self.subTest(change=change), self.assertRaises(NativeUnavailable):
                m.reader().read()

    def test_exact_window_boundary_and_mission_progression(self):
        for seconds, accepted in ((0.125, True), (0.1251, False), (-0.0625, False)):
            m = ClockMemory()
            reader = m.reader()
            with (patch("hotstate.gameplay.time.monotonic", side_effect=[1.0, 1.125]),
                  patch.object(reader.native, "read_clock", side_effect=[123.5, 123.5 + seconds])):
                if accepted:
                    self.assertEqual(reader.read()["read_window_s"], 0.125)
                else:
                    with self.assertRaises(NativeUnavailable): reader.read()

    def test_aslr_and_fixed_point_fractions(self):
        for base in (0x40000000, 0x7FF500000000):
            m = ClockMemory(base)
            m.phase("playing", seconds=0.0625)
            self.assertEqual(m.reader().read()["t_s"], 0.0625)


if __name__ == "__main__":
    unittest.main()
