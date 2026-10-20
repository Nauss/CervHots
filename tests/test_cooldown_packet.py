"""Mapped-memory cooldown packet fixtures; NOT native/live evidence."""
import copy
import hashlib
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from hotstate import cooldown_packet as candidate
from test_positions import PositionMemory
from test_native_match import add_match
from hotstate import cooldown_sources, cooldown_costs
from hotstate import cooldown_qualification
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.acquisition import fresh
from cerveau.cooldowns import _project as project


def memory_fixture(m=None):
    m=add_match(PositionMemory()) if m is None else m
    m.context['meta']['context_source']='initdata_native_fields'
    m.local_unit=0x900000+5*0x2f0;m.local_player=0x600000+6*0x1000
    (state,head,node,cdstring,slots,instance,data,cls,desc,namestr,nametable,datatable,db,dbroot,membership,overlays,overlay)=tuple(0x2000000+i*0x1000 for i in range(17))
    def string(address,value):
        m.pack(address+0x18,'II',len(value)*4,0);m.put(address+0x20,value.encode())
    string(cdstring,'Abil/FixtureSpell');string(namestr,'FixtureSpell')
    for address,value in ((m.local_unit+8,state),(state+8,head),(head+8,node),
            (node+8,0),(node+0x10,cdstring),(m.local_unit+0x140,slots|2),
            (slots+0x68,instance),(instance+0x28,data|6),(data+0x60,cls),
            (data+0x70,overlays),(overlays+6*8,overlay),
            (m.module_base+0x3388b18,dbroot),(dbroot+8,db),(db+0xa0,nametable),
            (db+0x48,datatable),(nametable+2*8,desc),(datatable+2*8,data),
            (desc+0x30,namestr),(cls+0x100,membership)):
        m.pack(address,'Q',value)
    m.pack(node+0x18,'i',0);m.pack(slots+0x40,'Q',1);m.pack(slots+0x62,'B',1)
    m.pack(data+2,'H',2);m.pack(desc+0x40,'H',2);m.pack(cls+0x24,'I',9)
    m.pack(db+0x90,'I',4);m.pack(db+0x38,'I',4);m.pack(membership+1,'B',2)
    cost=overlay+0x18
    m.pack(cost+0x20,'i',0);m.pack(cost+0x50,'I',1);m.pack(cost+0x38,'I',1)
    m.pack(cost+0x48,'Q',cdstring);m.pack(cost+0x54,'III',0,5,65536)
    profiles=[]
    for ordinal,original in enumerate((cooldown_sources.PROFILE,cooldown_costs.PROFILE)):
        p=copy.deepcopy(original)
        for i,s in enumerate(p['signatures']):
            marker=('FIXTURE_ONLY_'+s['name']).encode()
            s.update(rva=0x10000+ordinal*0x20000+i*0x1000,size=len(marker),sha256=hashlib.sha256(marker).hexdigest())
            m.put(m.module_base+s['rva'],marker)
        profiles.append(p)
    profile=profiles[1]
    m.pack(m.module_base+profile['registry_flags_rva']+1,'B',2)
    registry=m.module_base+profile['registry_rva']+9*0x2a48
    m.pack(registry,'I',1);m.pack(registry+8,'B',1)
    m.pack(registry+0x60,'Q',m.module_base+next(s['rva'] for s in profile['signatures'] if s['name']=='CostClass9'))
    m.pack(m.module_base+profile['cooldown_condition_index_rva'],'I',0xffffffff)
    m.pack(m.module_base+profile['condition_player_mask_rva'],'I',0)
    m.cd_node=node;m.data_table=datatable;m.data=data;m.cost=cost;m.name_string=namestr
    return m,profiles


class CooldownPacketTests(unittest.TestCase):
    def setUp(self):
        self.m,profiles=memory_fixture();self.now=100.0;self.calls=[]
        original=self.m.read_memory
        def traced(a,s):self.calls.append((a,s));return original(a,s)
        self.m.read_memory=traced
        self.native=NativeReader(self.m,profile=self.m.profile)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('time.monotonic',side_effect=lambda:self.now))
        self.stack.enter_context(patch('hotstate.positions.PROFILE',self.m.position_profile))
        self.stack.enter_context(patch('hotstate.match.PROFILE',self.m.match_profile))
        self.stack.enter_context(patch.object(candidate,'SIGNATURES',tuple(self.m.profile['signatures'])*3))
        self.stack.enter_context(patch.object(cooldown_sources,'PROFILE',profiles[0]))
        self.stack.enter_context(patch.object(cooldown_costs,'PROFILE',profiles[1]))
        self.stack.enter_context(patch.dict(cooldown_qualification.QUALIFIED_BINDINGS,{
            (98348,'Volskaya','ragnaros'):{'FixtureSpell':(9,'unit','Abil/FixtureSpell',None,None,0)}}))
        self.reader=candidate.LocalCooldowns(self.native)

    def opened(self):return patch.object(candidate,'VALIDATED_SCOPES',(('Volskaya','ragnaros'),))
    def read(self):return self.reader.read(self.m.context,hero_ids=self.m.hero_ids)

    def test_unqualified_scope_refuses_before_physical_reads(self):
        before=len(self.calls)
        with self.assertRaisesRegex(NativeUnavailable,'recette_cooldowns_absente'):self.read()
        self.assertEqual(before,len(self.calls))

    def test_actual_helpers_and_native_identity_yield_only_local_packet(self):
        with self.opened():
            before=len(self.calls);p=self.read()
        self.assertTrue(fresh(p));self.assertEqual(p['local_id'],5);self.assertEqual(p['team'],1)
        self.assertEqual(p['abilities'][0]['remaining_s'],0);self.assertTrue(p['abilities'][0]['cooldown_ready'])
        self.assertEqual(p['read_count'],len(self.calls)-before)
        self.assertEqual(p['bytes_requested'],sum(s for a,s in self.calls[before:]))
        for slot in range(1,11):
            if slot==6:continue
            player=0x600000+slot*0x1000;unit=0x900000+(slot-1)*0x2f0
            for address in (player+0x1e8,player+0x1f8,unit+8,unit+0x140):
                self.assertFalse(any(a==address for a,s in self.calls[before:]),'non-local ability/storage read')
        raw={'meta':dict(self.m.context['meta'],source='live',native_status='valide',native_build=98348,t_s=p['mission_t_s']),
             'heroes':[{'id':5,'team':1,'hero':'ragnaros','alive':True}],'local_cooldowns':p}
        clean=project(raw,{'id':5,'team':1,'hero':'ragnaros'},1,scopes=(('Volskaya','ragnaros'),))
        self.assertTrue(clean['abilities'][0]['cooldown_ready']);self.assertNotIn('acquisition',clean)

    def test_dead_has_no_values_and_respawn_rereads(self):
        with self.opened():
            self.m.pack(self.m.local_unit+0x39,'B',2);p=self.read()
            self.assertFalse(p['alive']);self.assertEqual(p['abilities'],[])
            self.m.pack(self.m.local_unit+0x39,'B',0);self.m.pack(self.m.cd_node+0x18,'i',2*65536)
            p=self.read();self.assertEqual(p['abilities'][0]['remaining_s'],2)
            self.assertFalse(p['abilities'][0]['cooldown_ready'])

    def test_generation_match_and_non_atomic_source_reject(self):
        with self.opened():
            self.m.recorded_non_atomic=True
            with self.assertRaisesRegex(NativeUnavailable,'non_atomic'):self.read()
            self.m.recorded_non_atomic=False
            self.m.context['meta']['match_id']='b'*64
            with self.assertRaisesRegex(NativeUnavailable,'active_match'):self.read()
            self.m.context['meta']['match_id']=candidate.ActiveMatch(profile=self.m.match_profile).observe(self.native)['match_id']
            tag=self.native.value(self.m.local_player+0x58);self.m.pack(self.m.local_player+0x58,'I',tag+1)
            with self.assertRaises(NativeUnavailable):self.read()

    def test_source_replacement_is_unknown_not_zero_or_old_cache(self):
        with self.opened():
            first=self.read();self.assertTrue(first['abilities'][0]['cooldown_ready'])
            self.m.pack(self.m.data_table+16,'Q',self.m.data+0x80000);self.m.pack(self.m.data+0x80000,'B',0)
            second=self.read()['abilities'][0]
            self.assertEqual(second['cooldown_status'],'unknown');self.assertNotIn('remaining_s',second)
            self.assertNotIn('cooldown_ready',second)

    def test_current_internal_name_does_not_get_a_ui_grant_or_base_fallback(self):
        name='UnprovenInternal'
        self.m.pack(self.m.name_string+0x18,'II',len(name)*4,0)
        self.m.put(self.m.name_string+0x20,name.encode('ascii'))
        with self.opened():p=self.read()
        self.assertEqual(p['abilities'],[])
        self.assertEqual(p['actor_scope'],'current_native_main_hero')
        self.assertEqual(p['ui_control_body'],'unknown')

    def test_final_value_mutation_refuses_receipt(self):
        original=self.m.read_memory;calls=0
        def mutate(a,s):
            nonlocal calls
            if a==self.m.cd_node+0x18:
                calls+=1
                if calls==2:self.m.pack(a,'i',65536)
            return original(a,s)
        self.m.read_memory=mutate
        with self.opened(),self.assertRaisesRegex(NativeUnavailable,'cooldown_torn'):self.read()

    def test_time_and_context_changes_do_not_issue_partial_packet(self):
        original=self.m.read_memory
        def late(a,s):
            data=original(a,s)
            if a==self.m.cd_node+0x18:self.now+=0.126
            return data
        self.m.read_memory=late
        with self.opened(),self.assertRaisesRegex(NativeUnavailable,'window_expired'):self.read()
        self.now=100
        def changed(a,s):
            data=original(a,s)
            if a==self.m.cd_node+0x18:self.m.context['players'][0]['team']=1
            return data
        self.m.read_memory=changed
        with self.opened(),self.assertRaisesRegex(NativeUnavailable,'context_changed'):self.read()

    def test_outer_whole_budget_refusal_stays_latched(self):
        from hotstate.live import LiveBudget
        outer=LiveBudget(self.m,clock=lambda:self.now);native=NativeReader(outer,profile=self.m.profile)
        outer.reads=8191  # Synthetic near-limit guard test, not measured pipeline cost.
        reader=candidate.LocalCooldowns(native)
        with self.opened(),self.assertRaisesRegex(NativeUnavailable,'budget_pipeline_depasse'):
            reader.read(self.m.context,hero_ids=self.m.hero_ids)
        self.assertEqual(outer.reads,8192)
        with self.assertRaisesRegex(NativeUnavailable,'budget_pipeline_depasse'):outer.check()


if __name__=='__main__':unittest.main()
