"""Synthetic refusal tests, not a Dragon live recipe."""
import unittest
from unittest.mock import patch
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.battlefield import VolskayaBattlefield, structure_kind
from hotstate.dragon_battlefield import DragonBattlefield, PROFILE, DEFENDERS
import test_battlefield
from hotstate.battlefield_details import camp_public


class DragonBattlefieldTests(unittest.TestCase):
    def camp_memory(self):
        memory, _ = test_battlefield.BattlefieldTests().camp_memory()
        for index, kind in enumerate((1, 2, 1, 2, 2), 1):
            a = memory.g+index*780
            memory.pack(a+0xDF074, 'i', kind)
            memory.pack(a+0xDF0BA, 'i', kind)
        return memory, DragonBattlefield(NativeReader(memory, profile=memory.profile))

    def test_five_map_specific_camps_and_no_volskaya_type_transfer(self):
        memory, reader = self.camp_memory()
        with patch.object(reader, '_unit_type', return_value='TownMercCampCaptureBeacon'):
            rows = reader._camps(reader.native)
        self.assertEqual([r['defender_type'] for r in rows], [1, 2, 1, 2, 2])
        memory.pack(memory.g+780+0xDF074, 'i', 5)
        with patch.object(reader, '_unit_type', return_value='TownMercCampCaptureBeacon'):
            with self.assertRaises(NativeUnavailable):
                reader._camps(reader.native)

    def test_wrong_type_and_recycled_beacon_refuse(self):
        memory, reader = self.camp_memory()
        with patch.object(reader, '_unit_type', return_value='MercLanerSiegeGiant'):
            with self.assertRaises(NativeUnavailable):
                reader._camps(reader.native)
        memory.pack(0x900010, 'I', 2)
        with self.assertRaises(NativeUnavailable):
            reader._camps(reader.native)

    def test_public_read_closed_even_with_forged_context(self):
        _, reader = self.camp_memory()
        with patch('hotstate.dragon_battlefield.VALIDATED_MAPS',()), \
             patch.object(reader, '_observe', side_effect=AssertionError('acquisition attempted')):
            with self.assertRaisesRegex(NativeUnavailable, 'recette_champ_bataille_dragon_absente'):
                reader.read({'map_id': 'DragonShire'})

    def test_rolling_dump_and_non_probe_rejected_before_reads(self):
        memory, reader = self.camp_memory()
        with self.assertRaises(NativeUnavailable):
            reader.diagnose(object())
        memory.recorded_non_atomic = True
        with self.assertRaises(NativeUnavailable):
            reader.diagnose(None)

    def test_profile_does_not_reuse_volskaya_map_hook(self):
        self.assertEqual(PROFILE['map'], 'DragonShire')
        self.assertEqual(len(PROFILE['functions']), 15)
        self.assertNotIn('gf_HookupJungleCreepData', [f['name'] for f in PROFILE['functions']])
        self.assertIn('gt_InitializeMapMechanic_Func', [f['name'] for f in PROFILE['functions']])
        self.assertEqual(len(DEFENDERS[1]), 2)
        self.assertEqual(len(DEFENDERS[2]), 4)
        self.assertEqual(DEFENDERS[2][-1], 'MercDefenderRangedMage')

    def test_dragon_gate_not_silently_omitted(self):
        self.assertEqual(structure_kind('TownGateL3VerticalRightVisionBlocked'), 'gate')
        self.assertIsNone(structure_kind('TownGateL3VerticalRightVisionBlockedFake'))

    def test_hidden_dragon_camp_never_discloses_cycle_owner_or_timer(self):
        row = {'index': 1, 'anchor_current_visible': False}
        result = camp_public(row, kinds=DragonBattlefield.CAMP_KINDS)
        self.assertEqual(result['kind'], 'siege_giants')
        self.assertEqual(result['state'], 'unknown')
        for key in ('owner', 'cycle', 'respawn_s', 'respawn_timer'):
            self.assertIsNone(result[key])

    def test_volskaya_configuration_unchanged(self):
        self.assertEqual(VolskayaBattlefield.CAMP_TYPES, (5, 5, 6, 6, 10))
        self.assertEqual(DragonBattlefield.CAMP_TYPES, (1, 2, 1, 2, 2))

    def test_position_fingerprint_failure_prevents_any_xy_or_camp_read(self):
        _, reader = self.camp_memory()
        with patch.object(VolskayaBattlefield, '_verify'), \
             patch('hotstate.dragon_battlefield.AlliedPositions._verify',
                   side_effect=NativeUnavailable('signature_positions_invalide')), \
             patch.object(reader, '_camps', side_effect=AssertionError('camp read')):
            with self.assertRaisesRegex(NativeUnavailable, 'signature_positions_invalide'):
                reader._sample(reader.native, 0)


if __name__ == '__main__':
    unittest.main()
