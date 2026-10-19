"""Late timer sampling, exact consumed elapsed/deadline still refuse change."""
import unittest
from unittest.mock import patch
from hotstate.battlefield import _SelectedCensusMemory,VolskayaBattlefield
from hotstate.native import NativeReader,NativeUnavailable
from test_battlefield_memo import Memory
from test_current_visibility import VisibilityMemory

class BattlefieldTimerTests(unittest.TestCase):
    def test_timer_masks_only_unused_bytes_and_is_rechecked_first(self):
        raw=Memory();m=_SelectedCensusMemory(raw)
        m.read_memory(100,4);m.timer_object(300)
        reads=VolskayaBattlefield._coherence_reads(m.read_set)
        plan=m.coherence_checks(reads)
        self.assertEqual(plan[0][:2],(300,40))
        self.assertEqual({(o,len(d)) for o,d in plan[0][2]},{(0,12),(16,16)})
        raw.data[312]=7;raw.data[333]=9
        for a,s,slices in plan:
            now=raw.read_memory(a,s)
            self.assertTrue(all(now[o:o+len(d)]==d for o,d in slices))
        for offset in (0,8,16,17,18,19,20,24,28):
            with self.subTest(offset=offset):
                raw.data[300+offset]=1
                now=raw.read_memory(300,40)
                self.assertTrue(any(now[o:o+len(d)]!=d for o,d in plan[0][2]))
                raw.data[300+offset]=0

    def test_combined_samples_timers_after_structures_and_camp_members(self):
        raw=VisibilityMemory();n=NativeReader(raw,profile=raw.profile);r=VolskayaBattlefield(n,profile={})
        order=[];identity={'native_match_id':raw.context['meta']['match_id'],'local_id':raw.context['local_player']['id'],'team':raw.context['local_player']['team']}
        def camps(n,**kw):
            self.assertFalse(kw['include_timers']);order.append('state');return []
        def members(*args,**kwargs):order.append('members');return []
        def structures(*args,**kwargs):order.append('structures');return []
        def timers(*args,**kwargs):order.append('timers')
        with patch.object(r,'_verify'),patch.object(r,'_camps',side_effect=camps),patch.object(r,'_camp_timers',side_effect=timers),patch.object(r,'_census',return_value={'unresolved_slots':[]}),patch('hotstate.objectives.VolskayaObjective._perspective',return_value=identity),patch('hotstate.visibility.CurrentVisibility._verify'),patch('hotstate.battlefield_details.camp_details',side_effect=members),patch('hotstate.battlefield_details.structure_details',side_effect=structures):
            r._observe('Volskaya',section='combined',context=raw.context)
        self.assertLess(order.index('structures'),order.index('timers'))
        self.assertLess(order.index('members'),order.index('timers'))

if __name__=='__main__':unittest.main()
