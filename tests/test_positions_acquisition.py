"""Synthetic refusal tests, not live perspective validation."""
import copy
import json
import time
import unittest
from unittest.mock import patch

from test_positions import PositionMemory
from test_positions_contract import raw_packet
from hotstate.native import NativeUnavailable
from cerveau.state import snapshot


class AcquisitionTests(unittest.TestCase):
    def test_native_identity_ignores_unchanged_python_dict(self):
        for change in ('local', 'team', 'mode', 'bot'):
            m = PositionMemory()
            if change == 'local': m.pack(0x120000 + 0xc, 'B', 1)
            elif change == 'team': m.pack(0x606000 + 0x1c, 'B', 0)
            elif change == 'mode': m.pack(0x120000, 'I', 0x20)
            else: m.pack(0x606000 + 0x1d, 'B', 2)
            with self.subTest(change=change), patch('hotstate.positions.VALIDATED_MAPS', ('Volskaya',)):
                with self.assertRaises(NativeUnavailable):
                    m.reader().read(m.context, hero_ids=m.hero_ids)

    def test_paused_mission_does_not_keep_reused_packet_fresh(self):
        raw = raw_packet()
        with patch('hotstate.positions.VALIDATED_MAPS', ('Volskaya',)):
            self.assertIn('positions', snapshot(raw))
            with patch('hotstate.acquisition.time.monotonic', return_value=time.monotonic() + 2):
                self.assertNotIn('positions', snapshot(raw))

    def test_forged_or_changed_acquisition_is_not_provenance(self):
        for change in ('missing', 'timestamp', 'coordinates', 'signature'):
            raw = raw_packet()
            p = raw['positions']
            if change == 'missing': p.pop('acquisition', None)
            elif change == 'timestamp': p.setdefault('acquisition', {})['monotonic_s'] += 0.25
            elif change == 'coordinates': p['heroes'][0]['x'] += 1
            else: p.setdefault('acquisition', {})['seal'] = 'a' * 64
            with self.subTest(change=change), patch('hotstate.positions.VALIDATED_MAPS', ('Volskaya',)):
                self.assertNotIn('positions', snapshot(raw))

    def test_diagnostic_runs_closed_same_core_but_never_publishes(self):
        m = PositionMemory()
        p = m.reader().diagnose('Volskaya', hero_ids=m.hero_ids)
        self.assertEqual(p['status'], 'diagnostic_unreleased')
        self.assertEqual([h['id'] for h in p['heroes']], list(range(5, 10)))
        self.assertNotIn('acquisition', p)

    def test_native_local_root_mutation_during_read_is_rejected(self):
        m = PositionMemory(); original = m.read_memory
        def changing(address, size):
            data = original(address, size)
            if address == 0x900000 + 5 * 0x2f0 + 0x60:
                m.pack(0x120000 + 0xc, 'B', 1)
            return data
        m.read_memory = changing
        with self.assertRaises(NativeUnavailable):
            m.reader().diagnose('Volskaya', hero_ids=m.hero_ids)

    def test_diagnostic_observer_rejects_without_any_xy_read(self):
        m = PositionMemory(); m.pack(0x120000, 'I', 0x20)
        original = m.read_memory; reads = []
        def reading(address, size):
            reads.append(address); return original(address, size)
        m.read_memory = reading
        with self.assertRaises(NativeUnavailable): m.reader().diagnose('Volskaya', hero_ids=m.hero_ids)
        self.assertNotIn(0x900000 + 5 * 0x2f0 + 0x60, reads)
