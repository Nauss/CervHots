"""Local cooldown diagnostic: hermetic tests, no game or KB dependency."""
import struct
import unittest
from types import SimpleNamespace
from hotstate.cooldowns import read_unit_links, select_link, observe
from hotstate.native import NativeUnavailable


class CooldownTests(unittest.TestCase):
    def fixture(self, entries):
        values = {0x10008: 0x20000, 0x20008: 0x30000,
                  0x30008: 0x40000 if entries else 0}
        blobs = {}
        for i, (name, remaining) in enumerate(entries):
            node, string = 0x40000+i*0x100, 0x80000+i*0x100
            values[node+8] = node+0x100 if i+1 < len(entries) else 0
            values[node+0x10] = string
            values[node+0x18] = remaining
            blobs[string+0x18] = struct.pack('<II', len(name)*4, 0)
            blobs[string+0x20] = name.encode('ascii')
        n = SimpleNamespace(value=lambda a, fmt='I': values[a],
                            read=lambda a, s: blobs[a])
        return n, values

    def test_cycle_usage_then_ready_is_native_not_catalogue(self):
        for raw in (0, 516096, 4096, 0):
            n, _ = self.fixture([('Abil/StitchesSlam', raw)])
            result = select_link(read_unit_links(n, 0x10000), 'Abil/StitchesSlam')
            self.assertEqual(result['remaining_s'], raw/65536)
            self.assertEqual(result['cooldown_ready'], raw == 0)
            self.assertEqual(result['cast_legality'], 'unknown')

    def test_absent_link_not_zero_or_absent_ability(self):
        n, _ = self.fixture([])
        result = select_link(read_unit_links(n, 0x10000), 'Abil/StitchesSlam')
        self.assertEqual(result['status'], 'unknown')
        self.assertNotIn('remaining_s', result)
        self.assertNotIn('cooldown_ready', result)
        self.assertEqual(result['reason'], 'cooldown_link_not_observed')

    def test_missing_root_not_empty_list(self):
        n, values = self.fixture([])
        values[0x20008] = 0
        with self.assertRaisesRegex(NativeUnavailable, 'cooldown_root_absent'):
            read_unit_links(n, 0x10000)

    def test_duplicates_negative_cycle_refuse(self):
        for entries in ([('Abil/A', 0), ('Abil/A', 0)], [('Abil/A', -1)]):
            n, _ = self.fixture(entries)
            with self.assertRaises(NativeUnavailable): read_unit_links(n, 0x10000)
        n, values = self.fixture([('Abil/A', 0)])
        values[0x40008] = 0x40000
        with self.assertRaises(NativeUnavailable): read_unit_links(n, 0x10000)

    def test_no_probe_means_no_reads_and_no_payload(self):
        result = observe(None, object())
        self.assertEqual(result['status'], 'rejected')
        self.assertNotIn('links', result)
        self.assertEqual(result['kind'], 'local_unit_cooldown_diagnostic_NOT_PRODUCT')

    def test_charge_player_and_active_slots_not_claimed(self):
        n, _ = self.fixture([('Abil/A', 0)])
        result = select_link(read_unit_links(n, 0x10000), 'Abil/A')
        self.assertEqual(result['storage'], 'unit')
        self.assertEqual(result['ability_binding'], 'unproven')
        self.assertNotIn('charges', result)
        self.assertNotIn('slot', result)


if __name__ == '__main__': unittest.main()
