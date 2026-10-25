"""SYNTHETIC mapped IO only; selected collection is not a live qualification."""
import unittest
from unittest.mock import patch

import test_day_composition as composition
from test_capture_visibility_pipeline import FixtureProcess

from cerveau.runner import tactical_key
from cerveau.state import snapshot
from hotstate import live
from hotstate.gameplay import GameplayClock


class TalentsCollectionModeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = composition.DayCompositionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def take(self, collection, observe=None):
        return live.read_current(
            FixtureProcess(self.fixture.memory),
            {'triggers': {}, 'collection': collection},
            context=self.fixture.memory.probe(), project=snapshot, key=tactical_key,
            observe=observe)

    def test_talents_mode_does_not_acquire_unselected_gameplay_clock(self):
        with patch.object(GameplayClock, 'read', side_effect=AssertionError('unselected IO')):
            clean = self.take('talents')
        self.assertIn('talents', clean)
        self.assertNotIn('local_cooldowns', clean)
        self.assertEqual(clean['talents']['players'][0]['status'], 'observed')

    def test_selection_is_durable_closed_and_not_reported_as_refusal(self):
        from cerveau.passive_session import measured_acquisition
        rows = []
        self.take('talents', rows.append)
        stored = measured_acquisition(rows[0])
        self.assertEqual(stored.get('collection'), 'talents')
        self.assertEqual(stored.get('not_selected'), [
            'gameplay_clock', 'positions', 'visibility', 'objective', 'local_cooldowns', 'battlefield'])
        self.assertEqual(stored['optional_refusals'], {})
        poisoned = dict(rows[0], collection='PRIVATE', not_selected=['PRIVATE'])
        self.assertNotIn('PRIVATE', str(measured_acquisition(poisoned)))

    def test_direct_native_reader_rejects_unknown_collection(self):
        from hotstate.native import NativeReader
        native = NativeReader(self.fixture.memory, profile=self.fixture.memory.profile)
        with self.assertRaisesRegex(ValueError, 'invalid_collection'):
            native.read_state(self.fixture.memory.context, collection='typo')

    # Additional safety characterizations: immediately green, not claimed RED.
    def test_every_unselected_family_is_skipped_before_its_reader(self):
        from contextlib import ExitStack
        names = ('hotstate.gameplay.GameplayClock.read', 'hotstate.positions.AlliedPositions.read',
                 'hotstate.visibility.CurrentVisibility.read', 'hotstate.objectives.VolskayaObjective.read',
                 'hotstate.dragon.DragonObjective.read', 'hotstate.cooldown_packet.LocalCooldowns.read',
                 'hotstate.battlefield.VolskayaBattlefield.read',
                 'hotstate.dragon_battlefield.DragonBattlefield.read')
        with ExitStack() as stack:
            for name in names:
                stack.enter_context(patch(name, side_effect=AssertionError('unselected IO')))
            clean = self.take('talents')
        self.assertIn('talents', clean)
        self.assertTrue(set(clean).isdisjoint(('objective', 'battlefield', 'positions', 'visibility')))

    def test_cost_is_reduced_without_changing_core_or_talent_physical_bytes(self):
        from contextlib import ExitStack

        from hotstate.battlefield import VolskayaBattlefield
        from hotstate.cooldown_packet import LocalCooldowns
        from hotstate.objectives import VolskayaObjective
        from hotstate.positions import AlliedPositions
        from hotstate.talents import NativeTalentChoices
        from hotstate.visibility import CurrentVisibility
        classes = (GameplayClock, AlliedPositions, CurrentVisibility, VolskayaObjective,
                   NativeTalentChoices, LocalCooldowns, VolskayaBattlefield)
        memory = self.fixture.memory
        original = memory.read_memory
        scope = ['core_context']
        trace = []
        def read(address, size):
            data = original(address, size)
            trace.append((scope[0], address, size, data))
            return data
        with ExitStack() as stack:
            stack.enter_context(patch.object(memory, 'read_memory', read))
            for cls in classes:
                old = cls.read
                def wrapped(reader, *args, _old=old, _name=cls.__name__, **kwargs):
                    before, scope[0] = scope[0], _name
                    try:
                        return _old(reader, *args, **kwargs)
                    finally:
                        scope[0] = before
                stack.enter_context(patch.object(cls, 'read', wrapped))
            full = self.take('all')
            all_trace = trace[:]
            trace.clear()
            selected = self.take('talents')
        relevant = [r for r in all_trace if r[0] in ('core_context', 'NativeTalentChoices')]
        self.assertEqual(trace, relevant, 'exact ordered core/context/talent physical byte coverage')
        self.assertLess(len(trace), len(all_trace))
        self.assertLess(sum(r[2] for r in trace), sum(r[2] for r in all_trace))
        self.assertEqual(selected['heroes'], full['heroes'])
        self.assertEqual(selected['talents'], full['talents'])
        selected_q, full_q = selected['talents_qualification'], full['talents_qualification']
        self.assertEqual({k: v for k, v in selected_q.items() if k != 'age_s'},
                         {k: v for k, v in full_q.items() if k != 'age_s'})
        self.assertGreater(selected_q['age_s'], 0)
        self.assertLess(selected_q['age_s'], full_q['age_s'])

    def test_synthetic_optional_load_cannot_spend_selected_collection_budget(self):
        from hotstate.native import NativeUnavailable
        def heavy(reader):
            # Real counted reads of mapped fixture MZ; synthetic workload, NOT
            # a reconstruction or attribution of the historical 8192 failure.
            for _ in range(8192):
                reader.native.read(reader.native.base, 2)
        with patch.object(GameplayClock, 'read', heavy):
            with self.assertRaisesRegex(NativeUnavailable, 'budget_pipeline_depasse'):
                self.take('all')
            self.assertIn('talents', self.take('talents'))

    def test_selected_collection_keeps_read_byte_and_late_decode_refusals(self):
        from hotstate.native import NativeUnavailable
        from hotstate.talents import NativeTalentChoices
        original = NativeTalentChoices.read
        kind = [None]
        def limited(reader, *args, **kwargs):
            packet = original(reader, *args, **kwargs)
            if kind[0] == 'reads':
                self.fixture.budgets[-1].reads = 8192
            elif kind[0] == 'bytes':
                self.fixture.budgets[-1].bytes_requested = 2**20
            else:
                self.fixture.clock.value += .126
            return packet
        with patch.object(NativeTalentChoices, 'read', limited):
            for item in ('reads', 'bytes', 'late'):
                kind[0] = item
                with self.subTest(item=item), self.assertRaisesRegex(NativeUnavailable, 'depasse'):
                    self.take('talents')

    def test_selected_collection_still_rejects_original_core_tick_conflict(self):
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
            self.take('talents')

    def test_selected_collection_keeps_build_guard(self):
        from hotstate.native import NativeUnavailable
        memory = self.fixture.memory
        memory.put(memory.module_base + 0x200, b'CHANGED')
        with self.assertRaises(NativeUnavailable):
            self.take('talents')

    def test_selected_collection_keeps_observer_perspective_guard(self):
        from hotstate.native import NativeUnavailable
        self.fixture.memory.pack(0x120000, 'I', 0x20)
        with self.assertRaises(NativeUnavailable):
            self.take('talents')

    def test_selected_collection_rejects_final_context_replacement(self):
        from hotstate.native import NativeReader, NativeUnavailable
        original = NativeReader.read_state
        def changed(reader, *args, **kwargs):
            result = original(reader, *args, **kwargs)
            memory = self.fixture.memory
            memory.pack(memory.config + 0x1d428, 'I', memory.seed + 1)
            return result
        with patch.object(NativeReader, 'read_state', changed), self.assertRaisesRegex(
                NativeUnavailable, 'contexte_natif_dechire'):
            self.take('talents')

    def test_invalid_mapping_fails_before_any_physical_read(self):
        for value in ('typo', None, True, [], {}):
            with self.subTest(value=value), patch.object(
                    self.fixture.memory, 'read_memory', side_effect=AssertionError('no IO')), \
                    self.assertRaisesRegex(ValueError, 'invalid_collection'):
                self.take(value)


class TalentsCollectionCLITests(unittest.TestCase):
    def test_explicit_talents_cli_mode_is_preserved_with_core_default(self):
        from cerveau.passive_session import parser
        self.assertEqual(getattr(parser().parse_args([]), 'collection', None), 'core')
        self.assertEqual(parser().parse_args(['--collection', 'talents']).collection, 'talents')

    def test_talent_only_observation_binds_native_map_without_objective_acquisition(self):
        import test_passive_session as transport

        from cerveau.passive_session import run_session
        state = transport.synthetic_state()
        state['talents'] = {'map_id': 'DragonShire'}  # synthetic normalized transport
        source = transport.SyntheticSource([state])
        clock = transport.Clock()
        rows = []
        run_session(lambda: source, lambda: False, rows.append,
                    duration=1, interval=1, clock=clock, sleep=clock.sleep)
        observed = next(r for r in rows if r['event'] == 'observation')
        self.assertEqual(observed['comparison']['map_id'], 'DragonShire')


if __name__ == '__main__':
    unittest.main()
