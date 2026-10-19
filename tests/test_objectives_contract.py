"""Synthetic boundary/integration tests, NOT a real objective recipe."""
import contextlib
import copy
import time
import unittest
from unittest.mock import patch

from test_current_visibility import VisibilityMemory
from test_objectives import ObjectiveMemory
from hotstate.acquisition import issue
from hotstate.native import NativeReader
from hotstate.objectives import VolskayaObjective
from cerveau.state import snapshot
from cerveau.runner import tactical_key


class ObjectiveContractTests(unittest.TestCase):
    def raw(self):
        m = VisibilityMemory()
        objective = ObjectiveMemory()
        objective.point(1, active=1, owner=1, state=0, progress=(22.5, 0))
        sample = objective.reader()._sample()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch('hotstate.objectives.VALIDATED_MAPS', ('Volskaya',)))
            stack.enter_context(patch('hotstate.positions.PROFILE', m.position_profile))
            stack.enter_context(patch('hotstate.match.PROFILE', m.match_profile))
            # Only candidate field bytes are mocked here. The independent
            # ObjectiveMemory tests exercise the actual VM/timer/unit reader.
            stack.enter_context(patch.object(VolskayaObjective, '_sample', return_value=sample))
            raw = NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)
        raw['meta'].update(m.context['meta'], source='live')
        return m, raw

    def normalize(self, raw):
        with patch('hotstate.objectives.VALIDATED_MAPS', ('Volskaya',)):
            return snapshot(raw)

    def test_real_optional_call_and_whitelist_omit_private_and_enemy_hero_data(self):
        m, raw = self.raw()
        self.assertIn('objective', raw)
        raw['objective']['untrusted_extra'] = {'enemy_x':123}
        issue(raw['objective'], time.monotonic())
        clean = self.normalize(raw)
        self.assertEqual(clean['objective']['point']['victory_percent'], [50,0])
        for key in ('points', 'native_session', 'match_id', 'untrusted_extra'):
            self.assertNotIn(key, clean['objective'])
        for hero in clean['heroes']:
            if hero['team'] != clean['ally_team']:
                for key in ('health','resource','x','y','cooldowns'):
                    self.assertNotIn(key, hero)

    def test_context_receipt_freshness_source_and_malformed_values_fail_closed(self):
        for change in ('receipt','age','future','tamper','map','match','source','diagnostic',
                       'window','boolowner','progress','team','protector','overtime'):
            _,raw = self.raw(); p = raw['objective']
            if change=='receipt': p.pop('acquisition')
            elif change=='age': issue(p,time.monotonic()-2)
            elif change=='future': issue(p,time.monotonic()+2)
            elif change=='tamper': p['point']['owner']=1
            elif change=='map': raw['meta']['map_id']='DragonShire'
            elif change=='match': raw['meta']['match_id']='f'*64
            elif change=='source': raw['meta']['source']='dump'
            else:
                if change=='diagnostic': p['status']='diagnostic_unreleased'
                elif change=='window': p['read_window_s']=0.126
                elif change=='boolowner': p['point']['owner']=True
                elif change=='progress': p['point']['victory_percent']=[-1,0]
                elif change=='team': p['team']=0
                elif change=='protector': p['protector']['state']='active'
                else: p['point']['overtime_remaining_s']=2
                issue(p,time.monotonic())
            with self.subTest(change=change):
                self.assertNotIn('objective',self.normalize(raw))

    def test_recycled_unknown_is_not_destroyed_zero_and_does_not_poison_current_point(self):
        _,raw=self.raw(); p=raw['objective']
        p['protector']={'state':'unknown','team':None,'health_percent':None,'remaining_s':None,
                        'reason':'reference_protecteur_recyclee'}
        issue(p,time.monotonic())
        clean=self.normalize(raw)['objective']
        self.assertEqual(clean['phase'],'active')
        self.assertEqual(clean['protector'],{'state':'unknown','team':None,'health_percent':None,'remaining_s':None})
        self.assertEqual(clean['point']['owner'],0)

    def test_only_validated_map_publishes_and_public_progress_is_not_a_tick_freshness_key(self):
        _,raw=self.raw()
        from hotstate.objectives import VALIDATED_MAPS
        self.assertEqual(VALIDATED_MAPS,('Volskaya',))
        self.assertIn('objective',snapshot(raw))
        wrong=copy.deepcopy(raw);wrong['meta']['map_id']='DragonShire'
        self.assertNotIn('objective',snapshot(wrong))
        clean=self.normalize(raw); before=tactical_key(clean)
        changed=copy.deepcopy(clean)
        changed['objective']['t']+=0.0625
        changed['objective']['point']['victory_percent'][0]+=1
        self.assertEqual(before,tactical_key(changed))
        for change in ('owner','state','phase','unknown'):
            changed=copy.deepcopy(clean)
            if change=='owner':changed['objective']['point']['owner']=1
            elif change=='state':changed['objective']['point']['state']='contested'
            elif change=='phase':changed['objective']['phase']='waiting'
            else:changed.pop('objective')
            self.assertNotEqual(before,tactical_key(changed))


if __name__=='__main__':
    unittest.main()
