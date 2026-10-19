"""Hermetic collector tests: synthetic bytes, no PID/GUI/client."""
import unittest
from unittest.mock import patch
from test_objectives import ObjectiveMemory
from etudes.rea.scripts.capture_objectives import attempt, capture_frame, replay_attempt, main


class CaptureObjectiveTests(unittest.TestCase):
    def profiles(self,m):
        return {'native_profile':m.profile,'objective_profile':m.p}

    def test_exact_readset_replay_and_screenshot_brackets(self):
        m=ObjectiveMemory()
        image_calls=[]
        def image():
            image_calls.append(True)
            return {'status':'synthetic_fixture_not_pixels'}
        with patch('hotstate.objectives.VolskayaObjective._perspective',return_value={}):
            row=capture_frame(m,screenshot=image,**self.profiles(m))
            for side in ('before','after'):
                self.assertEqual(row[side]['objective']['status'],'diagnostic_unreleased')
                replay_attempt(m.module_base,row[side],**self.profiles(m))
            self.assertEqual(image_calls,[True])
            self.assertLessEqual(row['before']['monotonic_after'],row['image']['monotonic_before'])
            self.assertLessEqual(row['image']['monotonic_after'],row['after']['monotonic_before'])
            row['before']['reads'][0]['size']+=1
            with self.assertRaises(AssertionError):replay_attempt(m.module_base,row['before'],**self.profiles(m))

    def test_rejection_has_ordered_trace_and_no_zero_fallback(self):
        m=ObjectiveMemory();m.pack(m.module_base+0x35C8CD9,'B',0)
        result=attempt(m,**self.profiles(m))
        self.assertIn('rejected',result)
        self.assertNotIn('objective',result)
        self.assertGreater(len(result['reads']),0)
        replay_attempt(m.module_base,result,**self.profiles(m))

    def test_preflight_never_opens_client(self):
        with patch('etudes.rea.scripts.capture_objectives.frozen_sources',return_value=('a'*40,{})),patch('etudes.rea.scripts.capture_objectives.ProcessBackend') as backend:
            self.assertEqual(main(['--preflight','--expected-commit','a'*40]),0)
            backend.assert_not_called()

    def test_bounds_rejected_before_client(self):
        with patch('etudes.rea.scripts.capture_objectives.ProcessBackend') as backend:
            for args in (['--live','--expected-commit','a'*40,'--duration','301'],['--live','--expected-commit','a'*40,'--interval','0']):
                with self.assertRaises(SystemExit):main(args)
            backend.assert_not_called()


if __name__=='__main__':unittest.main()
