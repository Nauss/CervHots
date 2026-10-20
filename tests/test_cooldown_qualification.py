"""Current-binding qualification, NOT a catalogue/loadout or native proof."""
import copy
import unittest
from hotstate.cooldown_qualification import qualify, binding
from hotstate.native import NativeUnavailable

SCOPE=(98348,'DragonShire','sonya')


def source():
    a='BarbarianAncientSpear'
    i={'ability':a,'current_cost':{'status':'diagnostic_current_cost',
        'source_scope':'current_local_player_overlay_NOT_BASE','native_class':9,'command':0,
        'cooldown_storage':'unit','cooldown_link':'Abil/'+a,'cooldown_applies':True,'charges_max':0}}
    r={'ability':a,'cooldown_status':'diagnostic_observed','remaining_s':0,'cooldown_ready':True,
       'charges_status':'not_applicable_current_max_zero','cast_legality':'unknown'}
    return i,r


class QualificationTests(unittest.TestCase):
    def test_only_whole_bracketed_spear_case_is_qualified(self):
        self.assertIsNotNone(binding(SCOPE,'BarbarianAncientSpear'))
        self.assertIsNone(binding(SCOPE,'BarbarianBattleRage'))
        self.assertIsNone(binding(SCOPE,'BarbarianWhirlwind'))
        i,r=source()
        for value in (0,12.6875,1.0625,0):
            r.update(remaining_s=value,cooldown_ready=value==0)
            self.assertEqual(qualify(SCOPE,i,r)['remaining_s'],value)

    def test_no_base_entry_is_created_if_ability_not_current(self):
        i,r=source();i['ability']=r['ability']='UnprovenInternal'
        self.assertIsNone(qualify(SCOPE,i,r))
        i,r=source()
        for scope in ((98348,'Volskaya','sonya'),(98348,'DragonShire','stitches'),(98349,'DragonShire','sonya')):
            self.assertIsNone(qualify(scope,i,r))

    def test_changed_current_root_link_class_command_never_keeps_zero(self):
        i,r=source();old=copy.deepcopy(i)
        for k,v in (('status','unknown'),('source_scope','base_catalogue'),('native_class',8),
                    ('command',1),('command',False),('cooldown_link','Abil/Other'),('cooldown_storage','player')):
            i=copy.deepcopy(old);i['current_cost'][k]=v;p=qualify(SCOPE,i,r)
            self.assertEqual(p['cooldown_status'],'unknown');self.assertNotIn('remaining_s',p);self.assertNotIn('cooldown_ready',p)
        i=copy.deepcopy(old);i['current_cost']={};self.assertNotIn('remaining_s',qualify(SCOPE,i,r))

    def test_condition_false_never_gives_ready(self):
        i,r=source();i['current_cost']['cooldown_applies']=False
        self.assertNotIn('cooldown_ready',qualify(SCOPE,i,r))

    def test_source_gained_unproven_charge_max_is_unknown_not_static_zero(self):
        i,r=source();i['current_cost']['charges_max']=2
        r.update(charges_status='diagnostic_observed',charges_max=2,charges_used=0,charges_available=2,charge_regen_s=0)
        p=qualify(SCOPE,i,r);self.assertEqual(p['charges_status'],'unknown')
        self.assertNotIn('charges_available',p);self.assertEqual(p['remaining_s'],0)

    def test_unknown_source_is_not_absent_ability_or_ready_default(self):
        i,r=source();i['current_cost']={'status':'unknown','reason':'root_replaced'}
        p=qualify(SCOPE,i,r)
        self.assertEqual(p['ability'],i['ability']);self.assertEqual(p['cooldown_status'],'unknown')
        self.assertNotIn('cooldown_ready',p)

    def test_mismatched_join_or_claimed_castability_refuses(self):
        i,r=source();r['ability']='Another'
        with self.assertRaises(NativeUnavailable):qualify(SCOPE,i,r)
        i,r=source();r['cast_legality']='ready'
        with self.assertRaises(NativeUnavailable):qualify(SCOPE,i,r)


if __name__=='__main__':unittest.main()
