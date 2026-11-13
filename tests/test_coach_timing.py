"""SYNTHETIC clocks: bounded API budget, measured stages, no drift/bursts."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest

from cerveau.brain import Coach
from cerveau.diagnostics import Journal, decision_reason
from cerveau.playtest import run_session
from cerveau.runner import Pipeline
from grocoapi import GrocoError
from test_cerveau import Gateway


class PipelineTimingTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.state = {'meta':{'source':'live'}, 'stats':{}}
        self.rows = []

    def advance(self, seconds, result=None):
        self.now += seconds
        return result

    def test_api_timeout_uses_remaining_budget_including_journal_and_is_restored(self):
        coach = Coach(Gateway(), timeout=25.)
        def emit(row):
            self.rows.append(row)
            if row['event'] == 'coach_attempt':
                self.now += 3
        pipeline = Pipeline(coach, lambda:copy.deepcopy(self.state),
            knowledge=lambda s:self.advance(4, ''), clock=lambda:self.now, journal=Journal(emit))
        self.assertTrue(pipeline.cycle().parler)
        self.assertEqual(coach.client.calls[0][1]['timeout'], 13.)
        self.assertEqual(coach.timeout, 25.)

    def test_remaining_budget_never_raises_a_lower_configured_timeout_even_on_error(self):
        coach = Coach(Gateway(GrocoError(0,'SYNTHETIC')), timeout=3.)
        pipeline = Pipeline(coach, lambda:self.state, knowledge=lambda s:self.advance(4,''),
                            clock=lambda:self.now)
        self.assertFalse(pipeline.cycle().parler)
        self.assertEqual(coach.client.calls[0][1]['timeout'], 3.)
        self.assertEqual(coach.timeout, 3.)
        self.assertEqual(decision_reason('erreur_api_0'), 'erreur_api_0')

    def test_zero_budget_never_starts_an_http_call(self):
        coach = Coach(Gateway())
        pipeline = Pipeline(coach, lambda:self.state, knowledge=lambda s:self.advance(20,''),
                            clock=lambda:self.now)
        self.assertEqual(pipeline.cycle().raison, 'périmé')
        self.assertEqual(coach.client.calls, [])

    def test_stages_are_measured_independently_and_delivery_is_not_labelled_first_audio(self):
        gateway = Gateway()
        original = gateway.chat
        gateway.chat = lambda *a,**k:self.advance(3, original(*a,**k))
        def deliver(decision, speech, valid):
            self.now += 5
            return valid()
        pipeline = Pipeline(Coach(gateway), lambda:self.state,
            knowledge=lambda s:self.advance(2,''), clock=lambda:self.now,
            synthesize=lambda d:self.advance(4,b'SYNTHETIC_NO_AUDIO'), deliver=deliver,
            journal=Journal(self.rows.append))
        self.assertTrue(pipeline.cycle().parler)
        timings = {r['stage']:r['latency_s'] for r in self.rows if r['event']=='stage_timing'}
        self.assertEqual(timings, {'knowledge':2., 'synthesis':4., 'delivery_complete':5.})
        self.assertEqual(next(r['latency_s'] for r in self.rows if r['event']=='coach_response'), 3.)


class SessionCadenceTests(unittest.TestCase):
    def exercise(self, api_seconds, maximum, *, extra_prepare=0., stop_during_sleep=False):
        from test_playtest_macro import MacroTests
        fixture = MacroTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        now, starts, timeouts, rows = [0.], [], [], []
        stopped = [False]
        class Source:
            closed = False
            def read(self, observe):
                return copy.deepcopy(fixture.state)
            def close(self):
                self.closed = True
        source = Source()
        gateway = Gateway({'parler':False})
        original = gateway.chat
        def chat(*args,**kwargs):
            starts.append(now[0])
            timeouts.append(kwargs['timeout'])
            now[0] += api_seconds
            return original(*args,**kwargs)
        gateway.chat = chat
        def knowledge(state):
            now[0] += extra_prepare
            return ''
        def sleep(seconds):
            now[0] += seconds
            if stop_during_sleep:
                stopped[0] = True
        args = SimpleNamespace(max_seconds=maximum, interval=15, collection='positions',
            coach_mode='free', mumble=False, wav=False, stop_file=Path('UNUSED'))
        result = run_session(args, lambda:source, lambda:Coach(gateway,timeout=25.), rows.append,
            clock=lambda:now[0], sleep=sleep, knowledge=knowledge, stopped=lambda:stopped[0])
        self.assertTrue(source.closed)
        return starts, timeouts, result, now[0]

    def test_eight_second_calls_start_at_0_15_30_not_0_23(self):
        starts, _, result, _ = self.exercise(8, 44)
        self.assertEqual(starts, [0.,15.,30.])
        self.assertEqual(result['coach_attempts'], 3)

    def test_overrun_does_not_queue_catchup_calls_or_add_another_full_sleep(self):
        starts, _, _, _ = self.exercise(17, 51)
        self.assertEqual(starts, [0.,17.,34.])

    def test_session_deadline_also_caps_the_effective_api_timeout(self):
        _, timeouts, _, _ = self.exercise(1, 12, extra_prepare=5)
        self.assertEqual(timeouts, [7.])

    def test_stop_during_remaining_sleep_is_still_cooperative(self):
        starts, _, result, _ = self.exercise(8, 44, stop_during_sleep=True)
        self.assertEqual(starts, [0.])
        self.assertEqual(result['reason'], 'stop_file')


if __name__ == '__main__':
    unittest.main()
