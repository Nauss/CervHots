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


if __name__ == '__main__': unittest.main()
