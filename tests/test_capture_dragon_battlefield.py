"""Synthetic orchestration tests. Mocked identity/sample is NOT live evidence."""
import copy
import unittest
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from test_objectives import ObjectiveMemory
from hotstate.dragon_battlefield import DragonBattlefield
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.native_context import NativeContextProbe
from etudes.rea.scripts.capture_dragon_battlefield import attempt, replay_attempt, main
from hotstate.battlefield_details import group_members, camp_public


class CaptureDragonBattlefieldTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        m = ObjectiveMemory()
        m.positions_clock = lambda: 100.0
        roster = [{'id': i, 'team': i//5, 'hero': None} for i in range(10)]
        context = {'players': roster, 'local_player': {'id': 0, 'team': 0, 'hero': 'Stitches'},
                   'meta': {'context_source': 'initdata_native_fields', 'map_id': 'DragonShire', 'match_id': 'a'*64}}
        probe = NativeContextProbe('PRIVATE_FIXTURE')
        target = m.g+0x100
        m.pack(target, 'I', 17)
        def sample(reader, n, local):
            return {'fixture_source': n.value(target), 'catalogue_complete': False}
        with ExitStack() as stack:
            stack.enter_context(patch.object(probe, 'observe_native'))
            stack.enter_context(patch.object(probe, 'finish', return_value=context))
            stack.enter_context(patch.object(probe, 'recheck'))
            stack.enter_context(patch('hotstate.dragon_battlefield.ActiveMatch.observe', return_value={'match_id': 'a'*64}))
            stack.enter_context(patch('hotstate.dragon_battlefield.AlliedPositions._identity',
                return_value=(0, 0, 'stitches', copy.deepcopy(roster), 'synthetic_stamp')))
            stack.enter_context(patch('hotstate.dragon_battlefield.DragonObjective._verify'))
            stack.enter_context(patch.object(DragonBattlefield, '_sample', sample))
            yield m, probe, context, target

    def test_nominal_orchestration_exact_reads_clocks_and_no_receipt(self):
        with self.fixture() as (m, probe, _, _):
            row = attempt(m, probe, native_profile=m.profile)
            self.assertEqual(row['status'], 'accepted_diagnostic_NOT_PRODUCT', row.get('rejected'))
            self.assertNotIn('acquisition', row['battlefield'])
            self.assertNotIn('normalized', row)
            self.assertNotIn('PRIVATE_FIXTURE', str(row))
            replay_attempt(m.module_base, row, probe, native_profile=m.profile)
            corrupt = copy.deepcopy(row)
            corrupt['core_monotonic'].append(100)
            with self.assertRaises(AssertionError):
                replay_attempt(m.module_base, corrupt, probe, native_profile=m.profile)

    def test_consumed_source_mutation_refused_and_replayed(self):
        with self.fixture() as (m, probe, _, target):
            original = m.read_memory
            changed = [False]
            def read(a, size):
                data = original(a, size)
                if a == target and not changed[0]:
                    changed[0] = True
                    m.pack(target, 'I', 18)
                return data
            m.read_memory = read
            row = attempt(m, probe, native_profile=m.profile)
            self.assertEqual(row['rejected'], 'lecture_champ_bataille_dragon_dechiree')
            self.assertNotIn('battlefield', row)
            replay_attempt(m.module_base, row, probe, native_profile=m.profile)

    def test_final_clock_root_mutation_not_silently_accepted(self):
        with self.fixture() as (m, probe, _, _):
            left, right = m.module_base+0x32C2130, m.module_base+0x34F01D4
            a = int.from_bytes(m.read_memory(left, 4), 'little')
            b = int.from_bytes(m.read_memory(right, 4), 'little')
            def mutate(backend):
                # Preserve the decoded pointer, change both encoded roots.
                m.pack(left, 'I', (a+1)&0xffffffff)
                m.pack(right, 'I', (b-1)&0xffffffff)
            probe.recheck.side_effect = mutate
            row = attempt(m, probe, native_profile=m.profile)
            self.assertEqual(row['rejected'], 'lecture_champ_bataille_dragon_dechiree')

    def test_map_match_hero_roster_and_team_mismatch_refused(self):
        for change in ('map', 'match', 'hero', 'team', 'roster'):
            with self.subTest(change=change), self.fixture() as (m, probe, context, _):
                if change == 'map': context['meta']['map_id'] = 'Volskaya'
                elif change == 'match': context['meta']['match_id'] = 'b'*64
                elif change == 'hero': context['local_player']['hero'] = 'Ragnaros'
                elif change == 'team':
                    context['local_player']['team'] = 1
                    for p in context['players']: p['team'] = 1-p['team']
                else:
                    context['players'][1]['team'], context['players'][5]['team'] = 1, 0
                row = attempt(m, probe, native_profile=m.profile)
                self.assertEqual(row['status'], 'rejected')
                self.assertNotIn('battlefield', row)

    def test_whole_time_and_physical_read_limits_refuse(self):
        with self.fixture() as (m, probe, _, _):
            times = iter([100, 101])
            m.positions_clock = lambda: next(times)
            row = attempt(m, probe, native_profile=m.profile)
            self.assertEqual(row['rejected'], 'fenetre_pipeline_globale_depassee')
        with self.fixture() as (m, probe, _, target):
            def overbudget(reader, n, local):
                for _ in range(8193):
                    n.memory.memory.read_memory(target, 4)
            with patch.object(DragonBattlefield, '_sample', overbudget):
                row = attempt(m, probe, native_profile=m.profile)
            self.assertIn('budget_pipeline', row['rejected'])

    def test_giant_and_knight_laners_not_defenders_or_cycle(self):
        for index, name in ((1, 'MercLanerSiegeGiant'), (2, 'MercLanerMeleeKnight'), (5, 'MercLanerRangedMage')):
            m = ObjectiveMemory()
            n = NativeReader(m, profile=m.profile)
            reader = DragonBattlefield(n)
            ref = 3<<16|7
            slots, ptr, array, unit = m.module_base+0x4020980, 0xA00000, 0xB00000, 0x900000
            m.pack(m.g+index*780+0xDF21E, 'I', ref)
            m.pack(m.module_base+0x4020970, 'Q', slots)
            m.pack(slots+7*16, 'HHHBBQ', 3, 0, 1, 22, 0, ptr)
            m.pack(ptr, 'QI', m.module_base+40586608, ref)
            m.pack(ptr+0x18, 'i', 1)
            m.pack(ptr+0x28, 'Q', array)
            m.pack(array, 'I', 5)
            m.pack(unit+0x44, 'B', 11)
            m.pack(unit+0x39, 'B', 0)
            with patch.object(reader, '_resolve', return_value=unit), \
                 patch.object(reader, '_unit_type', return_value=name), \
                 patch('hotstate.battlefield_details.CurrentVisibility._current', side_effect=AssertionError('laner sight read')):
                group = group_members(n, reader, index, 0, None)
            self.assertEqual(group['members'][0]['role'], 'departed_laner')
            row = {'index': index, 'anchor_current_visible': True, 'enabled': True,
                   'state_code': 0, 'defender_group': group, 'capture_enabled': False,
                   'last_capture_team': 'neutral', 'respawn': {'remaining_s': None}}
            result = camp_public(row, kinds=reader.CAMP_KINDS)
            self.assertEqual(result['state'], 'unknown')
            self.assertIsNone(result['cycle'])
            m.pack(slots+7*16, 'H', 4)
            with self.assertRaisesRegex(NativeUnavailable, 'type_generation_groupe'):
                group_members(n, reader, index, 0, None)

    def test_preflight_never_opens_process_and_png_rejected(self):
        with patch('etudes.rea.scripts.capture_dragon_battlefield.frozen_sources', return_value=('a'*40, {})), \
             patch('etudes.rea.scripts.capture_dragon_battlefield.ProcessBackend') as process:
            self.assertEqual(main(['--preflight', '--expected-commit', 'a'*40]), 0)
            for flags in (['--png'], ['--duration', '31'], ['--interval', 'nan']):
                with self.assertRaises(SystemExit):
                    main(['--live', '--expected-commit', 'a'*40, *flags])
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
