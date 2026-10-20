"""Collector boundaries, no game/process/network/KB required."""
import io
import copy
import unittest
from contextlib import redirect_stdout, ExitStack, contextmanager, redirect_stderr
from unittest.mock import patch
from etudes.rea.scripts import capture_talents as c
import test_talents as primitive
from test_native_context import TypedContextMemory
from test_capture_visibility_pipeline import FixtureClock
from hotstate import talents


class TalentCollectorTests(unittest.TestCase):
    def fixture(self):
        m = TypedContextMemory()
        tree, _ = primitive.TalentSelectionTests().tree_fixture()
        for address, byte in tree.data.items():
            if address < tree.base:
                m.put(address, bytes([byte]))
        m.pack(0x606050, 'Q', 0x30000)
        m.pack(m.module_base+0x3388b18, 'Q', 0x40000)
        m.pack(0x30030, 'Q', 0xb0000)
        m.pack(0xb0018, 'II', len('Ragnaros')<<2, 0)
        m.put(0xb0020, b'Ragnaros')
        for tier in range(32):
            m.pack(m.module_base+0x3677a30+6*128+tier*4, 'I', 0xffffffff)
        m.pack(m.module_base+0x3677a30+6*128+4, 'I', 0)
        return m

    @contextmanager
    def options(self, m):
        with ExitStack() as stack:
            stack.enter_context(patch('hotstate.talents.PROFILE',
                dict(talents.PROFILE, signatures=m.profile['signatures']*6)))
            stack.enter_context(patch('hotstate.positions.PROFILE', m.position_profile))
            stack.enter_context(patch('hotstate.match.PROFILE', m.match_profile))
            yield

    def test_full_bound_acquisition_strict_replay_with_no_map_cache_dependency(self):
        m = self.fixture()
        with self.options(m):
            row = c.attempt(m, m.probe(), native_profile=m.profile, clock=FixtureClock())
            self.assertEqual(row['status'], 'accepted_diagnostic_NOT_PRODUCT', row.get('reason'))
            self.assertEqual(row['tree']['selected'][0]['slot'], 2)
            probe = m.probe()
            probe.map_resolver = lambda handles: self.fail('external map lookup during replay')
            again = c.replay_attempt(m.module_base, row, probe, native_profile=m.profile)
            self.assertEqual(again['tree'], row['tree'])

            for mutation in ('extra_read', 'missing_read', 'altered_result', 'missing_tick'):
                bad = copy.deepcopy(row)
                if mutation == 'extra_read':
                    bad['reads'].append(bad['reads'][-1])
                elif mutation == 'missing_read':
                    bad['reads'].pop()
                elif mutation == 'altered_result':
                    bad['tree']['selected'] = []
                else:
                    bad['core_monotonic'].pop()
                with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                    c.replay_attempt(m.module_base, bad, probe, native_profile=m.profile)

    def test_observer_absent_choice_non_atomic_and_generation_rejected(self):
        for mutation in ('observer', 'non_atomic', 'generation', 'unknown_id', 'reset'):
            m = self.fixture()
            if mutation == 'observer':
                m.pack(0x120000, 'I', 0x20)
            elif mutation == 'non_atomic':
                m.recorded_non_atomic = True
            elif mutation == 'generation':
                m.pack(0x900000+5*0x2f0+0x10, 'I', 0)
            else:
                m.pack(m.module_base+0x3677a30+6*128+4, 'I',
                    123 if mutation == 'unknown_id' else 0xffffffff)
            with self.subTest(mutation=mutation), self.options(m):
                row = c.attempt(m, m.probe(), native_profile=m.profile, clock=FixtureClock())
                if mutation == 'reset':
                    self.assertEqual(row['status'], 'accepted_diagnostic_NOT_PRODUCT')
                    self.assertEqual(row['tree']['selected'], [])
                else:
                    self.assertEqual(row['status'], 'rejected')
                    self.assertNotIn('tree', row)

    def test_preflight_never_opens_process(self):
        with patch.object(c, 'frozen_sources', return_value=('a'*40, {})), \
                patch.object(c, 'ProcessBackend', side_effect=AssertionError('live opened')), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(c.main(['--preflight', '--expected-commit', 'a'*40]), 0)
        self.assertIn('"live_opened": false', output.getvalue())

    def test_duration_bound_before_freeze_or_process(self):
        with patch.object(c, 'frozen_sources', side_effect=AssertionError('freeze')), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            c.main(['--preflight', '--expected-commit', 'a'*40, '--duration', '31'])


if __name__ == '__main__':
    unittest.main()
