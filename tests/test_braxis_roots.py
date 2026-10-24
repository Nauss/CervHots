"""Hermetic native root diagnostics; synthetic memory, no game backend."""
import importlib.util
import struct
import unittest
from hotstate import braxis
from tests.test_braxis_diagnostic import Sparse


class SelectorTests(unittest.TestCase):
    def roots(self):
        self.assertIsNotNone(importlib.util.find_spec('hotstate.braxis_roots'),
                             'independent runtime-root experiment missing')
        from hotstate import braxis_roots
        return braxis_roots

    def test_empty_execution_stack_records_fallback_without_dereference(self):
        roots = self.roots()
        m = Sparse()
        m.put(m.module_base + 0x2f71528, struct.pack('<I', 0))
        result = roots.context_selector(braxis.WholeTx(m))
        self.assertEqual(result['selection'], 'fallback_only')
        self.assertIsNone(result['selected'])
        self.assertEqual(len(m.calls), 2)
        self.assertTrue(all(a == m.module_base + 0x2f71528 for a, _ in m.calls))
        self.assertFalse(result['active_vm_proven'])

    def test_selected_context_is_bracketed_but_not_active_membership(self):
        roots = self.roots()
        m = Sparse()
        m.put(m.module_base + 0x2f71528, struct.pack('<I', 2))
        m.u(m.module_base + 0x2f71538, 0x20000)
        m.u(0x20008, 0x30000)
        row = braxis.run_channel(braxis.WholeTx(m), roots.context_selector)
        self.assertEqual(row['status'], 'observed')
        self.assertEqual(row['result']['selected'], 0x30000)
        self.assertEqual(row['result']['selection'], 'stack_selected')
        self.assertFalse(row['result']['active_vm_proven'])
        self.assertEqual(row['requests'], 6)
        self.assertFalse(any(a == 0x30000 for a, _ in m.calls))

    def test_descriptor_arena_header_is_physical_not_scho_allocation(self):
        roots = self.roots()
        self.assertTrue(hasattr(roots, 'descriptor_arena'), 'arena channel missing')
        m = Sparse()
        # Growth publishes block, end, base and cursor at +10/+18/+20/+28.
        m.put(m.module_base + 0x2fa7300,
              struct.pack('<6Q', 4096, 15, 0x40000, 0x41000, 0x40010, 0x40100))
        m.put(0x40000, struct.pack('<2Q', 0x41000, 0))
        row = braxis.run_channel(braxis.WholeTx(m), roots.descriptor_arena)
        self.assertEqual(row['status'], 'observed')
        self.assertEqual(row['requests'], 4)
        self.assertTrue(row['result']['header_consistent'])
        self.assertFalse(row['result']['scho_allocation_proven'])
        self.assertEqual({n for _, n in m.calls}, {16, 48})

    def test_simulation_root_rechecks_database_and_raw_reset_bound(self):
        roots = self.roots()
        self.assertTrue(hasattr(roots, 'simulation_root'), 'simulation root channel missing')
        m = Sparse()
        m.u(m.module_base + 0x3388b18, 0x20000)
        m.u(0x202a0, 0x30000)
        m.put(0x30038, struct.pack('<H', 32))
        row = braxis.run_channel(braxis.WholeTx(m), roots.simulation_root)
        self.assertEqual(row['status'], 'observed')
        self.assertEqual(row['requests'], 6)
        self.assertEqual(row['result']['reset_bound_raw'], 32)
        self.assertFalse(row['result']['scho_membership_proven'])

    def test_null_simulation_root_is_scoped_not_unattempted_or_global_absence(self):
        from hotstate import braxis_roots as roots
        m = Sparse()
        m.u(m.module_base + 0x3388b18, 0)
        row = braxis.run_channel(braxis.WholeTx(m), roots.simulation_root)
        report = braxis.measure({'roots.simulation_root': row})
        self.assertIn('roots.simulation_root', report['scoped_absences'])
        self.assertEqual(report['unattempted'], [])
        self.assertFalse(report['global_absence_proven'])

    def test_unit_pages_measure_reference_slots_not_tactical_state(self):
        roots = self.roots()
        self.assertTrue(hasattr(roots, 'unit_pages'), 'native alternative channel missing')
        m = pool_memory()
        result = roots.unit_pages(braxis.WholeTx(m))
        self.assertEqual(result['limit'], 2)
        self.assertEqual(result['references'], [[0, 2]])
        self.assertEqual(result['null_pages'], [])
        self.assertFalse(result['scho_allocation_proven'])
        self.assertFalse(result['lifetime_proven'])
        self.assertEqual([a for a, n in m.calls if n == 4 and 0x40000 <= a < 0x41000],
                         [0x40010, 0x40300, 0x40010, 0x40300])


class BoundaryCharacterizationTests(unittest.TestCase):
    """Immediately-green safety characterization, not extra historical RED."""
    def test_selector_bound_and_null_roots_have_real_attempt_costs(self):
        from hotstate import braxis_roots as roots
        for count, table, expected in ((4097, None, 'selector_bound'),
                                       (1, 0, 'selector_table_null'),
                                       (1, 0x20000, 'selector_slot_null')):
            m = Sparse()
            m.put(m.module_base + 0x2f71528, struct.pack('<I', count))
            if table is not None:
                m.u(m.module_base + 0x2f71538, table)
                m.u(0x20000, 0)
            row = braxis.run_channel(braxis.WholeTx(m), roots.context_selector)
            with self.subTest(expected=expected):
                self.assertEqual(row['reason'], expected)
                self.assertGreater(row['requests'], 0)

    def test_selector_change_is_not_absence(self):
        from hotstate import braxis_roots as roots
        m = Sparse()
        m.put(m.module_base + 0x2f71528, struct.pack('<I', 0))
        original = m.read_memory
        def changed(a, n):
            if len(m.calls) == 1:
                return struct.pack('<I', 1)
            return original(a, n)
        m.read_memory = changed
        row = braxis.run_channel(braxis.WholeTx(m), roots.context_selector)
        self.assertEqual(row['reason'], 'selector_changed')
        self.assertEqual(braxis.measure({'roots.selector': row})['scoped_absences'], [])

    def test_budget_before_roots_remains_unattempted(self):
        from hotstate import braxis_roots as roots
        tx = braxis.WholeTx(Sparse())
        tx.limit_reads = 0
        rows = roots.diagnose(tx)
        self.assertTrue(all(r['status'] == 'not_attempted' and r['requests'] == 0 for r in rows.values()))
        self.assertEqual(braxis.measure(rows)['scoped_absences'], [])

    def test_null_unit_page_is_not_read_as_allocated_payload(self):
        from hotstate import braxis_roots as roots
        m = pool_memory()
        m.put(m.module_base + 0x34f02c8, struct.pack('<II', 0x1234, (-7) & 0xffffffff))
        result = roots.unit_pages(braxis.WholeTx(m))
        self.assertEqual(result['null_pages'], [0])
        self.assertEqual(result['references'], [])
        self.assertFalse(any(0x40000 <= a < 0x41000 for a, _ in m.calls))

    def test_generation_changing_during_bracket_refuses_whole_channel(self):
        from hotstate import braxis_roots as roots
        m = pool_memory()
        original = m.read_memory
        read_count = [0]
        def changed(a, n):
            if a == 0x40010:
                read_count[0] += 1
                if read_count[0] == 2:
                    return struct.pack('<I', 3)
            return original(a, n)
        m.read_memory = changed
        row = braxis.run_channel(braxis.WholeTx(m), roots.unit_pages)
        self.assertEqual(row['reason'], 'unit_reference_changed')
        self.assertNotIn('result', row)

    def test_max_native_registry_is_bounded_below_whole_read_and_byte_limits(self):
        from hotstate import braxis_roots as roots
        m = pool_memory()
        m.put(m.module_base + 0x34f02c0, struct.pack('<II', 0, 1024))
        for ordinal in range(64):
            page = 0x100000 + ordinal * 0x4000
            m.put(m.module_base + 0x34f02c8 + ordinal * 8,
                  struct.pack('<II', page ^ 0x1234, (-7) & 0xffffffff))
            for index in range(16):
                m.put(page + index * 0x2f0 + 0x10,
                      struct.pack('<I', ((ordinal * 16 + index) << 22) | 2))
        tx = braxis.WholeTx(m)
        result = roots.unit_pages(tx)
        self.assertEqual(len(result['references']), 1024)
        self.assertEqual(len(tx.reads), 2182)
        self.assertEqual(tx.bytes, 9248)
        self.assertFalse(result['lifetime_proven'])

    def test_out_of_scope_pool_domain_is_not_clamped_to_zero_or_partial(self):
        from hotstate import braxis_roots as roots
        for limit in (0, 1025):
            m = pool_memory()
            m.put(m.module_base + 0x34f02c0, struct.pack('<II', 0, limit))
            row = braxis.run_channel(braxis.WholeTx(m), roots.unit_pages)
            self.assertEqual(row['reason'], 'unit_pool_bound')
            self.assertEqual(row['requests'], 1)

    def test_inconsistent_arena_bounds_refuse_before_block_dereference(self):
        from hotstate import braxis_roots as roots
        m = Sparse()
        m.put(m.module_base + 0x2fa7300,
              struct.pack('<6Q', 4096, 15, 0x40000, 0x41000, 0x40010, 0x42000))
        row = braxis.run_channel(braxis.WholeTx(m), roots.descriptor_arena)
        self.assertEqual(row['reason'], 'descriptor_arena_bounds')
        self.assertEqual(row['requests'], 1)


class SampledLifetimeTests(unittest.TestCase):
    def test_session_persists_adjacent_sample_states_without_exporting_tags(self):
        import copy
        import json
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        now, calls = [0.0], [0]
        backend = Sparse()
        backend.close = lambda: None
        def collect(memory, **kwargs):
            raw = qualified_sample()
            calls[0] += 1
            raw.update(physical_requests=1, bytes_requested=4, reads=[])
            raw['mission_clock'] = [float(calls[0]), float(calls[0])]
            if calls[0] == 2:
                raw['channels']['roots.unit_pages']['result']['references'] = [[0, 3]]
            if calls[0] == 3:
                raw['channels']['roots.unit_pages'] = {'status': 'refused', 'reason': 'unit_pool_changed', 'requests': 1}
            return raw
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'new'
            summary = cli.run_session(out, [], seconds=10, interval=1, max_attempts=3,
                player_label='SYNTHETIC', backend_factory=lambda: backend, clock=lambda: now[0],
                sleep=lambda seconds: now.__setitem__(0, now[0] + seconds), collect_attempt=collect)
            self.assertEqual(summary['public_persisted'], 3)
            rows = [json.loads(x) for x in (out / 'attempts.jsonl').read_text().splitlines()]
            self.assertIn('sample_transitions', rows[0].get('runtime_roots', {}),
                          'session does not persist sampled lifecycle measurements')
            self.assertEqual([x['runtime_roots']['sample_transitions']['roots.unit_pages'] for x in rows],
                             ['first_sample', 'sample_changed', 'not_comparable'])
            self.assertNotIn('references', json.dumps(rows))

    def test_sampled_changes_require_same_bracketed_holdout_and_never_prove_lifetime(self):
        from hotstate import braxis_roots as roots
        self.assertTrue(hasattr(roots, 'sample_transitions'), 'sampled lifecycle measurement missing')
        import copy
        current = qualified_sample()
        first = roots.sample_transitions(None, current)
        self.assertEqual(first['roots.unit_pages'], 'first_sample')
        previous = copy.deepcopy(current)
        current['mission_clock'] = [2.0, 2.0]
        self.assertEqual(roots.sample_transitions(previous, current)['roots.unit_pages'], 'sample_equal')
        current['channels']['roots.unit_pages']['result']['references'] = [[0, 3]]
        self.assertEqual(roots.sample_transitions(previous, current)['roots.unit_pages'], 'sample_changed')
        for mutation in ('match', 'outpost', 'context', 'clock', 'gap', 'budget', 'refusal'):
            raw = copy.deepcopy(current)
            if mutation == 'match':
                raw['channels']['context']['result']['meta']['match_id'] = 'OTHER_SYNTHETIC'
            elif mutation == 'outpost':
                raw['target_map'] = 'wrong_map'
            elif mutation == 'context':
                raw['channels']['context_after']['status'] = 'refused'
            elif mutation == 'clock':
                raw['mission_clock'] = [0.0, 0.0]
            elif mutation == 'gap':
                raw['mission_clock'] = [12.0, 12.0]
            elif mutation == 'budget':
                raw['elapsed_s'] = .126
            else:
                raw['channels']['roots.unit_pages']['status'] = 'refused'
            with self.subTest(mutation=mutation):
                self.assertEqual(roots.sample_transitions(previous, raw)['roots.unit_pages'], 'not_comparable')


def qualified_sample():
    return {'experiment': 'runtime-roots', 'target_map': 'holdout_recorded',
            'build': {'status': 'observed'}, 'mission_clock': [1.0, 1.0], 'elapsed_s': .001,
            'channels': {'context': {'status': 'observed', 'result': {'meta': {'match_id': 'SYNTHETIC'}}},
                         'context_after': {'status': 'observed'},
                         'roots.unit_pages': {'status': 'observed', 'result': {'references': [[0, 2]]}}}}


class ReplayRootsTests(unittest.TestCase):
    def test_exact_runtime_readset_replays_pins_and_missing_roots_without_synthesis(self):
        from hotstate import braxis_roots as roots, braxis_diagnostic as cli
        import copy
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        m = pool_memory()
        m.put(m.module_base + 0x1000, b'OK')
        m.put(m.module_base + 0x2f71528, struct.pack('<I', 0))
        m.u(m.module_base + 0x3388b18, 0)
        pin = {'rva': 0x1000, 'size': 2, 'sha256': hashlib.sha256(b'OK').hexdigest()}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'profile.json'
            path.write_text(json.dumps({'image_size': m.module_size,
                                        'channels': {n: [pin] for n in roots.DECODERS}}))
            with patch.object(roots, 'PROFILE', path):
                tx = braxis.WholeTx(m)
                rows = roots.diagnose(tx)
                raw = {'schema': 'braxis-runtime-roots-v1', 'module_base': m.module_base,
                       'module_size': m.module_size, 'experiment': 'runtime-roots',
                       'channels': rows, 'reads': tx.reads}
                replay = cli.replay_attempt(raw)
                self.assertEqual(replay['channels']['roots.selector']['status'], 'observed')
                self.assertEqual(replay['channels']['roots.unit_pages']['status'], 'observed')
                self.assertEqual(replay['channels']['roots.simulation_root']['reason'], 'simulation_root_null')
                self.assertEqual(replay['channels']['roots.descriptor_arena']['reason'], 'short_read')
                self.assertFalse(replay['build_verified_by_replay'])
                forged = copy.deepcopy(raw)
                forged['channels']['roots.selector']['result']['selection'] = 'stack_selected'
                with self.assertRaisesRegex(ValueError, 'result_mismatch'):
                    cli.replay_attempt(forged)
                extra = copy.deepcopy(raw)
                extra['reads'].append(None)
                # Only slices are replayed; reject unowned physical rows, too.
                with self.assertRaises(ValueError):
                    cli.replay_attempt(extra)
                missing = copy.deepcopy(raw)
                del missing['channels']['roots.unit_pages']
                # Missing channels stay missing, never reconstructed from other slices.
                result = cli.replay_attempt(missing)
                self.assertEqual(result['channels']['roots.unit_pages']['status'], 'not_recorded')


class PublicMeasurementTests(unittest.TestCase):
    def test_cli_selects_runtime_experiment_in_offline_preflight_and_stop(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(['--preflight', '--experiment', 'runtime-roots'],
                            backend_factory=lambda: self.fail('offline opened backend'))
        self.assertEqual(code, 0, 'new experiment is not exposed by the product command')
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload['experiment'], 'runtime-roots')
        self.assertEqual(set(payload['runtime_channel_pins']),
                         {'selector', 'descriptor_arena', 'simulation_root', 'unit_pages'})
        self.assertFalse(payload['backend_opened'])
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'STOP').touch()
            player = root / 'player.txt'
            player.write_text('SYNTHETIC')
            with contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(['--live', '--experiment', 'runtime-roots', '--operator-private-game',
                                 '--out', str(root / 'new'), '--stop', str(root / 'STOP'),
                                 '--player-file', str(player)],
                                backend_factory=lambda: self.fail('STOP opened backend'))
            self.assertEqual(code, 0)
            self.assertFalse((root / 'new').exists())

    def test_live_command_routes_selected_experiment_to_injected_transport_only(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        m = Sparse()
        m.close = lambda: None
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            player = root / 'player.txt'
            player.write_text('SYNTHETIC')
            out = root / 'new'
            with contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(['--live', '--experiment', 'runtime-roots', '--operator-private-game',
                                 '--out', str(out), '--stop', str(root / 'STOP'),
                                 '--player-file', str(player), '--max-attempts', '1'], backend_factory=lambda: m)
            self.assertEqual(code, 2)  # synthetic transport fails genuine build pin
            raw = json.loads((out / 'PRIVATE/readsets.jsonl').read_text())
            self.assertEqual(raw['experiment'], 'runtime-roots')
            self.assertIn('roots.unit_pages', raw['channels'])
            self.assertNotIn('compiler', raw['channels'])

    def test_runtime_public_report_names_missing_links_without_private_values(self):
        from hotstate import braxis_diagnostic as cli
        raw = braxis.collect(Sparse(), experiment='runtime-roots')
        raw['channels']['roots.selector'] = {'status': 'observed', 'requests': 2,
            'result': {'selection': 'fallback_only', 'selected': None}}
        raw['channels']['roots.simulation_root'] = {'status': 'refused', 'requests': 1,
            'reason': 'simulation_root_null'}
        public = cli.public_attempt(raw)
        self.assertIn('roots.selector', public['channels'], 'new channels lost by public projection')
        self.assertEqual(public['channels']['roots.simulation_root']['reason'], 'simulation_root_null')
        self.assertEqual(public['runtime_roots']['selector_selection'], 'fallback_only')
        self.assertIn('executing_context_not_sampled', public['runtime_roots']['missing_links'])
        self.assertIn('scho_global_allocation_and_generation', public['runtime_roots']['missing_links'])
        self.assertFalse(public['runtime_roots']['continuous_lifetime_proven'])
        for forbidden in ('module_base', 'selected', 'references', 'record_hex'):
            self.assertNotIn(forbidden, public)


class IntegratedExperimentTests(unittest.TestCase):
    roots = SelectorTests.roots
    def test_collect_runtime_roots_has_own_schema_and_preserves_whole_guards(self):
        import inspect
        from unittest.mock import patch
        self.assertIn('experiment', inspect.signature(braxis.collect).parameters,
                      'collector cannot select the new experiment')
        m = pool_memory()
        with patch.object(braxis, 'verify_build', return_value={'build': 98348}), \
                patch.object(braxis, 'read_clock', return_value=12.0), \
                patch.object(braxis, 'read_context', return_value={'meta': {'map_id': 'BraxisHoldout'}}), \
                patch.object(braxis, 'recheck_context', return_value={'stable': True}):
            raw = braxis.collect(m, experiment='runtime-roots', player_label='SYNTHETIC')
        self.assertEqual(raw['schema'], 'braxis-runtime-roots-v1')
        self.assertEqual(raw['experiment'], 'runtime-roots')
        self.assertEqual(raw['target_map'], 'holdout_recorded')
        self.assertIn('roots.selector', raw['channels'])
        self.assertNotIn('compiler', raw['channels'])
        self.assertNotIn('type', raw['channels'])
        self.assertIsNone(raw['objective'])
        self.assertLessEqual(raw['physical_requests'], 8192)
        self.assertLessEqual(raw['bytes_requested'], 1048576)
        blocked = braxis.collect(Sparse(), experiment='runtime-roots')
        self.assertTrue(all(c['status'] == 'not_attempted' for c in blocked['channels'].values()))

    def test_root_channels_are_independent_and_never_poll_compiler(self):
        roots = self.roots()
        self.assertTrue(hasattr(roots, 'diagnose'), 'pinned independent experiment missing')
        import tempfile
        import hashlib
        import json
        from pathlib import Path
        from unittest.mock import patch
        m = pool_memory()
        m.put(m.module_base + 0x1000, b'OK')
        m.put(m.module_base + 0x2f71528, struct.pack('<I', 0))
        m.put(m.module_base + 0x2fa7300,
              struct.pack('<6Q', 4096, 15, 0x50000, 0x51000, 0x50010, 0x50100))
        m.put(0x50000, struct.pack('<2Q', 0x51000, 0))
        m.u(m.module_base + 0x3388b18, 0)
        pin = {'rva': 0x1000, 'size': 2, 'sha256': hashlib.sha256(b'OK').hexdigest()}
        pins = {name: [pin] for name in roots.DECODERS}
        pins['selector'] = [{**pin, 'sha256': hashlib.sha256(b'NO').hexdigest()}]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'profile.json'
            path.write_text(json.dumps({'image_size': m.module_size, 'channels': pins}))
            with patch.object(roots, 'PROFILE', path):
                rows = roots.diagnose(braxis.WholeTx(m))
        self.assertEqual(rows['roots.selector']['reason'], 'runtime_code_pin')
        self.assertEqual(rows['roots.descriptor_arena']['status'], 'observed')
        self.assertEqual(rows['roots.simulation_root']['reason'], 'simulation_root_null')
        self.assertEqual(rows['roots.unit_pages']['status'], 'observed')
        self.assertNotIn(m.module_base + 0x3b8c918, [a for a, _ in m.calls])


def pool_memory():
    m = Sparse()
    m.put(m.module_base + 0x34f02c0, struct.pack('<II', 0, 2))
    m.put(m.module_base + 0x32c38b4, struct.pack('<I', 0x1234))
    m.put(m.module_base + 0x32c55d0, struct.pack('<I', 7))
    m.put(m.module_base + 0x34f02c8, struct.pack('<II', 0x40000 ^ 0x1234, (-7) & 0xffffffff))
    m.put(0x40010, struct.pack('<I', 2))  # valid full reference at index zero
    m.put(0x40300, struct.pack('<I', 0xffffffff))  # invalid/recycled slot
    return m
