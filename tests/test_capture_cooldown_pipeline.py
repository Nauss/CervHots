"""Whole real entrypoint with synthetic memory. NO live/Full qualification."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch
from test_cooldown_packet import memory_fixture
from test_native_context import TypedContextMemory
from test_capture_visibility_pipeline import FixtureProcess, FixtureClock
from etudes.rea.scripts import capture_cooldown_pipeline as capture
from hotstate import cooldown_packet, cooldown_sources, cooldown_costs
from hotstate import cooldown_qualification
from hotstate.native import NativeReader


class CooldownPipelineTests(unittest.TestCase):
    def setUp(self):
        self.m,self.profiles=memory_fixture(TypedContextMemory())
        self.probe=self.m.probe();self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        for target,value in (
                ('hotstate.positions.PROFILE',self.m.position_profile),
                ('hotstate.match.PROFILE',self.m.match_profile),
                ('hotstate.visibility.PROFILE',self.m.visibility_profile),
                ('hotstate.cooldown_packet.SIGNATURES',tuple(self.m.profile['signatures'])*3),
                ('hotstate.cooldown_sources.PROFILE',self.profiles[0]),
                ('hotstate.cooldown_costs.PROFILE',self.profiles[1]),
                ('etudes.rea.scripts.capture_cooldown_pipeline.CANDIDATE_SCOPES',(('Volskaya','ragnaros'),))):
            self.stack.enter_context(patch(target,value))
        self.stack.enter_context(patch.dict(cooldown_qualification.QUALIFIED_BINDINGS,{
            (98348,'Volskaya','ragnaros'):{'FixtureSpell':(9,'unit','Abil/FixtureSpell',None,None,0)}}))

    def take(self,clock=None):
        return capture.take_sample(FixtureProcess(self.m),self.probe,clock=clock or FixtureClock(),native_profile=self.m.profile)

    def test_real_entrypoint_projection_key_and_exact_replay(self):
        with patch('cerveau.brain.Coach.decide',side_effect=AssertionError('coach forbidden')):
            row=self.take()
        self.assertEqual(row['status'],'accepted',row.get('rejected'))
        self.assertEqual(row['raw']['meta']['context_source'],'initdata_native_fields')
        self.assertTrue(row['normalized']['local_cooldowns']['abilities'][0]['cooldown_ready'])
        self.assertIn('local_cooldowns',json.loads(row['tactical_key']))
        self.assertLessEqual(row['read_count'],8192);self.assertLessEqual(row['bytes_requested'],2**20)
        self.assertLessEqual(row['whole_snapshot_window_s'],0.125)
        self.assertEqual(row['read_count'],len(row['reads']))
        self.assertNotIn('OWNER_TEST',json.dumps(row['normalized']))
        self.assertEqual(cooldown_packet.VALIDATED_SCOPES,(('DragonShire','sonya'),))
        replay=capture.replay_sample(row,self.m.module_base,self.probe,native_profile=self.m.profile)
        self.assertEqual(row['normalized'],replay['normalized'])
        self.assertEqual(row['tactical_key'],replay['tactical_key'])
        self.assertEqual(row['wall_clock_calls'],replay['wall_clock_calls'])
        self.assertEqual(replay['execution_kind'],'historical_exact_replay_NOT_LIVE')

    def test_key_ignores_seconds_and_invalidates_at_zero(self):
        keys=[]
        for remaining in (2,1,0):
            self.m.pack(self.m.cd_node+0x18,'i',remaining*65536)
            row=self.take();self.assertEqual(row['status'],'accepted',row.get('rejected'));keys.append(row['tactical_key'])
        self.assertEqual(keys[0],keys[1]);self.assertNotEqual(keys[1],keys[2])

    def test_native_class8_player_cd_and_charge_join_reaches_real_key(self):
        # Synthetic binding ONLY; no actual BattleRage production grant.
        self.stack.enter_context(patch.dict(cooldown_qualification.QUALIFIED_BINDINGS,{
            (98348,'Volskaya','ragnaros'):{'FixtureSpell':(8,'player','Abil/FixtureSpell','player','Abil/FixtureSpell',2)}}))
        n=NativeReader(self.m,profile=self.m.profile);p=self.profiles[1]
        cls=n.value(self.m.data+0x60,'Q');membership=n.value(cls+0x100,'Q')
        self.m.pack(cls+0x24,'I',8);self.m.pack(membership+1,'B',1)
        self.m.pack(self.m.module_base+p['registry_flags_rva']+1,'B',1)
        entry=self.m.module_base+p['registry_rva']+8*0x2a48
        self.m.pack(entry,'I',1);self.m.pack(entry+8,'B',1)
        callback=next(s['rva'] for s in p['signatures'] if s['name']=='CostClass8')
        self.m.pack(entry+0x60,'Q',self.m.module_base+callback)
        cd_link=n.value(self.m.cost+0x48,'Q');cd,charge=0x3000000,0x3001000
        self.m.pack(self.m.cost+0x20,'i',2*4096);self.m.pack(self.m.cost+0x30,'Q',cd_link)
        self.m.pack(self.m.cost+0x38,'I',2);self.m.pack(self.m.cost+0x50,'I',2)
        self.m.pack(self.m.local_player+0x1f8,'Q',cd);self.m.pack(self.m.local_player+0x1e8,'Q',charge)
        for node in (cd,charge):self.m.pack(node+8,'Q',0);self.m.pack(node+0x10,'Q',cd_link)
        self.m.pack(charge+0x20,'ii',15*65536,15*65536)
        keys=[]
        for used,remaining in ((0,0),(1,7),(2,6),(1,0),(0,0)):
            self.m.pack(cd+0x18,'i',remaining*65536)
            self.m.pack(charge+0x18,'i',13*65536);self.m.pack(charge+0x1c,'i',used*4096)
            row=self.take();self.assertEqual(row['status'],'accepted',row.get('rejected'))
            ability=row['normalized']['local_cooldowns']['abilities'][0]
            self.assertEqual(ability['remaining_s'],remaining)
            self.assertEqual(ability['charges_max'],2);self.assertEqual(ability['charges_available'],2-used)
            keys.append(row['tactical_key'])
        self.assertEqual(keys[0],keys[-1]);self.assertNotEqual(keys[0],keys[1]);self.assertNotEqual(keys[1],keys[2])

    def test_unknown_source_is_not_an_accepted_all_unknown_full(self):
        self.m.pack(self.m.data_table+16,'Q',self.m.data+0x80000);self.m.pack(self.m.data+0x80000,'B',0)
        row=self.take();self.assertEqual(row['status'],'rejected');self.assertEqual(row['rejected'],'cooldowns_pipeline_all_unknown')
        ability=row['normalized']['local_cooldowns']['abilities'][0]
        self.assertNotIn('remaining_s',ability);self.assertNotIn('cooldown_ready',ability)

    def test_dead_has_no_ability_values_then_respawn_is_newly_read(self):
        self.m.pack(self.m.local_unit+0x39,'B',2)
        dead=self.take();self.assertEqual(dead['status'],'accepted',dead.get('rejected'))
        self.assertEqual(dead['evidence_kind'],'dead_current_no_values')
        self.assertEqual(dead['normalized']['local_cooldowns']['abilities'],[])
        self.m.pack(self.m.local_unit+0x39,'B',0);self.m.pack(self.m.cd_node+0x18,'i',2*65536)
        revived=self.take();self.assertEqual(revived['status'],'accepted',revived.get('rejected'))
        self.assertEqual(revived['normalized']['local_cooldowns']['abilities'][0]['remaining_s'],2)

    def test_whole_timeout_is_not_hidden_by_optional_family(self):
        clock=FixtureClock();original=self.m.read_memory
        def late(a,s):
            data=original(a,s)
            if a==self.m.cd_node+0x18:clock.value+=0.126
            return data
        self.m.read_memory=late;row=self.take(clock)
        self.assertEqual(row['status'],'rejected');self.assertIn('globale_depassee',row['rejected'])
        self.assertLessEqual(row['read_count'],8192)

    def test_preflight_never_opens_process_and_freezes_consumers(self):
        with patch.object(capture,'frozen_sources',return_value=('a'*40,{})) as freeze, \
                patch.object(capture,'ProcessBackend') as process,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(capture.main(['--preflight','--expected-commit','a'*40]),0)
        process.assert_not_called()
        self.assertIn(capture.ROOT/'cerveau/cooldowns.py',freeze.call_args.kwargs['extra_paths'])
        self.assertIn(capture.ROOT/'cerveau/__init__.py',freeze.call_args.kwargs['extra_paths'])


if __name__=='__main__':unittest.main()
