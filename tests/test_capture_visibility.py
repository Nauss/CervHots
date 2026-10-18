"""Synthetic exact ordered trace/playback, not a player recipe."""

import subprocess
import sys
import unittest

from test_current_visibility import VisibilityMemory
from etudes.rea.scripts.capture_visibility import attempt, capture_frame
from etudes.rea.scripts.capture_positions import ReplayTrace


class CaptureVisibilityTests(unittest.TestCase):
    def test_same_reader_exact_replay_consumes_every_read_and_clock(self):
        m = VisibilityMemory(); m.fog(True)
        options = dict(native_profile=m.profile, visibility_profile=m.visibility_profile,
                       position_profile=m.position_profile, match_profile=m.match_profile, hero_ids=m.hero_ids)
        row = attempt(m, 'Volskaya', **options)
        self.assertNotIn('rejected', row)
        self.assertLess(row['bytes_requested'], 2**20)
        replay = ReplayTrace(m.module_base, row['reads'], row['core_monotonic'])
        repeated = attempt(replay, 'Volskaya', **options)
        replay.finish()
        self.assertEqual(row['visibility'], repeated['visibility'])
        self.assertEqual([(r['address'], r['size'], r['hex']) for r in row['reads']],
                         [(r['address'], r['size'], r['hex']) for r in repeated['reads']])
        with self.assertRaises(AssertionError):
            attempt(ReplayTrace(m.module_base, row['reads'][1:]), 'Volskaya', **options)

    def test_brackets_image_and_preserves_visible_to_hidden_transition(self):
        m = VisibilityMemory(); m.fog(True)
        def image():
            m.fog(False)
            return {'skipped': 'synthetic_pixels_not_evidence'}
        row = capture_frame(m, 'Volskaya', screenshot=image, native_profile=m.profile,
                            visibility_profile=m.visibility_profile,
                            position_profile=m.position_profile, match_profile=m.match_profile, hero_ids=m.hero_ids)
        self.assertIs(row['before']['visibility']['heroes'][0]['visible'], True)
        self.assertIs(row['after']['visibility']['heroes'][0]['visible'], False)
        self.assertLessEqual(row['before']['monotonic_after'], row['image']['monotonic_before'])
        self.assertLessEqual(row['image']['monotonic_after'], row['after']['monotonic_before'])
        self.assertNotIn('acquisition', row['before']['visibility'])

    def test_observer_refusal_is_exactly_replayable(self):
        m = VisibilityMemory(); m.pack(0x120000, 'I', 0x20)
        options = dict(native_profile=m.profile, visibility_profile=m.visibility_profile,
                       position_profile=m.position_profile, match_profile=m.match_profile, hero_ids=m.hero_ids)
        row = attempt(m, 'Volskaya', **options)
        self.assertEqual(row['rejected'], 'perspective_observateur_ou_replay')
        replay = ReplayTrace(m.module_base, row['reads'], row['core_monotonic'])
        self.assertEqual(attempt(replay, 'Volskaya', **options)['rejected'], row['rejected'])
        replay.finish()

    def test_cli_help_and_missing_live_never_open_process(self):
        script = 'etudes/rea/scripts/capture_visibility.py'
        result = subprocess.run([sys.executable, script, '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--expected-commit', result.stdout)
        result = subprocess.run([sys.executable, script], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--live', result.stderr)


if __name__ == '__main__':
    unittest.main()
