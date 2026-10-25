"""SYNTHETIC core history; no native or HUD qualification."""
import json
import unittest
from cerveau import native_history, session_html
from tests.test_native_history import observation, rows


def core_observation(cycle=1):
    obs=observation(cycle)
    obs['heroes'][0].update(hero='hero_'+'c'*12, health=125.5,health_max=200.,
                           resource=0.,resource_max=100.,alive=True)
    return obs


def project(records):
    return native_history._summarize(records,dict(state='complete'))


class CoreHistoryTests(unittest.TestCase):
    def test_local_core_projects_same_observation_and_renders_without_identity(self):
        result=project(rows(core_observation()))
        core=result['local_core']
        self.assertEqual(core['status'],'recorded')
        self.assertEqual(core['health'],dict(status='recorded',value=125.5,maximum=200.))
        self.assertEqual(core['resource'],dict(status='recorded',value=0.,maximum=100.))
        self.assertEqual(core['alive'],True)
        self.assertIn('Vie locale : vivant',native_history.readable(result))
        self.assertIsNone(core['original_age_s'])
        self.assertEqual(core['identity_basis'],'validated_recorded_local_talents')
        text=native_history.readable(result)
        self.assertIn('Santé locale : 125.5 / 200',text)
        self.assertIn('Ressource locale : 0 / 100',text)
        self.assertNotIn('hero_'+'c'*12,json.dumps(core)+text)
        self.assertFalse(result['hud_validated'])
        self.assertFalse(result['current_permission'])
        self.assertIn('resource_kind_not_recorded',result['limitations'])

    def test_invalid_pairs_never_emit_numbers_or_boolean_as_number(self):
        for key in ('health','health_max','resource','resource_max'):
            for value in (True,False,-1,100001,float('nan'),float('inf'),'PRIVATE',[],{}):
                with self.subTest(key=key,value=repr(value)):
                    obs=core_observation()
                    obs['heroes'][0][key]=value
                    core=project(rows(obs))['local_core']
                    pair=core['health' if key.startswith('health') else 'resource']
                    self.assertEqual(pair,dict(status='invalid',value=None,maximum=None))
        for current,maximum in ((201,200),(0,0)):
            obs=core_observation()
            obs['heroes'][0].update(health=current,health_max=maximum)
            self.assertEqual(project(rows(obs))['local_core']['health']['status'],'invalid')

    def test_absence_latest_no_merge_and_later_error_preserve_instant(self):
        first,second=core_observation(1),core_observation(2)
        second['heroes'][0].pop('health')
        records=rows(first,second)
        records.insert(-1,dict(schema_version=1,sequence=5,cycle=3,event='error'))
        records[-1].update(sequence=6,cycle=3)
        result=project(records)
        self.assertEqual(result['local_core']['health'],dict(status='absent',value=None,maximum=None))
        self.assertEqual(result['local_core']['resource']['value'],0)
        self.assertTrue(result['later_refusal_or_error'])
        self.assertEqual(result['instant']['cycle'],2)

    def test_unbound_or_invalid_roster_never_selects_first_ally(self):
        for mutate in (lambda o:o.pop('talents'),
                       lambda o:o['talents'].update(status='refused'),
                       lambda o:o['talents'].update(age_s=None),
                       lambda o:o['heroes'][0].update(team=1),
                       lambda o:o['heroes'][0].update(slot=True),
                       lambda o:o['heroes'][0].update(hero='PRIVATE'),
                       lambda o:o['available_fields'].remove('heroes')):
            obs=core_observation()
            mutate(obs)
            core=project(rows(obs))['local_core']
            self.assertNotEqual(core['status'],'recorded')
            self.assertIsNone(core['health']['value'])
            self.assertIsNone(core['resource']['value'])

    def test_mixed_roster_local_identity_refuses_whole_stream(self):
        first,second=core_observation(1),core_observation(2)
        second['heroes'][0]['hero']='hero_'+'d'*12
        result=project(rows(first,second))
        self.assertEqual(result['state'],'refused')
        self.assertEqual(result['local_core']['status'],'refused')
        self.assertIsNone(result['local_core']['health']['value'])

    def test_local_alias_changes_in_unbound_observation_still_refuse_stream(self):
        for which in (0,1):
            records_obs=[core_observation(1),core_observation(2)]
            records_obs[which]['talents'].update(status='refused',value=None)
            records_obs[which]['heroes'][0]['hero']='hero_'+'e'*12
            result=project(rows(*records_obs))
            self.assertEqual(result['state'],'refused')
            self.assertEqual(result['local_core']['status'],'refused')

    def test_refused_stream_has_no_core(self):
        records=rows(core_observation())
        records[0]['outcome']='refused'
        result=project(records)
        self.assertEqual(result['local_core']['status'],'refused')
        self.assertIsNone(result['local_core']['health']['value'])

    def test_html_exposes_core_through_history_only(self):
        obs=core_observation()
        records=rows(obs)
        # Characterize the existing diagnosis; HTML gets values only from history.
        from cerveau.session_diagnosis import _diagnose
        diagnosis=_diagnose(records,dict(state='complete',records=len(records)))
        html=session_html.render(dict(history=project(records),diagnosis=diagnosis))
        self.assertIn('Santé locale : 125.5 / 200',html)
        self.assertIn('Ressource locale : 0 / 100',html)
        self.assertNotIn('limité aux niveaux publics',html)
        self.assertIn("default-src 'none'",html)
