"""SYNTHETIC multi-map acquisition; not a per-map live recipe."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_day_composition as composition
from test_capture_visibility_pipeline import FixtureProcess
from cerveau.diagnostics import Journal, coach_coverage
from cerveau.runner import tactical_key
from cerveau.state import snapshot
from hotstate.live import read_current

CATALOG = (
    'AlteracPass', 'BattlefieldOfEternity', 'BlackheartsBay', 'BraxisHoldout',
    'BraxisOutpost', 'ControlPoints', 'Crypts', 'CursedHollow', 'DragonShire',
    'Hanamura', 'HauntedMines', 'HauntedWoods', 'IndustrialDistrict', 'LostCavern',
    'Shrines', 'SilverCity', 'TowersOfDoom', 'Volskaya', 'Warhead Junction',
)


class MultiMapPositionsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = composition.DayCompositionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def take(self, map_id, bounds, *, project=snapshot, observe=None):
        memory = self.fixture.memory
        memory.pack(0x100000 + 0x2f0, 'iiii', *bounds)
        probe = memory.probe()
        probe.map_resolver = lambda handles: {'map_id': map_id, 'map': map_id}
        return read_current(FixtureProcess(memory), {'triggers': {}, 'collection': 'positions'},
                            context=probe, project=project, key=tactical_key, observe=observe)

    def test_dragon_native_bounds_reach_normalizer_and_both_journals(self):
        bounds = [8, 24, 240, 182]
        state = self.take('DragonShire', bounds)
        self.assertIn('positions', state)
        packet = state['positions']
        self.assertEqual(packet['map_id'], 'DragonShire')
        self.assertEqual(packet['bounds'], bounds)
        self.assertEqual(packet['map_validation'], 'native_bounds_only')
        self.assertEqual(state['positions_qualification']['map_validation'], 'native_bounds_only')
        self.assertEqual(len(packet['heroes']), 5)
        self.assertTrue(all(h['team'] == state['ally_team'] for h in packet['heroes']))
        for h in packet['heroes']:
            self.assertAlmostEqual(h['u'], (h['x']-8)/232)
            self.assertAlmostEqual(h['v'], 1-(h['y']-24)/158)
        rows = []
        Journal(rows.append).observation(state)
        stored = rows[0]['positions']
        self.assertEqual(stored['status'], 'normalized')
        self.assertEqual(stored['map_validation'], 'native_bounds_only')
        self.assertEqual(stored['value']['bounds'], bounds)
        self.assertEqual(stored['value'], coach_coverage(state)['positions'])
        from hotstate.positions import VALIDATED_MAPS
        self.assertEqual(VALIDATED_MAPS, ('Volskaya',))

    def test_catalog_matches_preserved_identifier_sources_not_claimed_player_recipes(self):
        import re
        from hotstate.position_maps import SUPPORTED_MAPS, PLAYER_RECIPE_MAPS
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads((root/'etudes/rea/positions-map-sources.json').read_text(encoding='utf-8'))
        self.assertEqual(tuple(evidence['map_ids']), SUPPORTED_MAPS)
        observed = set()
        for source in evidence['sources']:
            self.assertRegex(source['archive'], r'^[0-9a-f]{64}\.s2ma$')
            self.assertTrue(re.fullmatch('[0-9a-f]{64}', source['script_sha256']))
            observed.update(source['map_ids'])
        self.assertEqual(observed, set(SUPPORTED_MAPS))
        self.assertEqual(PLAYER_RECIPE_MAPS, ('Volskaya',))

    def test_expiration_during_normalization_never_publishes_positions(self):
        import cerveau.state as normalizer
        captured = {}
        def project(raw):
            captured.update(copy.deepcopy(raw))
            return snapshot(raw)
        self.take('DragonShire', [8, 24, 240, 182], project=project)
        original = normalizer._native_positions
        def slow(*args, **kwargs):
            result = original(*args, **kwargs)
            self.fixture.clock.value += 2
            return result
        with patch.object(normalizer, '_native_positions', side_effect=slow):
            state = snapshot(captured)
        self.assertNotIn('positions', state)
        self.assertEqual(state['positions_qualification']['status'], 'rejected')
        self.assertIsNone(state['positions_qualification']['age_s'])

    def test_every_catalogued_map_acquires_only_living_allies_with_its_observed_bounds(self):
        from hotstate.position_maps import SUPPORTED_MAPS
        from test_core_collection_mode import READERS
        self.assertEqual(SUPPORTED_MAPS, CATALOG)
        original_read = self.fixture.memory.read_memory
        reads = []
        def read(address, size):
            reads.append((address, size))
            return original_read(address, size)
        self.fixture.memory.read_memory = read
        for index, map_id in enumerate(CATALOG):
            # Deliberately SYNTHETIC rectangles, not claimed terrain measurements.
            bounds = [4, 4, 244, 196] if map_id == 'Volskaya' else [-index, 0, 260+index, 210+index]
            with self.subTest(map_id=map_id), contextlib.ExitStack() as stack:
                for name in READERS:
                    if name != 'hotstate.positions.AlliedPositions.read':
                        stack.enter_context(patch(name, side_effect=AssertionError('unselected IO')))
                reads.clear()
                acquisitions = []
                state = self.take(map_id, bounds, observe=acquisitions.append)
                self.assertEqual(state['meta']['map_id'], map_id)
                self.assertEqual([h['id'] for h in state['positions']['heroes']], list(range(5, 10)))
                self.assertEqual(state['positions']['bounds'], bounds)
                qualification = 'player_recipe' if map_id == 'Volskaya' else 'native_bounds_only'
                self.assertEqual(state['positions']['map_validation'], qualification)
                self.assertEqual(acquisitions[0]['outcome'], 'accepted')
                self.assertLessEqual(acquisitions[0]['elapsed_ms'], 125)
                self.assertLessEqual(acquisitions[0]['reads'], 8192)
                self.assertLessEqual(acquisitions[0]['bytes_requested'], 2**20)
                rows = []
                Journal(rows.append).observation(state)
                self.assertEqual(rows[0]['positions']['status'], 'normalized')
                self.assertEqual(rows[0]['positions']['map_validation'], qualification)
                self.assertEqual(rows[0]['positions']['value'], coach_coverage(state)['positions'])
                self.assertTrue(coach_coverage(state)['map_supported'])
                for slot in range(5):
                    xy = 0x900000 + slot * 0x2f0 + 0x60
                    self.assertFalse(any(a <= xy < a+s for a,s in reads), 'enemy xy was read')

    def test_runtime_bounds_are_reacquired_and_participate_in_freshness(self):
        first = self.take('BraxisHoldout', [0, 0, 256, 224])
        second = self.take('BraxisHoldout', [0, 0, 260, 228])
        self.assertNotEqual(first['positions']['bounds'], second['positions']['bounds'])
        self.assertNotEqual(tactical_key(first), tactical_key(second))

    def test_inverted_outside_and_measured_map_mismatch_bounds_refuse(self):
        for map_id, bounds in (
                ('DragonShire', [8, 24, 8, 182]), ('DragonShire', [8, 182, 240, 24]),
                ('DragonShire', [-257, 0, 256, 256]), ('DragonShire', [0, 0, 513, 256]),
                ('Volskaya', [0, 0, 256, 256])):
            with self.subTest(map_id=map_id, bounds=bounds):
                state = self.take(map_id, bounds)
                self.assertNotIn('positions', state)
                self.assertEqual(state['positions_qualification']['status'], 'refused')
                self.assertEqual(state['positions_qualification']['reason']['code'], 'bornes_positions_incoherentes')

    def test_unknown_map_refuses_before_any_position_read(self):
        with patch('hotstate.positions.AlliedPositions._xy', side_effect=AssertionError('unknown map xy')):
            state = self.take('PRIVATE_UNKNOWN_MAP', [0, 0, 256, 256])
        self.assertNotIn('positions', state)
        self.assertEqual(state['positions_qualification']['reason']['code'], 'carte_positions_non_prise_en_charge')
        rows = []
        Journal(rows.append).observation(state)
        self.assertNotIn('PRIVATE_UNKNOWN_MAP', json.dumps(rows))

    def test_torn_bounds_and_runtime_overrun_never_publish(self):
        from hotstate.native import NativeUnavailable
        original = self.fixture.memory.read_memory
        def torn(address, size):
            data = original(address, size)
            if address == 0x100000 + 0x2f0:
                self.fixture.memory.pack(address, 'iiii', 0, 0, 260, 228)
            return data
        self.fixture.memory.read_memory = torn
        state = self.take('BraxisHoldout', [0, 0, 256, 224])
        self.assertNotIn('positions', state)
        self.assertEqual(state['positions_qualification']['reason']['code'], 'lecture_positions_dechiree')
        def expensive(address, size):
            data = original(address, size)
            self.fixture.clock.value += .01
            return data
        self.fixture.memory.read_memory = expensive
        with self.assertRaises(NativeUnavailable):
            self.take('BraxisHoldout', [0, 0, 256, 224])

    def test_forged_recipe_bounds_map_and_recorded_receipts_are_rejected(self):
        from hotstate.acquisition import issue
        original = {}
        def project(raw):
            original.update(copy.deepcopy(raw))
            return snapshot(raw)
        state = self.take('BraxisHoldout', [0, 0, 256, 224], project=project)
        for change in ('recipe', 'bounds', 'map', 'missing_receipt', 'expired'):
            raw = copy.deepcopy(original)
            packet = raw['positions']
            if change == 'recipe': packet['map_validation'] = 'player_recipe'
            elif change == 'bounds': packet['bounds'][0] = True
            elif change == 'map': raw['meta']['map_id'] = 'DragonShire'
            elif change == 'missing_receipt': packet.pop('acquisition')
            else: packet['acquisition']['monotonic_s'] -= 2
            if change != 'missing_receipt':
                issue(packet, packet['acquisition']['monotonic_s'])
            with self.subTest(change=change):
                self.assertNotIn('positions', snapshot(raw))
        forged = copy.deepcopy(state)
        forged['positions']['map_validation'] = 'player_recipe'
        forged['positions_qualification']['map_validation'] = 'player_recipe'
        self.assertIsNone(coach_coverage(forged)['positions'])

    def test_non_volskaya_observation_retains_map_binding_for_offline_reports(self):
        from cerveau.passive_session import NativeSource, run_session
        from cerveau import native_history, session_diagnosis
        memory = self.fixture.memory
        memory.pack(0x100000 + 0x2f0, 'iiii', 0, 0, 256, 224)
        probe = memory.probe()
        probe.map_resolver = lambda handles: {'map_id': 'BraxisHoldout', 'map': 'BraxisHoldout'}
        class Backend(FixtureProcess):
            def close(self):
                self.closed = True
        backend = Backend(memory)
        with patch('hotstate.reader.ProcessBackend', return_value=backend), patch(
                'hotstate.native_context.NativeContextProbe', return_value=probe):
            source = NativeSource('SYNTHETIC_PRIVATE_IDENTITY', collection='positions')
        self.addCleanup(source.close)
        rows = []
        with patch('hotstate.reader.ProcessBackend.__init__', side_effect=AssertionError('no game')), patch(
                'socket.socket', side_effect=AssertionError('no network')):
            result = run_session(lambda: source,
                lambda: any(row['event'] == 'observation' for row in rows), rows.append,
                duration=1, interval=1, clock=self.fixture.clock)
        self.assertEqual(result['accepted'], 1)
        self.assertFalse(result['reader_active'])
        self.assertIsNone(source.backend)
        observation = next(row for row in rows if row['event'] == 'observation')
        self.assertEqual(observation['comparison']['map_id'], 'BraxisHoldout')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'SYNTHETIC-events.jsonl'
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
            diagnosis = session_diagnosis.diagnose(path)
            history = native_history.summarize(path)
        self.assertEqual(diagnosis['metadata']['identity_binding'], {'available': 1, 'missing_or_invalid': 0})
        self.assertEqual(history['map'], 'BraxisHoldout')
        self.assertEqual(history['state'], 'recorded_observation')
        self.assertFalse(history['hud_validated'])
        self.assertFalse(history['current_permission'])

    def test_preflight_distinguishes_acquisition_catalog_from_player_recipes(self):
        from cerveau import playtest
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), patch('cerveau.passive_session.NativeSource',
                side_effect=AssertionError('no backend')), patch('socket.create_connection',
                side_effect=AssertionError('no network')):
            code = playtest.main([])
        row = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(row['positions_maps'], list(CATALOG))
        self.assertEqual(row['positions_player_recipe_maps'], ['Volskaya'])
        self.assertFalse(row['memory_opened'])
        self.assertFalse(row['audio_enabled'])


if __name__ == '__main__':
    unittest.main()
