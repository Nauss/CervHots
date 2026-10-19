"""Hermetic Dragon boundary/consumer tests; live qualification is separate."""
import copy
import time
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from test_dragon import DragonMemory
from test_current_visibility import VisibilityMemory
from hotstate.acquisition import issue
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.dragon import DragonObjective
from cerveau.dragon import project_dragon, dragon_key
from cerveau.state import snapshot
from cerveau.runner import tactical_key


def public_fixture():
    p = DragonMemory().sample()
    for row in p['shrines']:
        row['capture_current_visible'] = True if row['state'] != 'disabled' else None
    return p


def packet():
    p = public_fixture()
    p.update(status='validated', map_id='DragonShire', match_id='a'*64, local_id=0, team=0,
             local_hero='stitches', mission_t_s=123.5, read_window_s=0.01)
    issue(p, time.monotonic())
    local = {'id':0, 'team':0, 'hero':'stitches'}
    raw = {'meta':{'source':'live', 'native_build':98348, 'map_id':'DragonShire', 'match_id':'a'*64,
                   'context_source':'initdata_native_fields', 't_s':123.5}, 'objective':p}
    return raw, local


class DragonContractTests(unittest.TestCase):
    def project(self, raw, local):
        with patch('hotstate.dragon.VALIDATED_MAPS', ('DragonShire',)):
            return project_dragon(raw, local, 0)

    def test_gate_closed_and_diagnostic_not_a_receipt(self):
        raw, local = packet()
        with patch('hotstate.dragon.VALIDATED_MAPS', ()):
            self.assertIsNone(project_dragon(raw,local,0))
        raw['objective']['status'] = 'diagnostic_unreleased'
        issue(raw['objective'],time.monotonic())
        self.assertIsNone(self.project(raw,local))

    def test_release_scope_is_objective_dragon_only_not_hero_visibility_or_positions(self):
        from hotstate.dragon import VALIDATED_MAPS
        from hotstate.positions import VALIDATED_MAPS as positions
        from hotstate.visibility import VALIDATED_MAPS as visibility
        from hotstate.battlefield import VALIDATED_MAPS as battlefield
        self.assertEqual(VALIDATED_MAPS, ('DragonShire',))
        self.assertEqual(positions, ('Volskaya',))
        self.assertEqual(visibility, ('Volskaya',))
        self.assertEqual(battlefield, ('Volskaya',))

    def test_typed_projection_discards_private_extras_and_counters(self):
        raw, local = packet(); p = raw['objective']; p['pointer'] = 'PRIVATE'
        p['shrines'][0].update(name='PRIVATE', tag='PRIVATE', capture_counter=64, enemy_cooldowns='PRIVATE')
        p['dragon'].update(pilot='PRIVATE', health_percent='PRIVATE')
        issue(p,time.monotonic()); s = self.project(raw,local)
        self.assertIsNotNone(s); self.assertNotIn('PRIVATE',str(s)); self.assertNotIn('capture_counter',str(s))
        self.assertNotIn('acquisition',s); self.assertNotIn('match_id',s)

    def test_receipt_freshness_context_and_typed_values_fail_closed(self):
        changes = ('receipt','future','stale','map','match','hero','source','build','bool_window','nan',
                   'local','team','paused','timer','bool_owner','duplicate','dragon','statue')
        for change in changes:
            with self.subTest(change=change):
                raw, local = packet(); p = raw['objective']
                if change == 'receipt': p.pop('acquisition',None)
                elif change == 'future': p['mission_t_s'] += 1
                elif change == 'stale': p['mission_t_s'] -= 2
                elif change == 'map': p['map_id'] = 'Volskaya'
                elif change == 'match': p['match_id'] = 'b'*64
                elif change == 'hero': p['local_hero'] = 'ragnaros'
                elif change == 'source': raw['meta']['source'] = 'dump'
                elif change == 'build': raw['meta']['native_build'] = 98349
                elif change == 'bool_window': p['read_window_s'] = True
                elif change == 'local': p['local_id'] = 1
                elif change == 'team': p['team'] = 1
                elif change == 'paused': p['respawn']['paused'] = 1
                elif change == 'timer': p['respawn']['remaining_s'] = -1
                elif change == 'bool_owner': p['shrines'][0]['owner'] = True
                elif change == 'duplicate': p['shrines'][1]['id'] = 'sun'
                elif change == 'dragon': p['dragon']['state'] = 'active'
                elif change == 'statue': p['statue']['state'] = 'capturable'
                else: p['mission_t_s'] = float('nan')
                if change not in ('receipt','nan'): issue(p,time.monotonic())
                self.assertIsNone(self.project(raw,local))

    def test_channel_requires_current_sight_not_owner_or_known_flag(self):
        raw, local = packet(); p = raw['objective']
        p['shrines'] = [{'id':name,'owner':0,'state':'captured','contested':False,
                         'capture_current_visible':True} for name in ('sun','moon')]
        p['statue'] = {'state':'capturable','team':0,'channeling':True,'name':'PRIVATE'}
        for visible in (None,False,'known',1,True):
            with self.subTest(visible=visible):
                p['statue']['current_visible'] = visible; issue(p,time.monotonic())
                result = self.project(raw,local)
                self.assertIsNotNone(result)
                self.assertIs(result['statue']['channeling'],True if visible is True else None)

    def test_unknown_not_neutral_and_countdown_ticks_not_tactical_changes(self):
        raw, local = packet(); p = raw['objective']
        p['shrines'][0].update(state='unknown',owner=None,contested=None,capture_current_visible=None)
        p['respawn']['remaining_s'] = 130; issue(p,time.monotonic()); first = self.project(raw,local)
        self.assertIsNone(first['shrines'][0]['owner'])
        p['respawn']['remaining_s'] = 129; issue(p,time.monotonic()); second = self.project(raw,local)
        self.assertEqual(dragon_key(first),dragon_key(second))
        p['respawn']['paused'] = True; issue(p,time.monotonic()); third = self.project(raw,local)
        self.assertNotEqual(dragon_key(first),dragon_key(third))
        p['shrines'][0]['owner'] = 'neutral'
        p['shrines'][0].pop('capture_current_visible'); issue(p,time.monotonic())
        self.assertIsNone(self.project(raw,local))

    def test_real_native_optional_dispatch_normalizer_and_key(self):
        m = VisibilityMemory(); m.context['meta']['map_id'] = 'DragonShire'
        sample = public_fixture()
        sample.update(map_id='DragonShire', match_id=m.context['meta']['match_id'], local_id=5, team=1,
                      local_hero='ragnaros', mission_t_s=123.5, read_window_s=0.01,
                      native_session='SYNTHETIC', _acquired=time.monotonic())
        with ExitStack() as stack:
            stack.enter_context(patch('hotstate.dragon.VALIDATED_MAPS', ('DragonShire',)))
            stack.enter_context(patch('hotstate.positions.PROFILE',m.position_profile))
            stack.enter_context(patch('hotstate.match.PROFILE',m.match_profile))
            stack.enter_context(patch.object(DragonObjective,'_observe',return_value=sample))
            raw = NativeReader(m,profile=m.profile).read_state(m.context,hero_ids=m.hero_ids)
            self.assertIn('objective',raw)
            raw['meta'].update(m.context['meta'],source='live')
            clean = snapshot(raw)
            self.assertEqual(clean['objective']['map_id'],'DragonShire')
            key = tactical_key(clean)
            changed = copy.deepcopy(clean); changed['objective']['shrines'][0]['owner'] = 0
            self.assertNotEqual(key,tactical_key(changed))
            for h in clean['heroes'][:5]:
                self.assertTrue({'x','y','health','resource','cooldowns','talents'}.isdisjoint(h))

    def test_hidden_statue_marker_is_not_even_read(self):
        m = DragonMemory(); m.capture(1,owner=11); m.capture(2,owner=11)
        m.pack(m.unit(4)+0x44,'B',11); r = m.reader()
        rows = [{'owner':0,'state':'captured'},{'owner':0,'state':'captured'}]
        with patch.object(r.units,'_unit_type',side_effect=lambda n,u:m.types[u]), \
             patch('hotstate.positions.AlliedPositions._verify'), \
             patch('hotstate.visibility.CurrentVisibility._verify'), \
             patch.object(r.mechanics,'_duration',side_effect=AssertionError('hidden marker read')):
            for visible in (False,None):
                with patch('hotstate.visibility.CurrentVisibility._current',return_value=visible):
                    s = r._statue(r.native,'shrines',rows,local_id=0)
                    self.assertIsNone(s['channeling']); self.assertIs(s['current_visible'],visible)


if __name__ == '__main__':
    unittest.main()
