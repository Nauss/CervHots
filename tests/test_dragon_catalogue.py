"""Catalogue integrity tests; no synthetic map coordinates become evidence."""
import copy
import unittest
from unittest.mock import patch
from hotstate.dragon_catalogue import qualified_layout, validate_layout
from hotstate.native import NativeUnavailable


class DragonCatalogueTests(unittest.TestCase):
    def test_initial_native_catalogue_qualification_never_grants_permission(self):
        layout = qualified_layout()
        self.assertEqual(len(layout['structures']),90)
        self.assertEqual(layout['status'],'QUALIFIED_INITIAL_NATIVE_AND_SAME_MATCH_TRACKER')
        from hotstate import dragon_battlefield
        with patch.object(dragon_battlefield,'VALIDATED_MAPS',()):
            qualified_layout()
            self.assertEqual(dragon_battlefield.VALIDATED_MAPS,())

    def test_wrong_map_build_count_type_duplicate_and_boolean_refuse(self):
        for change in ('map','build','count','id','point','type','kind','team','bool','bounds','ruins'):
            layout = copy.deepcopy(qualified_layout()); row = layout['structures'][0]
            if change == 'map':layout['map'] = 'Volskaya'
            elif change == 'build':layout['build'] += 1
            elif change == 'count':layout['structures'].pop()
            elif change == 'id':row['id'] = layout['structures'][1]['id']
            elif change == 'point':row.update(x_fixed=layout['structures'][1]['x_fixed'],y_fixed=layout['structures'][1]['y_fixed'])
            elif change == 'type':row['unit_type'] = 'MercLanerSiegeGiant'
            elif change == 'kind':row['kind'] = 'keep'
            elif change == 'team':row['team'] = True
            elif change == 'bool':row['x_fixed'] = True
            elif change == 'bounds':row['x_fixed'] = -1
            else:row.update(unit_type='TownCannonTowerDead',kind='tower_ruins')
            with self.subTest(change=change), self.assertRaises(NativeUnavailable):
                validate_layout(layout)

    def test_legal_coordinate_tampering_still_fails_canonical_digest(self):
        layout = copy.deepcopy(qualified_layout())
        layout['structures'][0]['x_fixed'] += 1
        with patch('hotstate.dragon_catalogue.STRUCTURE_LAYOUT',layout), self.assertRaises(NativeUnavailable):
            qualified_layout()

    def test_wrong_header_types_and_permuted_stable_ids_refuse(self):
        for change in ('swap_ids','bool_schema_version','float_build'):
            layout = copy.deepcopy(qualified_layout())
            if change == 'swap_ids':
                a,b = layout['structures'][:2]
                a['id'],b['id'] = b['id'],a['id']
            elif change == 'bool_schema_version':
                layout['schema_version'] = True
            else:
                layout['build'] = float(layout['build'])
            with self.subTest(change=change), patch('hotstate.dragon_catalogue.STRUCTURE_LAYOUT',layout):
                with self.assertRaises(NativeUnavailable):
                    qualified_layout()


if __name__ == '__main__':
    unittest.main()
