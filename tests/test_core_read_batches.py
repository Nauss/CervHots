"""Synthetic final-check costs, never a live refusal-rate qualification."""
import unittest
from unittest.mock import patch

from hotstate.native import NativeReader, NativeUnavailable
from hotstate.positions import _RecordedMemory
from test_native import NativeMemory


class CoreReadBatchTests(unittest.TestCase):
    def test_real_core_final_checks_avoid_21_calls_without_new_bytes(self):
        memory = NativeMemory()
        memory.add_roster()
        physical, initial = [], []
        original = memory.read_memory
        coherence = _RecordedMemory.coherence_reads

        def read(address, size):
            physical.append((address, size))
            return original(address, size)

        def plan(recorded, reason):
            result = coherence(recorded, reason)
            if recorded.diagnose:
                initial.append((len(physical), result))
            return result

        memory.read_memory = read
        with patch.object(_RecordedMemory, 'coherence_reads', plan):
            result = NativeReader(memory, profile=memory.profile).read_state(
                memory.context, hero_ids=memory.hero_ids)
        start, checks = initial[-1]
        final = physical[start:]
        self.assertEqual(result['meta']['native_status'], 'valide')
        self.assertEqual(len(checks), 257)
        self.assertEqual(len(final), 236)
        self.assertEqual(sum(size for _, size in final), sum(len(d) for _, d in checks))
        expected = {a+i for a, data in checks for i in range(len(data))}
        self.assertEqual({a+i for a, size in final for i in range(size)}, expected)

    def test_plan_never_bridges_holes_reorders_or_groups_clocks_or_scopes(self):
        memory = NativeMemory()
        recorded = _RecordedMemory(memory, diagnose=True)
        reads = [(100, b'ab', 'roster'), (102, b'cd', 'roster'),
                 (105, b'e', 'roster'), (106, b'f', 'identity'),
                 (107, b'g', 'clock_tick'), (108, b'h', 'clock_tick'),
                 (109, b'i', 'clock_roots'), (110, b'j', 'clock_roots'),
                 (111, b'k', 'vitals'), (110, b'jk', 'vitals'),
                 (112, b'l', 'vitals')]
        recorded.read_set = [(a, d) for a, d, _ in reads]
        recorded.read_fields = {(a, len(d)): f for a, d, f in reads}
        plan = recorded.core_coherence_checks('lecture_native_dechiree')
        self.assertEqual([(a, s) for a, s, _ in plan],
                         [(100, 4), (105, 1), (106, 1), (107, 1), (108, 1),
                          (109, 1), (110, 1), (111, 1), (110, 3)])
        self.assertEqual([pair for _, _, slices in plan for pair in slices],
                         [(a, d) for a, d, _ in reads])

    def test_batch_cap_and_initial_overlap_conflicts_remain_strict(self):
        memory = NativeMemory()
        recorded = _RecordedMemory(memory, diagnose=True)
        recorded.read_set = [(100, b'a' * 65535), (65635, b'b'), (65636, b'c')]
        recorded.read_fields = {(a, len(d)): 'roster' for a, d in recorded.read_set}
        plan = recorded.core_coherence_checks('lecture_native_dechiree')
        self.assertEqual([(a, s) for a, s, _ in plan], [(100, 65536), (65636, 1)])
        for at, data in ((100, b'Z'), (65635, b'Z'), (101, b'ZZ')):
            with self.subTest(at=at):
                recorded.read_set.append((at, data))
                with self.assertRaisesRegex(NativeUnavailable, '^lecture_native_dechiree$'):
                    recorded.core_coherence_checks('lecture_native_dechiree')
                recorded.read_set.pop()

    def test_every_byte_of_real_batched_fields_still_rejects_with_original_width(self):
        # Obtain the real plan, not a handwritten approximation of its fields.
        memory = NativeMemory()
        memory.add_roster()
        plans = []
        actual = _RecordedMemory.core_coherence_checks
        def plan(recorded, reason):
            result = actual(recorded, reason)
            plans.append((recorded, result))
            return result
        with patch.object(_RecordedMemory, 'core_coherence_checks', plan):
            NativeReader(memory, profile=memory.profile).read_state(
                memory.context, hero_ids=memory.hero_ids)
        recorded, batches = plans[-1]
        cases = [(a+i, a, len(data), recorded.read_fields[(a, len(data))])
                 for _, _, slices in batches if len(slices) > 1
                 for a, data in slices for i in range(len(data))]
        self.assertGreater(len(cases), 100)
        for target, original, width, field in cases:
            with self.subTest(target=target, field=field):
                memory = NativeMemory()
                memory.add_roster()
                def mutate(recorded, reason):
                    result = actual(recorded, reason)
                    before = memory.read_memory(target, 1)
                    memory.put(target, bytes([before[0] ^ 1]))
                    return result
                with patch.object(_RecordedMemory, 'core_coherence_checks', mutate), \
                        self.assertRaises(NativeUnavailable) as caught:
                    NativeReader(memory, profile=memory.profile).read_state(
                        memory.context, hero_ids=memory.hero_ids)
                self.assertEqual(caught.exception.args, ('lecture_native_dechiree',))
                self.assertEqual(caught.exception.coherence,
                                 {'phase': 'final_equality', 'field': field, 'width': width})

    def test_same_payload_receipt_age_and_initial_io_as_unbatched_baseline(self):
        def baseline(recorded, reason):
            return [(a, len(d), [(a, d)]) for a, d in recorded.coherence_reads(reason)]
        actual = _RecordedMemory.core_coherence_checks
        results, traces, starts = [], [], []
        for selected in (baseline, actual):
            memory = NativeMemory()
            memory.add_roster()
            physical = []
            original = memory.read_memory
            def read(a, s):
                physical.append((a, s))
                return original(a, s)
            memory.read_memory = read
            def checks(recorded, reason):
                starts.append(len(physical))
                return selected(recorded, reason)
            with patch.object(_RecordedMemory, 'core_coherence_checks', checks), \
                    patch('time.monotonic', return_value=100.0):
                results.append(NativeReader(memory, profile=memory.profile).read_state(
                    memory.context, hero_ids=memory.hero_ids))
            traces.append(physical)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1]['perspective']['acquisition']['monotonic_s'], 100.0)
        self.assertEqual(traces[0][:starts[0]], traces[1][:starts[1]])
        self.assertEqual(len(traces[0]) - len(traces[1]), 21)
        self.assertEqual(sum(s for _, s in traces[0]), sum(s for _, s in traces[1]))

    def test_grouped_short_read_or_os_error_is_charged_without_fallback(self):
        from hotstate.live import LiveBudget
        from test_live_pipeline import Clock
        for outcome in ('short', 'error'):
            memory = NativeMemory()
            memory.add_roster()
            original = memory.read_memory
            requests = []
            armed = [False]
            actual = _RecordedMemory.core_coherence_checks
            def checks(recorded, reason):
                result = actual(recorded, reason)
                armed[0] = True
                return result
            def read(a, s):
                requests.append((a, s))
                # First batched identity interval in this fixture.
                if armed[0] and s == 16:
                    if outcome == 'error':
                        raise OSError('synthetic OS failure')
                    return original(a, s)[:-1]
                return original(a, s)
            memory.read_memory = read
            budget = LiveBudget(memory, clock=Clock())
            with patch.object(_RecordedMemory, 'core_coherence_checks', checks), \
                    self.assertRaises(OSError if outcome == 'error' else NativeUnavailable):
                NativeReader(budget, profile=memory.profile).read_state(
                    memory.context, hero_ids=memory.hero_ids)
            self.assertEqual(budget.reads, len(requests))
            self.assertEqual(budget.bytes_requested, sum(s for _, s in requests))
            self.assertEqual(requests[-1][1], 16)
            self.assertEqual(sum(1 for _, s in requests if armed[0] and s == 16), 1)

    def test_less_physical_io_can_complete_inside_unchanged_whole_deadline(self):
        from hotstate.live import LiveBudget
        from test_live_pipeline import Clock
        def baseline(recorded, reason):
            return [(a, len(d), [(a, d)]) for a, d in recorded.coherence_reads(reason)]
        actual = _RecordedMemory.core_coherence_checks
        # Calibrate a deterministic per-physical-request cost from an exercised
        # stable baseline; this is NOT a measured Windows/live latency.
        memory = NativeMemory()
        memory.add_roster()
        clock = Clock()
        budget = LiveBudget(memory, clock=clock)
        with patch.object(_RecordedMemory, 'core_coherence_checks', baseline):
            NativeReader(budget, profile=memory.profile).read_state(
                memory.context, hero_ids=memory.hero_ids)
        cost = .125 / (budget.reads - 10)
        for batched in (False, True):
            memory = NativeMemory()
            memory.add_roster()
            original = memory.read_memory
            clock = Clock()
            start = clock.value
            requests = []
            def read(a, s):
                requests.append((a, s))
                clock.value += cost
                return original(a, s)
            memory.read_memory = read
            budget = LiveBudget(memory, clock=clock)
            with patch('time.monotonic', clock), patch.object(
                    _RecordedMemory, 'core_coherence_checks', actual if batched else baseline):
                if not batched:
                    with self.assertRaisesRegex(NativeUnavailable, 'fenetre_pipeline_globale_depassee'):
                        NativeReader(budget, profile=memory.profile).read_state(
                            memory.context, hero_ids=memory.hero_ids)
                    with self.assertRaises(NativeUnavailable):
                        budget.check()
                else:
                    result = NativeReader(budget, profile=memory.profile).read_state(
                        memory.context, hero_ids=memory.hero_ids)
                    budget.check()
                    self.assertLessEqual(clock.value - start, .125)
                    acquired = result['perspective']['acquisition']['monotonic_s']
                    self.assertLess(acquired, clock.value)
                    self.assertGreaterEqual(acquired, start)
            self.assertEqual(budget.reads, len(requests))
            self.assertEqual(budget.bytes_requested, sum(s for _, s in requests))


if __name__ == '__main__':
    unittest.main()
