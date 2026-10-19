"""Masked bulk I/O synthetic tests: no live process or permission issuance."""
import unittest
from unittest.mock import patch
from test_native import NativeMemory
from test_current_visibility import VisibilityMemory
from hotstate.native import NativeReader,NativeUnavailable
from hotstate.battlefield import VolskayaBattlefield,_SelectedCensusMemory
from etudes.rea.scripts.capture_positions import TraceMemory

class SelectedCensusTests(unittest.TestCase):
    def fixture(self,alternate=False):
        m=NativeMemory();b=m.module_base
        m.pack(b+0x34F02C4,'I',16);m.pack(b+0x34F02C8,'Q',0x900000)
        m.pack(b+0x32C38B4,'I',0);m.pack(b+0x32C55D0,'I',0)
        for slot in range(16):m.put(0x900000+slot*0x2F0+0x10,bytes(0x38))
        m.pack(0x900010,'I',1);m.pack(0x900039,'B',0x20 if alternate else 0)
        m.pack(0x900020 if alternate else 0x900018,'Q',0xA00000)
        m.pack(0x900044,'B',11)
        trace=TraceMemory(m);memory=_SelectedCensusMemory(trace);n=NativeReader(memory,profile=m.profile)
        r=VolskayaBattlefield(n,profile={})
        with patch.object(r,'_unit_type',return_value='TownCannonTowerL2'):census=r._census(n)
        return m,trace,memory,n,r,census

    def test_bulk_is_traced_but_only_consumed_fields_are_rechecked(self):
        m,trace,memory,n,r,census=self.fixture()
        self.assertEqual(census['known_structure_count'],1)
        self.assertTrue(any(x['address']==0x900010 and x['size']==0x38 for x in trace.reads))
        self.assertFalse(any(a==0x900010 and len(d)==0x38 for a,d in memory.read_set))
        m.pack(0x900014,'I',12345);m.pack(0x900042,'B',7)
        for a,data in r._coherence_reads(memory.read_set):self.assertEqual(m.read_memory(a,len(data)),data)
        for address,value in ((0x900010,2),(0x900039,1),(0x900018,0xB00000),(0x900044,12)):
            m,trace,memory,n,r,census=self.fixture()
            m.pack(address,'I' if address==0x900010 else 'Q' if address==0x900018 else 'B',value)
            self.assertTrue(any(m.read_memory(a,len(data))!=data for a,data in r._coherence_reads(memory.read_set)))

    def test_snapshot_type_link_branch_and_owner_are_selected_exactly(self):
        m,trace,memory,n,r,census=self.fixture(alternate=True)
        selected={(a,len(d)) for a,d in memory.read_set}
        self.assertIn((0x900020,8),selected);self.assertNotIn((0x900018,8),selected)
        self.assertIn((0x900044,1),selected)
        self.assertNotIn((0x900060,8),selected)
        self.assertFalse(any(a in (0x900220,0x90022C) for a,d in memory.read_set))

    def test_truncated_bulk_fails_closed_and_never_records_default_bytes(self):
        class Missing:
            module_base=0x140000000
            def read_memory(self,a,s):return bytes(s-1)
        memory=_SelectedCensusMemory(Missing())
        with self.assertRaises(NativeUnavailable):memory.census_header(0x900000)
        self.assertEqual(memory.read_set,[])

    def test_combined_rechecks_both_sources_contradictions_and_window_before_receipts(self):
        # _observe itself is real; identity, VM and business helpers are
        # synthetic stubs. This tests the guard, NOT native perspective proof.
        for mode in ('camp_delta','structure_delta','contradiction','late'):
            with self.subTest(mode=mode):
                m=VisibilityMemory();n=NativeReader(m,profile=m.profile)
                r=VolskayaBattlefield(n,profile={});context=m.context
                m.pack(0xF10000,'I',1);m.pack(0xF20000,'I',7)
                if mode=='late':
                    clock=iter((0.0,0.126));m.positions_clock=lambda:next(clock)
                identity={'native_match_id':context['meta']['match_id'],
                          'local_id':context['local_player']['id'],'team':context['local_player']['team']}
                def camps(n,*args,**kwargs):n.value(0xF10000);return []
                def structures(n,*args,**kwargs):
                    n.value(0xF20000)
                    if mode=='camp_delta':m.pack(0xF10000,'I',2)
                    elif mode=='structure_delta':m.pack(0xF20000,'I',8)
                    elif mode=='contradiction':
                        m.pack(0xF10000,'I',2);n.value(0xF10000)
                        m.pack(0xF10000,'I',1);n.value(0xF10000)
                    return []
                with patch('hotstate.battlefield.VALIDATED_MAPS',('Volskaya',)), \
                     patch.object(r,'_verify'),patch.object(r,'_camps',return_value=[]), \
                     patch.object(r,'_census',return_value={'unresolved_slots':0}), \
                     patch('hotstate.objectives.VolskayaObjective._perspective',return_value=identity), \
                     patch('hotstate.visibility.CurrentVisibility._verify'), \
                     patch('hotstate.battlefield_details.camp_details',side_effect=camps), \
                     patch('hotstate.battlefield_details.structure_details',side_effect=structures), \
                     patch('hotstate.acquisition.issue',side_effect=AssertionError('no partial receipt')) as issue:
                    with self.assertRaises(NativeUnavailable):r.read(context)
                    issue.assert_not_called()

    def test_1024_live_nonstructures_remain_bounded_without_xy_or_vitals(self):
        m=NativeMemory();b=m.module_base;m.pack(b+0x34F02C4,'I',1024)
        m.pack(b+0x32C38B4,'I',0);m.pack(b+0x32C55D0,'I',0)
        for page in range(64):
            pointer=0x900000+page*0x10000
            m.pack(b+0x34F02C8+page*8,'Q',pointer)
            for slot in range(16):
                unit=pointer+slot*0x2F0;index=page*16+slot
                m.put(unit+0x10,bytes(0x38));m.pack(unit+0x10,'I',(index<<22)|1)
                m.pack(unit+0x18,'Q',0xA00000)
        trace=TraceMemory(m);memory=_SelectedCensusMemory(trace);n=NativeReader(memory,profile=m.profile)
        r=VolskayaBattlefield(n,profile={})
        with patch.object(r,'_unit_type',return_value='Barbarian'):census=r._census(n)
        self.assertEqual(census['known_structure_count'],0)
        for a,data in r._coherence_reads(memory.read_set):self.assertEqual(trace.read_memory(a,len(data)),data)
        self.assertLess(len(trace.reads),8192)
        self.assertTrue(all(r['size']<=0x38 for r in trace.reads if 0x900000<=r['address']<0xD00000))

if __name__=='__main__':unittest.main()
