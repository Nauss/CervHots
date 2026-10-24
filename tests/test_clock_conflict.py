"""Synthetic clock conflict classification; no CURRENT qualification."""
import struct
import unittest

from hotstate.native import NativeUnavailable
from hotstate.positions import _RecordedMemory
from hotstate.diagnostics import coherence_detail
from test_native import NativeMemory


class ClockConflictTests(unittest.TestCase):
    def test_equal_address_tick_conflict_reports_bounded_forward_without_values(self):
        memory = NativeMemory()
        recorded = _RecordedMemory(memory, cache=True, diagnose=True)
        with recorded.read_scope('clock_tick'), recorded.fresh_reads():
            recorded.read_memory(0x100068, 4)
            memory.pack(0x100068, 'i', int(123.5625 * 4096))
            recorded.read_memory(0x100068, 4)
        with self.assertRaises(NativeUnavailable) as caught:
            recorded.coherence_reads('lecture_native_dechiree')
        self.assertEqual(caught.exception.args, ('lecture_native_dechiree',))
        self.assertEqual(caught.exception.coherence, {
            'phase': 'initial_overlap', 'field': 'clock_tick', 'width': 4,
            'clock_transition': 'forward_bounded'})


    def test_other_complete_tick_changes_remain_refused_and_are_discriminated(self):
        cases = ((100, 99, 'backward'), (100, 4197, 'forward_over_window'),
                 (100, -1, 'out_of_range'),
                 (21600 * 4096, 21600 * 4096 + 1, 'out_of_range'))
        for first, last, category in cases:
            with self.subTest(category=category):
                memory = NativeMemory()
                recorded = _RecordedMemory(memory, cache=True, diagnose=True)
                with recorded.read_scope('clock_tick'), recorded.fresh_reads():
                    memory.pack(0x100068, 'i', first)
                    recorded.read_memory(0x100068, 4)
                    memory.pack(0x100068, 'i', last)
                    recorded.read_memory(0x100068, 4)
                with self.assertRaises(NativeUnavailable) as caught:
                    recorded.coherence_reads('lecture_native_dechiree')
                self.assertEqual(caught.exception.coherence.get('clock_transition'), category)


    def test_final_tick_change_is_discriminated_without_an_extra_read(self):
        from hotstate.native import NativeReader
        memory = NativeMemory()
        memory.add_roster()
        original = memory.read_memory
        ticks = []
        def read(address, size):
            if address == 0x100068:
                ticks.append(None)
            return original(address, size)
        memory.read_memory = read
        from unittest.mock import patch
        original_coherence = _RecordedMemory.coherence_reads
        def checks(recorded, reason):
            result = original_coherence(recorded, reason)
            if reason == 'lecture_native_dechiree':
                memory.pack(0x100068, 'i', int(123.5625 * 4096))
            return result
        with patch.object(_RecordedMemory, 'coherence_reads', checks), \
                self.assertRaises(NativeUnavailable) as caught:
            NativeReader(memory, profile=memory.profile).read_state(
                memory.context, hero_ids=memory.hero_ids)
        self.assertEqual(caught.exception.coherence, {
            'phase': 'final_equality', 'field': 'clock_tick', 'width': 4,
            'clock_transition': 'forward_bounded'})
        self.assertEqual(len(ticks), 7)


    def test_transition_schema_is_closed_and_only_applies_to_complete_tick(self):
        base = {'phase': 'initial_overlap', 'field': 'clock_tick', 'width': 4}
        for category in ('forward_bounded', 'forward_over_window', 'backward', 'out_of_range'):
            detail = dict(base, clock_transition=category)
            self.assertEqual(coherence_detail(dict(detail, before=b'PRIVATE', address=123)), detail)
        for hostile in (None, {}, [], True, 1, 'PRIVATE', 'forward_bounded\nPRIVATE'):
            self.assertEqual(coherence_detail(dict(base, clock_transition=hostile)), base)
        for field, width in (('clock_roots', 4), ('vitals', 4), ('clock_tick', 2)):
            detail = dict(base, field=field, width=width)
            self.assertEqual(coherence_detail(dict(detail, clock_transition='forward_bounded')), detail)

    def test_partial_overlap_is_not_promoted_to_complete_tick_transition(self):
        memory = NativeMemory()
        recorded = _RecordedMemory(memory, diagnose=True)
        with recorded.read_scope('clock_tick'):
            recorded.read_memory(0x100069, 2)
            memory.pack(0x100068, 'i', 124 * 4096)
            recorded.read_memory(0x100068, 4)
        with self.assertRaises(NativeUnavailable) as caught:
            recorded.coherence_reads('lecture_native_dechiree')
        self.assertNotIn('clock_transition', caught.exception.coherence)

    def test_equal_ticks_and_new_acquisition_do_not_reuse_a_conflict(self):
        memory = NativeMemory()
        for tick in (0, 21600 * 4096):
            memory.pack(0x100068, 'i', tick)
            recorded = _RecordedMemory(memory, cache=True, diagnose=True)
            with recorded.read_scope('clock_tick'), recorded.fresh_reads():
                recorded.read_memory(0x100068, 4)
                recorded.read_memory(0x100068, 4)
            self.assertEqual(recorded.coherence_reads('lecture_native_dechiree'),
                             [(0x100068, struct.pack('<i', tick))])

    def test_forward_bounded_threshold_is_inclusive_not_a_tolerance(self):
        for delta, category in ((1, 'forward_bounded'), (4096, 'forward_bounded'),
                                (4097, 'forward_over_window')):
            memory = NativeMemory()
            recorded = _RecordedMemory(memory, diagnose=True)
            with recorded.read_scope('clock_tick'):
                memory.pack(0x100068, 'i', 0)
                recorded.read_memory(0x100068, 4)
                memory.pack(0x100068, 'i', delta)
                recorded.read_memory(0x100068, 4)
            with self.assertRaises(NativeUnavailable) as caught:
                recorded.coherence_reads('lecture_native_dechiree')
            self.assertEqual(caught.exception.coherence['clock_transition'], category)


if __name__ == '__main__':
    unittest.main()
