"""Generic per-family acquisition memo, never caches boundary clocks or final reads."""
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from hotstate.positions import _RecordedMemory
from hotstate.native import NativeReader,NativeUnavailable
from etudes.rea.scripts.capture_positions import TraceMemory
from test_native import NativeMemory
from test_battlefield_memo import Memory
from test_current_visibility import VisibilityMemory
from hotstate.positions import AlliedPositions
from hotstate.visibility import CurrentVisibility
from hotstate.objectives import VolskayaObjective

class AcquisitionMemoTests(unittest.TestCase):
    def test_incomplete_reads_never_cached_and_fresh_scope_restores_on_exception(self):
        for data in (None,b'\0'):
            raw=Memory();calls=[]
            def read(a,s):calls.append((a,s));return data
            raw.read_memory=read;m=_RecordedMemory(raw,cache=True)
            self.assertEqual(m.read_memory(100,4),data);self.assertEqual(m.read_memory(100,4),data)
            self.assertEqual(len(calls),2)
            with self.assertRaises(ValueError):
                with m.fresh_reads():
                    self.assertTrue(m.fresh);raise ValueError('synthetic')
            self.assertFalse(m.fresh)

    def test_final_clock_root_change_refuses_each_family_but_tick_can_advance(self):
        # Real native clock and _observe boundaries; synthetic business stubs.
        for family in ('positions','visibility','objectives'):
            for change_root in (False,True):
                with self.subTest(family=family,change_root=change_root),ExitStack() as stack:
                    raw=VisibilityMemory();n=NativeReader(raw,profile=raw.profile)
                    if family=='positions':
                        reader=AlliedPositions(n,profile=raw.position_profile)
                        stack.enter_context(patch.object(reader,'_identity',return_value=(5,1,'ragnaros',[],'a'*64)))
                    elif family=='visibility':reader=CurrentVisibility(n,position_profile=raw.position_profile,match_profile=raw.match_profile)
                    else:
                        reader=VolskayaObjective(n)
                        stack.enter_context(patch.object(reader,'_perspective',return_value={}))
                    stack.enter_context(patch.object(reader,'_sample',return_value={}))
                    stack.enter_context(patch.object(AlliedPositions,'_verify'))
                    stack.enter_context(patch.object(AlliedPositions,'_bounds'))
                    actual_clock=NativeReader.read_clock;calls=[0]
                    def clock(self):
                        calls[0]+=1
                        if calls[0]==2:
                            if change_root:
                                raw.pack(raw.module_base+0x34f01d0,'I',0x110000)
                                raw.pack(0x110068,'i',int(123.5*4096))
                            else:raw.pack(0x100068,'i',int(123.5*4096)+256)
                        return actual_clock(self)
                    stack.enter_context(patch.object(NativeReader,'read_clock',clock))
                    if change_root:
                        with self.assertRaises(NativeUnavailable):reader._observe('Volskaya',hero_ids=raw.hero_ids)
                    else:self.assertEqual(reader._observe('Volskaya',hero_ids=raw.hero_ids)['mission_t_s'],123.5625)

    def test_memo_is_optin_per_instance_and_uncached_scope_detects_change(self):
        raw=Memory();m=_RecordedMemory(raw,cache=True)
        self.assertEqual(m.read_memory(100,4),bytes(4));raw.data[100]=1
        self.assertEqual(m.read_memory(100,4),bytes(4));self.assertEqual(len(raw.calls),1)
        with m.fresh_reads():self.assertEqual(m.read_memory(100,4),b'\1\0\0\0')
        with self.assertRaises(NativeUnavailable):m.coherence_reads('torn')
        self.assertEqual(_RecordedMemory(raw,cache=True).read_memory(100,4),b'\1\0\0\0')

    def test_boundary_clock_always_performs_all_five_physical_reads(self):
        raw=NativeMemory();trace=TraceMemory(raw);m=_RecordedMemory(trace,cache=True)
        n=NativeReader(m,profile=raw.profile);start=len(trace.reads)
        first=n.read_clock();counter=trace.reads[-1]['address']
        raw.pack(counter,'i',int(first*4096)+256)
        second=n.read_clock()
        self.assertEqual(second-first,0.0625);self.assertEqual(len(trace.reads)-start,10)
        self.assertFalse(m.fresh)

    def test_full_final_checks_still_use_physical_original_backend(self):
        raw=Memory();m=_RecordedMemory(raw,cache=True)
        m.read_memory(100,4);m.read_memory(100,4)
        raw.data[100]=2
        checks=m.coherence_reads('torn')
        self.assertTrue(any(raw.read_memory(a,len(data))!=data for a,data in checks))
        self.assertEqual(len(raw.calls),2)

if __name__=='__main__':unittest.main()
