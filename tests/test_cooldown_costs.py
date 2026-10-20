"""Current LOCAL ability cost-overlay tests; no live qualification."""
import struct
import unittest
from types import SimpleNamespace
from hotstate.cooldown_costs import current_cost, applicability, diagnostic_abilities, PROFILE
from hotstate.native import NativeUnavailable


class CurrentCostTests(unittest.TestCase):
    def setUp(self):
        self.values = {0x10028: 0x20001, 0x20002: 2,
            0x100000+0x3388b18: 0x30000, 0x30008: 0x40000,
            0x40090: 10, 0x400a0: 0x50000, 0x50010: 0x60000,
            0x60040: 3, 0x40038: 10, 0x40048: 0x70000, 0x70018: 0x20000,
            0x20000: 0, 0x20060: 0x80000, 0x80024: 6,
            0x80100: 0x90000, 0x90000: 1 << 6,
            0x20070: 0xa0000, 0xa0008: 0xb0000,
            0xb0028: 0, 0xb0058: 1, 0xb0040: 1,
            0xb0050: 0xc0000, 0xb0038: 0,
            0xb005c: 0, 0xb0060: 5, 0xb0064: 65536}
        self.values[0x100000+PROFILE['registry_flags_rva']] = 1 << 6
        registry = 0x100000+PROFILE['registry_rva']+6*0x2a48
        self.values.update({registry: 1, registry+8: 1,
            registry+0x60: 0x100000+next(s['rva'] for s in PROFILE['signatures'] if s['name']=='CostClass6')})
        self.values[0x100000+PROFILE['cooldown_condition_index_rva']] = 0xffffffff
        self.values[0x100000+PROFILE['condition_player_mask_rva']] = 0
        link = 'Abil/Fixture'
        self.values[0xc0018] = len(link)*4
        self.blobs = {0xc0018: struct.pack('<II', len(link)*4, 0), 0xc0020: link.encode()}
        self.n = SimpleNamespace(base=0x100000, value=lambda a, fmt='I': self.values[a],
                                 read=lambda a, size: self.blobs[a])

    def test_actual_owner_overlay_not_base_and_not_duration_reconstruction(self):
        row = current_cost(self.n, 0x10000, 1)
        self.assertEqual(row['cooldown_link'], 'Abil/Fixture')
        self.assertEqual(row['charges_max'], 0)
        self.assertEqual(row['cooldown_storage'], 'unit')
        self.assertTrue(row['cooldown_applies'])
        self.assertNotIn('remaining_s', row)
        self.assertEqual(row['source_scope'], 'current_local_player_overlay_NOT_BASE')

    def test_lazy_or_replaced_current_source_never_native_call_or_base_fallback(self):
        self.values[0x70018] |= 1
        with self.assertRaisesRegex(NativeUnavailable, 'FORBIDDEN'): current_cost(self.n, 0x10000, 1)
        self.values[0x70018] = 0x21000
        self.values[0x21000] = 0
        with self.assertRaisesRegex(NativeUnavailable, 'root_not_current'): current_cost(self.n, 0x10000, 1)

    def test_callback_changed_refuses_even_valid_class(self):
        registry = 0x100000+PROFILE['registry_rva']+6*0x2a48
        self.values[registry+0x60] += 8
        with self.assertRaisesRegex(NativeUnavailable, 'callback'): current_cost(self.n, 0x10000, 1)

    def test_unknown_class_owner_and_storage_fail_closed(self):
        self.values[0x80024] = 10
        self.assertEqual(current_cost(self.n, 0x10000, 1)['reason'], 'cost_native_class_unqualified')
        for value in (0, 11, True, None):
            with self.assertRaises(NativeUnavailable): current_cost(self.n, 0x10000, value)
        self.values[0x80024] = 6
        self.values[0xb0058] = 3
        row = current_cost(self.n, 0x10000, 1)
        self.assertEqual(row['cooldown_storage'], 'unqualified')
        self.assertIsNone(row['cooldown_applies'])

    def test_live_observed_classes8_9_use_distinct_current_cost_overlay_offset(self):
        for cls, callback in ((8, 12209904), (9, 12213248)):
            with self.subTest(native_class=cls):
                self.setUp()
                fields = (0x20, 0x50, 0x38, 0x48, 0x30, 0x54, 0x58, 0x5c)
                old = {offset:self.values[0xb0008+offset] for offset in fields}
                for offset, value in old.items(): self.values[0xb0018+offset] = value
                self.values[0xb0018+0x20] = 2*4096
                self.values[0x80024] = cls
                self.values[0x90000+(cls >> 3)] = 1 << (cls & 7)
                self.values[self.n.base+PROFILE['registry_flags_rva']+(cls >> 3)] = 1 << (cls & 7)
                registry = self.n.base+PROFILE['registry_rva']+cls*0x2a48
                self.values.update({registry:1, registry+8:1, registry+0x60:self.n.base+callback})
                row = current_cost(self.n, 0x10000, 1)
                self.assertEqual(row['status'], 'diagnostic_current_cost')
                self.assertEqual(row['charges_max'], 2)
                self.assertEqual(row['cooldown_link'], 'Abil/Fixture')
                self.assertTrue(row['cooldown_applies'])

    def test_applicability_native_conditions_and_player_mask(self):
        for mode, value, expected in ((0,0,False),(0,1,True),(2,65536,False),
                                      (2,65552,True),(3,2147483647,False),
                                      (3,0,True),(4,-1,False),(4,1,True),
                                      (5,0,True),(6,1,False)):
            self.assertEqual(applicability(self.n, 1, 0, mode, value), expected)
        self.values[0x100000+PROFILE['condition_player_mask_rva']] = 1 << 1
        self.assertFalse(applicability(self.n, 1, 0, 5, 0))
        self.values[0x100000+PROFILE['cooldown_condition_index_rva']] = 0
        self.values[0x100000+PROFILE['condition_bits_rva']] = 0
        self.assertTrue(applicability(self.n, 1, 0, 5, 0))

    def test_bound_link_absent_is_unknown_not_zero(self):
        cost = current_cost(self.n, 0x10000, 1)
        rows = [{'ability': 'Fixture', 'current_cost': cost}]
        row = diagnostic_abilities(rows, {}, {})[0]
        self.assertEqual(row['cooldown_status'], 'unknown')
        self.assertNotIn('cooldown_ready', row)
        row = diagnostic_abilities(rows, {'Abil/Fixture':0}, {})[0]
        self.assertEqual(row['remaining_s'], 0)
        self.assertTrue(row['cooldown_ready'])
        self.assertEqual(row['cast_legality'], 'unknown')

    def test_out_of_range_condition_rejects_before_globals_and_join_never_ready(self):
        original = self.n.value
        def guarded(address, fmt='I'):
            if address in (self.n.base+PROFILE['cooldown_condition_index_rva'],
                           self.n.base+PROFILE['condition_player_mask_rva']):
                self.fail('invalid native mode read globals instead of returning false')
            return original(address, fmt)
        for mode in (7, 8, 255, 0xffffffff):
            with self.subTest(mode=mode):
                self.n.value = guarded
                self.assertFalse(applicability(self.n, 1, 0, mode, 1))
                self.values[0xb0060], self.values[0xb0064] = mode, 1
                cost = current_cost(self.n, 0x10000, 1)
                row = diagnostic_abilities([{'ability': 'Fixture', 'current_cost': cost}],
                                           {'Abil/Fixture': 0}, {})[0]
                self.assertEqual(row['cooldown_status'], 'unknown')
                self.assertNotIn('cooldown_ready', row)
        self.n.value = original
        # Native flag!=0 intentionally bypasses the mode check, not player mask.
        self.assertTrue(applicability(self.n, 1, 1, 0xffffffff, 1))
        self.values[self.n.base+PROFILE['condition_player_mask_rva']] = 1 << 1
        self.assertFalse(applicability(self.n, 1, 1, 0xffffffff, 1))

    def test_current_player_charge_max_is_not_catalogue_base_or_guessed_available(self):
        cost = current_cost(self.n, 0x10000, 1)
        cost.update(charges_max=3, charge_link='Charge/Fixture', charge_storage='player')
        rows = [{'ability':'Fixture', 'current_cost':cost}]
        stores = {'player_charges': {'status':'diagnostic_observed', 'value':{
            'Charge/Fixture': {'charges_used':2, 'regen_s':1.5}}}}
        row = diagnostic_abilities(rows, {'Abil/Fixture':0}, stores)[0]
        self.assertEqual(row['charges_available'], 1)
        self.assertEqual(row['charges_max'], 3)
        self.assertEqual(row['charge_regen_s'], 1.5)
        self.assertNotIn('ready', row)
        del stores['player_charges']['value']['Charge/Fixture']
        row = diagnostic_abilities(rows, {'Abil/Fixture':0}, stores)[0]
        self.assertEqual(row['charges_status'], 'unknown')
        self.assertNotIn('charges_available', row)


if __name__ == '__main__': unittest.main()
