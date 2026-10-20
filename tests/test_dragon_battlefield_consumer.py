"""Dragon candidate consumer tests. Literal fixtures are not live evidence."""
import copy
import time
import unittest
from unittest.mock import patch
from hotstate.native import NativeUnavailable
from hotstate.acquisition import issue
from hotstate.dragon_battlefield import DragonBattlefield, qualified_layout
import test_battlefield_contract as contract_tests
from cerveau.state import snapshot
from cerveau.runner import tactical_key


class DragonBattlefieldConsumerTests(unittest.TestCase):
    def raw(self):
        raw = contract_tests.BattlefieldContractTests().raw()
        raw['meta']['map_id'] = 'DragonShire'
        layout = qualified_layout()
        for section, packet in raw['battlefield'].items():
            packet['map_id'] = 'DragonShire'
            if section == 'camps':
                for row, kind in zip(packet['camps'], DragonBattlefield.CAMP_KINDS):
                    row['kind'] = kind
            else:
                packet['structures'] = [{'id':s['id'],'kind':s['kind'],'state':'unknown','owner':None,
                    'generation':None,'health_percent':None,'current_visible':None} for s in layout['structures']]
            issue(packet, time.monotonic())
        return raw

    def test_explicitly_closed_scope_refuses_even_with_inprocess_receipts(self):
        with patch('hotstate.dragon_battlefield.VALIDATED_MAPS',()):
            self.assertNotIn('battlefield', snapshot(self.raw()))
            with self.assertRaisesRegex(NativeUnavailable,'recette_champ_bataille_dragon_absente'):
                DragonBattlefield(None).read({'map_id':'DragonShire'})

    def test_default_branch_scope_is_dragon_only_not_forged_context_permission(self):
        from hotstate.dragon_battlefield import VALIDATED_MAPS
        self.assertEqual(VALIDATED_MAPS,('DragonShire',))
        with self.assertRaises(NativeUnavailable):
            DragonBattlefield(None).read({'map_id':'DragonShire'})

    def test_qualified_map_contract_uses_dragon_types_ids_and_key(self):
        with patch('hotstate.dragon_battlefield.VALIDATED_MAPS', ('DragonShire',)):
            clean = snapshot(self.raw())
            camps = clean['battlefield']['camps']['entries']
            structures = clean['battlefield']['structures']['entries']
            self.assertEqual([c['kind'] for c in camps], list(DragonBattlefield.CAMP_KINDS))
            self.assertEqual(len(structures),90)
            self.assertEqual(structures[0]['id'],'dragon-001')
            before = tactical_key(clean)
            changed = copy.deepcopy(clean)
            changed['battlefield']['camps']['entries'][0].update(state='available', current_visible=True, owner='neutral')
            self.assertNotEqual(before, tactical_key(changed))
            self.assertNotIn('x_fixed',str(clean['battlefield']))

    def test_wrong_types_fog_bad_generation_and_forged_receipts_refuse(self):
        for change in ('volskaya','id','fog','generation','receipt','source','session','stale'):
            raw = self.raw(); packet = raw['battlefield']['structures']
            if change == 'volskaya':raw['battlefield']['camps']['camps'][0]['kind'] = 'turret'
            elif change == 'id':packet['structures'][0]['id'] = 'not-dragon'
            elif change == 'fog':packet['structures'][0].update(owner=0,current_visible=False)
            elif change == 'generation':packet['structures'][0]['generation'] = True
            elif change == 'source':raw['meta']['source'] = 'dump'
            elif change == 'session':packet['native_session'] = 'f'*64
            if change not in ('receipt','volskaya'):
                issue(packet,time.monotonic()-2 if change == 'stale' else time.monotonic())
            if change == 'volskaya':issue(raw['battlefield']['camps'],time.monotonic())
            if change == 'receipt':packet.pop('acquisition')
            with self.subTest(change=change), patch('hotstate.dragon_battlefield.VALIDATED_MAPS', ('DragonShire',)):
                self.assertNotIn('battlefield',snapshot(raw))

    def test_candidate_observe_rechecks_consumed_fields_and_context(self):
        from contextlib import ExitStack
        from test_current_visibility import VisibilityMemory
        from hotstate.native import NativeReader
        from hotstate.positions import AlliedPositions
        from hotstate.match import ActiveMatch
        from hotstate.dragon import DragonObjective
        for mutation in ('none','field','context','identity'):
            memory = VisibilityMemory()
            context = NativeReader(memory,profile=memory.profile).read_state(memory.context,hero_ids=memory.hero_ids)
            context['meta'].update(memory.context['meta'],map_id='DragonShire')
            local = context['local_player']
            reader = DragonBattlefield(NativeReader(memory,profile=memory.profile))
            memory.pack(0xB00000,'I',7)
            def census(n, **options):
                n.value(0xB00000)
                return {'structures':[], 'unresolved_slots':[]}
            def timers(n, camps):
                if mutation == 'field':memory.pack(0xB00000,'I',8)
                if mutation == 'context':context['meta']['match_id'] = 'f'*64
            identity = (local['id'],local['team'],local['hero'],context['players'],context['perspective']['native_session'])
            if mutation == 'identity':identity = (local['id'],1-local['team'],*identity[2:])
            anchors = iter(reader.profile['camp_anchors_fixed'])
            with ExitStack() as stack:
                stack.enter_context(patch.object(memory,'positions_clock',lambda:100.0,create=True))
                stack.enter_context(patch.object(reader,'_verify'))
                stack.enter_context(patch.object(DragonObjective,'_verify'))
                stack.enter_context(patch.object(ActiveMatch,'observe',return_value={'match_id':context['meta']['match_id']}))
                stack.enter_context(patch.object(AlliedPositions,'_identity',return_value=identity))
                stack.enter_context(patch('hotstate.visibility.CurrentVisibility._verify'))
                stack.enter_context(patch.object(reader,'_camps',return_value=[{'beacon_tag':i} for i in range(5)]))
                stack.enter_context(patch.object(reader,'_resolve',return_value=0x900000))
                stack.enter_context(patch.object(AlliedPositions,'_xy',side_effect=lambda *a:tuple(v/4096 for v in next(anchors))))
                stack.enter_context(patch('hotstate.dragon_battlefield.camp_details'))
                stack.enter_context(patch.object(reader,'_census',side_effect=census))
                stack.enter_context(patch('hotstate.dragon_battlefield.structure_details',return_value=[]))
                stack.enter_context(patch.object(reader,'_camp_timers',side_effect=timers))
                with self.subTest(mutation=mutation):
                    if mutation == 'none':
                        result = reader._observe(context,hero_ids=memory.hero_ids)
                        self.assertEqual(result['local_id'],local['id'])
                    else:
                        with self.assertRaises(NativeUnavailable):
                            reader._observe(context,hero_ids=memory.hero_ids)


if __name__ == '__main__':
    unittest.main()
