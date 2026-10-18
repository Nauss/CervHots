"""Synthetic allowlist/privacy tests; no live position release is claimed."""
import copy
import unittest
from unittest.mock import patch

from cerveau.state import snapshot
from cerveau.runner import tactical_key
from test_positions import PositionMemory
from hotstate.native import NativeReader


def raw_packet():
    m = PositionMemory()
    with patch('hotstate.positions.VALIDATED_MAPS', ('Volskaya',)):
        p = m.reader().read(m.context, hero_ids=m.hero_ids)
    # Independent P0/P1 read with positions still closed.
    raw = NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)
    raw['meta'].update(m.context['meta'], source='live')
    raw['positions'] = p
    return raw


class PositionContractTests(unittest.TestCase):
    def test_release_gate_rejects_even_a_forged_validated_packet(self):
        self.assertNotIn('positions', snapshot(raw_packet()))

    def test_normalizer_keeps_typed_allies_and_discards_every_extra_identifier(self):
        raw = raw_packet()
        raw['positions']['pointer'] = 'PRIVATE'
        raw['positions']['heroes'][0].update(name='PRIVATE', owner='PRIVATE')
        # Deliberately re-issue a SYNTHETIC acquisition to test the typed
        # sanitizer independently of tamper/provenance rejection.
        from hotstate.acquisition import issue
        issue(raw['positions'], raw['positions']['acquisition']['monotonic_s'])
        with patch('hotstate.positions.VALIDATED_MAPS', ('Volskaya',)):
            state = snapshot(raw)
        self.assertEqual([h['id'] for h in state['positions']['heroes']], list(range(5, 10)))
        self.assertNotIn('PRIVATE', str(state))
        self.assertNotIn('match_id', state['positions'])

    def test_unknown_stale_corrupt_enemy_dead_duplicate_and_observer_are_omitted(self):
        for change in ('offline', 'future', 'stale', 'nan', 'bool', 'infinite', 'huge', 'bounds',
                       'enemy', 'dead', 'duplicate', 'match', 'local', 'team', 'map', 'window'):
            raw = raw_packet()
            p = raw['positions']
            if change == 'offline': p['status'] = 'offline_non_atomic'
            elif change == 'future': p['mission_t_s'] += 1
            elif change == 'stale': p['mission_t_s'] -= 2
            elif change == 'nan': p['heroes'][0]['x'] = float('nan')
            elif change == 'bool': p['heroes'][0]['x'] = True
            elif change == 'infinite': p['heroes'][0]['x'] = float('inf')
            elif change == 'huge': p['heroes'][0]['x'] = 10 ** 400
            elif change == 'bounds': p['bounds'][2] = 4
            elif change == 'enemy': p['heroes'][0]['id'] = 0
            elif change == 'dead': raw['heroes'][5]['alive'] = False
            elif change == 'duplicate': p['heroes'][1]['id'] = 5
            elif change == 'match': p['match_id'] = 'b' * 64
            elif change == 'local': p['local_id'] = 1
            elif change == 'team': p['team'] = 0
            elif change == 'map': raw['meta']['map_id'] = 'DragonShire'
            else: p['read_window_s'] = 1
            from hotstate.acquisition import issue
            if change not in ('nan', 'infinite'):
                issue(p, p['acquisition']['monotonic_s'])
            with self.subTest(change=change), patch('hotstate.positions.VALIDATED_MAPS', ('Volskaya',)):
                self.assertNotIn('positions', snapshot(raw))
        raw = raw_packet(); raw['local_player'] = None
        with self.assertRaises(ValueError): snapshot(raw)

    def test_team_override_never_turns_enemies_into_allies(self):
        with patch('hotstate.positions.VALIDATED_MAPS', ('Volskaya',)):
            self.assertNotIn('positions', snapshot(raw_packet(), team=0))
            self.assertNotIn('positions', snapshot(raw_packet(), map_name='Dragon Shire'))

    def test_availability_and_movement_cancel_advice_not_identical_sample_timestamp(self):
        with patch('hotstate.positions.VALIDATED_MAPS', ('Volskaya',)):
            state = snapshot(raw_packet())
        key = tactical_key(state)
        next_state = copy.deepcopy(state); next_state['positions']['t'] += 0.0625
        self.assertEqual(key, tactical_key(next_state))
        next_state['positions']['heroes'][0]['x'] += 1
        self.assertNotEqual(key, tactical_key(next_state))
        next_state = copy.deepcopy(state); next_state.pop('positions')
        self.assertNotEqual(key, tactical_key(next_state))

    def test_native_default_never_publishes_before_real_recipe(self):
        m = PositionMemory()
        result = NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)
        self.assertNotIn('positions', result)
        self.assertEqual(len(result['heroes']), 10)


if __name__ == '__main__':
    unittest.main()
