"""SYNTHETIC mapped physical IO; never live/native or HUD qualification."""
from contextlib import ExitStack
import unittest
from unittest.mock import patch

import test_day_composition as composition
from test_capture_visibility_pipeline import FixtureProcess
from cerveau.runner import tactical_key
from cerveau.state import snapshot
from hotstate import live

OPTIONAL = ('gameplay_clock', 'positions', 'visibility', 'objective',
            'talents', 'local_cooldowns', 'battlefield')
READERS = ('hotstate.gameplay.GameplayClock.read', 'hotstate.positions.AlliedPositions.read',
           'hotstate.visibility.CurrentVisibility.read', 'hotstate.objectives.VolskayaObjective.read',
           'hotstate.dragon.DragonObjective.read', 'hotstate.talents.NativeTalentChoices.read',
           'hotstate.cooldown_packet.LocalCooldowns.read', 'hotstate.battlefield.VolskayaBattlefield.read',
           'hotstate.dragon_battlefield.DragonBattlefield.read')


class CoreCollectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = composition.DayCompositionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def take(self, collection='core', observe=None, project=snapshot):
        return live.read_current(FixtureProcess(self.fixture.memory),
            {'triggers': {}, 'collection': collection}, context=self.fixture.memory.probe(),
            project=project, key=tactical_key, observe=observe)

    def test_core_normalizes_without_entering_any_optional_reader(self):
        from cerveau.passive_session import measured_acquisition
        rows = []
        with ExitStack() as stack:
            for name in READERS:
                stack.enter_context(patch(name, side_effect=AssertionError('unselected physical IO')))
            state = self.take(observe=rows.append)
        self.assertEqual(len(state['heroes']), 10)
        self.assertEqual(state['meta']['native_status'], 'valide')
        self.assertTrue(set(state).isdisjoint(OPTIONAL))
        for hero in state['heroes']:
            if hero['team'] == state['ally_team']:
                self.assertIn('health', hero)
            else:
                self.assertNotIn('health', hero)
        row = measured_acquisition(rows[0])
        self.assertEqual(row['collection'], 'core')
        self.assertEqual(row['not_selected'], list(OPTIONAL))
        self.assertEqual(row['optional_refusals'], {})
        self.assertGreater(row['reads'], 0)
        self.assertGreater(row['bytes_requested'], 0)

    def test_core_normalizer_does_not_project_poisoned_optional_packets(self):
        captured = {}
        def capture(raw):
            captured['raw'] = raw
            return snapshot(raw)
        self.take('all', project=capture)
        raw = captured['raw']
        raw['meta']['collection'] = 'core'
        with ExitStack() as stack:
            for name in ('cerveau.state._native_positions', 'cerveau.state._native_visibility',
                         'cerveau.objectives.project_objective', 'cerveau.battlefield.project_battlefield',
                         'cerveau.cooldowns.project_local_cooldowns', 'cerveau.talents.project_talents',
                         'cerveau.state.validated_gameplay_clock'):
                stack.enter_context(patch(name, side_effect=AssertionError('unselected normalization')))
            state = snapshot(raw)
        self.assertEqual(state['meta']['collection'], 'core')
        self.assertTrue(set(state).isdisjoint(OPTIONAL))

    def test_core_journal_is_usable_by_historical_summary(self):
        import json
        import tempfile
        from pathlib import Path
        from cerveau.passive_session import run_session
        from cerveau.native_history import summarize
        owner = self
        class Source:
            closed = False
            def read(self, observe):
                return owner.take(observe=observe)
            def close(self):
                self.closed = True
        source = Source()
        rows = []
        result = run_session(lambda: source,
            lambda: any(r['event'] == 'observation' for r in rows), rows.append,
            duration=1, interval=1, clock=self.fixture.clock)
        self.assertEqual(result['accepted'], 1)
        self.assertTrue(source.closed)
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory)/'SYNTHETIC-events.jsonl'
            journal.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
            history = summarize(journal)
            from cerveau.session_diagnosis import diagnose
            diagnosis = diagnose(journal)
        for family in OPTIONAL:
            self.assertEqual(diagnosis['families'][family], {'not_selected': 1})
        self.assertEqual(history['state'], 'recorded_observation', history)
        self.assertEqual(history['map'], 'Volskaya')
        self.assertEqual(history['talents']['status'], 'not_selected')
        self.assertEqual(history['objective']['status'], 'not_selected')
        self.assertIsNone(history['talents']['original_age_s'])
        self.assertFalse(history['current_permission'])

    def test_exact_ordered_core_physical_bytes_and_synthetic_cost_reduction(self):
        import importlib
        trace, scope = [], ['core_context']
        memory = self.fixture.memory
        read = memory.read_memory
        def physical(address, size):
            data = read(address, size)
            trace.append((scope[0], address, size, data))
            return data
        with ExitStack() as stack:
            stack.enter_context(patch.object(memory, 'read_memory', physical))
            for name in READERS:
                module, cls, method = name.rsplit('.', 2)
                kind = getattr(importlib.import_module(module), cls)
                original = getattr(kind, method)
                def scoped(reader, *args, _old=original, _name=cls, **kwargs):
                    previous, scope[0] = scope[0], _name
                    try:
                        return _old(reader, *args, **kwargs)
                    finally:
                        scope[0] = previous
                stack.enter_context(patch.object(kind, method, scoped))
            full = self.take('all')
            all_trace = trace[:]
            trace.clear()
            core = self.take()
        self.assertEqual(trace, [r for r in all_trace if r[0] == 'core_context'])
        self.assertEqual(core['heroes'], full['heroes'])
        self.assertEqual(core['composition'], full['composition'])
        self.assertLess(len(trace), len(all_trace))
        self.assertLess(sum(r[2] for r in trace), sum(r[2] for r in all_trace))
        self.costs = dict(basis='SYNTHETIC_same_mapped_fixture_NOT_LIVE',
            all=dict(reads=len(all_trace), bytes_requested=sum(r[2] for r in all_trace)),
            core=dict(reads=len(trace), bytes_requested=sum(r[2] for r in trace)))
        self.assertEqual(self.fixture.budgets[-1].reads, self.costs['core']['reads'])
        self.assertEqual(self.fixture.budgets[-1].bytes_requested, self.costs['core']['bytes_requested'])

    def test_optional_budget_bomb_cannot_run_in_core(self):
        from hotstate.native import NativeUnavailable
        def bomb(reader, *args, **kwargs):
            for _ in range(8192):
                reader.native.read(reader.native.base, 2)
        with patch('hotstate.talents.NativeTalentChoices.read', bomb):
            with self.assertRaisesRegex(NativeUnavailable, 'budget_pipeline_depasse'):
                self.take('all')
            self.assertEqual(len(self.take()['heroes']), 10)

    def test_core_whole_budget_still_covers_decode_and_final_context(self):
        from hotstate.native import NativeUnavailable
        def late(raw):
            state = snapshot(raw)
            self.fixture.clock.value += .126
            return state
        with self.assertRaisesRegex(NativeUnavailable, 'globale_depassee'):
            self.take(project=late)
        for kind in ('reads', 'bytes'):
            def limit(raw):
                state = snapshot(raw)
                if kind == 'reads':
                    self.fixture.budgets[-1].reads = 8192
                else:
                    self.fixture.budgets[-1].bytes_requested = 2**20
                # Exact ceiling is legal; the NEXT physical request must fail.
                self.fixture.budgets[-1].read_memory(self.fixture.memory.module_base, 2)
                return state
            with self.subTest(kind=kind), self.assertRaisesRegex(NativeUnavailable, 'budget_pipeline_depasse'):
                self.take(project=limit)

    def test_core_rejects_changed_final_context(self):
        from hotstate.native import NativeReader, NativeUnavailable
        original = NativeReader.read_state
        def changed(reader, *args, **kwargs):
            result = original(reader, *args, **kwargs)
            memory = self.fixture.memory
            memory.pack(memory.config + 0x1d428, 'I', memory.seed + 1)
            return result
        rows = []
        with patch.object(NativeReader, 'read_state', changed), self.assertRaisesRegex(
                NativeUnavailable, 'contexte_natif_dechire'):
            self.take(observe=rows.append)
        self.assertEqual(rows[0]['outcome'], 'refused')
        self.assertGreater(rows[0]['reads'], 0)

    def test_core_rejects_build_and_observer_with_costs(self):
        from hotstate.native import NativeUnavailable
        rows = []
        self.fixture.memory.pack(0x120000, 'I', 0x20)
        with self.assertRaises(NativeUnavailable):
            self.take(observe=rows.append)
        self.assertGreater(rows[0]['reads'], 0)
        self.fixture.memory.pack(0x120000, 'I', 0)
        self.fixture.memory.put(self.fixture.memory.module_base + 0x200, b'CHANGED')
        with self.assertRaises(NativeUnavailable):
            self.take()

    def test_core_keeps_initial_clock_conflict(self):
        from hotstate.native import NativeReader, NativeUnavailable
        original = NativeReader.read_clock
        changed = [False]
        def tick(reader):
            result = original(reader)
            if getattr(reader.memory, 'diagnose', False) and not changed[0]:
                changed[0] = True
                self.fixture.memory.pack(0x100068, 'i', int((result + .0625) * 4096))
            return result
        with patch.object(NativeReader, 'read_clock', tick), self.assertRaisesRegex(
                NativeUnavailable, 'lecture_native_dechiree'):
            self.take()

    def test_core_final_physical_equality_is_not_memoized(self):
        from hotstate.positions import _RecordedMemory
        from hotstate.native import NativeUnavailable
        original = _RecordedMemory.core_coherence_checks
        memory = self.fixture.memory
        def changed(recorded, *args, **kwargs):
            mutated = False
            for address, size, slices in original(recorded, *args, **kwargs):
                if not mutated:
                    start, data = slices[0]
                    memory.put(start, bytes([data[0] ^ 1]) + data[1:])
                    mutated = True
                yield address, size, slices
        rows = []
        with patch.object(_RecordedMemory, 'core_coherence_checks', changed), self.assertRaisesRegex(
                NativeUnavailable, 'lecture_native_dechiree'):
            self.take(observe=rows.append)
        self.assertEqual(rows[0]['coherence']['phase'], 'final_equality')
        self.assertGreater(rows[0]['reads'], 0)

    def test_core_identity_and_malformed_roster_remain_refused(self):
        from hotstate.native import NativeReader, NativeUnavailable
        import copy
        reader = NativeReader(self.fixture.memory, profile=self.fixture.memory.profile)
        for change in ('identity', 'team', 'roster'):
            context = copy.deepcopy(self.fixture.memory.context)
            if change == 'identity':
                context['local_player']['hero'] = 'OTHER_HERO'
            elif change == 'team':
                context['local_player']['team'] = 1-context['local_player']['team']
            else:
                context['players'].pop()
            with self.subTest(change=change), self.assertRaises(NativeUnavailable):
                reader.read_state(context, collection='core')

    def test_original_core_receipt_is_not_reissued_or_refreshed(self):
        import copy
        raw = {}
        def capture(value):
            raw.update(copy.deepcopy(value))
            return snapshot(value)
        state = self.take(project=capture)
        original = copy.deepcopy(raw['perspective']['acquisition'])
        self.assertTrue(any('health' in h for h in state['heroes']))
        self.fixture.clock.value += 2
        stale = snapshot(raw)
        self.assertTrue(all('health' not in h for h in stale['heroes']))
        self.assertEqual(raw['perspective']['acquisition'], original)

    def test_invalid_collection_never_reads_or_means_core(self):
        from hotstate.native import NativeReader
        for value in (None, True, [], {}, 'CORE', 'typo'):
            with self.subTest(value=value), patch.object(self.fixture.memory, 'read_memory',
                    side_effect=AssertionError('no physical IO')), self.assertRaisesRegex(ValueError, 'invalid_collection'):
                self.take(value)
        reader = NativeReader(self.fixture.memory, profile=self.fixture.memory.profile)
        with patch.object(self.fixture.memory, 'read_memory', side_effect=AssertionError('no physical IO')):
            with self.assertRaisesRegex(ValueError, 'invalid_collection'):
                reader.read_state(self.fixture.memory.context, collection=None)
        with patch('hotstate.talents.NativeTalentChoices.read', side_effect=AssertionError('legacy all')):
            with self.assertRaisesRegex(AssertionError, 'legacy all'):
                live.read_current(FixtureProcess(self.fixture.memory), {'triggers': {}},
                    context=self.fixture.memory.probe(), project=snapshot)

    def test_core_stop_before_open_after_read_and_during_wait_keeps_closure(self):
        from tests.helpers.core_session_synthetic import mapped_core_source
        from cerveau import passive_session as product
        original = product.run_session
        # Explicitly synthetic control clock; actual native reads use fixture clock.
        import test_passive_session as transport
        for phase in ('before_open', 'after_read', 'wait'):
            rows, flag = [], [phase == 'before_open']
            clock = transport.Clock()
            def sleep(seconds):
                clock.sleep(seconds)
                flag[0] = True
            with self.subTest(phase=phase), mapped_core_source(self.fixture,
                    stop_after_read=(lambda: flag.__setitem__(0, True)) if phase == 'after_read' else None) as sources:
                result = original(lambda: product.NativeSource('SYNTHETIC_IDENTITY', collection='core'),
                    lambda: flag[0], rows.append, duration=2, interval=1, clock=clock, sleep=sleep)
            self.assertEqual(result['reason'], 'stop_file')
            self.assertEqual(result['accepted'], 1 if phase == 'wait' else 0)
            self.assertEqual(len(sources), 0 if phase == 'before_open' else 1)
            self.assertFalse(result['reader_active'])
            for source in sources:
                self.assertIsNone(source.backend)
                self.assertIsNone(source.guard.handle)
            if phase == 'after_read':
                self.assertTrue(all(row['event'] == 'boundary' for row in rows))

    def test_core_source_exclusivity_invalid_selection_and_close_failure(self):
        from tests.helpers.core_session_synthetic import mapped_core_source
        from cerveau import passive_session as product
        from cerveau.native_reader_guard import ReaderGuardError
        with mapped_core_source(self.fixture) as sources:
            with self.assertRaisesRegex(ValueError, 'invalid_collection'):
                product.NativeSource('SYNTHETIC_IDENTITY', collection=None)
            self.assertEqual(sources, [])
            first = product.NativeSource('SYNTHETIC_IDENTITY', collection='core')
            try:
                with self.assertRaises(ReaderGuardError):
                    product.NativeSource('SYNTHETIC_IDENTITY', collection='core')
                with patch.object(first.backend, 'close', side_effect=OSError('SYNTHETIC')):
                    with self.assertRaises(OSError):
                        first.close()
                    self.assertIsNotNone(first.guard.handle)
                    with self.assertRaises(ReaderGuardError):
                        product.NativeSource('SYNTHETIC_IDENTITY', collection='core')
            finally:
                first.close()
            second = product.NativeSource('SYNTHETIC_IDENTITY', collection='core')
            second.close()

    def test_core_session_change_keeps_cost_but_never_second_observation(self):
        from cerveau.passive_session import run_session
        import test_passive_session as transport
        import copy
        owner = self
        class Source:
            calls = 0
            closed = False
            def read(self, observe):
                self.calls += 1
                state = owner.take(observe=observe)
                if self.calls == 2:
                    state = copy.deepcopy(state)
                    state['meta']['match_id'] = 'f'*64
                return state
            def close(self):
                self.closed = True
        source, rows, clock = Source(), [], transport.Clock()
        result = run_session(lambda: source, lambda: False, rows.append,
            duration=3, interval=1, clock=clock, sleep=clock.sleep)
        self.assertEqual(result['reason'], 'session_changed')
        self.assertEqual(result['accepted'], 1)
        self.assertEqual(sum(r['event'] == 'acquisition' for r in rows), 2)
        self.assertEqual(sum(r['event'] == 'observation' for r in rows), 1)
        self.assertTrue(source.closed)

    def test_invalid_core_normalization_selection_is_not_a_core_fallback(self):
        raw = {}
        def capture(value):
            raw.update(value)
            return snapshot(value)
        self.take(project=capture)
        for value in (None, 'unknown', True, [], {}):
            raw['meta']['collection'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'invalid_collection'):
                snapshot(raw)
        raw['meta'].pop('collection')
        with patch('cerveau.state._native_positions', side_effect=AssertionError('legacy normalization')):
            with self.assertRaisesRegex(AssertionError, 'legacy normalization'):
                snapshot(raw)

    def test_cli_accepts_only_explicit_core_and_keeps_all_default(self):
        from cerveau.passive_session import parser, measured_acquisition
        self.assertEqual(parser().parse_args(['--collection', 'core']).collection, 'core')
        self.assertEqual(parser().parse_args([]).collection, 'all')
        for value in (None, 'typo', True, [], {}):
            self.assertNotIn('not_selected', measured_acquisition({'collection': value}))
        self.assertNotIn('not_selected', measured_acquisition({}))


if __name__ == '__main__':
    unittest.main()
