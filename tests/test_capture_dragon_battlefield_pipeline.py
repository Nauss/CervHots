"""Real consumer composition using literal fixtures, NOT live recipe evidence."""
import copy
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_capture_dragon_battlefield as battlefield_tests
import test_capture_dragon_pipeline as objective_tests
from test_dragon_contract import public_fixture
from test_native_context import TypedContextMemory
from hotstate.dragon_battlefield import DragonBattlefield, qualified_layout
from hotstate.native import NativeUnavailable
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

    def test_qualified_path_never_overrides_either_public_gate(self):
        harness = objective_tests.DragonPipelineTests(); memory = TypedContextMemory(); probe = harness.probe(memory)
        with harness.options(memory, public_fixture()), \
             patch('hotstate.dragon_battlefield.VALIDATED_MAPS',('DragonShire',)), \
             patch('hotstate.dragon.VALIDATED_MAPS',('DragonShire',)), \
             patch.object(DragonBattlefield,'_observe',side_effect=self.sample), \
             patch.object(capture,'patch',wraps=patch) as battlefield_spy, \
             patch.object(capture.objective_capture,'patch',wraps=patch) as objective_spy:
            row = capture.take_sample(memory,probe,clock=lambda:100.0,native_profile=memory.profile,qualified=True)
            self.assertEqual(row['status'],'accepted',row.get('rejected'))
            self.assertIs(row['candidate_override'],False)
            self.assertEqual(row['kind'],'qualified_full_dragon_battlefield_NOT_RELEASE')
            capture.replay_sample(row,memory.module_base,probe,native_profile=memory.profile)
            for spy in (battlefield_spy,objective_spy):
                self.assertFalse(any('VALIDATED_MAPS' in str(call.args[0]) for call in spy.call_args_list))
                self.assertFalse(any(len(call.args)>1 and call.args[1]=='VALIDATED_MAPS'
                                     for call in spy.object.call_args_list))

    def test_qualified_path_requires_both_real_gates_before_any_read(self):
        for battlefield,objective in (((),('DragonShire',)),(('DragonShire',),())):
            with self.subTest(battlefield=battlefield,objective=objective), \
                 patch('hotstate.dragon_battlefield.VALIDATED_MAPS',battlefield), \
                 patch('hotstate.dragon.VALIDATED_MAPS',objective), \
                 patch.object(capture,'BASE_SAMPLE') as base:
                with self.assertRaisesRegex(NativeUnavailable,'portes_qualifiees_dragon_absentes'):
                    capture.take_sample(None,None,qualified=True)
                base.assert_not_called()

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
             patch.dict(sys.modules, {'mpyq': SimpleNamespace(MPQArchive=object, __file__=__file__)}), \
             patch('importlib.metadata.version', return_value='fixture-not-installed'), \
             patch.object(capture,'ProcessBackend') as process:
            self.assertEqual(capture.main(['--preflight','--expected-commit','a'*40]),0)
            for extra in ([], ['--candidate-battlefield','--duration','31'], ['--candidate-battlefield','--png']):
                with self.assertRaises(SystemExit):
                    capture.main(['--live','--expected-commit','a'*40,*extra])
            process.assert_not_called()


class DragonBattlefieldPipelineDependencyTests(battlefield_tests.DragonBattlefieldDependencyTests):
    collector = capture
    freezer = capture.objective_capture
    clock_owner = capture
    clock_name = 'REAL_CLOCK'
    extra_args = ('--candidate-battlefield',)


if __name__ == '__main__':
    unittest.main()
