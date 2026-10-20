"""Hermetic cooldown boundary fixtures; not live/source qualification."""
import copy
import json
import unittest
from unittest.mock import patch
from cerveau.cooldowns import _project as project, cooldown_key as key
from hotstate.acquisition import issue


class CooldownContractTests(unittest.TestCase):
    def setUp(self):
        clock=patch('time.monotonic', return_value=100.0)
        self.clock=clock.start();self.addCleanup(clock.stop)
        self.local={'id':0,'team':0,'hero':'sonya'}
        self.scope=(('DragonShire','sonya'),)
        self.raw={'meta':{'source':'live','native_status':'valide','native_build':98348,
            'context_source':'initdata_native_fields','map_id':'DragonShire','match_id':'a'*64,'t_s':20},
            'heroes':[dict(self.local,alive=True)],
            'local_cooldowns':{'status':'validated','map_id':'DragonShire','match_id':'a'*64,
                'local_id':0,'team':0,'local_hero':'sonya','alive':True,'mission_t_s':20,'read_window_s':0.01,
                'private_pointer':123456789,'private_name':'PRIVATE_FIXTURE',
                'abilities':[{'ability':'BarbarianAncientSpear','instance_slot':22,
                    'slot_kind':'native_instance_NOT_HUD_button','cooldown_status':'observed',
                    'remaining_s':2.0,'cooldown_ready':False,'charges_status':'not_applicable_current_max_zero',
                    'cast_legality':'unknown','raw':{'account':'PRIVATE_FIXTURE'}}]}}
        self.seal()

    def seal(self):issue(self.raw['local_cooldowns'],100.0)
    def result(self):return project(self.raw,self.local,0,scopes=self.scope)

    def test_scope_closed_by_default_and_private_fields_removed(self):
        self.assertIsNone(project(self.raw,self.local,0))
        result=self.result();self.assertEqual(result['abilities'][0]['remaining_s'],2)
        self.assertNotIn('PRIVATE_FIXTURE',json.dumps(result));self.assertNotIn('123456789',json.dumps(result))
        self.assertNotIn('acquisition',result)

    def test_replay_stale_mutation_missing_source_and_counterparty_are_refused(self):
        old=copy.deepcopy(self.raw)
        for field,value in (('source','replay'),('source','memory'),('native_build',98349),('native_build',True),('context_source','replay')):
            self.raw=copy.deepcopy(old);self.raw['meta'][field]=value;self.assertIsNone(self.result())
        for actor in (1,5,True):
            self.raw=copy.deepcopy(old);self.raw['local_cooldowns']['local_id']=actor;self.seal();self.assertIsNone(self.result())
        self.raw=copy.deepcopy(old);self.clock.return_value=102;self.assertIsNone(self.result())
        self.clock.return_value=100;self.raw=copy.deepcopy(old)
        self.raw['local_cooldowns']['abilities'][0]['remaining_s']=0;self.assertIsNone(self.result())
        self.assertIsNone(project(None,self.local,0,scopes=self.scope))
        self.raw=copy.deepcopy(old);self.raw['meta']=None;self.assertIsNone(self.result())

    def test_unknown_and_dead_have_no_ready_default(self):
        a=self.raw['local_cooldowns']['abilities'][0]
        a.update(cooldown_status='unknown');del a['remaining_s'];del a['cooldown_ready'];self.seal()
        result=self.result()['abilities'][0]
        self.assertNotIn('remaining_s',result);self.assertNotIn('cooldown_ready',result)
        self.raw['local_cooldowns']['alive']=False;self.raw['heroes'][0]['alive']=False;self.seal();self.assertIsNone(self.result())
        self.raw['local_cooldowns']['abilities']=[];self.seal();self.assertEqual(self.result()['abilities'],[])

    def test_key_tracks_states_not_continuous_seconds(self):
        first=key(self.result());a=self.raw['local_cooldowns']['abilities'][0]
        a['remaining_s']=1;self.seal();self.assertEqual(first,key(self.result()))
        a.update(remaining_s=0,cooldown_ready=True);self.seal();self.assertNotEqual(first,key(self.result()))
        a.update(charges_status='observed',charges_max=3,charges_used=2,charges_available=1,charge_regen_s=1.5)
        self.seal();before=key(self.result());a['charge_regen_s']=1;self.seal();self.assertEqual(before,key(self.result()))
        a.update(charges_used=1,charges_available=2);self.seal();self.assertNotEqual(before,key(self.result()))

    def test_invalid_typed_values_and_orphan_unknown_fields_refuse(self):
        old=copy.deepcopy(self.raw)
        for field,value in (('remaining_s',True),('remaining_s',float('nan')),('remaining_s',-1),
                            ('cooldown_ready',True),('instance_slot',True),('cast_legality','ready'),('slot_kind','HUD')):
            self.raw=copy.deepcopy(old);self.raw['local_cooldowns']['abilities'][0][field]=value
            if field=='remaining_s' and value!=value:
                with self.assertRaises(ValueError):self.seal()
                continue
            self.seal();self.assertIsNone(self.result())
        self.raw=copy.deepcopy(old);self.raw['local_cooldowns']['abilities'][0]['cooldown_status']='unknown'
        self.seal();self.assertIsNone(self.result())


if __name__=='__main__':unittest.main()
