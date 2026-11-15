"""SYNTHETIC latency regressions: real orchestration, no game/API/audio."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest

from cerveau.brain import Coach
from cerveau.playtest import run_session
from test_cerveau import Gateway



class ReactiveSessionTests(unittest.TestCase):
    def setUp(self):
        from test_playtest_macro import MacroTests
        fixture = MacroTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.state = copy.deepcopy(fixture.state)
        self.now = 0.

    def exercise(self, *, mutate=None, mutate_at=3, gateway=None, mode='reactive'):
        rows, sends, knowledge_calls = [], [], []
        gateway = gateway or Gateway()
        owner = self
        class Source:
            reads = 0
            closed = False
            def read(self, observe):
                self.reads += 1
                state = copy.deepcopy(owner.state)
                if mutate and self.reads >= mutate_at:
                    mutate(state)
                return state
            def close(self):
                self.closed = True
        source = Source()
        def sleep(seconds):
            self.now += seconds
        def knowledge(state):
            knowledge_calls.append(True)
            return 'SYNTHETIC KB'
        def deliver(decision, speech, valid):
            if valid():
                sends.append(decision)
                return True
            return False
        args = SimpleNamespace(max_seconds=12, interval=30, coach_mode=mode,
            collection='positions', mumble=True, wav=False, stop_file=Path('UNUSED'))
        result = run_session(args, lambda: source, lambda: Coach(gateway), rows.append,
            stopped=lambda: False, clock=lambda: self.now, sleep=sleep, knowledge=knowledge,
            synthesize=lambda d: b'SYNTHETIC_NOT_AUDIO', deliver=deliver)
        self.assertTrue(source.closed)
        return result, rows, sends, gateway.calls, knowledge_calls

    def test_controlled_warning_survives_irrelevant_changes_without_waiting_for_api(self):
        def movement_and_vitals(state):
            state['positions']['heroes'][0]['x'] += 1
            for hero in state['heroes']:
                hero.update(health=1, resource=0, respawn_s=7, level=19)
        result, rows, sends, calls, knowledge = self.exercise(mutate=movement_and_vitals)
        self.assertEqual(result['mumble_sent'], 1)
        self.assertEqual(result['expired'], 0)
        self.assertEqual(calls, [])
        self.assertEqual(knowledge, [])
        from cerveau.macro import TEXT
        self.assertEqual(sends[0].texte, TEXT)
        self.assertEqual(sends[0].intent, 'outnumbered')

    def test_all_supported_maps_get_nonspatial_warning_without_broadening_player_recipes(self):
        from hotstate.position_maps import SUPPORTED_MAPS, PLAYER_RECIPE_MAPS
        from cerveau.macro import facts
        for map_id in SUPPORTED_MAPS:
            with self.subTest(map_id=map_id):
                self.now = 0.
                self.state['meta']['map_id'] = map_id
                result, _, sends, calls, _ = self.exercise()
                self.assertEqual((result['mumble_sent'], len(sends), calls), (1, 1, []))
                if map_id != 'Volskaya':
                    self.assertIsNone(facts(self.state))  # Legacy macro still narrow.
        self.assertEqual(PLAYER_RECIPE_MAPS, ('Volskaya',))

    def test_respawn_or_changed_identity_cancels_even_if_still_outnumbered(self):
        changes = [(lambda s:s['heroes'][0].update(alive=not s['heroes'][0]['alive']), 'session_limit'),
                   (lambda s:s['meta'].update(match_id='e'*64), 'session_changed'),
                   (lambda s:s.update(composition_complete=False), 'session_limit')]
        for change, reason in changes:
            for at in (3, 4, 5):  # Before TTS, after TTS, at the actual enqueue gate.
                with self.subTest(reason=reason, at=at):
                    self.now = 0.
                    result, _, sends, calls, _ = self.exercise(mutate=change, mutate_at=at)
                    self.assertEqual((result['reason'], sends, calls), (reason, [], []))
                    self.assertEqual(result['expired'] + result['not_sent'], int(reason != 'session_changed'))

    def test_free_fallback_keeps_exact_position_key_and_never_trusts_model_intent(self):
        for row in self.state['heroes']:
            row['alive'] = True
            row['level'] = 10
        gateway = Gateway({**Gateway().answer, 'intent':'outnumbered'})
        result, _, sends, calls, knowledge = self.exercise(gateway=gateway,
            mutate=lambda s:s['positions']['heroes'][0].update(x=999.))
        self.assertEqual((result['expired'], sends, len(calls), len(knowledge)), (1, [], 1, 1))

    def test_network_free_warning_does_not_masquerade_as_an_api_request(self):
        result, rows, _, _, _ = self.exercise()
        self.assertEqual(result['coach_attempts'], 0)
        self.assertEqual(result['fact_decisions'], 1)
        self.assertFalse(any(r['event']=='coach_response' for r in rows))
        self.assertTrue(any(r['event']=='intent_revalidation' and r['accepted'] for r in rows))

    def test_native_map_id_without_display_name_keeps_instant_warning(self):
        from hotstate.position_maps import SUPPORTED_MAPS
        for map_id in SUPPORTED_MAPS:
            for name in (None, ''):
                with self.subTest(map_id=map_id, display_name=name):
                    self.now = 0.
                    self.state['meta']['map_id'] = map_id
                    self.state['meta'].pop('map', None)
                    if name is not None:
                        self.state['meta']['map'] = name
                    result, _, sends, calls, knowledge = self.exercise(
                        mutate=lambda s:s['positions']['heroes'][0].update(x=999.))
                    self.assertEqual((result['mumble_sent'], len(sends), calls, knowledge),
                                     (1, 1, [], []))

    def test_default_cli_is_reactive_but_explicit_legacy_modes_remain(self):
        from cerveau.playtest import parser
        self.assertEqual(parser().parse_args([]).coach_mode, 'reactive')
        for mode in ('free', 'macro', 'reactive'):
            self.assertEqual(parser().parse_args(['--coach-mode',mode]).coach_mode, mode)

    def test_two_level_deficit_is_instant_without_position_or_api_dependency(self):
        self.state['meta'].pop('map', None)
        self.state['meta']['map_id'] = 'Shrines'
        for hero in self.state['heroes']:
            hero['alive'] = True
            hero['level'] = 8 if hero['team'] == self.state['ally_team'] else 10
        result, _, sends, calls, knowledge = self.exercise(
            mutate=lambda s:s['positions']['heroes'][0].update(x=999.))
        self.assertEqual((result['mumble_sent'], calls, knowledge), (1, [], []))
        self.assertEqual(sends[0].intent, 'level_disadvantage')
        self.assertIn("deux niveaux", sends[0].texte)


class ReactiveLevelTests(unittest.TestCase):
    def setUp(self):
        from test_playtest_macro import MacroTests
        from cerveau.reactive import ReactiveCoach, ReactivePolicy
        fixture = MacroTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.state = copy.deepcopy(fixture.state)
        self.state['meta'].pop('map', None)
        self.state['meta']['map_id'] = 'Shrines'
        for hero in self.state['heroes']:
            hero['alive'] = True
            hero['level'] = 8 if hero['team'] == self.state['ally_team'] else 10
        self.coach = ReactiveCoach(Gateway(), 'synthetic')
        self.policy = ReactivePolicy()
        self.decision = self.coach.prepare(self.state)

    def test_missing_or_inconsistent_levels_fail_closed(self):
        from cerveau.reactive import level_facts
        for value in (None, True, 0, 31, 8., '8', 7):
            with self.subTest(value=value):
                changed = copy.deepcopy(self.state)
                changed['heroes'][0]['level'] = value
                self.assertIsNone(level_facts(changed))
                self.assertIsNone(self.coach.prepare(changed))

    def test_level_alert_does_not_claim_unobserved_talents(self):
        self.assertNotIn('talent', self.decision.texte)
        self.assertNotIn('héroïque', self.decision.texte)
        self.assertLessEqual(len(self.decision.texte.split()), 25)

    def test_unknown_facts_do_not_rearm_a_delivered_warning(self):
        self.coach.remember(self.decision)
        unknown = copy.deepcopy(self.state)
        unknown['heroes'][0].pop('level')
        self.coach.observe(unknown)
        self.assertEqual(self.coach.prepare(self.state).raison, 'répétition')

    def test_retry_until_delivered_then_rearm_only_after_known_safe_state(self):
        self.assertTrue(self.coach.prepare(self.state).parler)
        self.assertTrue(self.coach.prepare(self.state).parler)
        self.coach.remember(self.decision)
        self.assertEqual(self.coach.prepare(self.state).raison, 'répétition')
        safe = copy.deepcopy(self.state)
        for hero in safe['heroes']:
            hero['level'] = 10
        self.assertTrue(self.coach.observe(safe))
        self.assertTrue(self.coach.prepare(self.state).parler)

    def test_life_level_identity_or_clock_changes_reject_warning(self):
        mutations = (
            lambda s:s['heroes'][0].update(alive=False),
            lambda s:s['heroes'][0].update(level=9),
            lambda s:s['meta'].update(match_id='b'*64),
            lambda s:s['meta'].update(map_id='Volskaya'),
            lambda s:s['meta'].update(t_s=s['meta']['t_s']-1),
            lambda s:s.update(composition_complete=False),
        )
        for mutate in mutations:
            changed = copy.deepcopy(self.state)
            mutate(changed)
            self.assertFalse(self.policy.revalidate(self.state, changed, self.decision))

    def test_only_exact_code_rendered_level_text_can_use_looser_position_key(self):
        from dataclasses import replace
        for decision in (replace(self.decision, texte='Attaquez le boss.'),
                         replace(self.decision, confiance=True),
                         replace(self.decision, confiance=float('nan')),
                         replace(self.decision, sujet='arbitrary')):
            self.assertFalse(self.policy.revalidate(self.state, self.state, decision))


class ReactivePolicyTests(unittest.TestCase):
    def setUp(self):
        from test_playtest_macro import MacroTests
        fixture = MacroTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.state = copy.deepcopy(fixture.state)
        from cerveau.reactive import ReactiveCoach, ReactivePolicy
        self.gateway = Gateway()
        self.coach = ReactiveCoach(self.gateway)
        self.policy = ReactivePolicy()

    def test_code_intent_cannot_authorize_arbitrary_text(self):
        from dataclasses import replace
        decision = self.coach.prepare(self.state)
        for change in ({'texte':'Avancez seul.'}, {'sujet':'forged'}, {'intent':'unknown'},
                       {'style':'urgent'}, {'priorite':3}, {'confiance':float('nan')}):
            self.assertFalse(self.policy.revalidate(self.state, self.state, replace(decision,**change)))

    def test_current_clock_must_not_rewind(self):
        decision = self.coach.prepare(self.state)
        after = copy.deepcopy(self.state)
        after['meta']['t_s'] = self.state['meta']['t_s'] - 1
        self.assertFalse(self.policy.revalidate(self.state, after, decision))

    def test_delivery_only_episode_ledger_rearms_on_complete_safe_observation_on_other_map(self):
        self.state['meta']['map_id'] = 'DragonShire'
        decision = self.coach.prepare(self.state)
        self.assertIsNotNone(decision)
        self.assertTrue(self.coach.prepare(self.state).parler)  # Not delivered yet.
        self.coach.remember(decision)
        self.assertFalse(self.coach.prepare(self.state).parler)
        unknown = copy.deepcopy(self.state)
        unknown['heroes'].pop()
        self.coach.observe(unknown)
        self.assertFalse(self.coach.prepare(self.state).parler)
        safe = copy.deepcopy(self.state)
        for hero in safe['heroes']:
            hero['alive'] = True
        self.assertTrue(self.coach.observe(safe))
        self.assertTrue(self.coach.prepare(self.state).parler)

    def test_model_authored_copy_cannot_mark_controlled_episode_delivered(self):
        from dataclasses import replace
        controlled = self.coach.prepare(self.state)
        self.coach.remember(replace(controlled, intent=None))
        self.assertTrue(self.coach.prepare(self.state).parler)

    def test_malformed_facts_never_enter_fast_path(self):
        for mutation in (lambda s:s['meta'].update(map_id='UnknownMap'),
                         lambda s:s['meta'].update(native_build=0),
                         lambda s:s['meta'].update(source='dump'),
                         lambda s:s['local_player'].update(team=not s['ally_team']),
                         lambda s:s['heroes'][0].update(alive=1),
                         lambda s:s['heroes'].pop()):
            bad = copy.deepcopy(self.state)
            mutation(bad)
            self.assertIsNone(self.coach.prepare(bad))


if __name__ == '__main__':
    unittest.main()
