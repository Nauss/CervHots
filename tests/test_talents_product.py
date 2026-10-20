"""Synthetic product-path tests, never native coverage evidence."""
import unittest
from unittest.mock import patch
import test_capture_talents as fixtures
from hotstate import talents
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.acquisition import fresh


class TalentProductTests(unittest.TestCase):
    def fixture(self):
        m = fixtures.TalentCollectorTests().fixture()
        m.pack(0x70518, 'I', 2)
        m.pack(0x70528, 'Q', 0xc0000)
        m.pack(0xc0000, 'III', 1, 1, 0)
        m.pack(0xc000c, 'III', 2, 4, 0)
        return m

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


if __name__ == '__main__':
    unittest.main()
