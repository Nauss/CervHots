"""Diagnostics are data minimisation, not replayable live authority."""
import copy
import json
import unittest

from cerveau.brain import Coach
from cerveau.runner import Pipeline
from hotstate.native import NativeUnavailable
from test_cerveau import Gateway


class ObservabilityTests(unittest.TestCase):
    def test_journal_rejects_hostile_advice_and_enemy_vitals(self):
        from cerveau.diagnostics import Journal
        records = []
        journal = Journal(records.append, private_labels=('Regroupez',))
        for text in ('Regroupez-vous avant le prochain combat.', 'Bearer sk-secret',
                     'token supersecret', '0x12345678', 'account#1234',
                     'https://private.test', 'PV 123456789', 'combat\nsecret',
                     'combat\u202esecret', 'combat secret@example.com'):
            self.assertEqual(journal.advice(text), '')
        state = {'meta': {'t_s': 12, 'match_id': 'secret'}, 'ally_team': 0,
                 'heroes': [{'id': 0, 'hero': 'private', 'team': 1,
                             'health': 12345, 'resource': 45678, 'level': 2}]}
        journal.observation(state)
        self.assertNotIn('health', json.dumps(records))
        self.assertNotIn('resource', json.dumps(records))
        self.assertEqual(records[0]['session'], journal.alias('session', 'secret'))

    def test_refusal_distinguishes_cycle_acquisition_from_freshness(self):
        from cerveau.diagnostics import Journal
        for fail_at, phase in ((1, 'cycle_acquisition'), (2, 'freshness')):
            records, calls = [], []
            def read():
                calls.append(None)
                if len(calls) == fail_at:
                    raise NativeUnavailable('lecture_native_dechiree')
                return {'meta': {}, 'stats': {}}
            journal = Journal(records.append)
            pipeline = Pipeline(Coach(Gateway()), read, knowledge=lambda s: '', journal=journal)
            with self.assertRaises(NativeUnavailable):
                pipeline.cycle()
            self.assertEqual(journal.phase, phase)
            self.assertFalse(pipeline.coach.history)

    def test_optional_refusal_survives_without_granting_optional_fields(self):
        from test_native import NativeMemory
        from hotstate.native import NativeReader
        from unittest.mock import patch
        memory = NativeMemory()
        memory.add_roster()
        with patch('hotstate.positions.AlliedPositions.read',
                   side_effect=NativeUnavailable('recette_positions_absente')):
            raw = NativeReader(memory, profile=memory.profile).read_state(
                memory.context, hero_ids=memory.hero_ids)
        self.assertNotIn('positions', raw)
        self.assertEqual(raw['meta']['optional_refusals']['positions'], 'recette_positions_absente')
        self.assertEqual(raw['meta']['native_status'], 'valide')

    def test_acquisition_reports_phase_budget_and_closed_refusal_without_raw_data(self):
        from hotstate.live import read_current
        from hotstate.native_context import NativeContextProbe
        from test_live_pipeline import Backend, Clock
        from unittest.mock import patch
        clock = Clock()
        records = []
        def fail(memory, *args, **kwargs):
            memory.read_memory(0x12340000, 8)
            raise NativeUnavailable('aucune_simulation_active')
        with patch('hotstate.live.memory_snapshot', side_effect=fail):
            with self.assertRaises(NativeUnavailable):
                read_current(Backend(), {}, context=NativeContextProbe('PRIVATE_PLAYER'),
                             clock=clock, observe=records.append)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['stage'], 'snapshot')
        self.assertEqual(records[0]['reads'], 1)
        self.assertEqual(records[0]['bytes_requested'], 8)
        self.assertEqual(records[0]['refusal']['category'], 'menu')
        self.assertNotIn('PRIVATE', json.dumps(records))
        self.assertNotIn('12340000', json.dumps(records))

    def test_stale_proposal_reports_safe_field_names_not_key_values(self):
        records = []
        state = {'meta': {'source': 'live', 'map': 'PRIVATE_MAP', 'match_id': 'PRIVATE_MATCH'},
                 'heroes': [{'id': 0, 'hero': 'PRIVATE_HERO', 'team': 0, 'alive': True, 'level': 1}],
                 'stats': {}}
        def read():
            return copy.deepcopy(state)
        gateway = Gateway()
        original = gateway.chat
        def chat(*args, **kwargs):
            state['heroes'][0]['level'] = 2
            return original(*args, **kwargs)
        gateway.chat = chat
        from cerveau.diagnostics import Journal
        pipeline = Pipeline(Coach(gateway), read, knowledge=lambda s: '',
                            journal=Journal(records.append, salt=b'test'), clock=lambda: 100)
        self.assertEqual(pipeline.cycle().raison, 'périmé')
        freshness = next(r for r in records if r['event'] == 'freshness')
        self.assertEqual(freshness['changed_fields'], ['heroes'])
        self.assertEqual(freshness['cause'], 'key_changed')
        self.assertEqual(next(r for r in records if r['event'] == 'proposal')['advice'],
                         'Regroupez-vous avant le prochain combat.')
        text = json.dumps(records)
        for private in ('PRIVATE_MAP', 'PRIVATE_MATCH', 'PRIVATE_HERO', 'match_id', 'perspective'):
            self.assertNotIn(private, text)
        self.assertEqual(len(pipeline.coach.history), 0)

    def test_unknown_exception_payload_never_becomes_a_code(self):
        from hotstate.diagnostics import refusal
        for hostile in ('Bearer sk-supersecret', '0x12345678', 'player#1234',
                        'lecture_native_dechiree\nsecret', {'secret': 'value'}):
            result = refusal(hostile)
            self.assertEqual(result, {'code': 'unknown_refusal', 'category': 'unknown'})
        self.assertEqual(refusal('aucune_simulation_active')['category'], 'menu')
        self.assertEqual(refusal('budget_pipeline_depasse')['category'], 'budget')
        self.assertEqual(refusal('lecture_native_dechiree')['category'], 'incoherence')


if __name__ == '__main__':
    unittest.main()
