"""SYNTHETIC collection evidence only: no game, network or audio."""
import copy
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


class PositionsJournalTests(unittest.TestCase):
    def setUp(self):
        self.fixture = composition.DayCompositionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def take(self, collection='positions', project=snapshot):
        return read_current(FixtureProcess(self.fixture.memory),
            {'triggers': {}, 'collection': collection}, context=self.fixture.memory.probe(),
            project=project, key=tactical_key)

    def record(self, state):
        rows = []
        Journal(rows.append).observation(state)
        return rows[0]['positions']

    def test_observation_preserves_exact_positions_and_original_age_without_identifiers(self):
        state = self.take()
        state['positions']['heroes'][0].update(name='PRIVATE', pointer='PRIVATE', acquisition='PRIVATE')
        state['positions'].update(match_id='PRIVATE', native_session='PRIVATE', acquisition='PRIVATE')
        self.fixture.clock.value += 10  # Flush must not refresh the original age.
        packet = self.record(state)
        self.assertEqual(packet['status'], 'normalized')
        self.assertEqual(packet['source'], 'native_player')
        self.assertEqual(packet['source_mission_t_s'], state['positions']['t'])
        self.assertEqual(packet['age_s'], state['positions_qualification']['age_s'])
        self.assertEqual(packet['read_window_s'], state['positions_qualification']['read_window_s'])
        self.assertEqual(packet['allies_expected'], 5)
        self.assertEqual(packet['allies_alive'], 5)
        self.assertEqual(packet['positions_acquired'], 5)
        self.assertEqual(packet['value']['heroes'], [
            dict(slot=h['id'], **{k: h[k] for k in ('team', 'x', 'y', 'u', 'v')})
            for h in state['positions']['heroes']])
        self.assertEqual(packet['value'], coach_coverage(state)['positions'])
        encoded = json.dumps(packet, allow_nan=False)
        for forbidden in ('PRIVATE', 'acquisition', 'native_session', 'match_id', 'pointer', 'hero_'):
            self.assertNotIn(forbidden, encoded)

    def test_real_native_source_passive_loop_persists_positions_without_coach(self):
        from cerveau.passive_session import NativeSource, run_session
        class Backend(FixtureProcess):
            def close(self):
                self.closed = True
        backend = Backend(self.fixture.memory)
        with patch('hotstate.reader.ProcessBackend', return_value=backend), patch(
                'hotstate.native_context.NativeContextProbe', return_value=self.fixture.memory.probe()):
            source = NativeSource('SYNTHETIC_PRIVATE_IDENTITY', collection='positions')
        self.addCleanup(source.close)
        with patch('hotstate.reader.ProcessBackend.__init__', side_effect=AssertionError('no game')), patch(
                'cerveau.brain.Coach', side_effect=AssertionError('no coach')), patch(
                'socket.socket', side_effect=AssertionError('no network')):
            rows = []
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'SYNTHETIC-events.jsonl'
                with path.open('x', encoding='utf-8') as stream:
                    def emit(row):
                        rows.append(row)
                        stream.write(json.dumps(row, allow_nan=False)+'\n')
                    result = run_session(lambda: source,
                        lambda: any(r['event'] == 'observation' for r in rows), emit,
                        duration=1, interval=1, clock=self.fixture.clock)
                stored = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(result['accepted'], 1, (result, stored))
        self.assertFalse(result['reader_active'])
        self.assertIsNone(source.backend)
        self.assertIsNone(source.guard.handle)
        observation = next(r for r in stored if r['event'] == 'observation')
        self.assertEqual(observation['comparison']['map_id'], 'Volskaya')
        self.assertEqual(observation['positions']['positions_acquired'], 5)
        self.assertEqual(observation['positions']['source_mission_t_s'], observation['mission_t_s'])
        self.assertNotIn('SYNTHETIC_PRIVATE_IDENTITY', json.dumps(stored))

    def test_both_supported_native_context_sources_preserve_normalized_positions(self):
        captured = {}
        def project(raw):
            captured.update(copy.deepcopy(raw))
            return snapshot(raw)
        self.take(project=project)
        for source in ('initdata_memory', 'initdata_native_fields'):
            with self.subTest(source=source):
                captured['meta']['context_source'] = source
                state = snapshot(captured)
                self.assertIn('positions', state)
                packet = self.record(state)
                self.assertEqual(packet['status'], 'normalized')
                self.assertEqual(packet['source'], 'native_player')
                self.assertEqual(packet['positions_acquired'], 5)
                self.assertEqual(packet['value'], coach_coverage(state)['positions'])

    def test_explicit_nonselection_is_preserved_without_collection_metadata(self):
        state = {'positions_qualification': {'status': 'not_selected', 'reason': None}}
        packet = self.record(state)
        self.assertEqual(packet['status'], 'not_selected')
        self.assertIsNone(packet['value'])
        self.assertEqual(coach_coverage(state)['positions_status'], 'not_selected')

    def test_optional_refusal_removes_values_instead_of_reusing_previous_sample(self):
        from hotstate.native import NativeUnavailable
        self.assertEqual(self.record(self.take())['positions_acquired'], 5)
        with patch('hotstate.positions.AlliedPositions.read',
                   side_effect=NativeUnavailable('recette_positions_absente')):
            state = self.take()
        packet = self.record(state)
        self.assertEqual(packet['status'], 'refused')
        self.assertEqual(packet['reason']['code'], 'recette_positions_absente')
        for field in ('value', 'positions_acquired', 'source_mission_t_s', 'age_s', 'read_window_s'):
            self.assertIsNone(packet[field])
        self.assertEqual(coach_coverage(state)['positions_reason'], packet['reason'])

    def test_core_and_talents_never_project_or_export_positions(self):
        for collection in ('core', 'talents'):
            with self.subTest(collection=collection), patch('cerveau.state._native_positions',
                    side_effect=AssertionError('unselected projection')):
                state = self.take(collection)
            packet = self.record(state)
            self.assertEqual(packet['status'], 'not_selected')
            self.assertIsNone(packet['value'])
            self.assertIsNone(packet['positions_acquired'])

    def test_dead_allies_are_omitted_and_zero_is_only_a_complete_dead_team(self):
        from hotstate.native import NativeReader
        memory = self.fixture.memory
        native = NativeReader(memory, profile=memory.profile)
        allies = [h['id'] for h in self.take()['positions']['heroes']]
        for count, slot in enumerate(allies, 1):
            player = native.player_pointer(slot + 1)
            unit = native.unit_pointer(native.value(player + 0x58), slot + 1)
            memory.pack(unit + 0x39, 'B', 6)
            packet = self.record(self.take())
            self.assertEqual(packet['status'], 'normalized')
            self.assertEqual(packet['allies_alive'], 5-count)
            self.assertEqual(packet['positions_acquired'], 5-count)
            self.assertNotIn(slot, [h['slot'] for h in packet['value']['heroes']])
        self.assertEqual(packet['value']['heroes'], [])

    def test_invalid_normalized_positions_are_closed_in_both_journals(self):
        original = self.take()
        for change in ('missing_ally', 'enemy', 'dead', 'duplicate', 'bool_slot', 'bool_team',
                       'nan', 'infinite', 'huge', 'outside', 'wrong_u', 'wrong_v', 'wrong_hero',
                       'unknown_map', 'map_mismatch', 'replay', 'wrong_build', 'bad_local',
                       'bad_roster', 'unknown_life', 'age', 'window', 'future', 'past',
                       'reason_conflict', 'bad_sample', 'bad_packet', 'bad_qualification'):
            state = copy.deepcopy(original)
            packet = state['positions']
            h = packet['heroes'][0]
            q = state['positions_qualification']
            if change == 'missing_ally': packet['heroes'].pop()
            elif change == 'enemy': h['id'] = next(r['id'] for r in state['heroes'] if r['team'] != state['ally_team'])
            elif change == 'dead': next(r for r in state['heroes'] if r['id'] == h['id'])['alive'] = False
            elif change == 'duplicate': packet['heroes'][1] = copy.deepcopy(h)
            elif change == 'bool_slot': h['id'] = True
            elif change == 'bool_team': h['team'] = bool(h['team'])
            elif change == 'nan': h['x'] = float('nan')
            elif change == 'infinite': h['y'] = float('inf')
            elif change == 'huge': h['x'] = 10**400
            elif change == 'outside': h['x'] = 300
            elif change == 'wrong_u': h['u'] = 1-h['u']
            elif change == 'wrong_v': h['v'] = 1-h['v']
            elif change == 'wrong_hero': h['hero'] = 'PRIVATE'
            elif change == 'unknown_map': packet['map_id'] = 'PRIVATE'
            elif change == 'map_mismatch': state['meta']['map_id'] = 'DragonShire'
            elif change == 'replay': state['meta']['source'] = 'replay'
            elif change == 'wrong_build': state['meta']['native_build'] = 1
            elif change == 'bad_local': state['local_player']['team'] = 1-state['ally_team']
            elif change == 'bad_roster': state['heroes'][1] = copy.deepcopy(state['heroes'][0])
            elif change == 'unknown_life': next(r for r in state['heroes'] if r['id'] == h['id'])['alive'] = None
            elif change == 'age': q['age_s'] = 2
            elif change == 'window': q['read_window_s'] = .2
            elif change == 'future': packet['t'] += 1
            elif change == 'past': packet['t'] -= 2
            elif change == 'reason_conflict': q['reason'] = {'code': 'recette_positions_absente'}
            elif change == 'bad_sample': packet['heroes'][0] = None
            elif change == 'bad_packet': state['positions'] = None
            else: state['positions_qualification'] = None
            with self.subTest(change=change):
                observed = self.record(state)
                coverage = coach_coverage(state)
                self.assertIn(observed['status'], ('rejected', 'unknown'))
                self.assertIsNone(observed['value'])
                self.assertIsNone(observed['positions_acquired'])
                self.assertIsNone(observed['age_s'])
                self.assertEqual(coverage['positions_status'], observed['status'])
                self.assertIsNone(coverage['positions'])
                self.assertNotIn('PRIVATE', json.dumps(observed, allow_nan=False))

    def test_incomplete_authenticated_packet_is_not_published_to_coach(self):
        from hotstate.acquisition import issue
        captured = {}
        def project(raw):
            captured.update(copy.deepcopy(raw))
            return snapshot(raw)
        self.take(project=project)
        captured['positions']['heroes'].pop()
        issue(captured['positions'], captured['positions']['acquisition']['monotonic_s'])
        state = snapshot(captured)
        self.assertNotIn('positions', state)
        self.assertEqual(state['positions_qualification']['status'], 'rejected')

    def test_persisted_positions_cannot_be_used_as_a_native_packet(self):
        captured = {}
        def project(raw):
            captured.update(copy.deepcopy(raw))
            return snapshot(raw)
        state = self.take(project=project)
        captured['positions'] = json.loads(json.dumps(self.record(state)['value']))
        self.assertNotIn('positions', snapshot(captured))

    def test_missing_qualification_remains_unknown_not_an_empty_team(self):
        packet = self.record({})
        self.assertEqual(packet['status'], 'unknown')
        for field in ('allies_expected', 'allies_alive', 'positions_acquired', 'value'):
            self.assertIsNone(packet[field])


if __name__ == '__main__':
    unittest.main()
