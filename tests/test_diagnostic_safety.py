"""Safety regressions: no live IO, no dependency on a private checkout."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cerveau.brain import Coach
from cerveau.diagnostic_session import run_session
from test_cerveau import Gateway


class SafetyTests(unittest.TestCase):
    def test_stop_during_api_phase_emission_prevents_request_and_closes_once(self):
        from cerveau.runner import Pipeline
        original_init = Pipeline.__init__
        records, closed = [], []
        gateway = Gateway()
        coach = Coach(gateway)
        with tempfile.TemporaryDirectory() as tmp:
            stop = Path(tmp) / 'STOP'
            def emit(event):
                records.append(event)
                if event.get('event') == 'phase' and event.get('phase') == 'api':
                    stop.touch()
            args = SimpleNamespace(stop_file=stop, max_seconds=1, interval=30)
            with patch.object(coach, 'remember', wraps=coach.remember) as remember, \
                    patch.object(Pipeline, '__init__', autospec=True) as init:
                # Keep the real constructor, but fail if any delivery is attempted.
                def initialize(instance, *a, **kw):
                    kw['deliver'] = lambda *a: self.fail('delivery forbidden')
                    original_init(instance, *a, **kw)
                init.side_effect = initialize
                result = run_session(args, lambda observe: (
                    lambda: {'meta': {}, 'stats': {}},
                    SimpleNamespace(close=lambda: closed.append(None))),
                    lambda: coach, emit, clock=lambda: 0, knowledge=lambda s: '')
            remember.assert_not_called()
        self.assertEqual(result, 0)
        self.assertFalse(gateway.calls)
        self.assertFalse(coach.history)
        self.assertEqual(len(closed), 1)
        self.assertFalse(any(r.get('event') in ('proposal', 'outcome') for r in records))
        self.assertTrue(any(r.get('event') == 'boundary' and r.get('reason') == 'stop_file'
                            for r in records))

    def test_stop_during_api_precedes_journal_proposal_and_never_remembers(self):
        for speaking in (False, True):
            with self.subTest(speaking=speaking), tempfile.TemporaryDirectory() as tmp:
                now = [0.0]
                records, reads, closed = [], [], []
                stop = Path(tmp) / 'STOP'
                gateway = Gateway({**Gateway().answer, 'parler': speaking})
                original = gateway.chat
                def chat(*a, **kw):
                    stop.touch()
                    return original(*a, **kw)
                gateway.chat = chat
                coach = Coach(gateway)
                def read():
                    reads.append(None)
                    return {'meta': {}, 'stats': {}}
                args = SimpleNamespace(stop_file=stop, max_seconds=1, interval=30)
                result = run_session(args, lambda observe: (read, SimpleNamespace(close=lambda: closed.append(None))),
                                     lambda: coach, records.append, clock=lambda: now[0],
                                     sleep=lambda d: now.__setitem__(0, now[0]+d), knowledge=lambda s: '')
                self.assertEqual(result, 0)
                self.assertFalse(any(r.get('event') in ('proposal', 'outcome') for r in records))
                self.assertFalse(coach.history)
                self.assertEqual(len(reads), 2)
                self.assertEqual(len(closed), 1)

    def test_pipeline_acquires_after_coach_initialization_not_cached_prevalidation(self):
        now = [0.0]
        records = []
        gateway = Gateway()
        reads = []
        def read():
            reads.append(now[0])
            return {'meta': {'t_s': now[0]}, 'stats': {}}
        def coach():
            now[0] += 19
            return Coach(gateway)
        with tempfile.TemporaryDirectory() as tmp:
            args = SimpleNamespace(stop_file=Path(tmp)/'STOP', max_seconds=20, interval=30)
            run_session(args, lambda observe: (read, SimpleNamespace(close=lambda: None)),
                        coach, records.append, clock=lambda: now[0],
                        sleep=lambda d: now.__setitem__(0, now[0]+d), knowledge=lambda s: '')
        observed = json.loads(gateway.calls[0][0][-1]['content'])['etat']['meta']['t_s']
        self.assertGreaterEqual(observed, 19)
        self.assertGreaterEqual(len(reads), 2)

    def test_unreadable_stop_fails_closed_before_open(self):
        opened = []
        records = []
        with tempfile.TemporaryDirectory() as tmp:
            args = SimpleNamespace(stop_file=Path(tmp)/'STOP', max_seconds=1, interval=30)
            original_stat = Path.stat
            def stat(path, *a, **kw):
                if path == args.stop_file:
                    raise PermissionError('PRIVATE_SECRET')
                return original_stat(path, *a, **kw)
            with patch.object(Path, 'stat', stat):
                result = run_session(args, lambda observe: opened.append(None), Coach,
                                     records.append, knowledge=lambda s: '')
        self.assertEqual(result, 1)
        self.assertFalse(opened)
        self.assertNotIn('PRIVATE_SECRET', json.dumps(records))


if __name__ == '__main__':
    unittest.main()
