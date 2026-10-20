"""Synthetic orchestration tests. Mocked identity/sample is NOT live evidence."""
import copy
import hashlib
import importlib.metadata
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from contextlib import ExitStack, contextmanager, redirect_stdout, redirect_stderr
from unittest.mock import patch, Mock, mock_open

from test_objectives import ObjectiveMemory
from hotstate.dragon_battlefield import DragonBattlefield
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.native_context import NativeContextProbe
from etudes.rea.scripts.capture_dragon_battlefield import attempt, replay_attempt, main
from etudes.rea.scripts import capture_dragon_battlefield as capture
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
             patch.dict(sys.modules, {'mpyq': SimpleNamespace(MPQArchive=object, __file__=__file__)}), \
             patch('importlib.metadata.version', return_value='fixture-not-installed'), \
             patch('etudes.rea.scripts.capture_dragon_battlefield.ProcessBackend') as process:
            self.assertEqual(main(['--preflight', '--expected-commit', 'a'*40]), 0)
            for flags in (['--png'], ['--duration', '31'], ['--interval', 'nan']):
                with self.assertRaises(SystemExit):
                    main(['--live', '--expected-commit', 'a'*40, *flags])
            process.assert_not_called()


@contextmanager
def mocked_output():
    # Leave dependency fingerprint reads real; intercept only output creation.
    real_open = Path.open
    opened = mock_open()
    def open_path(path, mode='r', *args, **kwargs):
        if mode == 'x':
            return opened(path, mode, *args, **kwargs)
        return real_open(path, mode, *args, **kwargs)
    with patch.object(Path, 'open', open_path):
        yield opened


class DragonBattlefieldDependencyTests(unittest.TestCase):
    collector = capture
    freezer = capture
    clock_owner = capture.time
    clock_name = 'monotonic'
    extra_args = ()

    def test_dependency_failures_stop_preflight_and_live_before_output_or_process(self):
        capture = self.collector
        for mode in ('--preflight', '--live'):
            for failure in ('missing_mpyq', 'uncallable_api', 'missing_metadata', 'unreadable_source'):
                archive = Mock(side_effect=AssertionError('map opened'))
                module = SimpleNamespace(MPQArchive=archive, __file__=__file__)
                if failure == 'missing_mpyq':
                    module = None
                elif failure == 'uncallable_api':
                    module.MPQArchive = None
                elif failure == 'unreadable_source':
                    module.__file__ = str(Path(__file__) / 'absent')
                with self.subTest(mode=mode, failure=failure), \
                     patch.object(self.freezer, 'frozen_sources', return_value=('a'*40, {})), \
                     patch.dict(sys.modules, {'mpyq': module}), \
                     patch('importlib.metadata.version', side_effect=importlib.metadata.PackageNotFoundError('mpyq')
                           if failure == 'missing_metadata' else None, return_value='fixture-not-installed'), \
                     patch.object(capture, 'ProcessBackend', side_effect=AssertionError('process opened')) as backend, \
                     patch.object(Path, 'mkdir') as mkdir, mocked_output() as opened, \
                     patch.dict('os.environ', {'DRAGON_TEST_PLAYER': 'PRIVATE_FIXTURE'}), \
                     redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as error:
                    with self.assertRaises(SystemExit) as stopped:
                        capture.main([mode, '--expected-commit', 'a'*40, '--duration', '1',
                                      '--private-player-env', 'DRAGON_TEST_PLAYER',
                                      '--out', str(capture.ROOT/'out/run402-never-created/capture.jsonl'), *self.extra_args])
                    self.assertEqual(stopped.exception.code, 2)
                    self.assertIn('mpyq', error.getvalue())
                    self.assertEqual(output.getvalue(), '')
                    backend.assert_not_called()
                    mkdir.assert_not_called()
                    opened.assert_not_called()
                    archive.assert_not_called()

    def test_success_fingerprints_dependency_and_freezes_helper_imports(self):
        capture = self.collector
        expected_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        archive = Mock(side_effect=AssertionError('map opened'))
        module = SimpleNamespace(MPQArchive=archive, __file__=__file__)
        with patch.object(self.freezer, 'frozen_sources', return_value=('a'*40, {})) as freeze, \
             patch.dict(sys.modules, {'mpyq': module}), \
             patch('importlib.metadata.version', return_value='fixture-not-installed'), \
             patch.object(capture, 'ProcessBackend') as backend, \
             patch.object(capture, 'NativeContextProbe') as probe, \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(capture.main(['--preflight', '--expected-commit', 'a'*40]), 0)
        report = json.loads(output.getvalue())
        self.assertFalse(report['live_opened'])
        self.assertEqual(report['runtime']['python_executable'], sys.executable)
        self.assertEqual(report['runtime']['python_version'], sys.version)
        self.assertEqual(report['runtime']['mpyq'], {'version': 'fixture-not-installed', 'source_sha256': expected_hash})
        extras = set(freeze.call_args.kwargs['extra_paths'])
        for name in ('capture_talents_pipeline.py', 'capture_talents.py', 'capture_visibility_pipeline.py'):
            self.assertIn(capture.ROOT/'etudes/rea/scripts'/name, extras)
        backend.assert_not_called()
        probe.assert_not_called()
        archive.assert_not_called()

    def test_live_header_includes_checked_runtime_without_map_io(self):
        capture = self.collector
        archive = Mock(side_effect=AssertionError('map opened'))
        module = SimpleNamespace(MPQArchive=archive, __file__=__file__)
        with patch.object(self.freezer, 'frozen_sources', return_value=('a'*40, {})), \
             patch.dict(sys.modules, {'mpyq': module}), \
             patch('importlib.metadata.version', return_value='fixture-not-installed'), \
             patch.object(capture, 'ProcessBackend') as backend, \
             patch.object(capture, 'NativeContextProbe'), \
             patch.dict('os.environ', {'DRAGON_TEST_PLAYER': 'PRIVATE_FIXTURE'}), \
             patch.object(Path, 'mkdir'), mocked_output() as opened, \
             patch.object(self.clock_owner, self.clock_name, side_effect=[0, 2]), \
             redirect_stdout(io.StringIO()):
            backend.return_value.module_base = 123
            self.assertEqual(capture.main(['--live', '--expected-commit', 'a'*40, '--duration', '1',
                '--private-player-env', 'DRAGON_TEST_PLAYER', '--out', str(capture.ROOT/'out/run402-mocked.jsonl'), *self.extra_args]), 0)
        header = json.loads(opened().write.call_args.args[0])
        self.assertEqual(header['runtime']['mpyq']['version'], 'fixture-not-installed')
        self.assertEqual(header['runtime']['mpyq']['source_sha256'], hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        backend.return_value.close.assert_called_once_with()
        archive.assert_not_called()


if __name__ == '__main__':
    unittest.main()
