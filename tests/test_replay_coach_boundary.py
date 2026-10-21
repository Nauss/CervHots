"""Synthetic replay/player boundary regressions; no account or live source."""
import copy
import json
import unittest

from cerveau.state import snapshot


def replay():
    return {
        'meta': {'source': 'replay', 'duration_s': 900, 'map': 'Cursed Hollow'},
        'players': [{'id': 0, 'name': 'SYNTHETIC_PRIVATE_ALLY', 'hero': 'Jaina', 'team': 0},
                    {'id': 1, 'name': 'SYNTHETIC_PRIVATE_ENEMY', 'hero': 'Arthas', 'team': 1}],
        'timeline': {'hero_events': [
            {'t': 0, 'type': 'spawn', 'player': 'SYNTHETIC_PRIVATE_ALLY', 'hero': 'Jaina'},
            {'t': 0, 'type': 'spawn', 'player': 'SYNTHETIC_PRIVATE_ENEMY', 'hero': 'Arthas'}]},
        'position_snapshots': [{'t': 10, 'positions': {
            'SYNTHETIC_PRIVATE_ALLY': {'x': 400, 'y': 800},
            'SYNTHETIC_PRIVATE_ENEMY': {'x': 900, 'y': 600}}}],
    }


class ReplayBoundaryTests(unittest.TestCase):
    def test_ambiguous_lifecycle_cannot_preserve_life_or_xy_in_prepared_prompt(self):
        from cerveau.brain import Coach

        class FakeClient:
            messages = None

            def chat(self, messages, **kwargs):
                self.messages = messages
                return {'choices': [{'message': {'content': '{"parler": false}'}}]}

        for identity in (
                {'player': 'SYNTHETIC_PRIVATE_ALLY', 'hero': 'Diablo'},
                {'player': 'SYNTHETIC_PRIVATE_ALLY', 'hero': {'private': 'SYNTHETIC_PRIVATE'}},
                {'hero': 'Jaina'},
                {'player': 'SYNTHETIC_PRIVATE_UNKNOWN', 'hero': 'Jaina'},
                {'player': ['SYNTHETIC_PRIVATE_ALLY'], 'hero': 'Jaina'}):
            for kind in ('death', 'spawn', 'respawn'):
                with self.subTest(identity=identity, kind=kind):
                    raw = replay()
                    raw['timeline']['hero_events'].append(dict(t=10.25, type=kind, **identity))
                    state = snapshot(raw, at=10.5, team=0)
                    client = FakeClient()
                    Coach(client).decide(state)
                    prepared = json.loads(client.messages[1]['content'])['etat']
                    for projected in (state, prepared):
                        self.assertNotIn('positions', projected)
                        self.assertTrue(all('alive' not in h for h in projected['heroes']))
                        self.assertNotIn('deaths_total', projected['stats'])
                        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(projected))

    def test_duplicate_names_remain_ambiguous_even_with_invalid_roster_rows(self):
        for extra in ({'hero': 'Diablo', 'team': 0},
                      {'hero': {'private': 'SYNTHETIC_PRIVATE'}, 'team': 0},
                      {'hero': 'Jaina', 'team': True}):
            with self.subTest(extra=extra):
                raw = replay()
                raw['players'].append(dict(id=2, name='SYNTHETIC_PRIVATE_ALLY', **extra))
                state = snapshot(raw, at=10, team=0)
                self.assertNotIn('positions', state)
                self.assertTrue(all('alive' not in h for h in state['heroes']))
                self.assertNotIn('deaths_total', state['stats'])

    def test_validly_dated_future_rows_do_not_change_the_projected_prefix(self):
        baseline = snapshot(replay(), at=10, team=0)
        for event in ({'t': 100, 'type': 'SYNTHETIC_PRIVATE_FUTURE'},
                      {'t': 100, 'type': {'private': 'SYNTHETIC_PRIVATE'}},
                      {'t': 100, 'type': 'death', 'hero': 'Jaina'},
                      {'t': 100, 'type': 'death', 'player': 'SYNTHETIC_PRIVATE_ALLY',
                       'hero': 'Diablo'}):
            with self.subTest(event=event):
                raw = replay()
                raw['timeline']['hero_events'].append(event)
                raw['position_snapshots'].append({'t': 100, 'positions': None})
                self.assertEqual(snapshot(raw, at=10, team=0), baseline)

    def test_duplicate_heroes_do_not_resolve_an_unbound_death_in_prompt(self):
        from cerveau.brain import Coach

        class FakeClient:
            def chat(self, messages, **kwargs):
                self.state = json.loads(messages[1]['content'])['etat']
                return {'choices': [{'message': {'content': '{"parler": false}'}}]}

        for duplicate_name in (False, True):
            with self.subTest(duplicate_name=duplicate_name):
                raw = replay()
                raw['players'].append({'id': 2, 'hero': 'Jaina', 'team': 0,
                                       'name': 'SYNTHETIC_PRIVATE_ALLY' if duplicate_name
                                       else 'SYNTHETIC_PRIVATE_SECOND'})
                raw['timeline']['hero_events'].extend([
                    {'t': 0, 'type': 'spawn', 'player': raw['players'][2]['name']},
                    {'t': 10.25, 'type': 'death', 'hero': 'Jaina'},
                    {'t': 10.3, 'type': 'respawn', 'player': 'SYNTHETIC_PRIVATE_ALLY'}])
                state = snapshot(raw, at=10.5, team=0)
                client = FakeClient()
                Coach(client).decide(state)
                for projected in (state, client.state):
                    self.assertNotIn('positions', projected)
                    self.assertTrue(all('alive' not in h for h in projected['heroes']))
                    self.assertNotIn('deaths_total', projected['stats'])

    def test_coherent_duplicate_heroes_keep_independently_bound_public_facts_in_prompt(self):
        from cerveau.brain import Coach

        class FakeClient:
            def chat(self, messages, **kwargs):
                self.state = json.loads(messages[1]['content'])['etat']
                return {'choices': [{'message': {'content': '{"parler": false}'}}]}

        raw = replay()
        raw['players'][1]['hero'] = 'Jaina'
        raw['timeline']['hero_events'][1]['hero'] = 'Jaina'
        raw['timeline']['hero_events'].append(
            {'t': 9, 'type': 'death', 'player': 'SYNTHETIC_PRIVATE_ENEMY', 'hero': 'Jaina'})
        raw['timeline']['stat_events'] = [
            {'t': 2, 'name': 'LevelUp', 'player': 'SYNTHETIC_PRIVATE_ALLY', 'data': {'Level': 7}},
            {'t': 3, 'name': 'TributeCollected', 'data': {'TeamID': 8192}}]
        state = snapshot(raw, at=10, team=0)
        client = FakeClient()
        Coach(client).decide(state)
        for projected in (state, client.state):
            self.assertTrue(projected['heroes'][0]['alive'])
            self.assertFalse(projected['heroes'][1]['alive'])
            self.assertEqual(projected['heroes'][0]['level'], 7)
            self.assertEqual(projected['stats']['deaths_total'], 1)
            self.assertEqual(projected['positions']['heroes'],
                             [{'hero': 'Jaina', 'team': 0, 'x': 100, 'y': 200}])
            self.assertIn({'t': 3, 'name': 'TributeCollected', 'team': 1}, projected['events'])

    def test_enemy_xy_is_absent_without_historical_player_visibility(self):
        state = snapshot(replay(), at=10, team=0)
        self.assertEqual(state['positions']['heroes'],
                         [{'hero': 'Jaina', 'team': 0, 'x': 100, 'y': 200}])

    def test_dead_ally_has_no_current_position(self):
        raw = replay()
        raw['timeline']['hero_events'].append(
            {'t': 10.25, 'type': 'death', 'player': 'SYNTHETIC_PRIVATE_ALLY'})
        self.assertNotIn('positions', snapshot(raw, at=10.5, team=0))

    def test_long_gap_does_not_keep_last_sample(self):
        self.assertNotIn('positions', snapshot(replay(), at=609, team=0))

    def test_missing_sample_time_stays_unknown(self):
        raw = replay()
        del raw['position_snapshots'][0]['t']
        self.assertNotIn('positions', snapshot(raw, at=10, team=0))

    def test_future_sample_stays_unknown(self):
        self.assertNotIn('positions', snapshot(replay(), at=9, team=0))

    def test_unknown_life_stays_unknown(self):
        raw = replay()
        raw['timeline'] = {}
        self.assertNotIn('positions', snapshot(raw, at=10, team=0))

    def test_respawn_does_not_revive_old_position(self):
        raw = replay()
        raw['timeline']['hero_events'].extend([
            {'t': 10.1, 'type': 'death', 'player': 'SYNTHETIC_PRIVATE_ALLY'},
            {'t': 10.2, 'type': 'respawn', 'player': 'SYNTHETIC_PRIVATE_ALLY'}])
        self.assertNotIn('positions', snapshot(raw, at=10.5, team=0))

    def test_coordinates_are_bounded_finite_numbers_not_booleans(self):
        for value in (True, False, float('nan'), float('inf'), -1, 10**100,
                      'SYNTHETIC_PRIVATE', {'nested': 'SYNTHETIC_PRIVATE'}, None):
            with self.subTest(value=value):
                raw = replay()
                raw['position_snapshots'][0]['positions']['SYNTHETIC_PRIVATE_ALLY']['x'] = value
                self.assertNotIn('positions', snapshot(raw, at=10, team=0))

    def test_latest_invalid_sample_does_not_fall_back_to_old_position(self):
        raw = replay()
        raw['position_snapshots'].append({'t': 10.5, 'positions': {}})
        self.assertNotIn('positions', snapshot(raw, at=10.5, team=0))

    def test_nested_event_pos_never_reaches_coach(self):
        raw = replay()
        raw['timeline']['hero_events'][1]['pos'] = {'account': ['SYNTHETIC_PRIVATE']}
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(snapshot(raw, at=10, team=0)))

    def test_enemy_event_xy_never_bypasses_position_policy(self):
        raw = replay()
        raw['timeline']['hero_events'][1]['pos'] = [123, 234]
        self.assertTrue(all('pos' not in event for event in snapshot(raw, at=10, team=0)['events']))

    def test_unknown_event_names_are_not_public_identifiers(self):
        for value in ('SYNTHETIC_PRIVATE', 'x' * 10000, {'private': 'SYNTHETIC_PRIVATE'}, ['private']):
            with self.subTest(value=value):
                raw = replay()
                raw['timeline']['stat_events'] = [{'t': 1, 'name': value}]
                state = snapshot(raw, at=10, team=0)
                self.assertEqual(len(state['events']), 2)

    def test_upgrade_ids_without_a_qualified_catalog_are_omitted(self):
        for value in ('SYNTHETIC_PRIVATE', 'SyntheticTalent', 'x' * 10000,
                      {'private': 'SYNTHETIC_PRIVATE'}, ['private']):
            with self.subTest(value=value):
                raw = replay()
                raw['timeline']['hero_events'].append(
                    {'t': 1, 'type': 'upgrade', 'hero': 'Jaina', 'upgrade': value})
                self.assertEqual(len(snapshot(raw, at=10, team=0)['events']), 2)

    def test_hero_strings_require_membership_in_the_existing_catalog(self):
        for value in ('SYNTHETIC_PRIVATE', 'x' * 10000, {'private': 'SYNTHETIC_PRIVATE'}, ['private']):
            with self.subTest(value=value):
                raw = replay()
                raw['players'][0]['hero'] = value
                raw['timeline']['hero_events'][0]['hero'] = value
                state = snapshot(raw, at=10, team=0)
                self.assertEqual(state['composition']['allies'], [])
                self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(state))

    def test_map_requires_a_known_public_identifier(self):
        for value in ('SYNTHETIC_PRIVATE', {'private': 'SYNTHETIC_PRIVATE'}, ['private']):
            with self.subTest(value=value):
                raw = replay()
                raw['meta']['map'] = value
                self.assertNotIn('map', snapshot(raw, at=10, team=0)['meta'])

    def test_composition_overrides_are_typed_known_heroes(self):
        state = snapshot(replay(), at=10, team=0,
                         allies=['Jaina', {'private': 'SYNTHETIC_PRIVATE'}, 'SYNTHETIC_PRIVATE'])
        self.assertEqual(state['composition']['allies'], ['Jaina'])

    def test_unspecified_replay_team_is_not_silently_zero(self):
        with self.assertRaises(ValueError):
            snapshot(replay(), at=10)

    def test_observer_local_identity_cannot_establish_player_perspective(self):
        raw = replay()
        raw['local_player'] = {'id': 15, 'team': 0, 'hero': 'Jaina'}
        with self.assertRaises(ValueError):
            snapshot(raw, at=10, team=0)

    def test_conflicting_local_team_is_rejected(self):
        raw = replay()
        raw['local_player'] = {'id': 0, 'team': 0, 'hero': 'Jaina'}
        with self.assertRaises(ValueError):
            snapshot(raw, at=10, team=1)

    def test_bool_player_team_does_not_make_an_ally(self):
        raw = replay()
        raw['players'][0]['team'] = False
        self.assertEqual(snapshot(raw, at=10, team=0)['composition']['allies'], [])

    def test_duplicate_player_names_cannot_bind_a_position(self):
        raw = replay()
        raw['players'].append(dict(raw['players'][0], hero='Diablo'))
        self.assertNotIn('positions', snapshot(raw, at=10, team=0))

    def test_lifecycle_is_applied_in_time_order_not_input_order(self):
        raw = replay()
        raw['timeline']['hero_events'].insert(
            0, {'t': 9, 'type': 'death', 'player': 'SYNTHETIC_PRIVATE_ALLY'})
        state = snapshot(raw, at=10, team=0)
        self.assertFalse(state['heroes'][0]['alive'])
        self.assertNotIn('positions', state)

    def test_malformed_containers_are_unknown_not_templates(self):
        for field, value in (('timeline', []), ('position_snapshots', [None]),
                             ('position_snapshots', {'private': 'SYNTHETIC_PRIVATE'})):
            with self.subTest(field=field):
                raw = replay()
                raw[field] = value
                self.assertNotIn('positions', snapshot(raw, at=10, team=0))

    def test_invalid_event_times_cannot_reach_output(self):
        for value in (True, float('nan'), float('inf'), -1, None, 11):
            with self.subTest(value=value):
                raw = replay()
                raw['timeline']['stat_events'] = [{'t': value, 'name': 'TributeCollected'}]
                self.assertEqual(len(snapshot(raw, at=10, team=0)['events']), 2)

    def test_public_composition_levels_deaths_and_objective_are_preserved(self):
        raw = replay()
        raw['timeline']['stat_events'] = [
            {'t': 2, 'name': 'LevelUp', 'player': 'SYNTHETIC_PRIVATE_ALLY', 'data': {'Level': 7}},
            {'t': 3, 'name': 'TributeCollected', 'data': {'TeamID': 8192, 'Account': 'SYNTHETIC_PRIVATE'}}]
        raw['timeline']['hero_events'].append(
            {'t': 9, 'type': 'death', 'player': 'SYNTHETIC_PRIVATE_ENEMY'})
        state = snapshot(raw, at=10, team=0)
        self.assertEqual(state['composition'], {'allies': ['Jaina'], 'enemies': ['Arthas']})
        self.assertEqual(state['heroes'][0]['level'], 7)
        self.assertFalse(state['heroes'][1]['alive'])
        self.assertEqual(state['stats']['deaths_total'], 1)
        self.assertIn({'t': 3, 'name': 'TributeCollected', 'team': 1}, state['events'])
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(state))

    def test_prepared_prompt_with_fake_client_contains_only_projected_facts(self):
        from cerveau.brain import Coach

        class FakeClient:
            messages = None

            def chat(self, messages, **kwargs):
                self.messages = messages
                return {'choices': [{'message': {'content': '{"parler": false}'}}]}

        raw = replay()
        raw['timeline']['hero_events'][1]['pos'] = {'private': 'SYNTHETIC_PRIVATE_HIDDEN'}
        raw['timeline']['stat_events'] = [
            {'t': 11, 'name': 'SYNTHETIC_PRIVATE_FUTURE'},
            {'t': 2, 'name': 'SYNTHETIC_PRIVATE_PERSONAL'}]
        client = FakeClient()
        Coach(client).decide(snapshot(raw, at=10, team=0))
        prompt = json.dumps(client.messages)
        self.assertNotIn('SYNTHETIC_PRIVATE', prompt)
        state = json.loads(client.messages[1]['content'])['etat']
        self.assertTrue(all(h['team'] == 0 for h in state['positions']['heroes']))

    def test_equal_time_conflicting_samples_are_not_arbitrarily_selected(self):
        raw = replay()
        raw['position_snapshots'].append({'t': 10, 'positions': {}})
        self.assertNotIn('positions', snapshot(raw, at=10, team=0))

    def test_undated_sample_does_not_allow_fallback_to_a_dated_one(self):
        raw = replay()
        raw['position_snapshots'].append({'positions': {}})
        self.assertNotIn('positions', snapshot(raw, at=10, team=0))

    def test_undated_death_invalidates_current_life_and_position(self):
        raw = replay()
        raw['timeline']['hero_events'].append(
            {'type': 'death', 'player': 'SYNTHETIC_PRIVATE_ALLY'})
        state = snapshot(raw, at=10, team=0)
        self.assertNotIn('positions', state)
        self.assertNotIn('alive', state['heroes'][0])

    def test_conflicting_simultaneous_life_events_stay_unknown(self):
        raw = replay()
        raw['timeline']['hero_events'].extend([
            {'t': 9, 'type': 'death', 'player': 'SYNTHETIC_PRIVATE_ALLY'},
            {'t': 9, 'type': 'respawn', 'player': 'SYNTHETIC_PRIVATE_ALLY'}])
        state = snapshot(raw, at=10, team=0)
        self.assertNotIn('positions', state)
        self.assertNotIn('alive', state['heroes'][0])

    def test_invalid_hero_event_family_does_not_create_zero_deaths(self):
        raw = replay()
        raw['timeline']['hero_events'] = [None]
        self.assertNotIn('deaths_total', snapshot(raw, at=10, team=0)['stats'])

    def test_coherent_local_slot_resolves_unspecified_team(self):
        raw = replay()
        raw['local_player'] = {'id': 0, 'team': 0, 'hero': 'Jaina'}
        self.assertEqual(snapshot(raw, at=10)['ally_team'], 0)

    def test_exact_age_boundary_is_inclusive_without_interpolation(self):
        self.assertIn('positions', snapshot(replay(), at=11, team=0))
        self.assertNotIn('positions', snapshot(replay(), at=11.001, team=0))

    def test_event_position_sources_are_not_used_as_current_samples(self):
        raw = replay()
        raw['position_snapshots'] = []
        raw['timeline']['hero_events'][0]['pos'] = [100, 200]
        raw['positions'] = {'t': 10, 'heroes': [{'hero': 'Jaina', 'x': 100, 'y': 200}]}
        self.assertNotIn('positions', snapshot(raw, at=10, team=0))

    def test_time_and_team_parameters_are_strict(self):
        for at, team in ((None, 0), (True, 0), (float('nan'), 0), (901, 0), (10, True), (10, 2)):
            with self.subTest(at=at, team=team), self.assertRaises(ValueError):
                snapshot(replay(), at=at, team=team)

    def test_replay_detection_by_timeline_still_uses_the_safe_boundary(self):
        raw = replay()
        raw['meta']['source'] = {'private': 'SYNTHETIC_PRIVATE'}
        state = snapshot(raw, at=10, team=0)
        self.assertEqual(state['meta']['source'], 'replay')
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(state))

    def test_projection_does_not_modify_the_omniscient_source(self):
        raw = replay()
        original = copy.deepcopy(raw)
        state = snapshot(raw, at=10, team=0)
        state['heroes'][0]['hero'] = 'changed'
        self.assertEqual(raw, original)

    def test_unknown_lifecycle_type_cannot_establish_a_complete_death_counter(self):
        for kind in ('SYNTHETIC_PRIVATE', {'nested': 'SYNTHETIC_PRIVATE'}, True, None):
            with self.subTest(kind=kind):
                raw = replay()
                raw['timeline']['hero_events'].append({'t': 9, 'type': kind})
                state = snapshot(raw, at=10, team=0)
                self.assertNotIn('deaths_total', state['stats'])
                self.assertNotIn('positions', state)

    def test_malformed_level_and_team_values_are_not_copied(self):
        for value in (True, -1, 31, 10**100, float('nan'), float('inf'),
                      'SYNTHETIC_PRIVATE', {'nested': ['SYNTHETIC_PRIVATE']}):
            with self.subTest(value=value):
                raw = replay()
                raw['timeline']['stat_events'] = [
                    {'t': 1, 'name': 'LevelUp', 'data': {'Level': value, 'TeamID': value}}]
                event = snapshot(raw, at=10, team=0)['events'][-1]
                self.assertEqual(event, {'t': 1, 'name': 'LevelUp'})


if __name__ == '__main__':
    unittest.main()
