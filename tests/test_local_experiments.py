"""Hermetic primitive/scope tests, not a live qualification."""
import unittest
from types import SimpleNamespace
from hotstate.local_experiments import (
    chosen_indices, cooldown_value, follow_link, require_fresh, supports_scope,
    talents, cooldowns, observe, _BudgetMemory,
)
from hotstate.native import NativeUnavailable
from hotstate import local_experiments


class LocalExperimentTests(unittest.TestCase):
    def test_unknown_profile_or_empty_signatures_refuse_before_read(self):
        n=SimpleNamespace(profile={'build':98348},read=lambda a,s:self.fail('invalid profile read memory'))
        for field,value in (('build',98349),('map','DragonShire'),('hero','diablo'),
                            ('context_source','replay'),('cooldown_link','Abil/Unknown'),('signatures',[])):
            profile=dict(local_experiments.PROFILE);profile[field]=value
            with self.subTest(field=field),self.assertRaises(NativeUnavailable):
                local_experiments.verify_experiment_profile(n,profile)

    def test_strict_scope_is_not_other_hero_build_map_or_source(self):
        self.assertTrue(supports_scope(98348,'Volskaya','stitches','initdata_native_fields'))
        for values in ((98349,'Volskaya','stitches','initdata_native_fields'),
                       (98348,'DragonShire','stitches','initdata_native_fields'),
                       (98348,'Volskaya','diablo','initdata_native_fields'),
                       (98348,'Volskaya','Stitches','initdata_native_fields'),
                       (98348,'Volskaya','stitches','replay'),
                       (98348,'Volskaya','stitches',None)):
            self.assertFalse(supports_scope(*values))

    def test_membership_bits_are_not_all_manual_choices(self):
        self.assertEqual(chosen_indices(b'\x08\x01',9),[3,8])
        self.assertEqual(chosen_indices(b'\0',8),[])
        with self.assertRaises(NativeUnavailable):chosen_indices(b'',9)
        with self.assertRaises(NativeUnavailable):chosen_indices(b'',True)

    def test_zero_count_does_not_dereference_missing_bitset(self):
        def value(a,fmt='I'):
            self.assertEqual(a,0x10190)
            return 0
        self.assertEqual(talents(SimpleNamespace(value=value),0x10000),[])

    def test_remaining_zero_means_only_cooldown_ready(self):
        self.assertEqual(cooldown_value(81920),1.25)
        self.assertEqual(cooldown_value(0),0)
        for invalid in (-1,True,3600*65536+1):
            with self.assertRaises(NativeUnavailable):cooldown_value(invalid)

    def test_tagged_links_stop_and_cycles_refuse(self):
        links={0x10008:0x20002,0x20008:0x30000}
        self.assertEqual(follow_link(0x10002,links.__getitem__),0x30000)
        self.assertEqual(follow_link(1,links.__getitem__),0)
        with self.assertRaises(NativeUnavailable):follow_link(0x10002,lambda _:0x10002)

    def test_missing_cooldown_is_not_zero_or_cast_legal(self):
        links={0x10008:0x20000,0x20008:0x30000,0x30008:0}
        def value(a,fmt='I'):return links[a]
        with self.assertRaisesRegex(NativeUnavailable,'stitches_slam_link_absent'):
            cooldowns(SimpleNamespace(value=value),0x10000)

    def test_freshness_does_not_renew_archives(self):
        require_fresh(10,10.1)
        for now in (11.1,9.9,float('nan')):
            with self.assertRaises(NativeUnavailable):require_fresh(10,now)

    def test_unsupported_probe_is_rejected_without_memory_access(self):
        row=observe(None,object())
        self.assertEqual(row['status'],'rejected')
        self.assertEqual(row['reason'],'prototype_source_unsupported')
        self.assertEqual(row['source'],'native_local_experiment_NOT_PRODUCT')
        self.assertEqual(row.get('execution_kind'),'historical_or_fixture_NOT_LIVE')

    def test_budget_refuses_before_extra_physical_read(self):
        calls=[]
        backend=SimpleNamespace(module_base=0x10000,read_memory=lambda a,s:(calls.append((a,s)) or bytes(s)))
        memory=_BudgetMemory(backend,clock=lambda:0)
        memory.read_count=8191
        self.assertEqual(memory.read_memory(0x10000,1),b'\0')
        with self.assertRaises(NativeUnavailable):memory.read_memory(0x10000,1)
        self.assertEqual(len(calls),1)
        memory.read_count=0;memory.bytes_requested=1048576
        with self.assertRaises(NativeUnavailable):memory.read_memory(0x10000,1)
        self.assertEqual(len(calls),1)

    def test_budget_checks_elapsed_and_rolling_capture(self):
        calls=[];now=[0]
        backend=SimpleNamespace(module_base=0x10000,read_memory=lambda a,s:(calls.append((a,s)) or bytes(s)))
        memory=_BudgetMemory(backend,clock=lambda:now[0]);now[0]=0.126
        with self.assertRaises(NativeUnavailable):memory.read_memory(0x10000,1)
        self.assertEqual(calls,[])


if __name__=='__main__':unittest.main()
