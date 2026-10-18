"""Hermetic reader regressions; real recipe evidence is documented separately."""
import copy
import json
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from test_native import NativeMemory
from hotstate.native import MASK, NativeReader, NativeUnavailable


class PositionMemory(NativeMemory):
    def __init__(self, base=0x40000000):
        super().__init__(base)
        self.add_roster()
        self.position_profile = copy.deepcopy(self.profile)
        self.position_profile['identity_signatures'] = copy.deepcopy(self.profile['signatures'])
        self.pack(base + 0x339fec8, 'II', (~0x120000) & MASK, MASK)
        self.pack(base + 0x32c51f8, 'I', 0)
        self.pack(base + 0x32c403c, 'I', 0)
        self.pack(base + 0x32c3850, 'I', 0)
        self.pack(0x120000, 'I', 0)
        self.pack(0x120000 + 0xc, 'B', 6)
        for slot in range(1, 11):
            self.pack(0x600000 + slot * 0x1000 + 0x1c, 'BB', (slot - 1) // 5, 1 if slot == 6 else 2)
        self.position_profile['maps'] = {'Volskaya': {'bounds': [4, 4, 244, 196]}}
        self.context['meta'] = {'map_id': 'Volskaya', 'context_source': 'initdata_memory',
                                'match_id': 'a' * 64}
        self.pack(0x100000 + 0x2F0, 'iiii', 4, 4, 244, 196)
        for slot in range(1, 11):
            self.position(slot, 20 + slot, 40 + slot)

    def position(self, slot, x, y):
        # Inverse of fingerprinted decode14; a non-zero key exercises bit exchange.
        left, right = int(x * 4096) & MASK, int(y * 4096) & MASK
        swap = (left ^ right) & 0x55555555
        def get(index):
            return struct.unpack('<I', self.read_memory(
                self.module_base + 0x32C1C90 + (index & 4095) * 4, 4))[0]
        upper = right ^ swap
        a = ((left ^ swap) - get((upper >> 12) + upper)) & MASK
        c = ((~(upper ^ 0x12345678)) + get(~a - (a >> 12))) & MASK
        self.pack(0x900000 + (slot - 1) * 0x2F0 + 0x60, 'II', a, c)

    def reader(self):
        from hotstate.positions import AlliedPositions
        return AlliedPositions(NativeReader(self, profile=self.profile),
                               profile=self.position_profile)


class PositionsTests(unittest.TestCase):
    def opened(self):
        return patch('hotstate.positions.VALIDATED_MAPS', ('Volskaya',))

    def test_release_gate_is_limited_to_measured_volskaya(self):
        from hotstate.positions import VALIDATED_MAPS
        self.assertEqual(VALIDATED_MAPS, ('Volskaya',))
        m = PositionMemory()
        m.context['meta']['map_id'] = 'DragonShire'
        with self.assertRaisesRegex(NativeUnavailable, 'recette_positions_absente'):
            m.reader().read(m.context, hero_ids=m.hero_ids)

    def test_released_read_needs_no_release_mock_and_still_omits_enemies(self):
        m = PositionMemory()
        result = m.reader().read(m.context, hero_ids=m.hero_ids)
        self.assertEqual(result['status'], 'validated')
        self.assertEqual([h['id'] for h in result['heroes']], list(range(5, 10)))

    def test_local_identity_missing_or_ambiguous_never_picks_a_bot(self):
        for change in ('observer', 'bool_id', 'bool_team', 'wrong_team', 'duplicate', 'hero'):
            with self.subTest(change=change), self.opened():
                m = PositionMemory()
                if change == 'observer': m.context['local_player'] = None
                elif change == 'bool_id': m.context['local_player']['id'] = True
                elif change == 'bool_team': m.context['local_player']['team'] = True
                elif change == 'wrong_team': m.context['local_player']['team'] = 0
                elif change == 'duplicate': m.context['players'][0]['id'] = 1
                else: m.context['local_player']['hero'] = 'Wizard'
                with self.assertRaises(NativeUnavailable):
                    m.reader().read(m.context, hero_ids=m.hero_ids)

    def test_allies_only_main_units_normalization_and_aslr(self):
        for base in (0x40000000, 0x7FF500000000):
            with self.subTest(base=base), self.opened():
                m = PositionMemory(base)
                result = m.reader().read(m.context, hero_ids=m.hero_ids)
                self.assertEqual([h['id'] for h in result['heroes']], list(range(5, 10)))
                h = result['heroes'][0]
                self.assertEqual((h['x'], h['y']), (26, 46))
                self.assertAlmostEqual(h['u'], (26 - 4) / 240)
                self.assertAlmostEqual(h['v'], 1 - (46 - 4) / 192)
                self.assertEqual(result['status'], 'validated')
                self.assertFalse(any(k in json.dumps(result) for k in ('pointer', 'tag', 'name')))

    def test_movement_re_reads_without_extrapolation_or_caching(self):
        with self.opened():
            m = PositionMemory(); r = m.reader()
            one = r.read(m.context, hero_ids=m.hero_ids)
            m.position(6, 80.25, 150.5)
            two = r.read(m.context, hero_ids=m.hero_ids)
            self.assertNotEqual(one['heroes'][0]['x'], two['heroes'][0]['x'])
            self.assertEqual(two['heroes'][0]['y'], 150.5)
            self.assertLess(two['heroes'][0]['v'], one['heroes'][0]['v'])

    def test_dead_unit_absent_then_respawn_re_resolves(self):
        with self.opened():
            m = PositionMemory(); r = m.reader(); unit = 0x900000 + 5 * 0x2F0
            m.pack(unit + 0x39, 'B', 2)
            self.assertNotIn(5, [h['id'] for h in r.read(m.context, hero_ids=m.hero_ids)['heroes']])
            m.pack(unit + 0x39, 'B', 0); m.position(6, 30, 60)
            self.assertEqual(r.read(m.context, hero_ids=m.hero_ids)['heroes'][0]['x'], 30)

    def test_out_of_bounds_unknown_map_bad_code_build_owner_generation_refused(self):
        for change in ('x', 'negative', 'bounds', 'map', 'build', 'code', 'owner', 'generation', 'encoding'):
            with self.subTest(change=change), self.opened():
                m = PositionMemory(); unit = 0x900000 + 5 * 0x2F0
                if change == 'x': m.position(6, 245, 60)
                elif change == 'negative': m.position(6, -1, 60)
                elif change == 'bounds': m.pack(0x100000 + 0x2F0, 'iiii', 4, 4, 4, 196)
                elif change == 'map': m.context['meta']['map_id'] = 'DragonShire'
                elif change == 'build': m.position_profile['build'] = 999
                elif change == 'code': m.put(m.module_base + 0x200, b'BAD')
                elif change == 'owner': m.pack(unit + 0x44, 'B', 1)
                elif change == 'generation': m.pack(unit + 0x10, 'I', 999)
                else: m.pack(m.module_base + 0x3366118, 'I', 15)
                with self.assertRaises(NativeUnavailable):
                    m.reader().read(m.context, hero_ids=m.hero_ids)

    def test_handle_replacement_follows_cplayer_not_old_unit_or_companion(self):
        with self.opened():
            m = PositionMemory(); r = m.reader()
            old = r.read(m.context, hero_ids=m.hero_ids)
            # New generation, same slot; stale CPlayer tag must fail.
            unit = 0x900000 + 5 * 0x2F0
            tag = (5 << 22) | 2
            m.pack(unit + 0x10, 'I', tag)
            with self.assertRaises(NativeUnavailable): r.read(m.context, hero_ids=m.hero_ids)
            m.pack(0x606000 + 0x58, 'I', tag); m.position(6, 90, 90)
            self.assertNotEqual(old['heroes'][0]['x'], r.read(m.context, hero_ids=m.hero_ids)['heroes'][0]['x'])

    def test_torn_position_owner_root_or_player_tag_rejected(self):
        for target in ('position', 'owner', 'root', 'player_tag'):
            with self.subTest(target=target), self.opened():
                m = PositionMemory(); original = m.read_memory; fired = False
                addresses = {'position': 0x900000 + 5 * 0x2F0 + 0x60,
                             'owner': 0x900000 + 5 * 0x2F0 + 0x44,
                             'root': m.module_base + 0x34F01D0,
                             'player_tag': 0x606000 + 0x58}
                def changing(address, size):
                    nonlocal fired
                    data = original(address, size)
                    if address == addresses[target] and not fired:
                        fired = True
                        m.put(address, bytes([data[0] ^ 1]) + data[1:])
                    return data
                m.read_memory = changing
                with self.assertRaises(NativeUnavailable):
                    m.reader().read(m.context, hero_ids=m.hero_ids)

    def test_nonuniform_decode_table_and_signed_fixed_point(self):
        m = PositionMemory()
        for i in range(4096):
            m.pack(m.module_base + 0x32C1C90 + i * 4, 'I', (i * 987654321 + 1234567) & MASK)
        native = NativeReader(m, profile=m.profile)
        for x, y in ((0, 0), (244, 196), (4.25, 150.5), (-3.25, -20.125), (511, -255)):
            m.position(6, x, y)
            self.assertEqual(m.reader()._xy(native, 0x900000 + 5 * 0x2F0), (x, y))

    def test_companion_is_ignored_until_main_hero_reference_actually_changes(self):
        with self.opened():
            m = PositionMemory(); reader = m.reader()
            unit = 0x900000 + 10 * 0x2F0
            tag = (10 << 22) | 3
            m.pack(unit + 0x10, 'I', tag)
            m.pack(unit + 0x44, 'B', 6)
            m.pack(unit + 0x39, 'B', 0)
            m.position(11, 140, 140)
            self.assertEqual(reader.read(m.context, hero_ids=m.hero_ids)['heroes'][0]['x'], 26)
            m.pack(0x606000 + 0x58, 'I', tag)
            self.assertEqual(reader.read(m.context, hero_ids=m.hero_ids)['heroes'][0]['x'], 140)

    def test_rolling_dump_is_inspectable_but_never_publishable(self):
        m = PositionMemory(); m.recorded_non_atomic = True
        result = m.reader().inspect_saved('Volskaya', hero_ids=m.hero_ids)
        self.assertEqual(result['status'], 'offline_non_atomic')
        self.assertEqual(len(result['heroes']), 9)  # slot 2 is dead in NativeMemory
        with self.opened(), self.assertRaisesRegex(NativeUnavailable, 'capture_positions_non_atomique'):
            m.reader().read(m.context, hero_ids=m.hero_ids)

    def test_supplied_context_mutation_during_read_is_rejected(self):
        with self.opened():
            m = PositionMemory(); original = m.read_memory
            def changing(address, size):
                data = original(address, size)
                if address == 0x900000 + 5 * 0x2F0 + 0x60:
                    m.context['meta']['match_id'] = 'b' * 64
                return data
            m.read_memory = changing
            with self.assertRaisesRegex(NativeUnavailable, 'contexte_positions_modifie'):
                m.reader().read(m.context, hero_ids=m.hero_ids)

    def test_elapsed_window_budget_is_enforced(self):
        with self.opened():
            m = PositionMemory()
            with patch('hotstate.positions.time.monotonic', side_effect=[0, 0.2]):
                with self.assertRaisesRegex(NativeUnavailable, 'fenetre_positions'):
                    m.reader().read(m.context, hero_ids=m.hero_ids)


if __name__ == '__main__':
    unittest.main()
