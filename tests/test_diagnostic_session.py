import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from cerveau.brain import Coach
from hotstate.native import NativeUnavailable
from test_cerveau import Gateway


class SessionTests(unittest.TestCase):
    def run_fixture(self, read, *, stop=False, gateway=None, seconds=1):
        from cerveau.diagnostic_session import run_session
        self.now = 0.0
        self.closed = []
        self.records = []
        self.opens = []
        with tempfile.TemporaryDirectory() as tmp:
            stop_file = Path(tmp) / 'STOP'
            if stop:
                stop_file.touch()
            args = SimpleNamespace(stop_file=stop_file, max_seconds=seconds, interval=15)
            def source(observe):
                self.opens.append(None)
                return read, SimpleNamespace(close=lambda: self.closed.append(None))
            def sleep(duration):
                self.now += duration
            return run_session(args, source, lambda: Coach(gateway or Gateway()),
                               self.records.append, clock=lambda: self.now, sleep=sleep,
                               knowledge=lambda s: '')

    def test_accepted_journal_has_time_advice_issue_and_single_source(self):
        state = {'meta': {'t_s': 123.5, 'map': 'PRIVATE_MAP', 'match_id': 'a' * 64},
                 'local_player': {'id': 0, 'team': 0, 'hero': 'PRIVATE_HERO'},
                 'stats': {'deaths_total': 1}}
        self.assertEqual(self.run_fixture(lambda: copy.deepcopy(state)), 0)
        self.assertEqual(len(self.opens), 1)
        self.assertEqual(len(self.closed), 1)
        self.assertTrue(any(r.get('mission_t_s') == 123.5 for r in self.records))
        self.assertTrue(any(r.get('advice') == 'Regroupez-vous avant le prochain combat.' for r in self.records))
        self.assertTrue(any(r.get('event') == 'outcome' and r.get('speaking') for r in self.records))
        self.assertNotIn('PRIVATE', json.dumps(self.records))
        self.assertTrue(all('cycle' in r for r in self.records))

    def test_stop_prevents_even_opening_source(self):
        self.assertEqual(self.run_fixture(lambda: self.fail('read'), stop=True), 0)
        self.assertFalse(self.opens)

    def test_refusals_keep_phase_and_code_and_cleanup_without_api(self):
        gateway = Gateway()
        def read():
            raise NativeUnavailable('aucune_simulation_active')
        self.assertEqual(self.run_fixture(read, gateway=gateway), 0)
        refusal = next(r for r in self.records if r.get('event') == 'refusal')
        self.assertEqual(refusal['phase'], 'prevalidation')
        self.assertEqual(refusal['code'], 'aucune_simulation_active')
        self.assertEqual(len(self.closed), 1)
        self.assertFalse(gateway.calls)

    def test_freshness_refusal_never_remembers_and_records_distinct_phase(self):
        gateway = Gateway()
        calls = []
        def read():
            calls.append(None)
            if len(calls) > 1:
                raise NativeUnavailable('lecture_native_dechiree')
            return {'meta': {}, 'stats': {}}
        self.assertEqual(self.run_fixture(read, gateway=gateway), 0)
        refusal = next(r for r in self.records if r.get('event') == 'refusal')
        self.assertEqual(refusal['phase'], 'freshness')
        self.assertFalse(any(r.get('event') == 'outcome' and r.get('speaking') for r in self.records))
        self.assertEqual(len(self.closed), 1)


if __name__ == '__main__':
    unittest.main()
