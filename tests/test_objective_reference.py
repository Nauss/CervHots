"""SYNTHETIC timed screen transport; author never captures GUI."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


class TimedReferenceTests(unittest.TestCase):
    def test_operator_has_bounded_timed_clip_without_ocr(self):
        self.assertIsNotNone(importlib.util.find_spec('cerveau.objective_reference'),
                             'operator monotonic capture helper missing')
        from cerveau.objective_reference import record_clip
        from test_passive_session import Clock
        clock = Clock()
        def capture():
            clock.sleep(.01)
            return b'SYNTHETIC_NOT_A_REAL_IMAGE'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic.zip'
            result = record_clip(capture, path, lambda: False, 'a' * 32,
                                 duration=.2, interval=.05, clock=clock, sleep=clock.sleep)
            self.assertEqual(result['event'], 'hud_clip_closed')
            self.assertGreaterEqual(result['frames'], 3)
            with zipfile.ZipFile(path) as archive:
                index = json.loads(archive.read('index.json'))
                self.assertEqual(index['clock_basis'], 'host_monotonic')
                self.assertEqual(index['session_token'], 'a' * 32)
                self.assertEqual(index['transcription'], 'manual_required')
                self.assertGreater(index['max_gap_s'], 0)
                self.assertGreater(index['max_capture_s'], 0)
                for frame in index['frames']:
                    self.assertGreater(frame['finished_s'], frame['started_s'])
                    self.assertEqual(archive.read(frame['member']), b'SYNTHETIC_NOT_A_REAL_IMAGE')
            with self.assertRaises(FileExistsError):
                record_clip(capture, path, lambda: False, 'a' * 32,
                            duration=.2, interval=.05, clock=clock, sleep=clock.sleep)

    def test_stop_during_capture_discards_frame_and_bounds_are_validated(self):
        self.assertIsNotNone(importlib.util.find_spec('cerveau.objective_reference'))
        from cerveau.objective_reference import record_clip
        from test_passive_session import Clock
        clock = Clock(); stopped = [False]
        def capture():
            stopped[0] = True
            return b'SYNTHETIC'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'stopped.zip'
            result = record_clip(capture, path, lambda: stopped[0], 'a' * 32,
                                 duration=.2, interval=.05, clock=clock, sleep=clock.sleep)
            self.assertEqual(result['frames'], 0)
            self.assertEqual(result['reason'], 'stop_file')
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.namelist(), ['index.json'])
            for duration, interval, token in ((11, .05, 'a'*32), (.2, 0, 'a'*32), (.2, .05, 'PRIVATE')):
                with self.subTest(duration=duration, interval=interval), self.assertRaises(ValueError):
                    record_clip(capture, Path(tmp)/'invalid.zip', lambda: False, token,
                                duration=duration, interval=interval, clock=clock, sleep=clock.sleep)

    def test_preflight_and_preexisting_stop_do_not_capture_or_query_windows(self):
        import importlib
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        self.assertIsNotNone(importlib.util.find_spec('cerveau.objective_reference'))
        product = importlib.import_module('cerveau.objective_reference')
        self.assertTrue(callable(getattr(product, 'main', None)), 'capture helper CLI missing')
        with tempfile.TemporaryDirectory() as tmp:
            stop = Path(tmp)/'STOP'; stop.touch()
            with patch.object(product, 'game_capture', side_effect=AssertionError('no GUI')), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(product.main(['--record', '--stop-file', str(stop),
                                               '--output-file', str(Path(tmp)/'clip.zip'),
                                               '--session-token', 'a'*32, '--region', '0', '0', '100', '50']), 0)
                self.assertEqual(json.loads(out.getvalue())['reason'], 'stop_file')
                self.assertFalse((Path(tmp)/'clip.zip').exists())
            with patch.object(product, 'game_capture', side_effect=AssertionError('no GUI')), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(product.main([]), 0)
                result = json.loads(out.getvalue())
                self.assertTrue(result['ready'])
                self.assertFalse(result['memory_opened'])
                self.assertFalse(result['gui_captured'])

    def test_capture_failure_marks_clip_incomplete_and_releases_windows_resources(self):
        from cerveau import objective_reference as product
        import ctypes
        from unittest.mock import patch
        calls = []
        class Function:
            def __init__(self, name): self.name = name
            def __call__(self, *args):
                calls.append(self.name)
                if self.name == 'GetForegroundWindow': return 100
                if self.name == 'GetWindowThreadProcessId': args[1]._obj.value = 42; return 1
                if self.name == 'QueryFullProcessImageNameW':
                    args[2].value = 'C:/SYNTHETIC/HeroesOfTheStorm_x64.exe'; return 1
                if self.name == 'GetWindowRect':
                    r = args[1]._obj; r.left = r.top = 0; r.right = 1920; r.bottom = 1080; return 1
                if self.name == 'GetSystemMetrics': return 1920 if args[0] == 0 else 1080
                if self.name == 'GetDIBits': return args[3]
                return 1
        class DLL:
            def __getattr__(self, name):
                value = Function(name); setattr(self, name, value); return value
        with patch('ctypes.WinDLL', side_effect=lambda *a, **kw: DLL()):
            capture = product.game_capture([0, 0, 100, 50])
            data = capture()
            self.assertEqual(data[:2], b'BM')
            self.assertEqual(len(data), 100 * 50 * 4 + 54)
        self.assertEqual(calls.count('CloseHandle'), 1)
        for name in ('ReleaseDC', 'DeleteDC', 'DeleteObject'):
            self.assertEqual(calls.count(name), 1)
        from test_passive_session import Clock
        clock = Clock()
        def failed(): raise ValueError('PRIVATE')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'incomplete.zip'
            with self.assertRaises(ValueError):
                product.record_clip(failed, path, lambda: False, 'a'*32,
                                    duration=.2, interval=.05, clock=clock, sleep=clock.sleep)
            with zipfile.ZipFile(path) as archive:
                self.assertFalse(json.loads(archive.read('index.json')).get('complete', True))


if __name__ == '__main__':
    unittest.main()
