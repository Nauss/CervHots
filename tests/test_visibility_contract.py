"""Visibility publication path under a synthetic release gate, not real evidence."""
import copy
import time
import unittest
from unittest.mock import patch

from test_current_visibility import VisibilityMemory
from hotstate.native import NativeReader, NativeUnavailable
from cerveau.state import snapshot


def packet(m):
    with patch('hotstate.visibility.VALIDATED_MAPS', ('Volskaya',)):
        return m.visibility().read(m.context, hero_ids=m.hero_ids)


def raw_state(m):
    raw = NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)
    raw['meta'].update(m.context['meta'], source='live')
    raw['visibility'] = packet(m)
    return raw


class VisibilityContractTests(unittest.TestCase):
    def test_public_boolean_fog_reveal_and_unknown_no_enemy_tactical_fields(self):
        m = VisibilityMemory()
        for fog in (True, False, True):
            m.fog(fog)
            raw = raw_state(m)
            for h in raw['heroes'][:5]:
                h.update(health=123, resource=456, x=10, y=20, cooldowns={'Q': 0})
            with patch('hotstate.visibility.VALIDATED_MAPS', ('Volskaya',)):
                clean = snapshot(raw)
            self.assertIs(clean['visibility']['heroes'][0]['visible'], fog)
            self.assertIsNone(clean['visibility']['heroes'][2]['visible'])
            for h in clean['heroes'][:5]:
                for key in ('health', 'resource', 'x', 'y', 'cooldowns'):
                    self.assertNotIn(key, h)
            self.assertNotIn('native_session', str(clean['visibility']))
            self.assertNotIn('match_id', clean['visibility'])

    def test_acquisition_untrusted_stale_future_paused_and_mutated_rejected(self):
        for change in ('receipt', 'age', 'future', 'tamper', 'context', 'team', 'source', 'map'):
            m = VisibilityMemory(); raw = raw_state(m)
            p = raw['visibility']
            if change == 'receipt': p.pop('acquisition')
            elif change == 'age':
                from hotstate.acquisition import issue
                issue(p, time.monotonic() - 2)
            elif change == 'future':
                from hotstate.acquisition import issue
                issue(p, time.monotonic() + 2)
            elif change == 'tamper': p['heroes'][0]['visible'] = True
            elif change == 'context': raw['meta']['match_id'] = 'f' * 64
            elif change == 'team': raw['local_player']['team'] = 0
            elif change == 'source': raw['meta']['source'] = 'dump'
            else: raw['meta']['map_id'] = 'DragonShire'
            with self.subTest(change=change), patch('hotstate.visibility.VALIDATED_MAPS', ('Volskaya',)):
                if change == 'team':
                    with self.assertRaises(ValueError): snapshot(raw)
                else:
                    self.assertNotIn('visibility', snapshot(raw))

    def test_native_match_seed_cache_and_torn_root_or_seed_rejected(self):
        for change in ('declared', 'new_seed', 'new_cache', 'torn_seed', 'torn_state', 'torn_root', 'torn_cache'):
            m = VisibilityMemory(); m.fog(True)
            config = m.app + 0x83f78
            if change == 'declared': m.context['meta']['match_id'] = 'f' * 64
            elif change == 'new_seed': m.pack(config + 0x1d428, 'I', m.seed + 1)
            elif change == 'new_cache': m.put(config + 0xd488 + 8, bytes([8]) * 32)
            else:
                original = m.read_memory
                address = {'torn_seed': config + 0x1d428, 'torn_state': m.app + 0x1d910,
                           'torn_root': m.module_base + 0x2f825f8,
                           'torn_cache': config + 0xd488}[change]
                fired = False
                def changing(a, s):
                    nonlocal fired
                    data = original(a, s)
                    if a == address and not fired:
                        fired = True
                        m.put(a, bytes([data[0] ^ 1]) + data[1:])
                    return data
                m.read_memory = changing
            with self.subTest(change=change), self.assertRaises(NativeUnavailable): packet(m)

    def test_diagnostic_and_disabled_map_never_publish(self):
        m = VisibilityMemory()
        with patch('hotstate.visibility.VALIDATED_MAPS', ()), self.assertRaisesRegex(NativeUnavailable, 'recette_visibilite_joueur_absente'):
            m.visibility().read(m.context, hero_ids=m.hero_ids)
        raw = raw_state(m)
        raw['visibility'] = m.visibility().diagnose('Volskaya', hero_ids=m.hero_ids)
        with patch('hotstate.visibility.VALIDATED_MAPS', ('Volskaya',)):
            self.assertNotIn('visibility', snapshot(raw))

    def test_actual_release_scope_is_only_proven_volskaya(self):
        from hotstate.visibility import VALIDATED_MAPS
        self.assertEqual(VALIDATED_MAPS, ('Volskaya',))
        m = VisibilityMemory(); m.fog(True)
        result = m.visibility().read(m.context, hero_ids=m.hero_ids)
        self.assertEqual(result['status'], 'validated')
        self.assertTrue(result['heroes'][0]['visible'])
        self.assertIn('acquisition', result)
        for map_id in ('DragonShire', 'BraxisHoldout'):
            context = copy.deepcopy(m.context)
            context['meta']['map_id'] = map_id
            with self.subTest(map_id=map_id), self.assertRaisesRegex(NativeUnavailable, 'recette_visibilite_joueur_absente'):
                m.visibility().read(context, hero_ids=m.hero_ids)

    def test_tactical_freshness_cancels_on_fog_or_unknown_not_new_timestamp(self):
        from cerveau.runner import tactical_key
        m = VisibilityMemory()
        with patch('hotstate.visibility.VALIDATED_MAPS', ('Volskaya',)):
            state = snapshot(raw_state(m))
        key = tactical_key(state)
        changed = copy.deepcopy(state)
        changed['visibility']['t'] += 0.0625
        self.assertEqual(key, tactical_key(changed))
        changed['visibility']['heroes'][0]['visible'] = True
        self.assertNotEqual(key, tactical_key(changed))
        changed['visibility']['heroes'][0]['visible'] = None
        self.assertNotEqual(key, tactical_key(changed))
        changed.pop('visibility')
        self.assertNotEqual(key, tactical_key(changed))

    def test_native_pipeline_uses_optional_isolated_current_reader(self):
        m = VisibilityMemory(); m.fog(True)
        with patch('hotstate.visibility.VALIDATED_MAPS', ('Volskaya',)), \
                patch('hotstate.visibility.PROFILE', m.visibility_profile), \
                patch('hotstate.positions.PROFILE', m.position_profile), \
                patch('hotstate.match.PROFILE', m.match_profile):
            raw = NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)
            raw['meta'].update(m.context['meta'], source='live')
            self.assertTrue(snapshot(raw)['visibility']['heroes'][0]['visible'])
            m.context['meta']['match_id'] = 'f' * 64
            refused = NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)
            self.assertNotIn('visibility', refused)
            self.assertEqual(len(refused['heroes']), 10)


if __name__ == '__main__':
    unittest.main()
