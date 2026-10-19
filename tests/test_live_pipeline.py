"""Production live-entrypoint budgets; synthetic IO, never live recipe evidence."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from hotstate.native import NativeUnavailable
from hotstate.native_context import NativeContextProbe
from hotstate.reader import ProcessBackend
from hotstate.live import LiveBudget, read_current


class Clock:
    def __init__(self):
        self.value = 100.0
    def __call__(self):
        return self.value


class Backend(ProcessBackend):
    def __init__(self):
        self.module_base = 0x140000000
        self.calls = []
    def read_memory(self, address, size):
        self.calls.append((address, size))
        return bytes(size)


class LivePipelineTests(unittest.TestCase):
    def test_physical_limits_refuse_before_io_and_latch_across_optional_catches(self):
        for size, count in ((1, 8192), (65536, 16)):
            clock = Clock(); backend = Backend(); memory = LiveBudget(backend, clock=clock)
            for _ in range(count):
                memory.read_memory(0x10000, size)
            with self.assertRaisesRegex(NativeUnavailable, 'budget_pipeline_depasse'):
                memory.read_memory(0x10000, size)
            with self.assertRaisesRegex(NativeUnavailable, 'budget_pipeline_depasse'):
                memory.read_memory(0x10000, 1)
            self.assertEqual(len(backend.calls), count)
            with self.assertRaises(NativeUnavailable):
                memory.check()

    def test_failures_count_and_time_is_wall_not_mission_and_is_latched(self):
        clock = Clock(); backend = Backend(); memory = LiveBudget(backend, clock=clock)
        with patch.object(backend, 'read_memory', return_value=None):
            self.assertIsNone(memory.read_memory(0x10000, 32))
        self.assertEqual(memory.reads, 1)
        self.assertEqual(memory.bytes_requested, 32)
        clock.value += 0.126
        with self.assertRaisesRegex(NativeUnavailable, 'fenetre_pipeline_globale_depassee'):
            memory.read_memory(0x10000, 1)
        self.assertEqual(backend.calls, [])
        clock.value = 100
        with self.assertRaises(NativeUnavailable):
            memory.check()

    def test_context_core_rechecks_normalization_and_key_share_one_budget(self):
        backend = Backend(); clock = Clock()
        probe = NativeContextProbe('PRIVATE_TEST')
        stages = []
        def acquire(memory, mapping, **options):
            self.assertIsInstance(memory, ProcessBackend)
            self.assertIs(options['context'], probe)
            stages.append('context-core-family')
            memory.read_memory(0x10000, 8)
            return {'meta': {'source': 'live', 'native_status': 'valide'}, 'battlefield': {}}
        def recheck(memory):
            stages.append('recheck'); memory.read_memory(0x10008, 4)
        def project(raw):
            stages.append('normalize'); clock.value += 0.04
            return {'normalized': True}
        def key(clean):
            stages.append('key'); clock.value += 0.04
            return 'key'
        with patch('hotstate.live.memory_snapshot', side_effect=acquire), patch.object(probe, 'recheck', side_effect=recheck):
            clean = read_current(backend, {}, context=probe, project=project, key=key, clock=clock)
        self.assertEqual(clean, {'normalized': True})
        self.assertEqual(stages, ['context-core-family', 'recheck', 'normalize', 'key'])
        self.assertEqual(len(backend.calls), 2)

    def test_post_normalization_and_key_overrun_never_returns_a_full(self):
        for delayed_stage in ('snapshot', 'recheck', 'project', 'key'):
            backend = Backend(); clock = Clock(); probe = NativeContextProbe('PRIVATE_TEST')
            def advance(stage, result=None):
                if stage == delayed_stage:
                    clock.value += 0.126
                return result
            with patch('hotstate.live.memory_snapshot', side_effect=lambda *a, **kw: advance('snapshot', {'meta': {'native_status': 'valide'}})), \
                    patch.object(probe, 'recheck', side_effect=lambda *a: advance('recheck')):
                with self.subTest(stage=delayed_stage), self.assertRaises(NativeUnavailable):
                    read_current(backend, {}, context=probe,
                        project=lambda raw: advance('project', {}), key=lambda clean: advance('key'), clock=clock)

    def test_optional_budget_refusal_cannot_publish_partial_core(self):
        backend = Backend(); clock = Clock(); probe = NativeContextProbe('PRIVATE_TEST')
        def swallowed(memory, *args, **options):
            try:
                for _ in range(8193):
                    memory.read_memory(0x10000, 1)
            except NativeUnavailable:
                pass
            return {'partial': True}
        with patch('hotstate.live.memory_snapshot', side_effect=swallowed), patch.object(probe, 'recheck'), \
                self.assertRaisesRegex(NativeUnavailable, 'budget_pipeline_depasse'):
            read_current(backend, {}, context=probe, clock=clock)
        self.assertEqual(len(backend.calls), 8192)

    def test_unknown_context_or_recorded_dump_refused_before_io(self):
        for context, recorded in ((None, False), (SimpleNamespace(), False), (NativeContextProbe('PRIVATE_TEST'), True)):
            backend = Backend(); backend.recorded_non_atomic = recorded
            with self.assertRaises(NativeUnavailable):
                read_current(backend, {}, context=context)
            self.assertEqual(backend.calls, [])

    def test_real_reader_context_normalizer_key_without_gate_patch(self):
        from test_native_context import TypedContextMemory
        from test_capture_visibility_pipeline import FixtureProcess, PipelineCollectorTests
        from test_capture_battlefield_pipeline import BattlefieldPipelineTests
        from hotstate.battlefield import VolskayaBattlefield
        from hotstate.reader import snapshot as acquire
        from cerveau.state import snapshot as normalize
        from cerveau.runner import tactical_key
        m = TypedContextMemory(); probe = m.probe()
        a, b, c = PipelineCollectorTests().options(m)
        # Only source bytes/profile and business observations are fixtures.
        # No reader, normalizer, key or release gate is replaced.
        def sample(reader, *args, **kwargs):
            return BattlefieldPipelineTests().sample(*args, **kwargs)
        def acquire_fixture(memory, mapping, **kwargs):
            return acquire(memory, mapping, native_profile=m.profile, **kwargs)
        with a, b, c, patch.object(VolskayaBattlefield, '_observe', autospec=True, side_effect=sample), \
                patch('hotstate.live.memory_snapshot', side_effect=acquire_fixture), \
                patch('cerveau.brain.Coach.decide', side_effect=AssertionError('no coach')):
            clean = read_current(FixtureProcess(m), {'triggers': {}}, context=probe,
                                 project=normalize, key=tactical_key)
        self.assertEqual(len(clean['battlefield']['camps']['entries']), 5)
        self.assertEqual(len(clean['battlefield']['structures']['entries']), 90)
        self.assertEqual(clean['battlefield']['structures']['health_basis'], 'life_component')
        self.assertEqual(clean['local_player']['id'], 5)
        self.assertNotIn('OWNER_TEST', str(clean))

    def test_native_core_failure_is_not_normalized_or_rechecked(self):
        probe = NativeContextProbe('PRIVATE_TEST')
        with patch('hotstate.live.memory_snapshot', return_value={'meta': {'native_status': 'lecture_native_dechiree'}}), \
                patch.object(probe, 'recheck') as recheck:
            with self.assertRaisesRegex(NativeUnavailable, 'lecture_native_dechiree'):
                read_current(Backend(), {}, context=probe)
            recheck.assert_not_called()

    def test_cerveau_live_source_uses_guarded_entrypoint_and_key(self):
        from cerveau.__main__ import make_source
        from cerveau.runner import tactical_key
        args = SimpleNamespace(at=None, team=None, map=None, allies=None, enemies=None,
                               state=None, dump=None, pid=None, player='PRIVATE_TEST')
        backend = Backend()
        with patch('hotstate.reader.ProcessBackend', return_value=backend), \
                patch('hotstate.live.read_current', return_value={'guarded': True}) as read:
            source, owned = make_source(args)
            self.assertIs(owned, backend)
            self.assertEqual(source(), {'guarded': True})
        self.assertIs(read.call_args.kwargs['key'], tactical_key)
        self.assertIsInstance(read.call_args.kwargs['context'], NativeContextProbe)


if __name__ == '__main__':
    unittest.main()
