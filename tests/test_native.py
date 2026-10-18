"""Explicit synthetic native-memory fixtures; no game process or private captures."""
import hashlib
import struct
import unittest


class NativeMemory:
    def __init__(self, base=0x40000000):
        self.module_base = base
        self.pages = {}
        marker = b"SYNTHETIC_NATIVE_FIXTURE"
        self.profile = {"build": 98348, "image_size": 0x45AE000,
                        "pe_timestamp": 0x12345678,
                        "signatures": [{"rva": 0x200, "size": len(marker),
                                        "sha256": hashlib.sha256(marker).hexdigest()}]}
        self.put(base, b"MZ")
        self.pack(base + 0x3C, "I", 0x80)
        self.put(base + 0x80, b"PE\0\0")
        self.pack(base + 0x88, "I", self.profile["pe_timestamp"])
        self.pack(base + 0x80 + 24 + 56, "I", self.profile["image_size"])
        self.put(base + 0x200, marker)
        self.pack(base + 0x35C8CD9, "B", 1)
        root = 0x100000
        self.pack(base + 0x32C2130, "I", 0)
        self.pack(base + 0x34F01D4, "I", (-0x6D6AFAFC) & 0xFFFFFFFF)
        self.pack(base + 0x34F01D0, "I", root)
        self.pack(base + 0x32C4880, "I", 0)
        self.pack(root + 0x68, "i", int(123.5 * 4096))

    def put(self, address, data):
        for index, value in enumerate(data):
            current = address + index
            self.pages.setdefault(current // 4096, bytearray(4096))[current % 4096] = value

    def pack(self, address, fmt, *values):
        self.put(address, struct.pack("<" + fmt, *values))

    def read_memory(self, address, size):
        try:
            return bytes(self.pages[(address + i) // 4096][(address + i) % 4096]
                         for i in range(size))
        except KeyError:
            return None

    def add_roster(self):
        base = self.module_base
        self.profile['identity_signatures'] = list(self.profile['signatures'])
        self.pack(base + 0x339fec8, 'II', (~0x120000) & 0xffffffff, 0xffffffff)
        self.pack(base + 0x32c51f8, 'I', 0)
        self.pack(base + 0x32c403c, 'I', 0)
        self.pack(base + 0x32c3850, 'I', 0)
        self.pack(0x120000, 'I', 0)
        self.pack(0x120000 + 0xc, 'B', 6)
        self.hero_ids = {"Monk": "kharazim", "Wizard": "liming", "Ragnaros": "ragnaros"}
        self.context = {"players": [{"id": i, "team": i // 5,
                                     "hero": "Ragnaros" if i == 5 else None} for i in range(10)],
                        "local_player": {"id": 5, "team": 1, "hero": "Ragnaros"},
                        "meta": {"map_id": "Volskaya", "match_id": "a" * 64,
                                 "context_source": "initdata_memory"}}
        self.pack(base + 0x3366118, "I", 14)
        self.pack(base + 0x35C8CB0, "I", 0x500000)
        self.pack(base + 0x35C8CB4, "I", 0)
        self.pack(base + 0x32C4CF4, "I", 0)
        self.put(base + 0x32C1C90, bytes(16384))
        self.pack(0x500000, "Q", 0x510000)
        self.pack(base + 0x3388AE0, "Q", 0x520000)
        self.pack(0x520000, "I", 0x12345678)
        self.pack(base + 0x34F02C4, "I", 16)
        self.pack(base + 0x34F02C8, "II", 0x900000, 0)
        self.pack(base + 0x32C38B4, "I", 0)
        self.pack(base + 0x32C55D0, "I", 0)
        self.pack(base + 0x4020970, "Q", 0xB00000)
        self.pack(0xF00000 + 0x140, "Q", base + 0x800)
        self.put(base + 0x800, b"\xB8\x0C\0\0\0\xC3")
        for slot in range(1, 11):
            player = 0x600000 + slot * 0x1000
            self.pack(player + 0x1c, 'BB', (slot - 1) // 5, 1 if slot == 6 else 2)
            swapped = player & 0x55555555
            self.pack(0x510000 + slot * 8, "II", player ^ swapped, swapped ^ 0x12345678)
            self.pack(player + 0x22, "B", slot)
            record = 0x700000 + slot * 0x1000
            self.pack(player + 0x50, "Q", record)
            self.pack(record + 0x30, "Q", record + 0x100)
            name = "Ragnaros" if slot == 6 else "Monk" if slot <= 5 else "Wizard"
            self.pack(record + 0x118, "II", len(name) << 2, 0)
            self.put(record + 0x120, name.encode("ascii"))
            tag = ((slot - 1) << 22) | 1
            self.pack(player + 0x58, "I", tag)
            self.pack(player + 0xF0, "I", slot)
            unit = 0x900000 + (slot - 1) * 0x2F0
            self.pack(unit + 0x10, "I", tag)
            self.pack(unit + 0x39, "B", 2 if slot == 3 else 0)
            self.pack(unit + 0x44, "B", slot)
            for offset, amount in ((0x220, 3000), (0x22C, 500), (0x228, 600), (0x234, 500)):
                self.pack(unit + offset, "i", amount * 4096)
            head = 0xD00000 + slot * 0x1000
            node, xp = head + 0x100, 0xE00000 + slot * 0x1000
            self.pack(unit + 0x160, "Q", head)
            self.pack(head, "Q", node)
            self.pack(node, "QQ", 1, xp)
            self.pack(node + 0x48, "B", 1)
            self.pack(xp, "Q", 0xF00000)
            self.pack(xp + 0x78, "B", 0)
            self.pack(xp + 0xD0, "i", 20 if slot <= 5 else 18)
            timer = 0xB10000 + slot * 0x1000
            self.pack(0xB00000 + slot * 16 + 6, "B", 0x13)
            self.pack(0xB00000 + slot * 16 + 8, "Q", timer)
            self.pack(timer + 0x18, "ii", 5 * 4096, (25 if slot == 3 else 5) * 4096)


class NativeTests(unittest.TestCase):
    def test_a_captured_module_base_is_decoded_instead_of_assuming_the_preferred_pe_base(self):
        from hotstate.native import module_base_from_image

        image = bytearray(0x4124C68)
        base = 0x7FF600000000
        pointer = base + 0x29A7CF8
        struct.pack_into("<I", image, 0x32C23C8, 0x1234)
        struct.pack_into("<I", image, 0x32C209C, 0x5678)
        struct.pack_into("<II", image, 0x4124C60,
                         (~(pointer & 0xFFFFFFFF) + 0x1234) & 0xFFFFFFFF,
                         (pointer >> 32) ^ 0x5678 ^ 0xE6F631CE)
        self.assertEqual(module_base_from_image(image), base)

    def test_allied_resource_values_are_observed_but_never_expose_hidden_enemy_resources(self):
        from hotstate.native import NativeReader

        memory = NativeMemory()
        memory.add_roster()
        observed = NativeReader(memory, profile=memory.profile).read_state(
            memory.context, hero_ids=memory.hero_ids)
        self.assertEqual(observed["heroes"][5]["resource"], 500)
        self.assertEqual(observed["heroes"][5]["resource_max"], 600)
        self.assertNotIn("resource", observed["heroes"][0])

    def test_bad_generation_owner_encoding_and_unknown_hero_never_produce_state(self):
        from hotstate.native import NativeReader, NativeUnavailable

        for change in ("generation", "owner", "encoding", "local_hero", "native_hero"):
            with self.subTest(change=change):
                memory = NativeMemory()
                memory.add_roster()
                if change == "generation":
                    memory.pack(0x900000 + 0x10, "I", 999)
                elif change == "owner":
                    memory.pack(0x900000 + 0x44, "B", 9)
                elif change == "encoding":
                    memory.pack(memory.module_base + 0x3366118, "I", 15)
                elif change == "local_hero":
                    memory.context["local_player"]["hero"] = "Wizard"
                else:
                    memory.hero_ids.pop("Monk")
                with self.assertRaises(NativeUnavailable):
                    NativeReader(memory, profile=memory.profile).read_state(
                        memory.context, hero_ids=memory.hero_ids)

    def test_an_unknown_death_timer_stays_absent_instead_of_becoming_zero(self):
        from hotstate.native import NativeReader

        memory = NativeMemory()
        memory.add_roster()
        memory.pack(0xB00000 + 3 * 16 + 6, "B", 0)
        observed = NativeReader(memory, profile=memory.profile).read_state(
            memory.context, hero_ids=memory.hero_ids)
        self.assertFalse(observed["heroes"][2]["alive"])
        self.assertNotIn("respawn_s", observed["heroes"][2])

    def test_native_read_rejects_missing_or_incomplete_context(self):
        from hotstate.native import NativeReader, NativeUnavailable

        for context in (None, {}, {"players": [], "local_player": {"id": 5, "team": 1, "hero": "Ragnaros"}}):
            with self.subTest(context=context):
                memory = NativeMemory()
                memory.add_roster()
                with self.assertRaises(NativeUnavailable):
                    NativeReader(memory, profile=memory.profile).read_state(
                        context, hero_ids=memory.hero_ids)

    def test_native_read_rejects_a_torn_snapshot(self):
        from hotstate.native import NativeReader, NativeUnavailable

        class AdvancingMemory(NativeMemory):
            def read_memory(self, address, size):
                result = super().read_memory(address, size)
                if address == 0x900000 + 9 * 0x2F0 + 0x220:
                    self.pack(0x100000 + 0x68, "i", 127 * 4096)
                return result

        memory = AdvancingMemory()
        memory.add_roster()
        with self.assertRaises(NativeUnavailable):
            NativeReader(memory, profile=memory.profile).read_state(
                memory.context, hero_ids=memory.hero_ids)

    def test_native_roster_has_levels_life_and_timer_without_names_or_hidden_enemy_vitals(self):
        from hotstate.native import NativeReader

        memory = NativeMemory()
        memory.add_roster()
        observed = NativeReader(memory, profile=memory.profile).read_state(
            memory.context, hero_ids=memory.hero_ids)
        self.assertEqual(observed["meta"]["t_s"], 123.5)
        self.assertEqual(observed["meta"]["clock_kind"], "mission")
        self.assertTrue(observed["composition_complete"])
        self.assertEqual(len(observed["heroes"]), 10)
        self.assertEqual([h["level"] for h in observed["heroes"]], [21] * 5 + [19] * 5)
        self.assertEqual(observed["heroes"][2]["alive"], False)
        self.assertEqual(observed["heroes"][2]["respawn_s"], 20)
        self.assertNotIn("health", observed["heroes"][2])
        self.assertEqual(observed["heroes"][5]["health"], 2500)
        self.assertEqual(observed["local_player"]["hero"], "ragnaros")
        self.assertNotIn("pointer", str(observed))
        self.assertNotIn("native_unit_tag", str(observed))

    def test_unknown_build_modified_code_inactive_game_and_negative_clock_are_rejected(self):
        from hotstate.native import NativeReader, NativeUnavailable

        for change in ("timestamp", "signature", "inactive", "negative", "empty_profile"):
            with self.subTest(change=change):
                memory = NativeMemory()
                if change == "timestamp":
                    memory.pack(memory.module_base + 0x88, "I", 0)
                elif change == "signature":
                    memory.put(memory.module_base + 0x200, b"CORRUPTED")
                elif change == "inactive":
                    memory.pack(memory.module_base + 0x35C8CD9, "B", 0)
                elif change == "negative":
                    memory.pack(0x100000 + 0x68, "i", -1)
                else:
                    memory.profile["signatures"] = []
                with self.assertRaises(NativeUnavailable):
                    NativeReader(memory, profile=memory.profile).read_clock()

    def test_mission_clock_uses_native_fixed_point_and_relocates_with_the_module(self):
        from hotstate.native import NativeReader

        for base in (0x40000000, 0x7FF500000000):
            with self.subTest(base=base):
                memory = NativeMemory(base)
                reader = NativeReader(memory, profile=memory.profile)
                self.assertEqual(reader.read_clock(), 123.5)


if __name__ == "__main__":
    unittest.main()
