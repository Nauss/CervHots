"""Hermetic receipt/normalizer/key tests; no player or live recipe evidence."""
import copy
import time
import unittest
from unittest.mock import patch
from test_current_visibility import VisibilityMemory
from hotstate.native import NativeReader
from hotstate.acquisition import issue
from hotstate.battlefield import STRUCTURE_LAYOUT
from cerveau.state import snapshot
from cerveau.runner import tactical_key

class BattlefieldContractTests(unittest.TestCase):
    def raw(self):
        m=VisibilityMemory()
        raw=NativeReader(m,profile=m.profile).read_state(m.context,hero_ids=m.hero_ids)
        raw['meta'].update(m.context['meta'],source='live')
        common={'map_id':'Volskaya','status':'validated','match_id':raw['meta']['match_id'],
                'local_id':raw['local_player']['id'],'team':raw['local_player']['team'],
                'local_hero':raw['local_player']['hero'],'native_session':raw['perspective']['native_session'],
                'mission_t_s':raw['meta']['t_s'],'read_window_s':0.01}
        camps=[{'id':i,'kind':('turret','turret','siege_troopers','siege_troopers','support')[i-1],
                'state':'unknown','owner':None,'current_visible':None,'cycle':None,'respawn_s':None} for i in range(1,6)]
        structures=[{'id':s['id'],'kind':s['kind'],'state':'unknown','owner':None,'current_visible':None,'generation':None}
                    for s in STRUCTURE_LAYOUT['structures']]
        raw['battlefield']={section:issue(dict(common,section=section,**{section:entries}),time.monotonic())
                            for section,entries in (('camps',camps),('structures',structures))}
        return raw

    def clean(self,raw):
        with patch('hotstate.battlefield.VALIDATED_MAPS',('Volskaya',)):return snapshot(raw)

    def test_boundary_uses_full_catalogue_and_strips_raw_positions_vitals_tags(self):
        raw=self.raw();p=raw['battlefield']['structures'];p['structures'][0].update(x=123,health=999,tag=45)
        p['untrusted_private']={'pointer':12345};issue(p,time.monotonic())
        clean=self.clean(raw)
        self.assertEqual(len(clean['battlefield']['structures']['entries']),90)
        self.assertEqual(len(clean['battlefield']['camps']['entries']),5)
        text=str(clean['battlefield'])
        for word in ("'health':",'pointer','untrusted_private','native_session','tag','x_fixed'):
            self.assertNotIn(word,text)
        self.assertNotIn('battlefield',snapshot(raw))

    def test_corruption_freshness_mismatch_fog_and_identity_refuse(self):
        for change in ('receipt','stale','future','tamper','source','match','map','session','diagnostic','window','fogowner','fogstate','boolid','badid','count','duplicate'):
            raw=self.raw();p=raw['battlefield']['camps'];row=p['camps'][0]
            if change=='receipt':p.pop('acquisition')
            elif change=='stale':issue(p,time.monotonic()-2)
            elif change=='future':issue(p,time.monotonic()+2)
            elif change=='tamper':p['team']=1-p['team']
            elif change=='source':raw['meta']['source']='replay'
            elif change=='match':raw['meta']['match_id']='f'*64
            elif change=='map':raw['meta']['map_id']='DragonShire'
            else:
                if change=='session':p['native_session']='f'*64
                elif change=='diagnostic':p['status']='diagnostic_unreleased'
                elif change=='window':p['read_window_s']=0.126
                elif change=='fogowner':row['owner']=1
                elif change=='fogstate':row.update(state='fighting',owner='neutral')
                elif change=='boolid':row['id']=True
                elif change=='badid':row['id']={}
                elif change=='count':p['camps'].pop()
                else:p['camps'][1]=copy.deepcopy(row)
                issue(p,time.monotonic())
            with self.subTest(change=change):
                if change=='source':
                    from cerveau.battlefield import project_battlefield
                    with patch('hotstate.battlefield.VALIDATED_MAPS',('Volskaya',)):
                        self.assertIsNone(project_battlefield(raw,raw['local_player'],raw['local_player']['team']))
                else:self.assertNotIn('battlefield',self.clean(raw))

    def test_tactical_key_tracks_transitions_not_sampling_or_timer_ticks(self):
        raw=self.raw();p=raw['battlefield']['camps'];p['camps'][0].update(state='captured',owner=0,current_visible=True,respawn_s=100,cycle='a'*64)
        issue(p,time.monotonic());clean=self.clean(raw);before=tactical_key(clean)
        changed=copy.deepcopy(clean);changed['battlefield']['camps']['t']+=0.5
        changed['battlefield']['camps']['entries'][0]['respawn_s']=99
        self.assertEqual(before,tactical_key(changed))
        changed['battlefield']['camps']['entries'][0]['state']='available'
        self.assertNotEqual(before,tactical_key(changed))

    def test_structure_health_requires_visible_alive_and_finite_percentage(self):
        for visible,state,health in ((None,'unknown',10),(False,'unknown',10),(True,'alive',True),(True,'alive',float('inf')),(True,'alive',101),(True,'destroyed',0)):
            raw=self.raw();p=raw['battlefield']['structures'];r=p['structures'][0]
            r.update(current_visible=visible,state=state,health_percent=health)
            # Nonfinite input cannot even obtain an acquisition receipt.
            if health==float('inf'):
                with self.assertRaises(ValueError):issue(p,time.monotonic())
                continue
            issue(p,time.monotonic())
            self.assertNotIn('battlefield',self.clean(raw))

    def test_precise_respawn_timer_survives_boundary_without_private_fields(self):
        raw=self.raw();p=raw['battlefield']['camps'];row=p['camps'][0]
        row.update(state='captured',owner=0,current_visible=True,respawn_s=0,
                   respawn_timer={'remaining_s':0.0625,'paused':True,'pointer':1234})
        issue(p,time.monotonic())
        clean=self.clean(raw)['battlefield']['camps']['entries'][0]
        self.assertEqual(clean.get('respawn_timer'),{'remaining_s':0.0625,'paused':True})

    def test_precise_respawn_rejects_invalid_hidden_and_stale_metadata(self):
        for change in ('hidden','unknown','available','fraction','paused','negative','range','boolean','stale','missing'):
            raw=self.raw();p=raw['battlefield']['camps'];row=p['camps'][0]
            row.update(state='captured',owner=0,current_visible=True,respawn_s=1,
                       respawn_timer={'remaining_s':1.0625,'paused':False})
            if change=='hidden':row['current_visible']=False
            elif change=='unknown':row.update(state='unknown',owner=None,respawn_s=None)
            elif change=='available':row.update(state='available',owner='neutral')
            elif change=='fraction':row['respawn_s']=2
            elif change=='paused':row['respawn_timer']['paused']=0
            elif change=='negative':row['respawn_timer']['remaining_s']=-0.0625
            elif change=='range':row['respawn_timer']['remaining_s']=601
            elif change=='boolean':row['respawn_timer']['remaining_s']=True
            elif change=='missing':row['respawn_timer'].pop('remaining_s')
            issue(p,time.monotonic()-2 if change=='stale' else time.monotonic())
            with self.subTest(change=change):
                self.assertNotIn('battlefield',self.clean(raw))

    def test_tactical_key_tracks_respawn_pause_not_fractional_ticks(self):
        raw=self.raw();p=raw['battlefield']['camps'];row=p['camps'][0]
        row.update(state='captured',owner=0,current_visible=True,respawn_s=1,
                   respawn_timer={'remaining_s':1.0625,'paused':False})
        issue(p,time.monotonic());clean=self.clean(raw);before=tactical_key(clean)
        changed=copy.deepcopy(clean)
        timer=changed['battlefield']['camps']['entries'][0]['respawn_timer']
        timer['remaining_s']=1
        self.assertEqual(before,tactical_key(changed))
        timer['paused']=True
        self.assertNotEqual(before,tactical_key(changed))


if __name__=='__main__':unittest.main()
