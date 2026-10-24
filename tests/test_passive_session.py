"""Synthetic transport only: these tests are NOT a live game recipe."""
import importlib
import unittest
from unittest.mock import patch


class PassivePreflightTests(unittest.TestCase):
    def test_product_entrypoint_preflight_without_coach_process_or_network(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('cerveau.passive_session'),
                             'durable passive entrypoint missing')
        product = importlib.import_module('cerveau.passive_session')
        with patch('hotstate.reader.ProcessBackend', side_effect=AssertionError('no process')), \
                patch('socket.socket', side_effect=AssertionError('no network')), \
                patch('cerveau.brain.Coach', side_effect=AssertionError('no coach')):
            result = product.preflight()
        self.assertTrue(result['ready'])
        for field in ('memory_opened', 'chat_called', 'audio_enabled'):
            self.assertFalse(result[field])


class Clock:
    def __init__(self):
        self.value = 10.0
    def __call__(self):
        return self.value
    def sleep(self, seconds):
        self.value += seconds


class SyntheticSource:
    """Explicitly synthetic already-normalized transport, no native evidence."""
    def __init__(self, samples):
        self.samples = iter(samples)
        self.closed = False
        self.calls = 0
    def read(self, observe):
        self.calls += 1
        item = next(self.samples)
        from hotstate.native import NativeUnavailable
        from hotstate.diagnostics import exception_refusal
        refused = isinstance(item, NativeUnavailable)
        observe({'event': 'acquisition', 'stage': 'key',
                 'outcome': 'refused' if refused else 'error' if isinstance(item, BaseException) else 'accepted',
                 'elapsed_ms': 12.5, 'reads': 30, 'bytes_requested': 500,
                 'refusal': exception_refusal(item) if refused else None, 'optional_refusals': {}})
        if isinstance(item, BaseException):
            raise item
        return item
    def close(self):
        self.closed = True


def synthetic_state(match='a'):
    return {'meta': {'match_id': match * 64, 'source': 'live',
                     'native_build': 98348, 'native_status': 'valide', 't_s': 15,
                     'context_source': 'initdata_native_fields', 'map': 'SYNTHETIC_MAP'},
            'local_player': {'id': 0, 'team': 0, 'hero': 'SYNTHETIC_HERO'},
            'ally_team': 0, 'heroes': [{'id': 0, 'team': 0, 'hero': 'SYNTHETIC_HERO'}]}


class PassiveLoopTests(unittest.TestCase):
    def run_loop(self, source, *, stopped=lambda: False, duration=1, interval=5, emit=None):
        from cerveau import passive_session as product
        rows = []
        clock = Clock()
        result = product.run_session(lambda: source, stopped, emit or rows.append,
                                     duration=duration, interval=interval,
                                     clock=clock, sleep=clock.sleep)
        return result, rows, clock

    def test_menu_waits_without_failure_but_core_refusals_hit_real_cap(self):
        from hotstate.native import NativeUnavailable
        source = SyntheticSource([NativeUnavailable('aucune_simulation_active')] * 15)
        result, rows, clock = self.run_loop(source, duration=61)
        self.assertEqual(result['reason'], 'session_limit')
        self.assertEqual(result['refused'], 13)
        self.assertEqual(result['failures'], 0)
        self.assertEqual(source.calls, 13)
        self.assertTrue(source.closed)
        source = SyntheticSource([NativeUnavailable('contexte_natif_invalide_ou_ambigu')] * 15)
        result, rows, _ = self.run_loop(source, duration=120)
        self.assertEqual(result['reason'], 'failure_limit')
        self.assertEqual(result['failures'], 12)
        self.assertEqual(source.calls, 12)
        self.assertEqual(len([r for r in rows if r['event'] == 'refusal']), 12)

    def test_session_changes_or_menu_after_binding_stop_without_second_observation(self):
        import copy
        from hotstate.native import NativeUnavailable
        changed = synthetic_state('b')
        local = copy.deepcopy(synthetic_state()); local['local_player']['hero'] = 'OTHER'
        rewind = copy.deepcopy(synthetic_state()); rewind['meta']['t_s'] = 1
        for item in (changed, local, rewind, NativeUnavailable('aucune_simulation_active'),
                     NativeUnavailable('contexte_natif_partie_changee')):
            with self.subTest(item=type(item).__name__):
                source = SyntheticSource([synthetic_state(), item])
                result, rows, _ = self.run_loop(source, duration=20)
                self.assertEqual(result['reason'], 'session_changed')
                self.assertEqual(result['accepted'], 1)
                self.assertEqual(len([r for r in rows if r['event'] == 'observation']), 1)
                self.assertEqual(len([r for r in rows if r['event'] == 'acquisition']), 2,
                                 'changed-session attempt cost was lost')
                if isinstance(item, NativeUnavailable):
                    self.assertEqual(result['refused'], 1)
                    self.assertEqual(len([r for r in rows if r['event'] == 'refusal']), 1)
                self.assertTrue(source.closed)

    def test_backend_and_open_failures_are_bounded_sanitized_and_closed(self):
        from cerveau import passive_session as product
        source = SyntheticSource([RuntimeError('PRIVATE pointer 0x123456')])
        result, rows, _ = self.run_loop(source)
        self.assertEqual(result['reason'], 'software_error')
        self.assertTrue(source.closed)
        self.assertNotIn('PRIVATE', str(rows))
        clock = Clock(); rows = []
        def absent():
            raise SystemExit('processus HeroesOfTheStorm_x64.exe introuvable')
        result = product.run_session(absent, lambda: False, rows.append,
                                     duration=120, interval=5, clock=clock, sleep=clock.sleep)
        self.assertEqual(result['reason'], 'failure_limit')
        self.assertEqual(result['attempts'], 12)
        self.assertEqual(result['failures'], 12)
        self.assertEqual([r['code'] for r in rows if r['event'] == 'source_error'], ['source_absent'] * 12)

    def test_io_failure_closes_backend_even_when_journal_raises(self):
        source = SyntheticSource([synthetic_state()])
        def broken(row):
            raise OSError('PRIVATE disk error')
        with self.assertRaises(OSError):
            self.run_loop(source, emit=broken)
        self.assertTrue(source.closed)

    def test_acquisition_is_measured_closed_vocabulary_not_a_raw_event_export(self):
        import json
        class PoisonSource(SyntheticSource):
            def read(self, observe):
                state = super().read(lambda row: None)
                observe({'event': 'PRIVATE', 'stage': 'key', 'outcome': 'accepted',
                         'elapsed_ms': 120.25, 'reads': 123, 'bytes_requested': 456,
                         'refusal': None, 'optional_refusals': {
                             'objective': {'code': 'PRIVATE', 'category': 'PRIVATE'},
                             'PRIVATE': 'PRIVATE'},
                         'raw_receipt': 'PRIVATE', 'address': '0x12345678'})
                state['heroes'].append({'id': 5, 'hero': 'PRIVATE', 'team': 1,
                                        'health': 12345, 'resource': 54321,
                                        'x': 999, 'account': 'PRIVATE'})
                state['meta']['raw_receipt'] = 'PRIVATE'
                return state
        result, rows, _ = self.run_loop(PoisonSource([synthetic_state()]))
        self.assertEqual(result['accepted'], 1)
        self.assertNotIn('PRIVATE', json.dumps(rows))
        self.assertNotIn('12345', json.dumps(rows))
        acquisition = next(r for r in rows if r['event'] == 'acquisition')
        self.assertEqual(acquisition['reads'], 123)
        self.assertEqual(acquisition['elapsed_ms'], 120.25)
        self.assertEqual(acquisition['optional_refusals']['objective']['category'], 'unknown')
        self.assertIn('timestamp_utc', acquisition)
        self.assertEqual(acquisition['cycle'], 1)

    def test_limits_reject_nonfinite_or_aggressive_values_before_factory(self):
        from cerveau import passive_session as product
        for duration, interval in ((float('nan'), 5), (0, 5), (1801, 5),
                                   (1, .1), (1, float('inf')), (1, 301)):
            with self.subTest(duration=duration, interval=interval), self.assertRaises(ValueError):
                product.run_session(lambda: self.fail('no source'), lambda: False,
                                    lambda row: None, duration=duration, interval=interval)

    def test_refused_acquisition_costs_and_phase_are_not_lost_or_fabricated(self):
        from hotstate.native import NativeUnavailable
        class Refused(SyntheticSource):
            def read(self, observe):
                self.calls += 1
                observe({'stage': 'context_recheck', 'outcome': 'refused',
                         'elapsed_ms': 130.75, 'reads': 999, 'bytes_requested': 1234,
                         'refusal': {'code': 'fenetre_pipeline_globale_depassee', 'category': 'budget'},
                         'optional_refusals': {'talents': {'code': 'PRIVATE', 'category': 'PRIVATE'}}})
                raise NativeUnavailable('fenetre_pipeline_globale_depassee')
        result, rows, _ = self.run_loop(Refused([]))
        acquisition = [r for r in rows if r['event'] == 'acquisition']
        self.assertEqual(len(acquisition), 1)
        self.assertEqual(acquisition[0]['reads'], 999)
        self.assertEqual(acquisition[0]['refusal']['category'], 'budget')
        self.assertEqual(result['failures'], 1)

    def test_close_failure_is_not_reported_as_reader_closed(self):
        from cerveau import passive_session as product
        class BrokenClose(SyntheticSource):
            def close(self):
                self.closed = True
                raise OSError('PRIVATE close error')
        source = BrokenClose([synthetic_state()])
        result, rows, _ = self.run_loop(source)
        self.assertEqual(result['reason'], 'source_close_failed')
        self.assertIsNone(result.get('reader_active'))
        self.assertIn('reader_active', result)
        self.assertTrue(source.closed)
        self.assertNotIn('PRIVATE', str(rows))

    def test_backend_error_retains_measured_failure_not_exception_text(self):
        class ErrorSource(SyntheticSource):
            def read(self, observe):
                observe({'stage': 'snapshot', 'outcome': 'error', 'elapsed_ms': 20,
                         'reads': 2, 'bytes_requested': 32, 'refusal': None})
                raise OSError('PRIVATE backend failure')
        result, rows, _ = self.run_loop(ErrorSource([]))
        self.assertEqual(result['reason'], 'software_error')
        self.assertEqual([r['outcome'] for r in rows if r['event'] == 'acquisition'], ['error'])
        self.assertEqual([r['phase'] for r in rows if r['event'] == 'error'], ['read'])
        self.assertNotIn('PRIVATE', str(rows))

    def test_deadline_after_read_discards_data_and_sleep_never_catches_up(self):
        from cerveau import passive_session as product
        clock = Clock(); rows = []
        class Slow(SyntheticSource):
            def read(self, observe):
                state = super().read(observe)
                clock.value += 2
                return state
        source = Slow([synthetic_state()])
        result = product.run_session(lambda: source, lambda: False, rows.append,
                                     duration=1, interval=5, clock=clock, sleep=clock.sleep)
        self.assertEqual(result['reason'], 'session_limit')
        self.assertEqual(result['accepted'], 0)
        self.assertFalse(any(r['event'] in ('acquisition', 'observation') for r in rows))
        self.assertTrue(source.closed)
        clock = Clock(); starts = []
        class Costly(SyntheticSource):
            def read(self, observe):
                starts.append(clock())
                clock.value += .1
                return super().read(observe)
        source = Costly([synthetic_state()] * 3)
        result = product.run_session(lambda: source, lambda: False, lambda row: None,
                                     duration=12, interval=5, clock=clock, sleep=clock.sleep)
        self.assertEqual(len(starts), 3)
        self.assertAlmostEqual(starts[1] - starts[0], 5.1)
        self.assertAlmostEqual(starts[2] - starts[1], 5.1)

    def test_stop_triggered_by_cost_persistence_preempts_refusal_or_observation(self):
        from hotstate.native import NativeUnavailable
        for item in (synthetic_state(), NativeUnavailable('contexte_natif_invalide_ou_ambigu')):
            rows = []; stop = [False]
            source = SyntheticSource([item])
            def emit(row):
                rows.append(row)
                if row['event'] == 'acquisition':
                    stop[0] = True
            result, _, _ = self.run_loop(source, stopped=lambda: stop[0], emit=emit)
            self.assertEqual(result['reason'], 'stop_file')
            self.assertFalse(any(r['event'] in ('refusal', 'observation') for r in rows))
            self.assertTrue(source.closed)

    def test_stop_before_open_and_post_read_preempts_emission_closes_source(self):
        from cerveau import passive_session as product
        self.assertTrue(callable(getattr(product, 'run_session', None)), 'session loop missing')
        source = SyntheticSource([synthetic_state()])
        result, rows, _ = self.run_loop(source, stopped=lambda: True)
        self.assertEqual(source.calls, 0)
        self.assertEqual(result['reason'], 'stop_file')
        source = SyntheticSource([synthetic_state()])
        result, rows, _ = self.run_loop(source, stopped=lambda: source.calls > 0)
        self.assertTrue(source.closed)
        self.assertEqual(result['accepted'], 0)
        self.assertFalse(any(r['event'] in ('acquisition', 'observation') for r in rows))


class PassiveCLITests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / 'session'
        self.stop = self.root / 'STOP'
        self.player = self.root / 'private.txt'
        self.player.write_text('SYNTHETIC_IDENTITY', encoding='utf-8')

    def arguments(self):
        return ['--live', '--player-file', str(self.player), '--output-dir', str(self.output),
                '--stop-file', str(self.stop), '--max-seconds', '1']

    def test_native_source_uses_actual_consumer_callbacks_and_fresh_probe(self):
        from cerveau import passive_session as product
        from cerveau.state import snapshot
        from cerveau.runner import tactical_key
        self.assertTrue(callable(getattr(product, 'NativeSource', None)), 'native adapter missing')
        backend = SyntheticSource([])
        with patch('hotstate.reader.ProcessBackend', return_value=backend), \
                patch('hotstate.live.read_current', return_value=synthetic_state()) as read:
            source = product.NativeSource('SYNTHETIC_IDENTITY')
            source.read(lambda row: None)
            source.close()
        self.assertTrue(backend.closed)
        self.assertIs(read.call_args.kwargs['project'], snapshot)
        self.assertIs(read.call_args.kwargs['key'], tactical_key)
        self.assertEqual(read.call_args.args[1], {'triggers': {}})

    def test_process_constructor_closes_handle_when_module_initialization_fails(self):
        from hotstate.reader import ProcessBackend
        from unittest.mock import MagicMock
        kernel = MagicMock(); kernel.OpenProcess.return_value = 123
        with patch('hotstate.reader.ctypes.WinDLL', return_value=kernel), \
                patch.object(ProcessBackend, '_find_pid', return_value=42), \
                patch.object(ProcessBackend, '_module_info', side_effect=RuntimeError('SYNTHETIC')):
            with self.assertRaises(RuntimeError):
                ProcessBackend()
        kernel.CloseHandle.assert_called_once_with(123)

    def test_cli_writes_current_status_and_summary_for_a_synthetic_session(self):
        import json
        from cerveau import passive_session as product
        source = SyntheticSource([synthetic_state()])
        def stop_after_observation(row):
            if row['event'] == 'observation':
                self.stop.touch()
        original = product.run_session
        def synthetic_run(factory, stopped, emit, **kwargs):
            def persist_then_stop(row):
                emit(row)
                self.assertTrue((self.output / 'status.json').is_file(), 'current status missing')
                stop_after_observation(row)
            return original(factory, stopped, persist_then_stop, **kwargs)
        with patch.object(product, 'NativeSource', return_value=source), \
                patch.object(product, 'run_session', side_effect=synthetic_run):
            self.assertEqual(product.main(self.arguments()), 0)
        summary = json.loads((self.output / 'summary.json').read_text())
        status = json.loads((self.output / 'status.json').read_text())
        self.assertEqual(summary['accepted'], 1)
        self.assertEqual(summary['reason'], 'stop_file')
        self.assertFalse(summary['reader_active'])
        self.assertEqual(status['event'], 'summary')
        self.assertTrue(source.closed)
        self.assertFalse((self.root / 'passive-session.lock').exists())

    def test_cli_help_import_and_default_preflight_real_subprocesses(self):
        """Entrypoint characterization, no live opt-in in any subprocess."""
        import subprocess
        import sys
        import json
        for argv in (['--help'], []):
            result = subprocess.run([sys.executable, '-B', '-m', 'cerveau.passive_session', *argv],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            if not argv:
                self.assertTrue(json.loads(result.stdout)['ready'])
            else:
                self.assertNotIn('--coach', result.stdout)
                self.assertIn('--player-file', result.stdout)
        result = subprocess.run([sys.executable, '-B', '-c',
                                 'import cerveau.passive_session, sys; print("hotstate.reader" in sys.modules)'],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'False')

    def test_stop_stat_error_and_initialization_stop_fail_closed(self):
        from cerveau import passive_session as product
        with patch('pathlib.Path.stat', side_effect=PermissionError('PRIVATE')):
            with self.assertRaises(PermissionError):
                product.stop_requested(self.stop)
        from cerveau.player_identity import read_player_label
        def read_then_stop(path):
            label = read_player_label(path)
            self.stop.touch()
            return label
        with patch('cerveau.player_identity.read_player_label', side_effect=read_then_stop), \
                patch.object(product, 'NativeSource', side_effect=AssertionError('no source')):
            self.assertEqual(product.main(self.arguments()), 0)
        self.assertFalse((self.root / 'passive-session.lock').exists())

    def test_stop_during_initial_status_precedes_identity(self):
        from cerveau import passive_session as product
        import os
        replace = os.replace
        def persist_then_stop(*args):
            replace(*args)
            self.stop.touch()
        with patch.object(product.os, 'replace', side_effect=persist_then_stop), \
                patch('cerveau.player_identity.read_player_label', side_effect=AssertionError('no identity')):
            self.assertEqual(product.main(self.arguments()), 0)
        self.assertFalse((self.root / 'passive-session.lock').exists())

    def test_cli_stop_precedes_identity_output_and_source(self):
        from cerveau import passive_session as product
        self.assertTrue(callable(getattr(product, 'main', None)), 'product CLI missing')
        self.stop.touch()
        with patch('cerveau.player_identity.read_player_label', side_effect=AssertionError('no identity')), \
                patch.object(product, 'NativeSource', side_effect=AssertionError('no source')):
            self.assertEqual(product.main(self.arguments()), 0)
        self.assertFalse(self.output.exists())

    def test_new_output_and_exclusive_parent_lock_release_after_io_error(self):
        from cerveau import passive_session as product
        self.assertTrue(callable(getattr(product, 'main', None)), 'product CLI missing')
        source = SyntheticSource([synthetic_state()])
        def broken(*args, **kwargs):
            raise OSError('PRIVATE IO ERROR')
        with patch.object(product, 'NativeSource', return_value=source), \
                patch.object(product, 'run_session', side_effect=broken):
            self.assertEqual(product.main(self.arguments()), 1)
        self.assertFalse((self.root / 'passive-session.lock').exists())
        with patch('cerveau.player_identity.read_player_label', side_effect=AssertionError('no identity')):
            self.assertEqual(product.main(self.arguments()), 1)
        other = self.root / 'other'
        self.output = other
        lock = self.root / 'passive-session.lock'; lock.touch()
        with patch('cerveau.player_identity.read_player_label', side_effect=AssertionError('no identity')):
            self.assertEqual(product.main(self.arguments()), 1)
        self.assertTrue(lock.exists())
        self.assertFalse(other.exists())


if __name__ == '__main__':
    unittest.main()
