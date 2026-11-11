"""SYNTHETIC: bounded factual macro, never a free spatial instruction."""
import copy
import json
import unittest

import test_positions_collection as positions_tests
from cerveau.brain import Coach, Decision
from cerveau.runner import Pipeline


class Client:
    payload = {'intent': 'outnumbered', 'confiance': .9}
    def chat(self, messages, **kwargs):
        self.messages = messages
        return {'choices': [{'message': {'content': json.dumps(self.payload)}}]}


class MacroTests(unittest.TestCase):
    def setUp(self):
        self.transport = positions_tests.PositionsCollectionTests()
        self.transport.setUp()
        self.addCleanup(self.transport.doCleanups)
        m = self.transport.fixture.memory
        from hotstate.native import NativeReader
        reader = NativeReader(m, profile=m.profile)
        for native_slot in range(1, 11):
            unit = reader.unit_pointer(reader.value(reader.player_pointer(native_slot)+0x58), native_slot)
            m.pack(unit+0x39, 'B', 0)
        team = m.context['local_player']['team']
        slot = next(p['id'] for p in m.context['players'] if p['team'] == team)
        self.unit = reader.unit_pointer(reader.value(reader.player_pointer(slot+1)+0x58), slot+1)
        m.pack(self.unit+0x39, 'B', 6)
        self.state = self.transport.take()

    def test_macro_only_renders_known_intent_with_complete_facts(self):
        from cerveau.macro import MacroCoach, MacroPolicy, TEXT
        client = Client()
        coach = MacroCoach(client)
        decision = coach.decide(self.state)
        self.assertTrue(decision.parler)
        self.assertEqual(decision.texte, TEXT)
        sent = json.loads(client.messages[1]['content'])
        self.assertEqual(sent['etat']['positions'], self.state['positions'])
        self.assertEqual(sent['intentions'], ['outnumbered'])
        self.assertTrue(MacroPolicy().revalidate(self.state, self.state, decision))
        self.assertFalse(MacroPolicy().revalidate(self.state, self.state,
            Decision(True, 2, 'Allez au boss.', .9, 'calme', 'outnumbered', 'conseil')))

    def test_unknown_counts_or_non_live_never_enable_macro(self):
        from cerveau.macro import MacroCoach, facts
        for change in ('source', 'status', 'missing', 'bool_team', 'bool_id', 'alive_unknown',
                       'duplicate', 'local', 'build', 'composition', 'map_id', 'time'):
            state = copy.deepcopy(self.state)
            if change == 'source':
                state['meta']['source'] = 'replay'
            elif change == 'status':
                state['meta']['native_status'] = 'unknown'
            elif change == 'missing':
                state['heroes'].pop()
            elif change == 'bool_team':
                state['ally_team'] = True
            elif change == 'bool_id':
                state['heroes'][0]['id'] = False
            elif change == 'alive_unknown':
                state['heroes'][0]['alive'] = None
            elif change == 'duplicate':
                state['heroes'][0] = state['heroes'][1]
            elif change == 'local':
                state['local_player']['hero'] = 'wrong'
            elif change == 'build':
                state['meta']['native_build'] = 1
            elif change == 'composition':
                state['composition_complete'] = False
            elif change == 'map_id':
                state['meta']['map_id'] = 'unsupported'
            elif change == 'time':
                state['meta']['t_s'] = None
            with self.subTest(change=change):
                self.assertIsNone(facts(state))
                self.assertFalse(MacroCoach(Client()).decide(state).parler)

    def test_identity_and_exact_alive_vector_rechecked_but_movement_allowed(self):
        from cerveau.macro import MacroCoach, MacroPolicy
        policy = MacroPolicy()
        decision = MacroCoach(Client()).decide(self.state)
        moved = copy.deepcopy(self.state)
        moved['positions']['heroes'][0]['x'] += 1
        self.assertTrue(policy.revalidate(self.state, moved, decision))
        for change in ('match', 'team', 'map', 'composition', 'local', 'alive', 'unknown'):
            state = copy.deepcopy(self.state)
            if change == 'match':
                state['meta']['match_id'] = 'e'*64
            elif change == 'team':
                state['ally_team'] = 1-state['ally_team']
            elif change == 'map':
                state['meta']['map'] = 'another'
            elif change == 'composition':
                state['composition']['enemies'][0] = 'another'
            elif change == 'local':
                state['local_player']['id'] = (state['local_player']['id']+1)%10
            elif change == 'alive':
                dead = next(h for h in state['heroes'] if h['alive'] is False)
                dead['alive'] = True
            elif change == 'unknown':
                state['heroes'][0]['alive'] = None
            with self.subTest(change=change):
                self.assertFalse(policy.revalidate(self.state, state, decision))

    def test_optional_positions_do_not_supply_required_life_facts(self):
        from cerveau.macro import MacroCoach, MacroPolicy, facts
        coach = MacroCoach(Client())
        decision = coach.decide(self.state)
        coach.remember(decision)
        for change in ('missing', 'packet_missing', 'unknown', 'refused', 'rejected', 'not_selected', 'core'):
            state = copy.deepcopy(self.state)
            if change == 'missing':
                state.pop('positions_qualification')
            elif change == 'packet_missing':
                state.pop('positions')
            elif change == 'core':
                state['meta']['collection'] = 'core'
            else:
                state['positions_qualification']['status'] = change
            with self.subTest(change=change):
                self.assertIsNotNone(facts(state))
                self.assertTrue(MacroPolicy().revalidate(self.state, state, decision))
                state['heroes'][0]['alive'] = None
                self.assertIsNone(facts(state))
                self.assertFalse(coach.decide(state).parler)
                self.assertFalse(MacroPolicy().revalidate(self.state, state, decision))
                self.assertFalse(coach.observe(state))
                self.assertTrue(coach.episode_delivered)

    def test_llm_spatial_or_extra_intent_never_leaks_free_text(self):
        from cerveau.macro import MacroCoach
        client = Client()
        for payload in ({'intent': 'boss', 'confiance': .99},
                        {'intent': 'outnumbered', 'confiance': .9, 'texte': 'Allez au boss'},
                        {'intent': None, 'confiance': 0}, {'intent': 'outnumbered', 'confiance': .3},
                        {'intent': 'outnumbered', 'confiance': True}):
            client.payload = payload
            with self.subTest(payload=payload):
                self.assertFalse(MacroCoach(client).decide(self.state).parler)
        client.payload = {'intent': 'outnumbered', 'confiance': .9}
        coach = MacroCoach(client)
        decision = coach.decide(self.state)
        coach.remember(decision)
        self.assertEqual(coach.decide(self.state).raison, 'répétition')

    def test_actual_pipeline_macro_movement_versus_free_exact_key(self):
        from cerveau.macro import MacroCoach, MacroPolicy
        for macro in (True, False):
            self.transport.fixture.memory.position(7, 27, 47)
            calls, sent = [], []
            def read():
                if calls:
                    self.transport.fixture.memory.position(7, 80.25, 150.5)
                state = self.transport.take()
                calls.append(None)
                return state
            coach = MacroCoach(Client()) if macro else Coach(Client())
            if not macro:
                coach.client.payload = {'parler': True, 'priorite': 2, 'texte': 'Reculez.',
                    'confiance': .9, 'style': 'calme', 'sujet': 'outnumbered'}
            pipeline = Pipeline(coach, read, knowledge=lambda s: '',
                deliver=lambda d, s, valid: valid() and not sent.append(True),
                intent_policy=MacroPolicy() if macro else None)
            decision = pipeline.cycle()
            self.assertEqual(bool(sent), macro)
            self.assertEqual(decision.raison, 'conseil' if macro else 'périmé')

    def test_repeat_is_per_episode_and_unknown_cannot_rearm(self):
        from cerveau.macro import MacroCoach
        coach = MacroCoach(Client())
        first = coach.decide(self.state)
        coach.remember(first)
        self.assertEqual(coach.decide(self.state).raison, 'répétition')
        unknown = copy.deepcopy(self.state)
        unknown['heroes'][0]['alive'] = None
        coach.decide(unknown)
        self.assertEqual(coach.decide(self.state).raison, 'répétition')
        safe = copy.deepcopy(self.state)
        for hero in safe['heroes']:
            hero['alive'] = True
        coach.decide(safe)
        self.assertTrue(coach.decide(self.state).parler)
        self.assertEqual(len(coach.history), 1)  # Past journal/history isn't erased.

    def test_deterministic_macro_phrase_is_journaled_but_arbitrary_text_is_not(self):
        from cerveau.macro import MacroCoach, TEXT
        from cerveau.diagnostics import Journal
        rows = []
        journal = Journal(rows.append)
        journal.proposal(MacroCoach(Client()).decide(self.state))
        self.assertEqual(rows[0]['advice'], TEXT)
        self.assertEqual(journal.advice('SYNTHETIC_PRIVATE_IDENTITY'), '')


if __name__ == '__main__':
    unittest.main()
