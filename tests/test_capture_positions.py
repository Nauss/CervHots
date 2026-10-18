import importlib.util
from pathlib import Path
import unittest
import tempfile
import subprocess
from unittest.mock import patch

from test_positions import PositionMemory

spec = importlib.util.spec_from_file_location('capture_positions', Path(__file__).resolve().parents[1]
                                             / 'etudes/rea/scripts/capture_positions.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class CollectorTests(unittest.TestCase):
    def test_same_core_closed_trace_roundtrip_and_png_brackets(self):
        m = PositionMemory()
        options = dict(native_profile=m.profile, position_profile=m.position_profile, hero_ids=m.hero_ids)
        row = capture.capture_frame(m, 'Volskaya', screenshot=lambda: {'file': 'SYNTHETIC.png'}, **options)
        self.assertLessEqual(row['before']['monotonic_after'], row['image']['monotonic_before'])
        self.assertLessEqual(row['image']['monotonic_after'], row['after']['monotonic_before'])
        for side in ('before', 'after'):
            original = row[side]
            self.assertEqual(original['positions']['status'], 'diagnostic_unreleased')
            replay = capture.ReplayTrace(m.module_base, original['reads'], original['core_monotonic'])
            repeated = capture.attempt(replay, 'Volskaya', **options)
            replay.finish()
            for key in ('heroes', 'local_id', 'team', 'native_session', 'mission_t_s'):
                self.assertEqual(original['positions'][key], repeated['positions'][key])
            self.assertLess(original['bytes_requested'], 2**20)
            xy = {0x900000 + i * 0x2f0 + 0x60 for i in range(5)}
            self.assertTrue(xy.isdisjoint({r['address'] for r in original['reads']}))

    def test_failure_and_exact_trace_are_preserved(self):
        m = PositionMemory(); m.pack(0x120000, 'I', 0x20)
        options = dict(native_profile=m.profile, position_profile=m.position_profile, hero_ids=m.hero_ids)
        original = capture.attempt(m, 'Volskaya', **options)
        replay = capture.ReplayTrace(m.module_base, original['reads'], original['core_monotonic'])
        repeated = capture.attempt(replay, 'Volskaya', **options)
        replay.finish()
        self.assertEqual(original['rejected'], 'perspective_observateur_ou_replay')
        self.assertEqual(original['rejected'], repeated['rejected'])

    def test_trace_missing_failed_read_order_or_bytes_never_fabricated(self):
        m = PositionMemory()
        trace = capture.TraceMemory(m)
        self.assertIsNone(trace.read_memory(0xdead0000, 4))
        self.assertIsNone(trace.reads[0]['hex'])
        replay = capture.ReplayTrace(m.module_base, trace.reads)
        with self.assertRaises(AssertionError): replay.read_memory(0xdead0001, 4)
        self.assertIsNone(replay.read_memory(0xdead0000, 4))
        replay.finish()
        with self.assertRaises(AssertionError): replay.read_memory(0xdead0000, 4)

    def test_wall_budget_rejection_replays_original_clock_not_machine_speed(self):
        m = PositionMemory(); times = iter([100.0, 100.2])
        m.positions_clock = lambda: next(times)
        options = dict(native_profile=m.profile, position_profile=m.position_profile, hero_ids=m.hero_ids)
        original = capture.attempt(m, 'Volskaya', **options)
        self.assertEqual(original['rejected'], 'fenetre_positions_trop_large')
        replay = capture.ReplayTrace(m.module_base, original['reads'], original['core_monotonic'])
        repeated = capture.attempt(replay, 'Volskaya', **options)
        replay.finish()
        self.assertEqual(repeated['rejected'], original['rejected'])

    def test_png_collision_does_not_overwrite_private_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'existing.png'
            path.write_bytes(b'ORIGINAL')
            class Image:
                def save(self, *args, **kwargs):
                    raise AssertionError('must not write')
            with self.assertRaises(FileExistsError): capture.save_png_exclusive(Image(), path)
            self.assertEqual(path.read_bytes(), b'ORIGINAL')

    def test_untracked_collector_is_not_a_frozen_source(self):
        with patch.object(capture.subprocess, 'check_output', side_effect=[
                'a' * 40, subprocess.CalledProcessError(128, ['git', 'show'])]), \
                patch.object(capture.subprocess, 'call', return_value=0):
            with self.assertRaises(subprocess.CalledProcessError): capture.frozen_sources('a' * 40)

    def test_no_foreground_game_skips_pixels_but_preserves_both_read_sides(self):
        m = PositionMemory()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'must-not-exist.png'
            def forbidden_grab(**kwargs): raise AssertionError('desktop capture forbidden')
            def screenshot():
                return capture.capture_game_image(path, lambda: {
                    'hwnd': 123, 'foreground': 456, 'rect': [1920, 0, 3200, 720]}, forbidden_grab)
            row = capture.capture_frame(m, 'Volskaya', screenshot=screenshot,
                    native_profile=m.profile, position_profile=m.position_profile, hero_ids=m.hero_ids)
            self.assertEqual(row['image']['skipped'], 'game_not_foreground')
            self.assertIn('positions', row['before'])
            self.assertIn('positions', row['after'])
            self.assertFalse(path.exists())

    def test_game_crop_multiscreen_and_focus_change_discards_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'game.png'
            state = {'hwnd': 123, 'foreground': 123, 'rect': [-1280, 0, 0, 720]}
            calls = []
            class Image:
                size = (1280, 720)
                def save(self, stream, format): stream.write(b'SYNTHETIC_PNG')
            def grab(**kwargs): calls.append(kwargs); return Image()
            result = capture.capture_game_image(path, lambda: dict(state), grab)
            self.assertEqual(result['hwnd'], 123)
            self.assertEqual(calls, [{'bbox': (-1280, 0, 0, 720), 'all_screens': True}])
            self.assertTrue(path.exists())
            path.unlink()
            states = iter([state, dict(state, foreground=456)])
            result = capture.capture_game_image(path, lambda: next(states), grab)
            self.assertEqual(result['skipped'], 'game_window_changed')
            self.assertFalse(path.exists())
