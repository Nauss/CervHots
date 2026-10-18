"""Hermetic audit regressions; no private memory/PNG fixture in Git."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_capture_positions import capture
from test_positions import PositionMemory

spec = importlib.util.spec_from_file_location('replay_positions', Path(__file__).resolve().parents[1]
                                             / 'etudes/rea/scripts/replay_positions.py')
replay = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'capture_positions': capture}):
    spec.loader.exec_module(replay)


class RecipeReplayTests(unittest.TestCase):
    def fixture(self):
        m = PositionMemory()
        options = dict(native_profile=m.profile, position_profile=m.position_profile, hero_ids=m.hero_ids)
        rows = []
        for sequence in range(2):
            if sequence:
                m.pack(0x120000, 'I', 0x20)
            row = capture.capture_frame(m, 'Volskaya', **options)
            row['sequence'] = sequence
            rows.append(row)
        header = {'kind': 'targeted_allied_positions', 'status': 'diagnostic_unreleased',
                  'map_id_requested': 'Volskaya', 'module_base': m.module_base, 'commit': 'a' * 40}
        return [header, *rows], options

    def run_audit(self, rows, options):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.jsonl'
            path.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')
            return replay.audit(path, public=True, options=options)

    def test_diagnostic_and_released_core_preserve_acceptances_and_refusals(self):
        rows, options = self.fixture()
        result = self.run_audit(rows, options)
        self.assertEqual(result['counts']['public_core_replayed_attempts'], 4)
        self.assertEqual(result['counts']['accepted'], 2)
        self.assertEqual(result['counts']['rejection:perspective_observateur_ou_replay'], 2)
        self.assertTrue(result['historical_not_fresh_live'])

    def test_corrupt_order_clock_or_claimed_output_fails_audit(self):
        original, options = self.fixture()
        for change in ('order', 'clock', 'output'):
            rows = copy.deepcopy(original)
            if change == 'order':
                rows[1]['before']['reads'][0]['order'] += 1
            elif change == 'clock':
                rows[1]['before']['core_monotonic'][1] += 1
            else:
                rows[1]['before']['positions']['heroes'][0]['x'] += 1
            with self.subTest(change=change), self.assertRaises(AssertionError):
                self.run_audit(rows, options)
