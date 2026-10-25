"""SYNTHETIC timeline. No clock, HUD or current permission established."""
import unittest
from tests.test_core_history import core_observation, project
from tests.test_native_history import rows


def long_series(count):
    # All clocks deliberately equal: ordinal order, never an invented duration.
    observations=[]
    for i in range(1,count+1):
        obs=core_observation()
        obs.update(sequence=2*i,cycle=i)
        obs['comparison']['read_finished_s']=obs['comparison']['read_started_s']
        obs['heroes'][0]['health']=i % 200
        observations.append(obs)
    return rows(*observations)


class CoreTimelineTests(unittest.TestCase):
    def test_bounded_tail_counts_whole_stream_including_late_refusal(self):
        records=long_series(350)
        records.insert(-1,dict(event='refusal',schema_version=1,sequence=701,cycle=351))
        records[-1].update(sequence=702,cycle=351)
        timeline=project(records)['core_timeline']
        self.assertEqual(timeline.get('entry_limit'),128)
        self.assertEqual(timeline['total_observations'],350)
        self.assertEqual(timeline['total_points'],350)
        self.assertEqual(timeline['total_entries'],352)
        self.assertEqual(len(timeline['entries']),128)
        self.assertEqual(timeline['omitted_entries'],224)
        self.assertEqual(timeline['displayed_points'],126)
        self.assertTrue(timeline['truncated'])
        self.assertEqual(timeline['entries'][-2]['kind'],'refusal')
        self.assertEqual(timeline['entries'][-1]['kind'],'boundary')
        self.assertEqual(timeline['entries'][0]['journal_ordinal'],450)

    def test_late_identity_rejection_discards_even_previously_valid_points(self):
        for mutate in (lambda o:o.update(session='session_'+'f'*12),
                       lambda o:o['comparison'].update(session_token='b'*32),
                       lambda o:o['heroes'][0].update(hero='hero_'+'d'*12),
                       lambda o:o['heroes'][0].update(team=1)):
            records=long_series(350)
            records[-2]['talents']['status']='refused'
            mutate(records[-2])
            result=project(records)
            self.assertEqual(result['state'],'refused')
            self.assertEqual(result['core_timeline']['entries'],[])
            self.assertFalse(result['core_timeline']['counts_complete'])
            self.assertIsNone(result['core_timeline']['total_points'])

    def test_divergent_team_cannot_hide_in_unbalanced_roster_before_binding(self):
        for mutation in (dict(team=1),dict(team=True),dict(hero='hero_'+'d'*12)):
            first,second=core_observation(1),core_observation(2)
            first['talents']['status']='refused'
            first['heroes'][0].update(mutation)
            result=project(rows(first,second))
            self.assertEqual(result['reason'],'identity_or_time_refused')
            self.assertEqual(result['core_timeline']['entries'],[])

    def test_refused_acquisition_alone_is_an_explicit_gap(self):
        records=rows(core_observation())
        records.insert(-1,dict(event='acquisition',schema_version=1,sequence=3,cycle=2,outcome='refused'))
        records[-1].update(sequence=4,cycle=2)
        timeline=project(records)['core_timeline']
        self.assertEqual([e['kind'] for e in timeline['entries']],
                         ['observation','acquisition_refused','boundary'])
        self.assertIsNone(timeline['entries'][1]['core'])

    def test_unbound_missing_invalid_and_refused_rows_do_not_backfill(self):
        for mutate in (lambda o:o.pop('talents'),
                       lambda o:o['talents'].update(status='refused'),
                       lambda o:o['heroes'][0].pop('health'),
                       lambda o:o['heroes'][0].update(health=True),
                       lambda o:o['heroes'][0].update(health=float('nan')),
                       lambda o:o['heroes'][0].update(resource=float('inf'))):
            first,second,third=core_observation(1),core_observation(2),core_observation(3)
            mutate(second)
            result=project(rows(first,second,third))
            entries=result['core_timeline']['entries']
            self.assertEqual(entries[0]['core']['health']['value'],125.5)
            self.assertEqual(entries[2]['core'],result['local_core'])
            from cerveau.native_history import _core,_talents,_packet
            expected=_core(second,_talents(_packet(second,'talents',[]),second))
            self.assertEqual(entries[1]['core'],expected)
            self.assertIsNone(entries[1]['core']['original_age_s'])

    def test_incomplete_or_multi_boundary_stream_never_retains_timeline(self):
        from cerveau.native_history import _summarize
        records=rows(core_observation())
        for state in ('invalid','truncated','limit_exceeded','empty','unavailable'):
            timeline=_summarize(records,dict(state=state))['core_timeline']
            self.assertEqual(timeline['entries'],[])
            self.assertIsNone(timeline['total_observations'])
        for bad in (records[:-1], [records[-1]]+records, records+[records[1]]):
            result=project(bad)
            self.assertEqual(result['core_timeline']['entries'],[])

    def test_html_accessible_table_and_text_show_series_gaps_and_truncation(self):
        from cerveau import session_html,native_history
        from cerveau.session_diagnosis import _diagnose
        records=long_series(350)
        history=project(records)
        html=session_html.render(dict(history=history,diagnosis=_diagnose(records,dict(state='complete',records=len(records)))))
        self.assertIn('<caption>Chronologie du cœur local',html)
        self.assertIn('scope="col">Ordre du journal',html)
        self.assertIn('Entrées antérieures omises : 223',html)
        self.assertIn('Points admissibles sur le flux complet : 350',html)
        self.assertIn('Frontière de clôture',html)
        self.assertIn('aucune durée',html)
        text=native_history.readable(history)
        self.assertIn('Chronologie du cœur local',text)
        self.assertIn('Points admissibles sur le flux complet : 350',text)
        self.assertNotIn('<script',html)

    def test_html_escape_and_raw_injections_do_not_leak_into_timeline(self):
        import json
        from cerveau import native_history,session_html
        from cerveau.session_diagnosis import _diagnose
        obs=core_observation()
        attack='<script>alert("SYNTHETIC")</script>'
        obs['heroes'][0]['private_extra']=attack
        obs['talents']['value']['players'][0]['tiers'][0]['label']=attack
        records=rows(obs)
        history=project(records)
        self.assertNotIn(attack,json.dumps(history['core_timeline']))
        history['core_timeline']['entries'][0]['journal_ordinal']=attack
        html=session_html.render(dict(history=history,diagnosis=_diagnose(records,dict(state='complete',records=len(records)))))
        self.assertNotIn(attack,html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn("default-src 'none'",html)

    def test_refusal_between_points_and_zero_admissible_counts_are_explicit(self):
        first,second=core_observation(1),core_observation(3)
        records=rows(first,second)
        records.insert(2,dict(event='source_error',schema_version=1,sequence=3,cycle=2))
        # The parser enforces contiguous records; renumber this valid synthetic log.
        for n,r in enumerate(records,1): r['sequence']=n
        timeline=project(records)['core_timeline']
        self.assertEqual([e['kind'] for e in timeline['entries']],
                         ['observation','source_error','observation','boundary'])
        self.assertEqual(timeline['total_points'],2)
        from cerveau import native_history
        self.assertIn('rupture',list(native_history.timeline_rows(timeline))[1][1])
        obs=core_observation()
        obs.pop('talents')
        timeline=project(rows(obs))['core_timeline']
        self.assertEqual(timeline['total_points'],0)
        self.assertEqual(timeline['total_observations'],1)
        self.assertEqual(timeline['displayed_points'],0)
        self.assertEqual(len(timeline['entries']),2)
        self.assertIn('liaison locale inconnue',list(native_history.timeline_rows(timeline))[0][1])

    def test_keeps_each_same_event_core_in_journal_order_without_clock(self):
        first,second=core_observation(1),core_observation(2)
        second['heroes'][0].update(health=0,resource=25,alive=False)
        result=project(rows(first,second))
        timeline=result.get('core_timeline')
        self.assertIsNotNone(timeline, 'historical series is missing')
        self.assertEqual(timeline['status'],'recorded')
        self.assertEqual(timeline['order_basis'],'journal_ordinal_not_time')
        self.assertEqual(timeline['total_observations'],2)
        self.assertEqual(timeline['total_points'],2)
        self.assertTrue(timeline['counts_complete'])
        self.assertEqual([e['journal_ordinal'] for e in timeline['entries']],[2,4,5])
        self.assertEqual([e['kind'] for e in timeline['entries']],['observation','observation','boundary'])
        cores=[e['core'] for e in timeline['entries'] if e['kind']=='observation']
        self.assertEqual([c['health']['value'] for c in cores],[125.5,0])
        self.assertEqual([c['resource']['value'] for c in cores],[0.,25])
        self.assertEqual([c['alive'] for c in cores],[True,False])
        self.assertEqual(cores[-1],result['local_core'])
        for e in timeline['entries']:
            self.assertNotIn('mission_t_s',e)
            self.assertNotIn('elapsed_s',e)
            self.assertNotIn('timestamp_utc',e)
            if e['kind']=='observation': self.assertIsNone(e['core']['original_age_s'])
