"""Full actual pipeline on synthetic business fields, not a native recipe."""
import copy
import time
import unittest
from unittest.mock import patch
import test_capture_visibility_pipeline as fixtures
from hotstate.battlefield import VolskayaBattlefield,STRUCTURE_LAYOUT
from etudes.rea.scripts import capture_battlefield_pipeline as capture

class BattlefieldPipelineTests(unittest.TestCase):
    def sample(self,map_id,*,section,context,**options):
        common={'local_id':context['local_player']['id'],'team':context['local_player']['team'],
                'local_hero':context['local_player']['hero'],'native_session':context['perspective']['native_session'],
                'map_id':map_id,'section':section,'read_window_s':0.001,
                'mission_t_s':context['meta']['t_s'],'_acquired':time.monotonic()}
        if section in ('camps','combined'):
            rows=[{'index':i,'state_code':2,'enabled':True,'capture_enabled':False,'last_capture_team':'neutral',
                   'anchor_current_visible':None,'respawn':{'remaining_s':None},'defender_group':{'members':[]}}
                  for i in range(1,6)]
            common['camps']=rows
        if section in ('structures','combined'):
            common['structures']=[{'id':s['id'],'spec':s,'observation':None} for s in STRUCTURE_LAYOUT['structures']]
        return common

    def test_reader_native_boundary_normalizer_key_and_exact_replay(self):
        helper=fixtures.PipelineCollectorTests();m,address,size,probe=helper.fixture()
        a,b,c=helper.options(m)
        with a,b,c,patch.object(VolskayaBattlefield,'_observe',side_effect=self.sample) as observe,patch('cerveau.brain.Coach.decide',side_effect=AssertionError('coach forbidden')):
            row=capture.take_sample(fixtures.FixtureProcess(m),probe,address,size,native_profile=m.profile,clock=fixtures.FixtureClock())
            self.assertEqual(row['status'],'accepted',(row.get('rejected'),row.get('optional_battlefield_refusals')))
            self.assertEqual(len(row['normalized']['battlefield']['structures']['entries']),90)
            self.assertIn('battlefield',row['tactical_key'])
            self.assertEqual(observe.call_count,1)
            self.assertEqual(observe.call_args.kwargs['section'],'combined')
            self.assertEqual(row['raw']['battlefield']['camps']['read_window_s'],row['raw']['battlefield']['structures']['read_window_s'])
            from hotstate.acquisition import fresh
            camps,structures=(row['raw']['battlefield'][s] for s in ('camps','structures'))
            self.assertEqual(camps['section'],'camps');self.assertEqual(structures['section'],'structures')
            self.assertEqual(camps['acquisition']['monotonic_s'],structures['acquisition']['monotonic_s'])
            self.assertNotEqual(camps['acquisition']['seal'],structures['acquisition']['seal'])
            with patch('hotstate.acquisition.time.monotonic',return_value=camps['acquisition']['monotonic_s']+0.001):
                self.assertTrue(fresh(camps));self.assertTrue(fresh(structures))
                tampered=copy.deepcopy(camps);tampered['section']='structures'
                self.assertFalse(fresh(tampered))
                tampered=copy.deepcopy(structures);tampered['structures'][0]['state']='alive'
                self.assertFalse(fresh(tampered))
            repeat=capture.replay_sample(row,m.module_base,probe,address,size,native_profile=m.profile)
            self.assertEqual(repeat['normalized'],row['normalized'])
        from hotstate.battlefield import VALIDATED_MAPS
        self.assertEqual(VALIDATED_MAPS,())

    def test_cli_requires_explicit_private_candidate_before_process(self):
        with patch.object(capture.shared,'ProcessBackend') as process:
            with self.assertRaises(SystemExit):capture.main(['--live'])
            process.assert_not_called()

if __name__=='__main__':unittest.main()
