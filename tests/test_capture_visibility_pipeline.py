"""Hermetic actual-code pipeline instrumentation; NO game/live proof."""
import copy
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from test_current_visibility import VisibilityMemory
from test_context import synthetic_initdata
from hotstate.context import ContextProbe
from hotstate.reader import ProcessBackend
from hotstate.native import NativeUnavailable
from etudes.rea.scripts import capture_visibility_pipeline as capture


class FixtureProcess(ProcessBackend):
    def __init__(self, memory):
        self.memory = memory
        self.module_base = memory.module_base
        self.recorded_non_atomic = False
    def read_memory(self, address, size):
        return self.memory.read_memory(address, size)


class FixtureClock:
    def __init__(self): self.value = 100.0
    def __call__(self):
        self.value += 0.000001
        return self.value


class PipelineCollectorTests(unittest.TestCase):
    def fixture(self):
        m = VisibilityMemory(); m.fog(True)
        address = 0x200000
        payload = b'\x10\x0aOWNER_TEST\0SYNTHETIC_INITDATA' + bytes(4096)
        m.put(address, payload)
        raw = synthetic_initdata(m.seed)
        raw['m_syncLobbyState']['m_gameDescription']['m_cacheHandles'] = m.handles
        probe = ContextProbe('OWNER_TEST', decoder=lambda data: copy.deepcopy(raw),
            map_resolver=lambda handles: {'map_id':'Volskaya','map':'Volskaya Foundry'})
        return m,address,len(payload),probe

    def options(self, m):
        return patch.multiple('hotstate.visibility', PROFILE=m.visibility_profile), \
               patch('hotstate.positions.PROFILE',m.position_profile), patch('hotstate.match.PROFILE',m.match_profile)

    def take(self,m,address,size,probe,**kwargs):
        a,b,c = self.options(m)
        with a,b,c:
            return capture.take_sample(FixtureProcess(m),probe,address,size,
                                       native_profile=m.profile,**kwargs)

    def test_full_real_code_chain_and_exact_reads_clocks_replay(self):
        m,address,size,probe=self.fixture()
        row=self.take(m,address,size,probe,clock=FixtureClock())
        self.assertEqual(row['status'],'accepted')
        self.assertTrue(row['normalized']['visibility']['heroes'][0]['visible'])
        self.assertIn('tactical_key',row)
        self.assertTrue(row['native_match_equals_context'])
        self.assertGreater(len(row['wall_clock_calls']),0)
        self.assertNotIn('OWNER_TEST',json.dumps({k:v for k,v in row.items() if k!='reads'}))
        a,b,c=self.options(m)
        with a,b,c:
            repeated=capture.replay_sample(row,m.module_base,probe,address,size,native_profile=m.profile)
        self.assertEqual(row['normalized'],repeated['normalized'])
        self.assertEqual(row['tactical_key'],repeated['tactical_key'])
        self.assertEqual(row['wall_clock_calls'],repeated['wall_clock_calls'])
        self.assertEqual(repeated['execution_kind'],'historical_exact_replay_NOT_LIVE')

    def test_real_forwarded_clock_and_no_coach_call(self):
        m,address,size,probe=self.fixture()
        with patch('cerveau.brain.Coach.decide',side_effect=AssertionError('coach forbidden')):
            row=self.take(m,address,size,probe)
        self.assertEqual(row['status'],'accepted')
        self.assertTrue(all(0 <= age <= 1 for age in row['receipt_ages_s'].values()))
        self.assertLess(row['bytes_requested'],2**20)
        a,b,c=self.options(m)
        with a,b,c:
            repeated=capture.replay_sample(row,m.module_base,probe,address,size,native_profile=m.profile)
        self.assertEqual(row['normalized'],repeated['normalized'])

    def test_visible_hidden_revisible_updates_key_without_enemy_vitals(self):
        m,address,size,probe=self.fixture();keys=[]
        for visible in (True,False,True):
            m.fog(visible)
            row=self.take(m,address,size,probe,clock=FixtureClock())
            self.assertEqual(row['status'],'accepted')
            self.assertIs(row['normalized']['visibility']['heroes'][0]['visible'],visible)
            keys.append(row['tactical_key'])
            for enemy in row['normalized']['heroes'][:5]:
                self.assertTrue({'health','resource','x','y','cooldowns'}.isdisjoint(enemy))
        self.assertNotEqual(keys[0],keys[1]);self.assertEqual(keys[0],keys[2])

    def test_observer_old_context_and_torn_initdata_fail_closed(self):
        for change in ('observer','old_context','torn_initdata'):
            m,address,size,probe=self.fixture()
            if change=='observer':m.pack(0x120000,'I',0x20)
            elif change=='old_context':m.pack(m.app+0x83f78+0x1d428,'I',m.seed+1)
            else:
                original=m.read_memory;fired=False
                def changing(a,s):
                    nonlocal fired
                    data=original(a,s)
                    if a==address and not fired:
                        fired=True;m.put(a,b'X'+data[1:])
                    return data
                m.read_memory=changing
            row=self.take(m,address,size,probe,clock=FixtureClock())
            with self.subTest(change=change):self.assertNotEqual(row['status'],'accepted')

    def test_whole_pipeline_limit_includes_context_core_rechecks_and_normalization(self):
        m,address,size,probe=self.fixture();clock=FixtureClock();real=capture.normalize
        def delayed(raw):
            clock.value+=0.2  # All local native acquisitions already completed.
            return real(raw)
        with patch.object(capture,'normalize',side_effect=delayed):
            row=self.take(m,address,size,probe,clock=clock)
        self.assertEqual(row['rejected'],'fenetre_pipeline_globale_depassee')
        self.assertGreater(row['whole_snapshot_window_s'],0.125)
        self.assertIn('visibility',row['normalized'])  # Fresh receipt != bounded whole acquisition.

    def test_elapsed_wall_age_not_mission_pause_controls_normalizer(self):
        m,address,size,probe=self.fixture();clock=FixtureClock();real=capture.normalize
        def delayed(raw):
            clock.value+=2
            return real(raw)
        with patch.object(capture,'normalize',side_effect=delayed):
            row=self.take(m,address,size,probe,clock=clock)
        self.assertEqual(row['rejected'],'visibilite_pipeline_absente')
        self.assertNotIn('visibility',row['normalized'])
        a,b,c=self.options(m)
        with a,b,c:
            repeated=capture.replay_sample(row,m.module_base,probe,address,size,native_profile=m.profile)
        self.assertEqual(row['rejected'],repeated['rejected'])

    def test_probe_exposes_only_private_candidate_address_not_public_context(self):
        m,address,size,probe=self.fixture()
        payload=m.read_memory(address,size)
        probe.begin();probe.feed(address,payload)
        self.assertEqual(next(iter(probe.candidate_addresses.values())),[address])
        self.assertNotIn('candidate_addresses',probe.finish())

    def test_help_and_unconsented_invocation_never_open_process(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                capture.main(['--help'])
        self.assertEqual(result.exception.code,0)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):capture.main([])

    def test_discovery_native_hash_selection_and_budgeted_missing_context(self):
        m,address,size,probe=self.fixture();a,b,c=self.options(m)
        with a,b,c:
            selected=capture.discover_context(FixtureProcess(m),probe,
                regions=[(address,m.read_memory(address,size))],native_profile=m.profile)
            self.assertEqual(selected['address'],address)
            self.assertEqual(selected['native_match_id'],m.context['meta']['match_id'])
            self.assertEqual(selected['permission'],'NONE_redecode_and_check_each_sample')
            m.pack(m.app+0x83f78+0x1d428,'I',m.seed+1)
            with self.assertRaisesRegex(NativeUnavailable,'non_trouve'):
                capture.discover_context(FixtureProcess(m),probe,
                    regions=[(address,m.read_memory(address,size))],native_profile=m.profile)

    def test_bounded_discovery_reads_only_requested_budget(self):
        from types import SimpleNamespace
        calls=[]
        def query(handle,address,output,size):
            mbi=output._obj
            mbi.BaseAddress=0x200000;mbi.RegionSize=8192
            mbi.State=0x1000;mbi.Type=0x20000;mbi.Protect=4
            return size
        def read(address,size):calls.append((address,size));return b'X'*size
        backend=SimpleNamespace(k32=SimpleNamespace(VirtualQueryEx=query),handle=1,read_memory=read)
        regions=list(capture.bounded_regions(backend,max_bytes=4096))
        self.assertEqual(calls,[(0x200000,4096)])
        self.assertEqual(sum(len(data) for _,data in regions),4096)
        with self.assertRaises(ValueError):list(capture.bounded_regions(backend,max_seconds=0))

    def test_context_buffer_redecode_each_sample_and_clock_gate_restored(self):
        import time
        import hotstate.visibility as visibility
        m,address,size,probe=self.fixture()
        clock_before,gate_before=time.monotonic,visibility.VALIDATED_MAPS
        self.take(m,address,size,probe,clock=FixtureClock())
        self.assertIs(time.monotonic,clock_before)
        self.assertEqual(visibility.VALIDATED_MAPS,gate_before)
        m.put(address,b'BROKEN_HEADER')
        row=self.take(m,address,size,probe,clock=FixtureClock())
        self.assertNotEqual(row['status'],'accepted')
        self.assertNotIn('normalized',row)

    def test_png_bracket_transition_uses_two_complete_pipelines(self):
        m,address,size,probe=self.fixture();a,b,c=self.options(m)
        def image():m.fog(False);return {'skipped':'SYNTHETIC_NO_REAL_PIXELS'}
        with a,b,c:
            row=capture.capture_frame(FixtureProcess(m),probe,address,size,
                native_profile=m.profile,clock=FixtureClock(),screenshot=image)
        self.assertTrue(row['before']['normalized']['visibility']['heroes'][0]['visible'])
        self.assertFalse(row['after']['normalized']['visibility']['heroes'][0]['visible'])
        self.assertNotEqual(row['before']['tactical_key'],row['after']['tactical_key'])
        self.assertLessEqual(row['before']['monotonic_after'],row['image']['monotonic_before'])
        self.assertLessEqual(row['image']['monotonic_after'],row['after']['monotonic_before'])

    def test_non_atomic_dump_proxy_never_becomes_a_fresh_live_packet(self):
        m,address,size,probe=self.fixture()
        backend=FixtureProcess(m);backend.recorded_non_atomic=True
        a,b,c=self.options(m)
        with a,b,c:row=capture.take_sample(backend,probe,address,size,native_profile=m.profile)
        self.assertEqual(row['rejected'],'capture_pipeline_non_atomique')
        self.assertNotIn('normalized',row)
        with a,b,c:
            repeated=capture.replay_sample(row,m.module_base,probe,address,size,native_profile=m.profile)
        self.assertEqual(repeated['rejected'],row['rejected'])

    def test_unexpected_exception_restores_clock_gate_and_read_method(self):
        import time
        import hotstate.visibility as visibility
        m,address,size,probe=self.fixture()
        clock_before,gate_before,read_before=time.monotonic,visibility.VALIDATED_MAPS,capture.CurrentVisibility.read
        with patch.object(capture,'normalize',side_effect=RuntimeError('SYNTHETIC_ABORT')):
            with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_ABORT'):
                self.take(m,address,size,probe,clock=FixtureClock())
        self.assertIs(time.monotonic,clock_before)
        self.assertEqual(visibility.VALIDATED_MAPS,gate_before)
        self.assertIs(capture.CurrentVisibility.read,read_before)

    def test_discovery_wall_query_caps_and_overlap(self):
        from types import SimpleNamespace
        count=0;reads=[]
        def query(handle,address,output,size):
            nonlocal count
            count+=1;mbi=output._obj
            mbi.BaseAddress=address.value or 0;mbi.RegionSize=4096;mbi.State=0
            return size
        backend=SimpleNamespace(k32=SimpleNamespace(VirtualQueryEx=query),handle=1)
        with patch.object(capture,'REAL_CLOCK',side_effect=[100.,101.]):
            self.assertEqual(list(capture.bounded_regions(backend,max_seconds=0.5)),[])
        self.assertEqual(count,0)
        with patch.object(capture,'REAL_CLOCK',return_value=0):
            self.assertEqual(list(capture.bounded_regions(backend)),[])
        self.assertEqual(count,16384)
        def readable_query(handle,address,output,size):
            mbi=output._obj;mbi.BaseAddress=0x200000;mbi.RegionSize=4*1024**2
            mbi.State=0x1000;mbi.Type=0x20000;mbi.Protect=4
            return size
        def read(address,size):reads.append((address,size));return b'X'*size
        backend.k32.VirtualQueryEx=readable_query;backend.read_memory=read
        list(capture.bounded_regions(backend,max_bytes=1024**2+131072))
        self.assertEqual(len(reads),2)
        self.assertEqual(reads[0][0]+reads[0][1]-reads[1][0],65536)
        self.assertEqual(sum(size for _,size in reads),1024**2+131072)


if __name__=='__main__':unittest.main()
