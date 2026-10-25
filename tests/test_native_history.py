"""Synthetic historical records: never native/HUD qualification."""
import contextlib
import copy
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cerveau import passive_session as product


def observation(cycle=1):
    players = [dict(slot=i, hero=hero, level=1, status='unknown', tiers=None)
               for i, hero in enumerate(('sonya', 'ltmorales', 'mei', 'kaelthas', 'murky'))]
    players[0].update(status='observed', tiers=[dict(tier=1, required_level=1,
        status='selected', slot=2, catalog_id='BarbarianWarPaint')])
    return dict(schema_version=1, sequence=cycle*2, cycle=cycle, event='observation',
        session='session_'+'a'*12, map='map_'+'b'*12,
        mission_t_s=40.+cycle, elapsed_s=float(cycle),
        timestamp_utc=f'2026-10-24T20:47:{cycle:02d}+00:00',
        available_fields=['heroes', 'talents'],
        comparison=dict(session_token='a'*32, map_id='DragonShire', perspective='native_player',
            clock_basis='host_monotonic', read_started_s=100.+cycle, read_finished_s=100.02+cycle),
        heroes=[dict(slot=i, team=int(i>=5), level=1+int(i>=5)) for i in range(10)],
        talents=dict(status='normalized', source='native_player', source_mission_t_s=40.+cycle,
            age_s=.01, read_window_s=.005,
            value=dict(build=98348, map_id='DragonShire', team=0, local_slot=0, players=players)),
        objective=dict(status='not_attempted', value=None))


def rows(*observations):
    result=[]
    for obs in observations:
        result.extend([dict(schema_version=1, sequence=obs['sequence']-1, cycle=obs['cycle'],
            event='acquisition', outcome='accepted', collection='talents',
            not_selected=['objective', 'positions', 'visibility', 'gameplay_clock', 'local_cooldowns', 'battlefield']), obs])
    result.append(dict(schema_version=1, sequence=observations[-1]['sequence']+1,
        cycle=observations[-1]['cycle'], event='boundary', reason='stop_file'))
    return result


class NativeHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'session/events.jsonl'
        self.source.parent.mkdir()
        self.n=0

    def invoke(self, records, suffix=b''):
        self.source.write_bytes(b''.join((json.dumps(r)+'\n').encode() for r in records)+suffix)
        before=self.source.read_bytes()
        self.n+=1
        report=self.root/f'report-{self.n}'
        out, err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                patch.object(product,'preflight',side_effect=AssertionError('no preflight')), \
                patch.object(product,'NativeSource',side_effect=AssertionError('no reader')):
            code=product.main(['--summarize','--journal',str(self.source),'--report-dir',str(report)])
        self.assertEqual(before,self.source.read_bytes())
        result=json.loads(out.getvalue())
        self.assertEqual(result,json.loads((report/'history.json').read_text()))
        self.assertEqual(err.getvalue(),(report/'SUMMARY.txt').read_text())
        return code,result,err.getvalue()

    def test_player_summary_is_minimized_deterministic_historical_and_useful(self):
        obs=observation()
        obs.update(chat='PRIVATE_SECRET', path='C:/PRIVATE_SECRET', enemy_xy=[1,2])
        obs['talents']['value']['players'][0]['tiers'][0]['label']='PRIVATE_SECRET'
        code,result,text=self.invoke(rows(obs))
        self.assertEqual(code,0)
        self.assertEqual(result['state'],'recorded_observation')
        self.assertEqual(result['map'],'DragonShire')
        self.assertEqual(result['public_levels']['by_team'],[1,2])
        self.assertIsNone(result['public_levels']['original_age_s'])
        self.assertEqual(result['talents']['local']['tiers'][0],
            dict(tier=1,required_level=1,status='selected',slot=2,label=None))
        self.assertEqual(result['talents']['original_age_s'],.01)
        self.assertFalse(result['current_permission'])
        self.assertFalse(result['authenticated'])
        self.assertFalse(result['hud_validated'])
        self.assertIsNone(result['current_age_s'])
        serialized=json.dumps(result)+text
        for forbidden in ('PRIVATE_SECRET','BarbarianWarPaint','session_'+'a'*12,'a'*32,'enemy_xy'):
            self.assertNotIn(forbidden,serialized)
        self.assertIn('palier 1',text)
        self.assertIn('choix natif 2',text)
        self.assertIn('NON authentifié',text)
        self.assertIn('Héros local : sonya',text)
        self.assertEqual(result['instant']['host_read_bounds'], dict(clock_basis='host_monotonic',
            started_s=101.,finished_s=101.02))
        self.assertEqual(result['closure']['recorded_reason'],'stop_file')
        self.assertIsNone(result['closure']['reader_active'])
        self.assertEqual(result,self.invoke(rows(obs))[1])

    def test_every_observation_must_share_complete_identity_and_ordered_time(self):
        mutations = [
            lambda r: r.update(session='session_'+'c'*12),
            lambda r: r.update(map='map_'+'d'*12),
            lambda r: r.pop('comparison'),
            lambda r: r['comparison'].update(session_token='b'*32),
            lambda r: r['comparison'].update(map_id='Volskaya'),
            lambda r: r['comparison'].update(perspective='observer'),
            lambda r: r['comparison'].update(clock_basis='utc'),
            lambda r: r['comparison'].update(read_started_s=999.),
            lambda r: r.update(mission_t_s=0),
            lambda r: r.update(elapsed_s=0),
            lambda r: r.update(timestamp_utc='2026-10-24T20:47:00'),
            lambda r: r.update(timestamp_utc='2026-10-24T20:46:00+00:00'),
            lambda r: r.update(mission_t_s=True),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                first,second=observation(1),observation(2)
                mutate(second)
                code,result,text=self.invoke(rows(first,second))
                self.assertEqual(code,1)
                self.assertEqual(result['state'],'refused')
                for key in ('map','instant','talents','objective','public_levels'):
                    self.assertIsNone(result[key])
                self.assertNotIn('choix natif',text)

    def test_mixed_local_identity_is_not_salvaged_from_last_good_row(self):
        first,second=observation(1),observation(2)
        second['talents']['value']['local_slot']=1
        code,result,_=self.invoke(rows(first,second))
        self.assertEqual(code,1)
        self.assertEqual(result['reason'],'identity_or_time_refused')

    def test_family_missing_refused_unknown_age_foreign_and_unselected_never_backfill(self):
        for status in ('refused','rejected','not_attempted','not_selected','unknown'):
            with self.subTest(status=status):
                obs=observation()
                obs['talents']['status']=status
                code,result,text=self.invoke(rows(obs))
                self.assertEqual(code,0)
                self.assertEqual(result['talents']['status'],status)
                self.assertIsNone(result['talents']['local'])
                self.assertIsNone(result['talents']['original_age_s'])
                self.assertNotIn('choix natif',text)
        for field,value in (('age_s',None),('age_s',2),('read_window_s',.126),
                            ('source','replay'),('source_mission_t_s',0)):
            obs=observation()
            obs['talents'][field]=value
            code,result,_=self.invoke(rows(obs))
            self.assertEqual(code,0)
            self.assertEqual(result['talents']['status'],'rejected')
            self.assertIsNone(result['talents']['local'])
            self.assertIsNone(result['talents']['original_age_s'])
        obs=observation()
        obs['available_fields'].remove('talents')
        _,result,_=self.invoke(rows(obs))
        self.assertEqual(result['talents']['status'],'not_selected')
        self.assertIsNone(result['talents']['local'])
        # An unrelated data family remains explicitly unselected, not normalized.
        self.assertEqual(result['families']['positions'],'not_selected')

    def test_roster_mismatch_and_unqualified_local_talents_are_not_exported(self):
        for mutate in (lambda r: r['heroes'][0].update(team=1),
                       lambda r: r['heroes'][0].update(level=True),
                       lambda r: r['talents']['value']['players'][0].update(hero='PRIVATE_SECRET'),
                       lambda r: r['talents']['value']['players'][0].update(status='unknown',tiers=None)):
            obs=observation()
            mutate(obs)
            code,result,text=self.invoke(rows(obs))
            self.assertEqual(code,0)
            self.assertIsNone(result['talents']['local'])
            self.assertNotIn('PRIVATE_SECRET',json.dumps(result)+text)

    def test_latest_observation_not_older_success_is_selected(self):
        first,second=observation(1),observation(2)
        second['talents'].update(status='refused',value=None)
        _,result,text=self.invoke(rows(first,second))
        self.assertEqual(result['instant']['sequence'],4)
        self.assertEqual(result['talents']['status'],'refused')
        self.assertNotIn('choix natif',text)

    def test_missing_selection_metadata_and_malformed_optional_do_not_publish_talents(self):
        for available in (None, 'talents', [], ['heroes']):
            obs=observation()
            obs['available_fields']=available
            records=rows(obs)
            records[0]['optional_refusals']=None
            code,result,_=self.invoke(records)
            self.assertEqual(code,0)
            self.assertEqual(result['talents']['status'],'not_selected')
            self.assertIsNone(result['talents']['local'])

    def test_absent_or_unknown_collection_never_proves_optional_family_selection(self):
        for collection in (None, 'unknown', [], True):
            with self.subTest(collection=collection):
                obs=observation()
                obs['available_fields'].append('objective')
                obs['objective']=dict(status='normalized',source='native_player',
                    source_mission_t_s=41.,age_s=.02,read_window_s=.01,
                    family='dragon',value_status='exported',
                    value=dict(phase='shrines',
                        shrines=[dict(id=s,owner=None,state='unknown',contested=None)
                                 for s in ('sun','moon')],
                        statue=dict(state='unknown',team=None,channeling=None),
                        dragon=dict(state='unknown',team=None,remaining_s=None),
                        start=dict(remaining_s=None,paused=False),
                        respawn=dict(remaining_s=None,paused=False),
                        warning=dict(remaining_s=None,paused=False)))
                records=rows(obs)
                # Neither available_fields nor an untrusted not_selected=[] can
                # replace a recognized acquisition collection.
                records[0]['not_selected']=[]
                if collection is None:
                    records[0].pop('collection')
                else:
                    records[0]['collection']=collection
                code,result,text=self.invoke(records)
                self.assertEqual(code,0)
                self.assertEqual(result['public_levels']['by_team'],[1,2])
                self.assertEqual(set(result['families'].values()),{'unknown'})
                self.assertEqual(result['talents']['status'],'unknown')
                self.assertIsNone(result['talents']['local'])
                self.assertIsNone(result['talents']['original_age_s'])
                self.assertEqual(result['objective']['status'],'unknown')
                self.assertIsNone(result['objective']['value'])
                self.assertIsNone(result['objective']['original_age_s'])
                self.assertNotIn('choix natif',text)
                self.assertNotIn('sanctuaires',text)
                self.assertIn('selection_metadata_unknown',result['limitations'])
                self.assertEqual(result,self.invoke(records)[1])

    def test_missing_or_misplaced_closure_is_not_a_complete_session(self):
        records=rows(observation())
        code,result,_=self.invoke(records[:-1])
        self.assertEqual(code,1)
        self.assertEqual(result['reason'],'session_closure_unknown')
        self.assertIsNone(result['talents'])
        # A boundary followed by additional data cannot close the whole stream.
        early=copy.deepcopy(records[-1])
        early['sequence']=1
        early['cycle']=0
        altered=[early]+rows(observation())
        for i,row in enumerate(altered,1):
            row['sequence']=i
        code,result,_=self.invoke(altered)
        self.assertEqual(code,1)

    def test_changed_local_hero_in_any_normalized_packet_refuses_whole_stream(self):
        first,second=observation(1),observation(2)
        second['talents']['value']['players'][0]['hero']='jaina'
        code,result,_=self.invoke(rows(first,second))
        self.assertEqual(code,1)
        self.assertEqual(result['reason'],'identity_or_time_refused')

    def test_observation_requires_its_recorded_accepted_acquisition(self):
        for outcome in ('refused','error','unknown',None):
            records=rows(observation())
            records[0]['outcome']=outcome
            code,result,_=self.invoke(records)
            self.assertEqual(code,1)
            self.assertEqual(result['reason'],'acquisition_pair_refused')
        records=rows(observation())
        records.pop(0)
        for i,r in enumerate(records,1):
            r['sequence']=i
        code,result,_=self.invoke(records)
        self.assertEqual(code,1)
        self.assertEqual(result['reason'],'acquisition_pair_refused')

    def test_public_levels_unknown_not_zero_and_later_refusal_never_advances_instant(self):
        obs=observation()
        obs['heroes'][0].pop('level')
        _,result,_=self.invoke(rows(obs))
        self.assertEqual(result['public_levels']['by_team'],[None,2])
        obs=observation()
        obs['heroes'][1]['slot']=0
        _,result,_=self.invoke(rows(obs))
        self.assertEqual(result['public_levels']['by_team'],[None,None])
        records=rows(observation())
        records.insert(-1,dict(schema_version=1,sequence=3,cycle=2,event='refusal',
                               code='lecture_native_dechiree'))
        records[-1].update(sequence=4,cycle=2)
        _,result,_=self.invoke(records)
        self.assertTrue(result['later_refusal_or_error'])
        self.assertEqual(result['instant']['cycle'],1)
        self.assertEqual(result['talents']['original_age_s'],.01)

    def test_inherited_parser_characterization_limits_truncation_and_invalid_json(self):
        # Already-GREEN inherited guards, NOT claimed as new RED evidence.
        from cerveau.native_history import summarize
        for suffix in (b'{"event":"observation"', b'{"valid":"json"}'):
            code,result,text=self.invoke(rows(observation()),suffix)
            self.assertEqual(code,1)
            self.assertEqual(result['journal']['state'],'truncated')
            self.assertIsNone(result['talents'])
            self.assertNotIn('choix natif',text)
        invalids=[b'null\n',b'[]\n',b'{"x":1,"x":2}\n',b'{"x":NaN}\n',
                  b'{"x":Infinity}\n',b'{"x":1e999}\n',b'\xff\n',b'{"x":'+b'['*1100+b'0'+b']'*1100+b'}\n']
        for data in invalids:
            self.source.write_bytes(data)
            result=summarize(self.source)
            self.assertEqual(result['journal']['state'],'invalid')
            self.assertIsNone(result['talents'])
        for data in (b'x'*65537+b'\n', b'x'*(4*2**20+1)):
            self.source.write_bytes(data)
            self.assertEqual(summarize(self.source)['journal']['state'],'limit_exceeded')
        many=b''.join((json.dumps(dict(schema_version=1,sequence=i,event='phase',cycle=0))+'\n').encode()
                      for i in range(1,10002))
        self.source.write_bytes(many)
        self.assertEqual(summarize(self.source)['journal']['state'],'limit_exceeded')
        self.source.write_bytes(b'')
        self.assertEqual(summarize(self.source)['journal']['state'],'empty')
        self.source.unlink()
        self.assertEqual(summarize(self.source)['journal']['state'],'unavailable')
        self.assertEqual(summarize(self.source.parent)['journal']['state'],'invalid')

    def test_cli_characterization_exclusive_modes_paths_and_nonoverwrite(self):
        self.invoke(rows(observation()))
        base=['--summarize','--journal',str(self.source),'--report-dir',str(self.root/'fresh')]
        for extra in (['--diagnose'],['--live'],['--status'],['--preflight'],
                      ['--player-file',str(self.root/'private')],['--output-dir',str(self.root/'live')],
                      ['--stop-file',str(self.root/'STOP')],['--visual-reference',str(self.root/'image.bmp')]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                product.main(base+extra)
            self.assertEqual(exc.exception.code,2)
        for argv in (['--summarize'], ['--summarize','--journal','relative','--report-dir',str(self.root/'fresh')],
                     ['--journal',str(self.source),'--report-dir',str(self.root/'fresh')]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                product.main(argv)
            self.assertEqual(exc.exception.code,2)
        for report in (self.root/'report-1',self.source.parent/'new'):
            with contextlib.redirect_stdout(io.StringIO()):
                code=product.main(['--summarize','--journal',str(self.source),'--report-dir',str(report)])
            self.assertEqual(code,1)
        self.assertFalse((self.source.parent/'new').exists())

    def test_fresh_real_cli_guard_forbids_network_backend_receipt_coach_audio_and_scans(self):
        self.invoke(rows(observation()))
        helper=Path(__file__).resolve().parent/'helpers/native_history_offline.py'
        process=subprocess.run([sys.executable,'-B',str(helper),'--summarize','--journal',str(self.source),
            '--report-dir',str(self.root/'guarded')],capture_output=True,encoding='utf-8',
            env=dict(os.environ,PYTHONIOENCODING='utf-8'),timeout=30)
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)
        self.assertEqual(json.loads(process.stdout)['talents']['local']['tiers'][0]['slot'],2)

    def test_objective_uses_existing_closed_dragon_projection_and_preserves_null(self):
        obs=observation()
        obs['available_fields'].append('objective')
        obs['objective']=dict(status='normalized',source='native_player',reason=None,
            source_mission_t_s=41.,age_s=.02,read_window_s=.01,family='dragon',value_status='exported',
            value=dict(phase='shrines',
                shrines=[dict(id=s,owner=None,state='unknown',contested=None) for s in ('sun','moon')],
                statue=dict(state='unknown',team=None,channeling=None),
                dragon=dict(state='unknown',team=None,remaining_s=None),
                start=dict(remaining_s=None,paused=False),respawn=dict(remaining_s=None,paused=False),
                warning=dict(remaining_s=None,paused=False),enemy_xy='PRIVATE_SECRET'))
        records=rows(obs)
        records[0]['collection']='all'
        records[0]['not_selected']=[]
        code,result,text=self.invoke(records)
        self.assertEqual(code,0)
        self.assertEqual(result['objective']['status'],'normalized')
        self.assertEqual(result['objective']['value']['phase'],'shrines')
        self.assertIsNone(result['objective']['value']['dragon']['remaining_s'])
        self.assertNotIn('PRIVATE_SECRET',json.dumps(result)+text)
        self.assertIn('sanctuaires',text)
        obs['objective']['age_s']=None
        _,result,_=self.invoke(records)
        self.assertEqual(result['objective']['status'],'rejected')
        self.assertIsNone(result['objective']['value'])
