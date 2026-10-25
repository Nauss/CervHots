"""SYNTHETIC samples only; no new native, HUD or charge qualification."""
import copy
import json
import unittest
from cerveau import native_history, session_html
from tests.test_native_history import observation, rows


def sample(cycle=1):
    row = observation(cycle)
    row['available_fields'].append('local_cooldowns')
    row['heroes'][0].update(hero='hero_'+'c'*12, alive=True)
    row['local_cooldowns'] = dict(status='normalized', source='native_player', reason=None,
        source_mission_t_s=row['mission_t_s'], age_s=.025, read_window_s=.01,
        value=dict(build=98348, map_id='DragonShire', hero='sonya', local_slot=0, team=0,
            actor_scope='current_native_main_hero', ui_control_body='unknown', alive=True,
            abilities=[dict(ability='BarbarianAncientSpear', instance_slot=22,
                slot_kind='native_instance_NOT_HUD_button', cast_legality='unknown',
                cooldown_status='observed', remaining_s=0., cooldown_ready=True,
                charges_status='not_applicable_current_max_zero')]))
    return row


def summarize(*samples):
    records=rows(*samples)
    for r in records:
        if r['event']=='acquisition': r['collection']='all'
    return native_history._summarize(records, dict(state='complete',sha256='d'*64))


class CooldownsHistoryTests(unittest.TestCase):
    def test_same_event_zero_is_preserved_with_original_age_and_trace(self):
        result=summarize(sample())
        p=result.get('local_cooldowns')
        self.assertIsNotNone(p, 'cooldown values must reach historical JSON')
        self.assertEqual(p['status'],'normalized')
        self.assertEqual(p['original_age_s'],.025)
        a=p['value']['abilities'][0]
        self.assertEqual(a['remaining_s'],0)
        self.assertTrue(a['cooldown_ready'])
        self.assertIsNone(a['charges_available'])
        self.assertEqual(a['cast_legality'],'unknown')
        self.assertEqual(p['provenance'],dict(journal_sha256='d'*64,sequence=2,
            key='/local_cooldowns/value',basis='recorded_not_authenticated'))
        self.assertNotIn('a'*32,json.dumps(p))
        text=native_history.readable(result)
        self.assertIn('Recharge locale',text)
        self.assertIn('ne signifie pas lançable',text)

    def test_changed_local_binding_anywhere_in_stream_refuses_whole_history(self):
        for index, mutate in enumerate((
            lambda r: r['local_cooldowns']['value'].update(local_slot=1),
            lambda r: r['local_cooldowns']['value'].update(team=1),
            lambda r: r['heroes'][0].update(hero='hero_'+'e'*12),
        )):
            first, second=sample(1), sample(2)
            second['talents']={'status':'refused'}
            mutate(second)
            with self.subTest(mutation=index):
                result=summarize(first,second)
                self.assertEqual(result['state'],'refused')
                self.assertIsNone(result['local_cooldowns'])

    def test_bad_values_and_contradictions_never_leak(self):
        mutations=[
            lambda r: r['local_cooldowns'].update(age_s=1.01),
            lambda r: r['local_cooldowns'].update(read_window_s=.126),
            lambda r: r['local_cooldowns'].update(source_mission_t_s=0),
            lambda r: r['local_cooldowns'].update(source='diagnostic'),
            lambda r: r['local_cooldowns']['value'].update(build=True),
            lambda r: r['local_cooldowns']['value'].update(map_id='Volskaya'),
            lambda r: r['local_cooldowns']['value'].update(hero='stitches'),
            lambda r: r['local_cooldowns']['value'].update(alive=False),
            lambda r: r['heroes'][0].update(alive=False),
            lambda r: r['local_cooldowns']['value']['abilities'].append(copy.deepcopy(r['local_cooldowns']['value']['abilities'][0])),
        ]
        for key,value in [('remaining_s',True),('remaining_s',float('nan')),('remaining_s',float('inf')),
                ('remaining_s',-1),('remaining_s',3601),('cooldown_ready',False),('instance_slot',True),
                ('instance_slot',64),('ability','PRIVATE_SECRET'),('slot_kind','HUD'),
                ('cast_legality','castable'),('charges_status','observed'),
                ('cooldown_status','unknown'),('charges_available',0)]:
            mutations.append(lambda r,k=key,v=value:r['local_cooldowns']['value']['abilities'][0].update({k:v}))
        for mutate in mutations:
            row=sample(); mutate(row)
            with self.subTest(mutation=mutations.index(mutate)):
                result=summarize(row)
                p=result.get('local_cooldowns')
                if result['state']=='refused':
                    self.assertIsNone(p)
                else:
                    self.assertEqual(p['status'],'rejected')
                    self.assertIsNone(p['value'])
                    self.assertIsNone(p['original_age_s'])
                self.assertNotIn('PRIVATE_SECRET',json.dumps(result))

    def test_no_carry_after_dead_refusal_unknown_or_unselected(self):
        for status in ('refused','not_attempted','unknown','rejected'):
            last=sample(2);last['local_cooldowns']['status']=status
            result=summarize(sample(1),last)
            self.assertEqual(result['local_cooldowns']['status'],status)
            self.assertIsNone(result['local_cooldowns']['value'])
        last=sample(2)
        last['local_cooldowns']['value'].update(alive=False,abilities=[])
        last['heroes'][0]['alive']=False
        p=summarize(sample(1),last)['local_cooldowns']
        self.assertEqual(p['value']['abilities'],[])
        self.assertFalse(p['value']['alive'])
        row=sample();a=row['local_cooldowns']['value']['abilities'][0]
        a.update(cooldown_status='unknown',charges_status='unknown')
        del a['remaining_s'];del a['cooldown_ready']
        a=summarize(row)['local_cooldowns']['value']['abilities'][0]
        self.assertIsNone(a['remaining_s']);self.assertIsNone(a['cooldown_ready'])
        self.assertIsNone(a['charges_max'])
        records=rows(sample());records[0]['collection']='core'
        p=native_history._summarize(records,dict(state='complete',sha256='d'*64))['local_cooldowns']
        self.assertEqual(p['status'],'not_selected');self.assertIsNone(p['value'])

    def test_normalizer_and_journal_durably_export_only_qualified_projection(self):
        from unittest.mock import patch
        from hotstate.acquisition import issue
        from cerveau.state import snapshot
        from cerveau.diagnostics import Journal
        local=dict(id=0,team=0,hero='sonya')
        heroes=[dict(id=i,team=int(i>=5),hero='sonya' if i==0 else 'mei',
                     level=1,alive=True) for i in range(10)]
        value=sample()['local_cooldowns']['value']
        packet=dict(status='validated', map_id='DragonShire',match_id='a'*64,
            local_id=0,team=0,local_hero='sonya',alive=True,mission_t_s=41.,read_window_s=.01,
            actor_scope=value['actor_scope'],ui_control_body='unknown',abilities=copy.deepcopy(value['abilities']))
        raw=dict(meta=dict(source='live',native_status='valide',native_build=98348,
            context_source='initdata_native_fields',map='Dragon Shire',map_id='DragonShire',
            match_id='a'*64,t_s=41.,collection='all'),local_player=local,
            players=[{k:h[k] for k in ('id','team','hero')} for h in heroes],heroes=heroes,
            local_cooldowns=packet)
        with patch('time.monotonic',return_value=100.):
            issue(packet,99.975)
            state=snapshot(raw)
        records=[]
        with patch('time.monotonic',side_effect=AssertionError('no age renewal')):
            Journal(records.append,salt=b'x'*32).observation(state)
        stored=records[0].get('local_cooldowns')
        self.assertIsNotNone(stored, 'qualified cooldown projection must be durable')
        self.assertEqual(stored['status'],'normalized')
        self.assertAlmostEqual(stored['age_s'],.025)
        self.assertEqual(stored['value']['abilities'][0]['remaining_s'],0)
        self.assertNotIn('acquisition',json.dumps(stored))
        with patch('time.monotonic',return_value=102.):
            expired=snapshot(raw)
        records=[];Journal(records.append).observation(expired)
        self.assertEqual(records[0]['local_cooldowns']['status'],'rejected')
        self.assertIsNone(records[0]['local_cooldowns']['value'])
        raw['meta']['collection']='core'
        with patch('cerveau.cooldowns.project_local_cooldowns',side_effect=AssertionError('unselected')):
            core=snapshot(raw)
        self.assertNotIn('local_cooldowns',core)

    def test_legacy_explicit_cooldowns_collection_is_historical_only(self):
        records=rows(sample());records[0]['collection']='cooldowns'
        result=native_history._summarize(records,dict(state='complete',sha256='d'*64))
        self.assertEqual(result['local_cooldowns']['status'],'normalized')
        self.assertEqual(result['families']['talents'],'not_selected')
        from cerveau.passive_session import measured_acquisition
        self.assertNotIn('collection', measured_acquisition({'collection':'cooldowns'}))

    def test_html_exposes_values_status_clocks_and_castability_limit(self):
        history=summarize(sample())
        diagnosis=dict(counts_scope='recorded_events',counts=dict(acquisitions=1,observations=1,
            refused_cycles=0,errors=0,source_errors=0),refusal_codes={},optional_refusals={},normalized_fields=[])
        html=session_html.render(dict(history=history,diagnosis=diagnosis))
        self.assertIn('Cooldowns et charges locaux enregistrés',html)
        self.assertIn('BarbarianAncientSpear',html)
        self.assertIn('0.025',html)
        self.assertIn('slot instance natif',html)
        self.assertNotIn('<script',html)

    def test_acquisition_optional_refusal_cannot_publish_contradictory_values(self):
        records=rows(sample());records[0].update(collection='all',
            optional_refusals=dict(local_cooldowns=dict(code='cooldown_identity_or_scope')))
        result=native_history._summarize(records,dict(state='complete',sha256='d'*64))
        self.assertEqual(result['local_cooldowns']['status'],'rejected')
        self.assertIsNone(result['local_cooldowns']['value'])

    def test_selection_absent_or_malformed_cannot_grant_values(self):
        for collection in (None,False,[],{},'UNKNOWN'):
            records=rows(sample());records[0]['collection']=collection
            result=native_history._summarize(records,dict(state='complete',sha256='d'*64))
            self.assertEqual(result['local_cooldowns']['status'],'unknown')
            self.assertIsNone(result['local_cooldowns']['value'])

    def test_receipt_live_projector_and_clock_are_never_used_by_history(self):
        from unittest.mock import patch
        with patch('hotstate.acquisition.issue',side_effect=AssertionError('no receipt')), \
                patch('cerveau.cooldowns.project_local_cooldowns',side_effect=AssertionError('no live')), \
                patch('time.monotonic',side_effect=AssertionError('no current clock')):
            first=summarize(sample())
            second=summarize(sample())
        self.assertEqual(first,second)

    def test_real_offline_clis_are_guarded_deterministic_and_sanitized(self):
        import os
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'source/events.jsonl';source.parent.mkdir()
            records=rows(sample());records[0]['collection']='all'
            records[1]['local_cooldowns']['value']['abilities'][0]['private']='PRIVATE_SECRET'
            source.write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
            before=source.read_bytes()
            results=[]
            for mode in ('--summarize','--report-html'):
                for repeat in (1,2):
                    report=root/f'{mode[2:]}-{repeat}'
                    args=[sys.executable,'-B','tests/helpers/history_offline_guard.py',mode,
                        '--journal',str(source),'--report-dir',str(report)]
                    proc=subprocess.run(args,capture_output=True,cwd=Path(__file__).resolve().parents[1],
                        env=dict(os.environ,PYTHONIOENCODING='utf-8'),timeout=20)
                    self.assertEqual(proc.returncode,0,proc.stderr.decode('utf-8'))
                    result=json.loads(proc.stdout)
                    history=result['history'] if mode=='--report-html' else result
                    self.assertEqual(history['local_cooldowns']['value']['abilities'][0]['remaining_s'],0)
                    self.assertNotIn('PRIVATE_SECRET',proc.stdout.decode('utf-8'))
                    self.assertNotIn('a'*32,proc.stdout.decode('utf-8'))
                    self.assertFalse(history['current_permission'])
                    results.append(result)
            self.assertEqual(results[0],results[1]);self.assertEqual(results[2],results[3])
            self.assertEqual(before,source.read_bytes())

    def test_collector_retains_map_from_same_qualified_cooldown_projection(self):
        from cerveau.passive_session import run_session
        row=sample();value=row['local_cooldowns']['value']
        state=dict(meta=dict(source='live',native_status='valide',native_build=98348,
            context_source='initdata_native_fields',match_id='a'*64,map='Dragon Shire',t_s=41.,collection='all'),
            local_player=dict(id=0,hero='sonya',team=0),ally_team=0,
            heroes=[dict(id=i,team=int(i>=5),hero='sonya' if i==0 else 'mei',alive=True,level=1) for i in range(10)],
            local_cooldowns=dict(value,t=41.,local_id=0),cooldowns_qualification=dict(
                status='normalized',source='native_player',source_mission_t_s=41.,age_s=.025,read_window_s=.01))
        class Source:
            def read(self, observe):
                observe(dict(collection='all',stage='key',outcome='accepted'))
                return state
            def close(self): pass
        records=[]
        result=run_session(Source,lambda:any(r['event']=='observation' for r in records),records.append,
            duration=1,interval=1)
        self.assertEqual(result['accepted'],1)
        observation=next(r for r in records if r['event']=='observation')
        self.assertEqual(observation['comparison']['map_id'],'DragonShire')
        history=native_history._summarize(records,dict(state='complete',sha256='d'*64))
        self.assertEqual(history['local_cooldowns']['status'],'normalized')

if __name__=='__main__': unittest.main()
