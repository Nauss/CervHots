"""Real consumer composition on literal memory fixtures, NOT a live recipe."""
import copy
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from test_native_context import TypedContextMemory
from test_dragon_contract import public_fixture
from hotstate.live import read_current
from hotstate.dragon import DragonObjective
from etudes.rea.scripts import capture_dragon_pipeline as capture


class DragonPipelineTests(unittest.TestCase):
    def options(self, m, sample=None):
        stack = ExitStack()
        stack.enter_context(patch('hotstate.positions.PROFILE', m.position_profile))
        stack.enter_context(patch('hotstate.match.PROFILE', m.match_profile))
        if sample is not None:
            stack.enter_context(patch.object(DragonObjective, '_sample', return_value=sample))
        return stack

    def probe(self, m):
        probe = m.probe()
        probe.map_resolver = lambda _: {'map_id':'DragonShire','map':'Dragon Shire'}
        return probe

    def test_actual_consumer_entrypoint_snapshot_normalizer_key_and_exact_replay(self):
        m = TypedContextMemory(); probe = self.probe(m)
        sample = public_fixture()
        with self.options(m,sample), patch.object(capture,'read_current',wraps=read_current) as called:
            row = capture.take_sample(m,probe,clock=lambda:100.0,native_profile=m.profile)
            self.assertEqual(row['status'],'accepted',row.get('rejected'))
            self.assertEqual(row['normalized']['objective']['map_id'],'DragonShire')
            self.assertEqual(row['execution_kind'],'fixture_or_historical_NOT_LIVE')
            self.assertIn('tactical_key',row)
            self.assertEqual(called.call_count,1)
            self.assertLessEqual(len(row['reads']),8192)
            self.assertLessEqual(row['bytes_requested'],1048576)
            self.assertNotIn('OWNER_TEST',str(row['normalized']))
            capture.replay_sample(row,m.module_base,probe,native_profile=m.profile)
            corrupted = copy.deepcopy(row); corrupted['reads'][0]['size'] += 1
            with self.assertRaises(AssertionError):
                capture.replay_sample(corrupted,m.module_base,probe,native_profile=m.profile)

    def test_absent_objective_is_not_a_full_acceptance(self):
        m = TypedContextMemory(); probe = self.probe(m)
        with self.options(m), patch.object(DragonObjective,'read',side_effect=ValueError('unsupported_fixture')):
            row = capture.take_sample(m,probe,clock=lambda:100.0,native_profile=m.profile)
            self.assertEqual(row['status'],'rejected')
        with self.options(m), patch.object(DragonObjective,'read',return_value=None):
            row = capture.take_sample(m,probe,clock=lambda:100.0,native_profile=m.profile)
            self.assertEqual(row['rejected'],'objectif_dragon_pipeline_absent')
            self.assertNotIn('objective',row['normalized'])

    def test_observer_and_non_atomic_source_refused(self):
        m = TypedContextMemory(); probe = self.probe(m)
        with self.options(m,public_fixture()):
            m.pack(0x120000,'I',0x20)
            row = capture.take_sample(m,probe,clock=lambda:100.0,native_profile=m.profile)
            self.assertEqual(row['status'],'rejected')
            m.recorded_non_atomic = True
            row = capture.take_sample(m,probe,clock=lambda:100.0,native_profile=m.profile)
            self.assertEqual(row['status'],'rejected')

    def test_preflight_and_input_guards_never_open_a_process(self):
        with patch.object(capture,'frozen_sources',return_value=('a'*40,{})), \
             patch.object(capture,'ProcessBackend') as process:
            self.assertEqual(capture.main(['--preflight','--expected-commit','a'*40]),0)
            for extra in ([],['--candidate-dragon','--duration','31'],['--candidate-dragon','--png']):
                with self.assertRaises(SystemExit):
                    capture.main(['--live','--expected-commit','a'*40,*extra])
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
