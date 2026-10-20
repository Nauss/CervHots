"""Fixture acquisition tests; mocked roots are NOT native/live qualification."""
import copy
import hashlib
import struct
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from hotstate import cooldowns as cd
from hotstate.native import NativeUnavailable
from hotstate.native_context import NativeContextProbe
from etudes.rea.scripts import capture_cooldowns as cli


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.now = 1.0
        self.cells = {0x10058: struct.pack('<I', 42), 0x20039: b'\0'}
        self.calls = []
        self.context = {'meta': {'map_id': 'DragonShire', 'match_id': 'a'*64,
                                'context_source': 'initdata_native_fields'},
                        'local_player': {'id': 0, 'team': 0, 'hero': 'stitches'},
                        'players': [{'id': i, 'team': i//5} for i in range(10)]}
        def read(a, size):
            self.calls.append((a, size))
            return self.cells.get(a, bytes(size))
        self.backend = SimpleNamespace(module_base=0x100000, read_memory=read)
        self.probe = NativeContextProbe('fixture-name', map_resolver=lambda _: self.fail('external resolver'))
        def native(memory):
            def value(a, fmt='I'):
                return struct.unpack('<'+fmt, memory.read_memory(a, struct.calcsize('<'+fmt)))[0]
            def read_clock():
                for i in range(5): memory.read_memory(0x90000+i*8, 4)
                return 10.0
            return SimpleNamespace(base=memory.module_base, profile={'build': 98348},
                read=memory.read_memory, value=value, read_clock=read_clock,
                player_pointer=lambda i: 0x10000 if i == 1 else self.fail('other player CD'),
                unit_pointer=lambda tag, i: 0x20000 if (tag, i) == (42, 1) else self.fail('wrong tag'))
        def context(probe, budget, **options):
            data = budget.read_memory(0x50000, 4)
            probe.read_set = [(0x50000, data)]
            probe.result = copy.deepcopy(self.context)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(cd, 'NativeReader', native))
        self.stack.enter_context(patch.object(cd, 'SIGNATURES', tuple(
            {'rva': i*8, 'size': 8, 'sha256': hashlib.sha256(bytes(8)).hexdigest()} for i in range(3))))
        self.stack.enter_context(patch.object(cd.ActiveMatch, 'observe', return_value={'match_id': 'a'*64}))
        self.stack.enter_context(patch.object(NativeContextProbe, 'observe_native', context))
        self.stack.enter_context(patch.object(cd.AlliedPositions, '_identity',
            return_value=(0, 0, 'stitches', self.context['players'], ())))
        self.links = self.stack.enter_context(patch.object(cd, 'read_unit_links', return_value={'Abil/StitchesSlam': 0.0}))

    def acquire(self):
        return cd.observe(self.backend, self.probe, clock=lambda: self.now)

    def test_success_whole_reads_rechecked(self):
        row = self.acquire()
        self.assertEqual(row['status'], 'diagnostic_observed')
        self.assertEqual(row['links'], {'Abil/StitchesSlam': 0.0})
        self.assertEqual(row['read_count'], len(self.calls))
        self.assertEqual(row['bytes_requested'], sum(s for a, s in self.calls))
        self.assertEqual(self.calls.count((0x50000, 4)), 2)
        self.assertEqual(self.calls.count((0x10058, 4)), 2)

    def test_dead_never_reads_corpse_links(self):
        self.cells[0x20039] = b'\x02'
        row = self.acquire()
        self.assertEqual(row['reason'], 'local_dead_no_ability_observation')
        self.assertNotIn('links', row)
        self.links.assert_not_called()

    def test_mismatched_match_hero_or_roster_rejected_before_links(self):
        for mutate in (lambda: self.context['meta'].update(match_id='b'*64),
                       lambda: self.context['local_player'].update(hero='diablo')):
            old = copy.deepcopy(self.context)
            mutate()
            self.assertEqual(self.acquire()['reason'], 'cooldown_identity_or_scope')
            self.context = old
        self.links.assert_not_called()

    def test_generation_read_change_is_rejected_and_no_partial_links(self):
        original = self.backend.read_memory
        def torn(a, size):
            count = self.calls.count((a, size))
            data = original(a, size)
            return struct.pack('<I', 43) if a == 0x10058 and count else data
        self.backend.read_memory = torn
        row = self.acquire()
        self.assertEqual(row['reason'], 'cooldown_torn')
        self.assertNotIn('links', row)

    def test_whole_context_timeout_is_not_reset(self):
        original = self.backend.read_memory
        def late(a, size):
            data = original(a, size)
            if a == 0x50000: self.now += 0.126
            return data
        self.backend.read_memory = late
        row = self.acquire()
        self.assertEqual(row['reason'], 'prototype_window_expired')
        self.assertNotIn('links', row)
        self.links.assert_not_called()

    def test_replay_has_no_external_map_cache_or_backend_dependency(self):
        row = cli.take_sample(self.backend, self.probe)
        actual = cli.replay_sample(row, self.backend.module_base, self.probe)
        self.assertEqual(actual, row['observation'])
        bad = copy.deepcopy(row)
        bad['reads'][0]['address'] += 8
        with self.assertRaises(AssertionError): cli.replay_sample(bad, self.backend.module_base, self.probe)
        bad = copy.deepcopy(row)
        bad['clock_values'].append(10)
        with self.assertRaises(AssertionError): cli.replay_sample(bad, self.backend.module_base, self.probe)

    def test_replay_preserves_non_atomic_refusal(self):
        self.backend.recorded_non_atomic = True
        row = cli.take_sample(self.backend, self.probe)
        self.assertEqual(row['observation']['reason'], 'cooldown_non_atomic_dump')
        self.assertEqual(cli.replay_sample(row, self.backend.module_base, self.probe), row['observation'])
        self.assertEqual(row['reads'], [])

    def test_preflight_never_constructs_backend(self):
        with patch.object(cli, 'frozen_sources', return_value=('fixture', {})), \
                patch.object(cli, 'ProcessBackend', side_effect=AssertionError('game opened')):
            self.assertEqual(cli.main(['--preflight', '--expected-commit', 'fixture']), 0)

    def test_extended_sources_are_local_independent_and_budgeted(self):
        from hotstate import cooldown_sources
        def instances(n, unit):
            self.assertEqual(unit, 0x20000)
            n.read(0x61000, 8)
            return [{'ability': 'CurrentAbility', 'cost_binding': 'unproven'}]
        def store(n, owner, *, storage, charges=False):
            self.assertEqual(owner, 0x10000 if storage == 'player' else 0x20000)
            n.read(0x62000, 8)
            if charges:
                raise NativeUnavailable('fixture_charge_unknown')
            return {'Abil/CurrentAbility': {'remaining_s': 1, 'ability_binding': 'unproven'}}
        with patch.object(cooldown_sources, 'verify'), \
                patch.object(cooldown_sources, 'active_instances', instances), \
                patch.object(cooldown_sources, 'stored_links', store):
            row = cli.take_sample(self.backend, self.probe, extended_sources=True)
            actual = cli.replay_sample(row, self.backend.module_base, self.probe)
        sources = actual['native_sources']
        self.assertEqual(sources['active_instances']['status'], 'diagnostic_observed')
        self.assertEqual(sources['unit_charges']['status'], 'unknown')
        self.assertEqual(sources['player_charges']['status'], 'unknown')
        self.assertEqual(actual['ability_binding'], 'unproven')
        self.assertEqual(row['observation']['read_count'], len(self.calls))

    def test_extended_budget_failure_cannot_be_hidden_as_optional_unknown(self):
        from hotstate import cooldown_sources
        with patch.object(cooldown_sources, 'verify'), \
                patch.object(cooldown_sources, 'active_instances', side_effect=NativeUnavailable('prototype_budget_exceeded')):
            row = cd.observe(self.backend, self.probe, clock=lambda: self.now, extended_sources=True)
        self.assertEqual(row['status'], 'rejected')
        self.assertEqual(row['reason'], 'prototype_budget_exceeded')
        self.assertNotIn('links', row)

    def test_current_cost_mode_is_explicit_and_includes_join_in_window(self):
        from hotstate import cooldown_sources, cooldown_costs
        self.assertEqual(cd.observe(self.backend, self.probe, clock=lambda: self.now,
            current_costs=True)['reason'], 'cooldown_diagnostic_mode_invalid')
        def instances(n, unit, *, native_owner):
            self.assertEqual(native_owner, 1)
            n.read(0x61000, 8)
            return [{'ability': 'CurrentAbility', 'current_cost': {'status': 'diagnostic_current_cost',
                'cooldown_applies': True, 'cooldown_storage': 'unit', 'cooldown_link': 'Abil/StitchesSlam',
                'charges_max': 0}}]
        with patch.object(cooldown_sources, 'verify'), patch.object(cooldown_costs, 'verify'), \
                patch.object(cooldown_sources, 'active_instances', instances), \
                patch.object(cooldown_sources, 'stored_links', return_value={}):
            row = cli.take_sample(self.backend, self.probe, extended_sources=True, current_costs=True)
            actual = cli.replay_sample(row, self.backend.module_base, self.probe)
            self.assertTrue(actual['ability_diagnostics'][0]['cooldown_ready'])
            def slow(*args):
                self.now += 0.126
                return []
            with patch.object(cooldown_costs, 'diagnostic_abilities', slow):
                late = cd.observe(self.backend, self.probe, clock=lambda: self.now,
                    extended_sources=True, current_costs=True)
            self.assertEqual(late['status'], 'rejected')
            self.assertNotIn('ability_diagnostics', late)

    def test_map_replay_roundtrip_cold_warm_and_original_probe_unchanged(self):
        import json
        handles = (b's2ma'+bytes(36),)
        def context(probe, budget, **options):
            data = budget.read_memory(0x50000, 4)
            probe.read_set = [(0x50000, data)]
            probe.result = copy.deepcopy(self.context)
            if handles not in probe.map_cache:
                probe.map_cache[handles] = probe.map_resolver(handles)
        self.probe.map_resolver = lambda h: {'map_id': 'DragonShire'}
        with patch.object(NativeContextProbe, 'observe_native', context):
            for warm in (False, True):
                row = json.loads(json.dumps(cli.take_sample(self.backend, self.probe)))
                self.assertEqual(bool(row['map_cache_before']), warm)
                saved = copy.deepcopy(self.probe.map_cache)
                self.probe.map_resolver = lambda _: self.fail('external resolution during replay')
                self.assertEqual(cli.replay_sample(row, self.backend.module_base, self.probe), row['observation'])
                self.assertEqual(self.probe.map_cache, saved)


if __name__ == '__main__': unittest.main()
