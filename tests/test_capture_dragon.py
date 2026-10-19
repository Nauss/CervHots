"""Hermetic Dragon diagnostic acquisition/collector tests. No live evidence."""
import copy
import unittest
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from test_dragon import DragonMemory
from hotstate.dragon import DragonObjective
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.native_context import NativeContextProbe
from hotstate.live import LiveBudget
from etudes.rea.scripts.capture_dragon import attempt, replay_attempt, main


class CaptureDragonTests(unittest.TestCase):
    @contextmanager
    def fixture(self, m=None):
        m = DragonMemory() if m is None else m
        m.positions_clock = lambda: 100.0
        roster = [{'id':i, 'team':i//5, 'hero':None} for i in range(10)]
        context = {'players':roster, 'local_player':{'id':0,'team':0,'hero':'Stitches'},
                   'meta':{'context_source':'initdata_native_fields','map_id':'DragonShire','match_id':'a'*64}}
        probe = NativeContextProbe('PRIVATE_FIXTURE')
        with ExitStack() as stack:
            stack.enter_context(patch.object(probe, 'observe_native'))
            stack.enter_context(patch.object(probe, 'finish', return_value=context))
            stack.enter_context(patch.object(probe, 'recheck'))
            stack.enter_context(patch('hotstate.dragon.ActiveMatch.observe', return_value={'match_id':'a'*64}))
            stack.enter_context(patch('hotstate.dragon.AlliedPositions._identity',
                return_value=(0,0,'stitches',roster,'synthetic_stamp')))
            stack.enter_context(patch('hotstate.battlefield.VolskayaBattlefield._unit_type',
                side_effect=lambda n,u:m.types[u]))
            yield m, probe, context

    def test_exact_trace_and_all_clock_events_replay(self):
        with self.fixture() as (m,probe,_):
            options = {'native_profile':m.profile,'dragon_profile':m.p}
            row = attempt(m,probe,**options)
            self.assertEqual(row['status'], 'accepted_diagnostic_NOT_PRODUCT', row.get('rejected'))
            self.assertNotIn('normalized', row)
            self.assertNotIn('acquisition', row['dragon'])
            self.assertNotIn('PRIVATE_FIXTURE', str(row))
            replay_attempt(m.module_base,row,probe,**options)
            bad = copy.deepcopy(row); bad['reads'][0]['size'] += 1
            with self.assertRaises(AssertionError):
                replay_attempt(m.module_base,bad,probe,**options)
            bad = copy.deepcopy(row); bad['core_monotonic'].append(100)
            with self.assertRaises(AssertionError):
                replay_attempt(m.module_base,bad,probe,**options)

    def test_torn_shrine_read_refused_and_strictly_replays(self):
        with self.fixture() as (m,probe,_):
            target = m.g+0x118C5+6*132+29
            original = m.read_memory; seen = [False]
            def changing(a,s):
                data = original(a,s)
                if a == target and not seen[0]:
                    seen[0] = True
                    m.pack(target,'i',0)
                return data
            m.read_memory = changing
            options = {'native_profile':m.profile,'dragon_profile':m.p}
            row = attempt(m,probe,**options)
            self.assertEqual(row['status'], 'rejected')
            self.assertEqual(row['rejected'], 'lecture_dragon_dechiree')
            self.assertNotIn('dragon', row)
            replay_attempt(m.module_base,row,probe,**options)

    def test_map_perspective_match_hero_and_roster_refused(self):
        for change in ('map','local','team','hero','roster','match'):
            with self.subTest(change=change), self.fixture() as (m,probe,context):
                if change == 'map': context['meta']['map_id'] = 'Braxis'
                elif change == 'local': context['local_player']['id'] = 1
                elif change == 'team':
                    for p in context['players']: p['team'] = 1-p['team']
                    context['local_player']['team'] = 1
                elif change == 'hero': context['local_player']['hero'] = 'Ragnaros'
                elif change == 'roster':
                    context['players'][1]['team'],context['players'][5]['team'] = 1,0
                else: context['meta']['match_id'] = 'b'*64
                # The mocked identity's roster shares the fixture list, so
                # freeze the native side independently for this refusal test.
                with patch('hotstate.dragon.AlliedPositions._identity', return_value=(
                    0,0,'stitches',[{'id':i,'team':i//5} for i in range(10)],'stamp')):
                    row = attempt(m,probe,native_profile=m.profile,dragon_profile=m.p)
                self.assertEqual(row['status'], 'rejected')
                self.assertNotIn('dragon', row)

    def test_monotone_and_mission_windows_include_construction_and_rechecks(self):
        with self.fixture() as (m,probe,_):
            times = iter([100,101])
            m.positions_clock = lambda: next(times)
            row = attempt(m,probe,native_profile=m.profile,dragon_profile=m.p)
            self.assertEqual(row['rejected'], 'fenetre_pipeline_globale_depassee')
        with self.fixture() as (m,probe,_):
            reader = DragonObjective(NativeReader(m,profile=m.profile),profile=m.p)
            for values in ([10,9], [10,10.25]):
                with patch('hotstate.native.NativeReader.read_clock',side_effect=values), \
                     patch('hotstate.positions._RecordedMemory.validate_clock_end'):
                    with self.assertRaisesRegex(NativeUnavailable,'fenetre_dragon'):
                        reader.diagnose(probe,clock=lambda:100)

    def test_budget_is_physical_and_latches(self):
        m = DragonMemory(); budget = LiveBudget(m,clock=lambda:0)
        for _ in range(8192): budget.read_memory(m.module_base,1)
        with self.assertRaisesRegex(NativeUnavailable,'budget_pipeline'):
            budget.read_memory(m.module_base,1)
        with self.assertRaises(NativeUnavailable): budget.check()

    def test_non_native_probe_or_rolling_dump_cannot_diagnose(self):
        m = DragonMemory(); reader = m.reader()
        with self.assertRaises(NativeUnavailable): reader.diagnose({})
        m.recorded_non_atomic = True
        with self.assertRaises(NativeUnavailable): reader.diagnose(NativeContextProbe('TEST'))

    def test_preflight_no_process_no_private_name(self):
        with patch('etudes.rea.scripts.capture_dragon.frozen_sources',return_value=('a'*40,{})), \
             patch('etudes.rea.scripts.capture_dragon.ProcessBackend') as process:
            self.assertEqual(main(['--preflight','--expected-commit','a'*40]),0)
            process.assert_not_called()

    def test_invalid_limits_or_png_rejected_before_process(self):
        with patch('etudes.rea.scripts.capture_dragon.ProcessBackend') as process:
            for more in (['--duration','31'],['--duration','nan'],['--interval','0'],['--png']):
                with self.assertRaises(SystemExit):
                    main(['--live','--expected-commit','a'*40,*more])
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
