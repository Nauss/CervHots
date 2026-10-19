"""Synthetic capture tests: no PID, screenshot or client access."""
import unittest
from unittest.mock import patch
from test_native import NativeMemory
from etudes.rea.scripts.capture_battlefield import attempt,capture_frame,replay_attempt,main

class BattlefieldCaptureTests(unittest.TestCase):
    def test_refusal_trace_is_strictly_replayable(self):
        m=NativeMemory();m.pack(m.module_base+0x35C8CD9,'B',0)
        row=attempt(m,native_profile=m.profile)
        self.assertIn('rejected',row)
        self.assertNotIn('battlefield',row)
        replay_attempt(m.module_base,row,native_profile=m.profile)
        row['reads'][0]['size']+=1
        with self.assertRaises(AssertionError):replay_attempt(m.module_base,row,native_profile=m.profile)

    def test_preflight_does_not_open_process(self):
        with patch('etudes.rea.scripts.capture_battlefield.frozen_sources',return_value=('a'*40,{})),patch('etudes.rea.scripts.capture_battlefield.ProcessBackend') as backend:
            self.assertEqual(main(['--preflight','--expected-commit','a'*40]),0)
            backend.assert_not_called()

    def test_brackets_contain_one_screenshot_between_attempts(self):
        m=NativeMemory();m.pack(m.module_base+0x35C8CD9,'B',0)
        calls=[]
        def image():
            calls.append(True)
            return {'status':'synthetic_not_pixels'}
        row=capture_frame(m,screenshot=image,native_profile=m.profile)
        self.assertEqual(calls,[True])
        self.assertLessEqual(row['before']['monotonic_after'],row['image']['monotonic_before'])
        self.assertLessEqual(row['image']['monotonic_after'],row['after']['monotonic_before'])

    def test_cli_bounds_are_rejected_before_process_access(self):
        with patch('etudes.rea.scripts.capture_battlefield.ProcessBackend') as backend:
            for flag,value in (('--duration','301'),('--duration','0'),('--interval','0')):
                with self.assertRaises(SystemExit):main(['--live','--expected-commit','a'*40,flag,value])
            backend.assert_not_called()

if __name__=='__main__':unittest.main()
