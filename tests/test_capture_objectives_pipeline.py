"""Actual-code E2E instrumentation on synthetic fixtures, NOT live proof."""
import copy
import unittest
from unittest.mock import patch

import test_capture_visibility_pipeline as fixtures
from test_objectives import ObjectiveMemory
from hotstate.objectives import VolskayaObjective
from etudes.rea.scripts import capture_objectives_pipeline as capture


class ObjectivePipelineTests(unittest.TestCase):
    def fixture(self):
        helper=fixtures.PipelineCollectorTests()
        m,address,size,probe=helper.fixture()
        o=ObjectiveMemory();o.point(1,active=1,owner=1,state=1,progress=(22.5,0))
        return helper,m,address,size,probe,o.reader()._sample()

    def test_complete_reader_normalizer_key_and_exact_historical_replay(self):
        helper,m,address,size,probe,sample=self.fixture()
        a,b,c=helper.options(m)
        with a,b,c,patch.object(VolskayaObjective,'_sample',return_value=sample), \
                patch('cerveau.brain.Coach.decide',side_effect=AssertionError('coach forbidden')):
            row=capture.take_sample(fixtures.FixtureProcess(m),probe,address,size,
                                    native_profile=m.profile,clock=fixtures.FixtureClock())
            self.assertEqual(row['status'],'accepted',row.get('optional_objective_refusals'))
            self.assertEqual(row['normalized']['objective']['point']['victory_percent'],[50,0])
            self.assertIn('objective',row['tactical_key'])
            repeat=capture.replay_sample(row,m.module_base,probe,address,size,native_profile=m.profile)
            self.assertEqual(repeat['normalized'],row['normalized'])
            self.assertEqual(repeat['tactical_key'],row['tactical_key'])
        from hotstate.objectives import VALIDATED_MAPS
        self.assertEqual(VALIDATED_MAPS,('Volskaya',))

    def test_missing_objective_does_not_count_other_valid_fields_as_pass(self):
        helper,m,address,size,probe,sample=self.fixture()
        from hotstate.native import NativeUnavailable
        a,b,c=helper.options(m)
        with a,b,c,patch.object(VolskayaObjective,'_sample',side_effect=NativeUnavailable('synthetic_refused')):
            row=capture.take_sample(fixtures.FixtureProcess(m),probe,address,size,
                                    native_profile=m.profile,clock=fixtures.FixtureClock())
        self.assertEqual(row['status'],'rejected')
        self.assertEqual(row['rejected'],'objectif_pipeline_absent')
        self.assertEqual(row['optional_objective_refusals'],['synthetic_refused'])

    def test_cli_requires_candidate_consent_before_any_client(self):
        with patch.object(capture.shared,'ProcessBackend') as process:
            with self.assertRaises(SystemExit):capture.main(['--live'])
            process.assert_not_called()


if __name__=='__main__':
    unittest.main()
