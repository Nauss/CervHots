"""Synthetic policy regressions; not live visibility or recipe evidence."""
import copy
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from hotstate.battlefield_details import camp_public,structure_public,structure_details

class BattlefieldPolicyTests(unittest.TestCase):
    def camp(self):
        return {'index':3,'state_code':0,'enabled':True,'anchor_current_visible':True,
                'last_capture_team':'neutral','capture_enabled':False,
                'respawn':{'remaining_s':0,'paused':False},
                'defender_group':{'members':[{'tag':5,'role':'defender','alive':True,'current_visible':True}]}}

    def test_current_anchor_and_defenders_required_no_beacon_permission(self):
        r=self.camp();self.assertEqual(camp_public(r)['state'],'available')
        for visible in (False,None):
            x=copy.deepcopy(r);x['anchor_current_visible']=visible
            p=camp_public(x);self.assertEqual(p['state'],'unknown');self.assertIsNone(p['owner']);self.assertIsNone(p['cycle'])
        r['defender_group']['members'][0]['current_visible']=None
        self.assertEqual(camp_public(r)['state'],'unknown')

    def test_departed_laner_never_makes_camp_available(self):
        r=self.camp();r['defender_group']['members'][0]['role']='departed_laner'
        self.assertEqual(camp_public(r)['state'],'unknown')
        r['state_code']=2;r['last_capture_team']=1;r['respawn']['remaining_s']=179.9
        p=camp_public(r);self.assertEqual(p['state'],'captured');self.assertEqual(p['owner'],1);self.assertEqual(p['respawn_s'],179)

    def test_pre_spawn_unknown_timer_is_not_capture_or_ready(self):
        r=self.camp();r['state_code']=2;r['respawn']['remaining_s']=None;r['defender_group']['members']=[]
        p=camp_public(r);self.assertEqual(p['state'],'unavailable');self.assertIsNone(p['respawn_s']);self.assertIsNone(p['owner'])

    def test_every_state_refuses_hidden_living_defenders_and_hidden_cycle(self):
        for code in range(6):
            for visible in (False,None):
                r=self.camp();r.update(state_code=code,capture_enabled=True,last_capture_team=1)
                r['respawn']['remaining_s']=100
                r['defender_group']['members'][0]['current_visible']=visible
                p=camp_public(r)
                self.assertEqual(p['state'],'unknown');self.assertIsNone(p['owner']);self.assertIsNone(p['cycle'])
        r=self.camp();r.update(state_code=3,capture_enabled=True);r['defender_group']['members']=[]
        self.assertEqual(camp_public(r)['state'],'capture_available')
        r.update(state_code=2,last_capture_team=1);r['respawn']['remaining_s']=100
        r['defender_group']['members']=[{'tag':45,'role':'departed_laner','alive':True,'current_visible':None}]
        self.assertIsNone(camp_public(r)['cycle'])

    def test_structure_missing_or_fog_is_unknown_not_destroyed(self):
        spec={'id':'extra-01','kind':'core'}
        self.assertEqual(structure_public({'spec':spec,'observation':None})['state'],'unknown')
        observation={'kind':'core','state':'destroyed','team':1,'generation':2,'current_visible':None}
        p=structure_public({'spec':spec,'observation':observation})
        self.assertEqual(p['state'],'unknown');self.assertIsNone(p['owner']);self.assertIsNone(p['generation'])
        observation['current_visible']=True
        self.assertEqual(structure_public({'spec':spec,'observation':observation})['state'],'destroyed')

    def test_hidden_or_unknown_structure_never_reads_health_bytes(self):
        spec={'id':'extra-01','kind':'core','unit_type':'KingsCore','x_fixed':0,'y_fixed':0}
        row={'tag':1,'unit_type':'KingsCore','kind':'core','state':'alive','team':1,'generation':1}
        calls=[]
        def value(address,fmt):
            calls.append(address)
            return 10000*4096 if address==0x900000+0x220 else 2500*4096
        n=SimpleNamespace(value=value)
        for visible in (False,None,True):
            calls.clear()
            with patch('hotstate.battlefield_details.CurrentVisibility._verify'),patch('hotstate.battlefield_details.CurrentVisibility._current',return_value=visible),patch('hotstate.battlefield_details.PositionMemo._xy',return_value=(0,0)):
                result=structure_details(n,SimpleNamespace(position_profile=None),{'structures':[row]},{1:0x900000},0,{'structures':[spec]})
            if visible is True:
                self.assertEqual(calls,[0x900000+0x220,0x900000+0x22C])
                self.assertEqual(structure_public(result[0])['health_percent'],75)
            else:
                self.assertEqual(calls,[])
                self.assertIsNone(structure_public(result[0])['health_percent'])

if __name__=='__main__':unittest.main()
