"""Source helpers fixture tests; no live/whole-product qualification."""
import struct
import unittest
from types import SimpleNamespace
from hotstate.cooldown_sources import active_instances, stored_links
from hotstate.native import NativeUnavailable


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.values = {0x10140: 0x20003, 0x20062: 4,
                       0x20068+8: 0x30000, 0x20068+24: 0x31000,
                       0x30028: 0x40010, 0x31028: 0x41010,
                       0x40002: 2, 0x41002: 3,
                       0x100000+0x3388b18: 0x50000, 0x50008: 0x60000,
                       0x60090: 10, 0x600a0: 0x70000,
                       0x70010: 0x80000, 0x70018: 0x81000,
                       0x80030: 0x90000, 0x81030: 0x91000}
        self.blobs = {0x20040: struct.pack('<Q', 0b1010)}
        for address, name in ((0x90000, 'StitchesSlam'), (0x91000, 'StitchesHook')):
            self.blobs[address+0x18] = struct.pack('<II', len(name)*4, 0)
            self.blobs[address+0x20] = name.encode('ascii')
        self.n = SimpleNamespace(base=0x100000, value=lambda a, fmt='I': self.values[a],
                                 read=lambda a, size: self.blobs[a])

    def test_sparse_bitmap_matches_current_ordinals_not_base_loadout(self):
        rows = active_instances(self.n, 0x10000)
        self.assertEqual([(r['ordinal'], r['instance_slot'], r['ability']) for r in rows],
                         [(1, 1, 'StitchesSlam'), (2, 3, 'StitchesHook')])
        self.assertTrue(all(r['cost_binding'] == 'unproven' for r in rows))
        self.assertTrue(all(r['slot_kind'] == 'native_instance_NOT_HUD_button' for r in rows))
        self.assertFalse(any('remaining_s' in r for r in rows))

    def test_replaced_instance_name_is_read_currently(self):
        self.values[0x70010] = 0x81000
        self.assertEqual(active_instances(self.n, 0x10000)[0]['ability'], 'StitchesHook')

    def test_missing_container_and_bad_bitmap_refuse(self):
        self.values[0x10140] = 0
        with self.assertRaises(NativeUnavailable): active_instances(self.n, 0x10000)
        self.values[0x10140] = 0x20000
        self.blobs[0x20040] = struct.pack('<Q', 1 << 6)
        with self.assertRaises(NativeUnavailable): active_instances(self.n, 0x10000)

    def test_catalogue_index_and_duplicate_instance_refuse(self):
        self.values[0x40002] = 11
        with self.assertRaises(NativeUnavailable): active_instances(self.n, 0x10000)
        self.values[0x40002] = 2
        self.values[0x20068+24] = 0x30000
        with self.assertRaises(NativeUnavailable): active_instances(self.n, 0x10000)

    def test_absent_native_descriptor_not_empty_name_or_absent_ability(self):
        self.values[0x30028] = 0x10
        with self.assertRaises(NativeUnavailable): active_instances(self.n, 0x10000)

    def list_fixture(self, charges):
        self.blobs[0x40020] = struct.pack('<ii', 65536, -32768)
        self.values.update({0x10008: 0x20000, 0x20000: 0x30000, 0x30008: 0x40000,
                            0x101f8: 0x40000, 0x101e8: 0x40000,
                            0x40008: 0, 0x40010: 0x90000, 0x40018: 65536,
                            0x4001c: 6144, 0x40020: 65536, 0x40024: -32768})
        return stored_links(self.n, 0x10000, storage='player' if not charges else 'unit', charges=charges)

    def test_player_cd_and_unit_charge_have_different_native_heads(self):
        self.assertEqual(self.list_fixture(False)['StitchesSlam']['remaining_s'], 1)
        row = self.list_fixture(True)['StitchesSlam']
        self.assertEqual(row['regen_s'], 1)
        self.assertEqual(row['charges_used'], 1.5)
        self.assertEqual(row['regen_full_s'], 0.5)
        self.assertNotIn('charges_available', row)
        self.assertNotIn('cooldown_ready', row)

    def test_player_empty_storage_not_default_ready(self):
        self.values[0x101f8] = 1
        self.assertEqual(stored_links(self.n, 0x10000, storage='player'), {})
        with self.assertRaises(ValueError): stored_links(self.n, 0x10000, storage='enemy')


if __name__ == '__main__': unittest.main()
