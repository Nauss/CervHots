import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cerveau.brain import Coach
from hotstate.native import NativeUnavailable
from test_cerveau import Gateway


class SessionTests(unittest.TestCase):
    def test_native_reader_normalizer_key_and_configured_coach_reach_journal(self):
        # Synthetic process bytes only: the real acquisition/normalizer/key,
        # configuration constructor, Pipeline and journal all run unchanged.
        import os
        from cerveau.diagnostic_session import configured_coach, run_session
        from cerveau.runner import tactical_key
        from cerveau.state import snapshot as normalize
        from hotstate.reader import snapshot as acquire
        from hotstate.live import read_current
        from test_native_context import TypedContextMemory
        from test_capture_visibility_pipeline import FixtureProcess, PipelineCollectorTests
        m = TypedContextMemory()
        a, b, c = PipelineCollectorTests().options(m)
        backend = FixtureProcess(m)
        closed, records, now = [], [], [0.0]
        backend.close = lambda: closed.append(True)
        gateway = Gateway()
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'runtime.conf'
            config.write_text('GROCO_MODEL=fixture-model\nGROCO_API_TOKEN=fixture-token\n', encoding='utf-8')
            args = SimpleNamespace(stop_file=Path(tmp)/'STOP', max_seconds=1, interval=15)
            probe = m.probe()
            def source(observe):
                return lambda: read_current(backend, {'triggers': {}}, context=probe,
                                            project=normalize, key=tactical_key, observe=observe), backend
            def acquire_fixture(memory, mapping, **kwargs):
                return acquire(memory, mapping, native_profile=m.profile, **kwargs)
            with a, b, c, patch.dict(os.environ, {}, clear=True), \
                    patch('hotstate.live.memory_snapshot', side_effect=acquire_fixture), \
                    patch('grocoapi.GrocoClient.chat', side_effect=gateway.chat):
                result = run_session(args, source, lambda: configured_coach(config), records.append,
                                     clock=lambda: now[0], sleep=lambda d: now.__setitem__(0, now[0]+d),
                                     knowledge=lambda s: '')
        self.assertEqual(result, 0)
        self.assertTrue(gateway.calls, records)
        self.assertEqual(len(closed), 1)
        self.assertTrue(any(r['event'] == 'observation' and len(r['heroes']) == 10 for r in records))
        self.assertTrue(any(r['event'] == 'acquisition' and r['outcome'] == 'accepted' for r in records))
        self.assertTrue(any(r['event'] == 'outcome' for r in records))
        self.assertNotIn('OWNER_TEST', json.dumps(records))

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
            if len(calls) > 2:
                raise NativeUnavailable('lecture_native_dechiree')
            return {'meta': {}, 'stats': {}}
        self.assertEqual(self.run_fixture(read, gateway=gateway), 0)
        refusal = next(r for r in self.records if r.get('event') == 'refusal')
        self.assertEqual(refusal['phase'], 'freshness')
        self.assertFalse(any(r.get('event') == 'outcome' and r.get('speaking') for r in self.records))
        self.assertEqual(len(self.closed), 1)


if __name__ == '__main__':
    unittest.main()
