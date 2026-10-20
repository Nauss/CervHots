"""Real consumer composition using literal fixtures, NOT live recipe evidence."""
import copy
import time
import unittest
from unittest.mock import patch
import test_capture_dragon_pipeline as objective_tests
from test_dragon_contract import public_fixture
from test_native_context import TypedContextMemory
from hotstate.dragon_battlefield import DragonBattlefield, qualified_layout
from etudes.rea.scripts import capture_dragon_battlefield_pipeline as capture


class DragonBattlefieldPipelineTests(unittest.TestCase):
    def sample(self, context):
        local = context['local_player']
        return {'map_id':'DragonShire', 'match_id':context['meta']['match_id'],
                'local_id':local['id'], 'team':local['team'], 'local_hero':local['hero'],
                'native_session':context['perspective']['native_session'],
                'mission_t_s':context['meta']['t_s'], 'read_window_s':0.001, '_acquired':time.monotonic(),
                'camps':[{'index':i, 'anchor_current_visible':False} for i in range(1,6)],
                'structures':[{'spec':s, 'observation':None} for s in qualified_layout()['structures']]}

    def test_actual_entrypoint_normalizer_key_and_ordered_replay(self):
        harness = objective_tests.DragonPipelineTests(); memory = TypedContextMemory(); probe = harness.probe(memory)
        with harness.options(memory, public_fixture()), \
             patch.object(DragonBattlefield, '_observe', side_effect=self.sample):
            row = capture.take_sample(memory, probe, clock=lambda:100.0, native_profile=memory.profile)
            self.assertEqual(row['status'],'accepted',row.get('rejected'))
            self.assertEqual(len(row['normalized']['battlefield']['structures']['entries']),90)
            self.assertEqual(len(row['normalized']['battlefield']['camps']['entries']),5)
            self.assertIn('tactical_key',row)
            self.assertEqual(row['execution_kind'],'fixture_or_historical_NOT_LIVE')
            capture.replay_sample(row, memory.module_base, probe, native_profile=memory.profile)
            corrupt = copy.deepcopy(row); corrupt['reads'][0]['size'] += 1
            with self.assertRaises(AssertionError):
                capture.replay_sample(corrupt, memory.module_base, probe, native_profile=memory.profile)

    def test_objective_only_is_not_a_battlefield_full_acceptance(self):
        harness = objective_tests.DragonPipelineTests(); memory = TypedContextMemory()
        with harness.options(memory, public_fixture()), patch.object(DragonBattlefield, 'read', return_value=None):
            row = capture.take_sample(memory, harness.probe(memory), clock=lambda:100.0, native_profile=memory.profile)
        self.assertEqual(row['status'],'rejected')
        self.assertEqual(row['rejected'],'champ_bataille_dragon_pipeline_absent')

    def test_one_missing_family_rejects_even_with_objective_and_key(self):
        harness = objective_tests.DragonPipelineTests(); memory = TypedContextMemory()
        original = DragonBattlefield.read
        def incomplete(reader, context, **options):
            packets = original(reader, context, **options)
            packets.pop('structures')
            return packets
        with harness.options(memory, public_fixture()), \
             patch.object(DragonBattlefield, '_observe', side_effect=self.sample), \
             patch.object(DragonBattlefield, 'read', incomplete):
            row = capture.take_sample(memory, harness.probe(memory), clock=lambda:100.0, native_profile=memory.profile)
        self.assertEqual(row['status'],'rejected')
        self.assertEqual(row['rejected'],'champ_bataille_dragon_pipeline_absent')

    def test_preflight_never_opens_process_and_cli_explicit_optin(self):
        with patch.object(capture.objective_capture,'frozen_sources',return_value=('a'*40,{})), \
             patch.object(capture,'ProcessBackend') as process:
            self.assertEqual(capture.main(['--preflight','--expected-commit','a'*40]),0)
            for extra in ([], ['--candidate-battlefield','--duration','31'], ['--candidate-battlefield','--png']):
                with self.assertRaises(SystemExit):
                    capture.main(['--live','--expected-commit','a'*40,*extra])
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
