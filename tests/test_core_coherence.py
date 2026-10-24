"""Synthetic deterministic core conflicts; never live qualification."""
import unittest
from unittest.mock import patch

from hotstate.native import NativeReader, NativeUnavailable
from test_native import NativeMemory


class CoreCoherenceTests(unittest.TestCase):
    def test_build_and_identity_final_changes_keep_full_equality(self):
        for field in ('build', 'identity'):
            with self.subTest(field=field):
                memory = NativeMemory()
                memory.add_roster()
                target = memory.module_base + 0x200 if field == 'build' else 0x12000C
                original = memory.read_memory
                calls = []
                def read(address, size):
                    data = original(address, size)
                    if address == target:
                        calls.append(None)
                        if len(calls) == (2 if field == 'build' else 1):
                            memory.put(address, b'CHANGED' if field == 'build' else b'\x07')
                    return data
                memory.read_memory = read
                with self.assertRaises(NativeUnavailable) as caught:
                    NativeReader(memory, profile=memory.profile).read_state(
                        memory.context, hero_ids=memory.hero_ids)
                self.assertEqual(caught.exception.args, ('lecture_native_dechiree',))
                self.assertEqual(caught.exception.coherence['phase'], 'final_equality')
                self.assertEqual(caught.exception.coherence['field'], field)

    def test_overlapping_reads_still_reject_conflicts_and_accept_equal_bytes(self):
        from hotstate.positions import _RecordedMemory
        for conflict in (False, True):
            memory = NativeMemory()
            recorded = _RecordedMemory(memory, cache=True, diagnose=True)
            with recorded.read_scope('clock_tick'):
                first = recorded.read_memory(0x100068, 4)
                if conflict:
                    memory.put(0x100069, b'\xff')
                recorded.read_memory(0x100069, 2)
            if conflict:
                with self.assertRaises(NativeUnavailable) as caught:
                    recorded.coherence_reads('lecture_native_dechiree')
                self.assertEqual(caught.exception.coherence, {
                    'phase': 'initial_overlap', 'field': 'clock_tick', 'width': 2})
            else:
                self.assertEqual(recorded.coherence_reads('lecture_native_dechiree'),
                                 [(0x100068, first), (0x100069, first[1:3])])

    def test_closed_detail_rejects_hostile_types_and_drops_extra_fields(self):
        from hotstate.diagnostics import coherence_detail
        from cerveau.passive_session import measured_acquisition
        good = {'phase': 'initial_overlap', 'field': 'clock_tick', 'width': 4}
        self.assertEqual(coherence_detail(dict(good, address='PRIVATE', before=b'PRIVATE')), good)
        for value in (None, 'PRIVATE', [], {},
                      dict(good, phase=['PRIVATE']), dict(good, phase='PRIVATE'),
                      dict(good, field={}), dict(good, field='clock_tick\nPRIVATE'),
                      dict(good, width=True), dict(good, width=4.0),
                      dict(good, width=0), dict(good, width=65537)):
            with self.subTest(value=type(value)):
                self.assertIsNone(coherence_detail(value))
        for outcome, code in (('accepted', None), ('error', None),
                              ('refused', 'PRIVATE'), ('refused', 'budget_pipeline_depasse')):
            row = measured_acquisition({'outcome': outcome, 'refusal': code, 'coherence': good})
            self.assertNotIn('coherence', row)
        self.assertEqual(measured_acquisition({
            'outcome': 'refused', 'refusal': 'lecture_native_dechiree',
            'coherence': dict(good, pointer='PRIVATE')})['coherence'], good)

    def test_stop_after_refused_read_discards_also_the_new_detail(self):
        from cerveau.passive_session import run_session
        from test_passive_session import Clock
        stopped = [False]
        class Source:
            closed = False
            def read(self, observe):
                observe({'outcome': 'refused', 'refusal': 'lecture_native_dechiree',
                         'coherence': {'phase': 'final_equality', 'field': 'vitals', 'width': 4}})
                stopped[0] = True
                raise NativeUnavailable('lecture_native_dechiree')
            def close(self):
                self.closed = True
        source = Source()
        rows = []
        clock = Clock()
        result = run_session(lambda: source, lambda: stopped[0], rows.append,
                             clock=clock, sleep=clock.sleep)
        self.assertEqual(result['reason'], 'stop_file')
        self.assertEqual(result['attempts'], 1)
        self.assertEqual(result['accepted'], 0)
        self.assertFalse(any(r['event'] in ('acquisition', 'observation', 'refusal') for r in rows))
        self.assertTrue(source.closed)

    def test_new_acquisition_does_not_reuse_diagnostic_or_cached_bytes(self):
        from hotstate.positions import _RecordedMemory
        memory = NativeMemory()
        first = _RecordedMemory(memory, cache=True, diagnose=True)
        with first.read_scope('clock_tick'):
            first.read_memory(0x100068, 4)
        memory.pack(0x100068, 'i', 124 * 4096)
        with first.fresh_reads(), first.read_scope('clock_tick'):
            first.read_memory(0x100068, 4)
        with self.assertRaises(NativeUnavailable):
            first.coherence_reads('lecture_native_dechiree')
        second = _RecordedMemory(memory, cache=True, diagnose=True)
        with self.assertRaises(ValueError):
            with second.read_scope('vitals'):
                raise ValueError('scope must restore')
        self.assertEqual(second.scope, 'unclassified')
        second.read_memory(0x100068, 4)
        self.assertEqual(second.coherence_reads('lecture_native_dechiree'),
                         [(0x100068, (124 * 4096).to_bytes(4, 'little'))])
        self.assertEqual(second.read_fields[(0x100068, 4)], 'unclassified')

    def test_clock_root_conflict_is_not_misreported_as_tick(self):
        memory = NativeMemory()
        memory.add_roster()
        original_clock = NativeReader.read_clock
        calls = []
        def changed(reader):
            if getattr(reader.memory, 'diagnose', False):
                calls.append(None)
                if len(calls) == 2:
                    memory.pack(memory.module_base + 0x34F01D0, 'I', 0x110000)
                    memory.pack(0x110068, 'i', int(123.5 * 4096))
            return original_clock(reader)
        with patch.object(NativeReader, 'read_clock', changed):
            with self.assertRaises(NativeUnavailable) as caught:
                NativeReader(memory, profile=memory.profile).read_state(
                    memory.context, hero_ids=memory.hero_ids)
        self.assertEqual(caught.exception.args, ('lecture_native_dechiree',))
        self.assertEqual(caught.exception.coherence, {
            'phase': 'initial_overlap', 'field': 'clock_roots', 'width': 4})

    def test_coherent_result_and_guard_failures_have_no_coherence_claim(self):
        memory = NativeMemory()
        memory.add_roster()
        result = NativeReader(memory, profile=memory.profile).read_state(
            memory.context, hero_ids=memory.hero_ids)
        self.assertEqual(result['meta']['native_status'], 'valide')
        self.assertNotIn('native_coherence', result['meta'])
        for change, code in (('build', 'build_natif_non_pris_en_charge'),
                             ('observer', 'perspective_observateur_ou_replay'),
                             ('generation', 'proprietaire_ou_generation_unite_incoherent')):
            memory = NativeMemory()
            memory.add_roster()
            if change == 'build':
                memory.pack(memory.module_base + 0x88, 'I', 0)
            elif change == 'observer':
                memory.pack(0x120000, 'I', 0x20)
            else:
                memory.pack(0x900010, 'I', 999)
            with self.subTest(change=change), self.assertRaises(NativeUnavailable) as caught:
                NativeReader(memory, profile=memory.profile).read_state(
                    memory.context, hero_ids=memory.hero_ids)
            self.assertEqual(caught.exception.args, (code,))
            self.assertFalse(hasattr(caught.exception, 'coherence'))

    def test_other_core_fields_are_separate_from_clock_and_vitals(self):
        for field, address, fmt, value in (
                ('roster', 0x900000 + 5 * 0x2F0 + 0x10, 'I', 7),
                ('life', 0x900000 + 5 * 0x2F0 + 0x39, 'B', 2),
                ('level', 0xE06000 + 0xD0, 'i', 19),
                ('respawn', 0xB13000 + 0x18, 'i', 6 * 4096)):
            with self.subTest(field=field):
                memory = NativeMemory()
                memory.add_roster()
                original = memory.read_memory
                hits = []

                def read(at, size):
                    data = original(at, size)
                    if at == address:
                        hits.append(None)
                        if len(hits) == 1:
                            memory.pack(at, fmt, value)
                    return data

                memory.read_memory = read
                with self.assertRaises(NativeUnavailable) as caught:
                    NativeReader(memory, profile=memory.profile).read_state(
                        memory.context, hero_ids=memory.hero_ids)
                self.assertEqual(caught.exception.args, ('lecture_native_dechiree',))
                self.assertEqual(caught.exception.coherence['phase'], 'final_equality')
                self.assertEqual(caught.exception.coherence['field'], field)
                self.assertEqual(len(hits), 2)

    def test_final_vital_change_is_named_and_still_refused(self):
        memory = NativeMemory()
        memory.add_roster()
        target = 0x900000 + 5 * 0x2F0 + 0x22C
        original = memory.read_memory
        calls = []

        def read(address, size):
            data = original(address, size)
            if address == target:
                calls.append(None)
                if len(calls) == 1:
                    memory.pack(target, 'i', 501 * 4096)
            return data

        memory.read_memory = read
        with self.assertRaises(NativeUnavailable) as caught:
            NativeReader(memory, profile=memory.profile).read_state(
                memory.context, hero_ids=memory.hero_ids)
        self.assertEqual(caught.exception.args, ('lecture_native_dechiree',))
        self.assertEqual(caught.exception.coherence, {
            'phase': 'final_equality', 'field': 'vitals', 'width': 4})
        self.assertEqual(len(calls), 2)

    def test_real_reader_live_observer_and_passive_journal_keep_guard_location(self):
        from cerveau.passive_session import run_session
        from hotstate.live import read_current
        from hotstate.reader import snapshot
        from test_native_context import TypedContextMemory
        from test_capture_visibility_pipeline import FixtureProcess, PipelineCollectorTests
        from test_passive_session import Clock
        memory = TypedContextMemory()
        probe = memory.probe()
        backend = FixtureProcess(memory)
        physical = []
        original_read = backend.read_memory

        def read(address, size):
            physical.append((address, size))
            return original_read(address, size)

        backend.read_memory = read
        original_clock = NativeReader.read_clock
        ticks = []

        def advancing(reader):
            if getattr(reader.memory, 'diagnose', False):
                ticks.append(None)
                if len(ticks) == 2:
                    memory.pack(0x100068, 'i', int(123.5625 * 4096))
            return original_clock(reader)

        class Source:
            closed = False
            def read(self, observe):
                return read_current(backend, {'triggers': {}}, context=probe,
                                    observe=observe, clock=clock)
            def close(self):
                self.closed = True

        def acquire(*args, **kwargs):
            return snapshot(*args, native_profile=memory.profile, **kwargs)

        clock = Clock()
        source = Source()
        rows = []
        a, b, c = PipelineCollectorTests().options(memory)
        with a, b, c, patch.object(NativeReader, 'read_clock', advancing), \
                patch('hotstate.live.memory_snapshot', side_effect=acquire):
            result = run_session(lambda: source, lambda: False, rows.append,
                                 duration=1, clock=clock, sleep=clock.sleep)
        self.assertEqual(result['accepted'], 0)
        self.assertEqual(result['refused'], 1)
        self.assertEqual(result['failures'], 1)
        self.assertTrue(source.closed)
        acq, = [r for r in rows if r['event'] == 'acquisition']
        self.assertEqual(acq['refusal']['code'], 'lecture_native_dechiree')
        self.assertEqual(acq.get('coherence'), {
            'phase': 'initial_overlap', 'field': 'clock_tick', 'width': 4})
        self.assertEqual(acq['reads'], len(physical))
        self.assertEqual(acq['bytes_requested'], sum(size for _, size in physical))
        self.assertEqual(len(ticks), 2)
        self.assertFalse(any(r['event'] == 'observation' for r in rows))

    def test_tick_conflict_is_explained_without_acceptance_or_extra_reads(self):
        memory = NativeMemory()
        memory.add_roster()
        original = memory.read_memory
        reads = []
        ticks = []

        def read(address, size):
            reads.append((address, size))
            if address == 0x100068:
                ticks.append(None)
                if len(ticks) == 2:
                    memory.pack(address, 'i', int(123.5625 * 4096))
            return original(address, size)

        memory.read_memory = read
        with self.assertRaises(NativeUnavailable) as caught:
            NativeReader(memory, profile=memory.profile).read_state(
                memory.context, hero_ids=memory.hero_ids)
        self.assertEqual(caught.exception.args, ('lecture_native_dechiree',))
        self.assertEqual(getattr(caught.exception, 'coherence', None), {
            'phase': 'initial_overlap', 'field': 'clock_tick', 'width': 4})
        self.assertEqual(len(ticks), 6)  # Core boundaries + existing optional clocks.
        self.assertEqual(reads[-1], (0x100068, 4))  # Refuse before final rereads.


if __name__ == '__main__':
    unittest.main()
