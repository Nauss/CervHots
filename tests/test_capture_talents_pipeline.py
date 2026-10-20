"""Hermetic FULL candidate pipeline, no game/KB/network/coach."""
import unittest
from unittest.mock import patch
import test_talents_product as product
import test_capture_talents as fixtures
from test_capture_visibility_pipeline import FixtureClock
from etudes.rea.scripts import capture_talents_pipeline as c


class TalentFullPipelineTests(unittest.TestCase):
    def test_actual_consumer_normalizer_key_and_ordered_replay(self):
        m = product.TalentProductTests().fixture()
        with fixtures.TalentCollectorTests().options(m), \
                patch.object(c, 'CANDIDATE_SCOPES', (('Volskaya','ragnaros'),)), \
                patch('cerveau.brain.Coach.decide', side_effect=AssertionError('coach forbidden')):
            row = c.take_sample(m, m.probe(), clock=FixtureClock(), native_profile=m.profile)
            self.assertEqual(row['status'], 'accepted', row.get('rejected'))
            self.assertIn('talents', row['normalized'])
            self.assertIn('talents', row['tactical_key'])
            for hero in row['normalized']['heroes'][:5]:
                self.assertTrue({'health','resource','x','y','talents'}.isdisjoint(hero))
            again = c.replay_sample(row, m.module_base, m.probe(), native_profile=m.profile)
            self.assertEqual(again['normalized'], row['normalized'])
            self.assertEqual(again['tactical_key'], row['tactical_key'])

    def test_non_atomic_has_no_full_acceptance(self):
        m = product.TalentProductTests().fixture()
        m.recorded_non_atomic = True
        with fixtures.TalentCollectorTests().options(m), patch.object(c, 'CANDIDATE_SCOPES', (('Volskaya','ragnaros'),)):
            row = c.take_sample(m, m.probe(), clock=FixtureClock(), native_profile=m.profile)
        self.assertEqual(row['status'], 'rejected')
        self.assertNotIn('normalized', row)

    def test_no_choice_then_choice_then_reset_changes_real_key(self):
        m = product.TalentProductTests().fixture()
        keys = []
        with fixtures.TalentCollectorTests().options(m), patch.object(c, 'CANDIDATE_SCOPES', (('Volskaya','ragnaros'),)):
            for index in (0xffffffff, 0, 0xffffffff):
                m.pack(m.module_base+0x3677a30+6*128+4, 'I', index)
                row = c.take_sample(m, m.probe(), clock=FixtureClock(), native_profile=m.profile)
                self.assertEqual(row['status'], 'accepted', row.get('rejected'))
                tier = row['normalized']['talents']['players'][0]['tiers'][0]
                self.assertEqual(tier['status'], 'selected' if index == 0 else 'unselected')
                keys.append(row['tactical_key'])
        self.assertNotEqual(keys[0], keys[1])
        self.assertEqual(keys[0], keys[2])

    def test_observer_unknown_id_missing_tree_level_and_torn_reject_full(self):
        for mutation in ('observer','unknown_id','missing_tree','level_unknown','torn'):
            m = product.TalentProductTests().fixture()
            if mutation == 'observer':
                m.pack(0x120000, 'I', 0x20)
            elif mutation == 'unknown_id':
                m.pack(m.module_base+0x3677a30+6*128+4, 'I', 100)
            elif mutation == 'missing_tree':
                m.pack(0x70500, 'I', 0)
            elif mutation == 'level_unknown':
                m.pack(0xc0004, 'I', 0)
            else:
                original = m.read_memory
                calls = [0]
                selected = m.module_base+0x3677a30+6*128
                def read(address, size):
                    if address == selected and size == 128:
                        calls[0] += 1
                        if calls[0] >= 2:
                            m.pack(selected+4, 'I', 0xffffffff)
                    return original(address, size)
                m.read_memory = read
            with self.subTest(mutation=mutation), fixtures.TalentCollectorTests().options(m), \
                    patch.object(c, 'CANDIDATE_SCOPES', (('Volskaya','ragnaros'),)):
                row = c.take_sample(m, m.probe(), clock=FixtureClock(), native_profile=m.profile)
                self.assertEqual(row['status'], 'rejected')
                self.assertNotIn('talents', row.get('normalized',{}))


if __name__ == '__main__':
    unittest.main()
