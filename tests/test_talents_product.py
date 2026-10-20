"""Synthetic product-path tests, never native coverage evidence."""
import unittest
from unittest.mock import patch
import test_capture_talents as fixtures
from hotstate import talents
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.acquisition import fresh


class TalentProductTests(unittest.TestCase):
    def test_release_policy_is_exactly_qualified_hero_map_roles(self):
        cases = {(c['map_id'],c['hero'],c['role']) for c in talents.PROFILE.get('qualified_cases',[])}
        self.assertEqual(cases, {('DragonShire','sonya','local'),
            ('DragonShire','arthas','ally'),('DragonShire','dehaka','ally'),
            ('DragonShire','ltmorales','ally'),('DragonShire','tassadar','ally')})
        self.assertTrue(talents.qualified_for('DragonShire','sonya',local=True))
        self.assertFalse(talents.qualified_for('DragonShire','sonya'))
        self.assertFalse(talents.qualified_for('DragonShire','arthas',local=True))
        self.assertTrue(talents.qualified_for('DragonShire','arthas'))
        self.assertFalse(talents.qualified_for('Volskaya','stitches',local=True))

    def fixture(self):
        m = fixtures.TalentCollectorTests().fixture()
        m.pack(0x70518, 'I', 2)
        m.pack(0x70528, 'Q', 0xc0000)
        m.pack(0xc0000, 'III', 1, 1, 0)
        m.pack(0xc000c, 'III', 2, 4, 0)
        return m

    def allied_fixture(self):
        m = self.fixture()
        for native_id in range(7,11):
            m.pack(0x700000+native_id*0x1000+0x40, 'H', 4)
            for tier in range(32):
                m.pack(m.module_base+0x3677a30+native_id*128+tier*4, 'I', 0xffffffff)
        m.pack(m.module_base+0x3677a30+7*128+4, 'I', 0)
        return m

    def test_allied_current_choices_and_no_enemy_talent_reads(self):
        m = self.allied_fixture()
        original = m.read_memory
        def read(address, size):
            for native_id in range(1,6):
                enemy = m.module_base+0x3677a30+native_id*128
                if address < enemy+128 and address+size > enemy:
                    self.fail('enemy talent read')
            return original(address,size)
        m.read_memory = read
        with fixtures.TalentCollectorTests().options(m), patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya','ragnaros'),('Volskaya','liming'))):
            probe = m.probe()
            probe.observe_native(m, native_profile=m.profile)
            packet = talents.NativeTalentChoices(NativeReader(m,profile=m.profile)).read(probe.finish())
            self.assertEqual([p['id'] for p in packet['players']], list(range(5,10)))
            ally = packet['players'][1]
            self.assertEqual(ally['hero'], 'liming')
            self.assertEqual(ally['tiers'][0]['status'], 'selected')

    def test_receipt_current_choice_and_missing_tier_not_defaulted(self):
        m = self.fixture()
        helper = fixtures.TalentCollectorTests()
        with helper.options(m), patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya','ragnaros'),)):
            probe = m.probe()
            probe.observe_native(m, native_profile=m.profile)
            n = NativeReader(m, profile=m.profile)
            packet = talents.NativeTalentChoices(n).read(probe.finish())
            self.assertTrue(fresh(packet))
            self.assertEqual(packet['tiers'][0]['catalog_id'], 'StitchesPatchworkCreation')
            self.assertEqual(packet['tiers'][1]['status'], 'unknown')
            self.assertNotIn('offered', packet)
            core = n.read_state(probe.finish())
            self.assertEqual(core['talents']['tiers'], packet['tiers'])

    def test_closed_scope_never_publishes_diagnostic(self):
        m = self.fixture()
        helper = fixtures.TalentCollectorTests()
        with helper.options(m), patch('time.monotonic', return_value=100):
            probe = m.probe()
            probe.observe_native(m, native_profile=m.profile)
            with self.assertRaises(NativeUnavailable):
                talents.NativeTalentChoices(NativeReader(m, profile=m.profile)).read(probe.finish())

    def test_core_receipt_binds_the_same_local_generation(self):
        m = self.fixture()
        helper = fixtures.TalentCollectorTests()
        with helper.options(m), patch('time.monotonic', return_value=100):
            probe = m.probe()
            probe.observe_native(m, native_profile=m.profile)
            raw = NativeReader(m, profile=m.profile).read_state(probe.finish())
            self.assertEqual(raw['perspective']['local_generation'], 1)
            self.assertEqual(raw['perspective']['allied_generations'], {str(i):1 for i in range(5,10)})


if __name__ == '__main__':
    unittest.main()
