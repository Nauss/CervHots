"""Actual normalizer/key boundary on hermetic native receipts, no KB/network."""
import copy
import json
import unittest
from unittest.mock import patch
import test_talents_product as product
import test_capture_talents as fixtures
from hotstate import talents
from hotstate.native import NativeReader
from hotstate.acquisition import issue
from cerveau.state import snapshot
from cerveau.runner import tactical_key


class TalentContractTests(unittest.TestCase):
    def raw(self, m):
        probe = m.probe()
        probe.observe_native(m, native_profile=m.profile)
        context = probe.finish()
        n = NativeReader(m, profile=m.profile)
        core = n.read_state(context)
        packet = talents.NativeTalentChoices(n).read(context)
        return dict(core, talents=packet, meta={**context['meta'], **core['meta'], 'source':'live'})

    def test_real_normalizer_key_and_expired_generation_enemy_guards(self):
        m = product.TalentProductTests().fixture()
        with fixtures.TalentCollectorTests().options(m), patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya','ragnaros'),)):
            raw = self.raw(m)
            clean = snapshot(raw)
            self.assertEqual(clean['talents']['players'][0]['tiers'][0]['catalog_id'], 'StitchesPatchworkCreation')
            self.assertEqual(clean['talents']['players'][0]['tiers'][1]['status'], 'unknown')
            key = tactical_key(clean)
            noisy = copy.deepcopy(raw)
            noisy['talents']['pointer'] = 'PRIVATE_SENTINEL'
            noisy['talents']['offered'] = ['DO_NOT_PUBLISH']
            issue(noisy['talents'], 100)
            self.assertEqual(snapshot(noisy)['talents'], clean['talents'])
            self.assertNotIn('PRIVATE_SENTINEL', json.dumps(snapshot(noisy)))
            changed = copy.deepcopy(raw)
            changed['talents']['players'][0]['tiers'][0].update(slot=None, catalog_id=None, status='unselected')
            issue(changed['talents'], 100)
            self.assertNotEqual(tactical_key(snapshot(changed)), key)
            for field, value in (('generation', 2), ('local_id', 0), ('team', 0),
                                 ('local_hero','sonya'), ('match_id','b'*64)):
                bad = copy.deepcopy(raw)
                bad['talents'][field] = value
                issue(bad['talents'], 100)
                with self.subTest(field=field):
                    self.assertNotIn('talents', snapshot(bad))
            with patch('time.monotonic', return_value=102):
                self.assertNotIn('talents', snapshot(raw))

    def test_allied_normalizer_filters_enemy_and_binds_each_generation(self):
        m = product.TalentProductTests().allied_fixture()
        with fixtures.TalentCollectorTests().options(m), patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya','ragnaros'),('Volskaya','liming'))):
            raw = self.raw(m)
            clean = snapshot(raw)
            self.assertEqual([p['id'] for p in clean['talents']['players']], list(range(5,10)))
            self.assertEqual(clean['talents']['players'][1]['status'], 'observed')
            for mutation in ('enemy', 'ally_generation', 'unknown_with_choice'):
                bad = copy.deepcopy(raw)
                if mutation == 'enemy':
                    bad['talents']['players'][1]['id'] = 0
                elif mutation == 'ally_generation':
                    bad['talents']['players'][1]['generation'] = 2
                else:
                    bad['talents']['players'][1]['status'] = 'unknown'
                issue(bad['talents'], 100)
                with self.subTest(mutation=mutation):
                    self.assertNotIn('talents', snapshot(bad))

    def test_unqualified_allies_are_unknown_not_unselected(self):
        m = product.TalentProductTests().allied_fixture()
        with fixtures.TalentCollectorTests().options(m), patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya','ragnaros'),)):
            clean = snapshot(self.raw(m))
            self.assertEqual(clean['talents']['players'][1],
                {'id':6,'hero':'liming','status':'unknown','tiers':None})


if __name__ == '__main__':
    unittest.main()
