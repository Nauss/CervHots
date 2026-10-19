"""Exact selected-bit coherence, not neighboring fog cells or stale slots."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from hotstate.battlefield import _SelectedCensusMemory,VolskayaBattlefield
from hotstate.native import NativeUnavailable
from hotstate.visibility import CurrentVisibility
from test_battlefield_memo import Memory
from test_current_visibility import VisibilityMemory
from test_native import NativeMemory
from hotstate.native import NativeReader

class BattlefieldBitTests(unittest.TestCase):
    def test_native_fog_predicate_masks_exact_cell_and_keeps_roots_full(self):
        raw=VisibilityMemory();raw.fog(True)
        m=_SelectedCensusMemory(raw);n=NativeReader(m,profile=raw.profile)
        self.assertTrue(CurrentVisibility._fog(n,21,41,6))
        address=0x130000+0x200d0+8192+41*32
        self.assertEqual(m.bits[address],(1<<21,1<<21))
        self.assertNotIn((address,4),{(a,len(d)) for a,d in m.read_set})
        raw.pack(address,'I',(1<<21)|(1<<20))
        m.verify_bits(NativeReader(raw,profile=raw.profile))
        root=raw.module_base+0x35c7980
        self.assertIn((root,4),{(a,len(d)) for a,d in m.read_set})
        raw.pack(root,'I',0)
        self.assertTrue(any(raw.read_memory(a,len(d))!=d for a,d in VolskayaBattlefield._coherence_reads(m.read_set)))

    def test_invalid_slots_are_omitted_not_alive_or_destroyed_rows(self):
        raw=NativeMemory();b=raw.module_base
        raw.pack(b+0x34F02C4,'I',16);raw.pack(b+0x34F02C8,'Q',0x900000)
        raw.pack(b+0x32C38B4,'I',0);raw.pack(b+0x32C55D0,'I',0)
        for slot in range(16):raw.put(0x900000+slot*0x2f0+0x10,bytes(0x38))
        raw.pack(0x900010,'I',(2<<22)|1)  # Nonzero, wrong slot index.
        m=_SelectedCensusMemory(raw);n=NativeReader(m,profile=raw.profile)
        reader=VolskayaBattlefield(n,profile={});result=reader._census(n)
        self.assertEqual(result['structures'],[])
        for slot in range(16):
            self.assertNotIn(0x900000+slot*0x2f0+0x10,{a for a,d in m.read_set})

    def test_observe_finally_refuses_changed_consumed_bit_but_not_neighbor(self):
        # Real _observe guard, synthetic identity and family fields ONLY.
        for consumed in (False,True):
            raw=VisibilityMemory();raw.pack(0xf10000,'I',1)
            n=NativeReader(raw,profile=raw.profile);reader=VolskayaBattlefield(n,profile={})
            identity={'native_match_id':raw.context['meta']['match_id'],'local_id':raw.context['local_player']['id'],'team':raw.context['local_player']['team']}
            def camps(n,*args,**kwargs):n.memory.bit_test(0xf10000,0);return []
            def structures(*args,**kwargs):raw.pack(0xf10000,'I',2 if consumed else 3);return []
            with patch.object(reader,'_verify'),patch.object(reader,'_camps',return_value=[]),patch.object(reader,'_census',return_value={'unresolved_slots':[]}),patch('hotstate.objectives.VolskayaObjective._perspective',return_value=identity),patch('hotstate.visibility.CurrentVisibility._verify'),patch('hotstate.battlefield_details.camp_details',side_effect=camps),patch('hotstate.battlefield_details.structure_details',side_effect=structures):
                if consumed:
                    with self.assertRaisesRegex(NativeUnavailable,'dechiree'):
                        reader._observe('Volskaya',section='combined',context=raw.context)
                else:
                    self.assertEqual(reader._observe('Volskaya',section='combined',context=raw.context)['status'],'diagnostic_unreleased')

    def test_only_consumed_bits_are_guarded_and_reads_still_physical(self):
        raw=Memory();raw.data[100]=0b1010;m=_SelectedCensusMemory(raw)
        self.assertTrue(m.bit_test(100,1));self.assertFalse(m.bit_test(100,0))
        self.assertEqual(raw.calls,[(100,4)])
        self.assertEqual(m.read_set,[])
        raw.data[100]^=1<<3
        m.verify_bits(SimpleNamespace(read=raw.read_memory))
        self.assertEqual(raw.calls,[(100,4),(100,4)])
        raw.data[100]^=1<<1
        with self.assertRaisesRegex(NativeUnavailable,'dechiree'):m.verify_bits(SimpleNamespace(read=raw.read_memory))

    def test_later_full_word_consumption_is_not_accidentally_masked(self):
        raw=Memory();m=_SelectedCensusMemory(raw)
        m.bit_test(100,1);m.read_memory(100,4)
        self.assertIn((100,bytes(4)),m.read_set)
        raw.data[100]=0x80
        self.assertNotEqual(raw.read_memory(100,4),m.read_set[0][1])

    def test_incomplete_word_refuses_without_default_bit(self):
        raw=Memory();raw.read_memory=lambda a,s:b'\0'
        m=_SelectedCensusMemory(raw)
        with self.assertRaises(NativeUnavailable):m.bit_test(100,1)

    def test_unconsumed_invalid_header_is_not_a_structure_generation_guard(self):
        raw=Memory();m=_SelectedCensusMemory(raw)
        m.census_header(0x900000)
        self.assertEqual(m.read_set,[])
        self.assertEqual(m.coherence_checks([]),[])

if __name__=='__main__':unittest.main()
