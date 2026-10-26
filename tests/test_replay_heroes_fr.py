"""Exact documentary frFR labels; SYNTHETIC players, no current build claim."""
import unittest
from cerveau.replay import project


class FrenchReplayHeroTests(unittest.TestCase):
    def test_six_primary_localized_labels_reach_projection(self):
        for label, hero in (('Anub’arak', 'Anubarak'), ('Malthaël', 'Malthael'),
                            ('Balafré', 'Stitches'), ('Bourbie', 'Murky'),
                            ('Tyraël', 'Tyrael'), ('Impérius', 'Imperius')):
            with self.subTest(label=label):
                raw = {'players': [{'name': 'SYNTHETIC_PRIVATE', 'hero': label, 'team': 0}]}
                result = project(raw, at=0, team=0)
                self.assertEqual(result['composition']['allies'], [hero])
                self.assertEqual(result['heroes'], [{'hero': hero, 'team': 0}])
                self.assertNotIn('SYNTHETIC_PRIVATE', str(result))

    def test_fixture_provenance_exact_pointer_join(self):
        import json, hashlib
        from cerveau.replay import ROOT, _REPLAY_FR
        source = _REPLAY_FR['source']
        self.assertEqual(source['commit'], '2a2207d08bdb2bac8038e8bc0e10c13a952ee043')
        self.assertEqual((source['locale'], source['license']), ('frfr', 'MIT'))
        payload = (ROOT / source['fixture']).read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), source['fixture_sha256'])
        excerpt = json.loads(payload)
        self.assertEqual(len(_REPLAY_FR['aliases']), 6)
        for row in _REPLAY_FR['aliases']:
            hero = row['hero']
            self.assertEqual(excerpt['gamestrings']['unit']['name'][hero], row['alias'])
            self.assertEqual(excerpt['heroes'][hero]['hyperlinkId'], hero)
            self.assertEqual(excerpt['heroes'][hero]['unitId'], 'Hero' + hero)
            self.assertEqual(row['alias_pointer'], '/gamestrings/unit/name/' + hero)
            self.assertEqual(row['identity_pointer'], '/' + hero + '/hyperlinkId')

    def test_french_collisions_all_orders_remain_unknown(self):
        import itertools
        from cerveau.replay import _hero_vocabulary, _HERO_IDS, _REPLAY_FR
        for row in _REPLAY_FR['aliases']:
            conflict = {'alias': row['alias'].upper(), 'hero': 'Jaina'}
            for rows in itertools.permutations([row, row, conflict]):
                vocabulary = _hero_vocabulary(_HERO_IDS, rows)
                self.assertNotIn(row['alias'].casefold(), vocabulary)
            for rows in ([row, {'alias': 'JAINA', 'hero': row['hero']}],
                         [{'alias': 'jaina', 'hero': row['hero']}, row]):
                self.assertNotIn('jaina', _hero_vocabulary(_HERO_IDS, rows))

    def test_unknown_near_matches_and_accounts_do_not_supply_heroes(self):
        import unicodedata
        from cerveau.replay import _REPLAY_FR, _known, HEROES
        for row in _REPLAY_FR['aliases']:
            label = row['alias']
            for unknown in (' ' + label, label + ' ', 'Hero' + label,
                            unicodedata.normalize('NFD', label), label.replace('’', "'")):
                if unknown == label:
                    continue
                self.assertIsNone(_known(unknown, HEROES))
            raw = {'players': [{'name': label, 'hero': 'SYNTHETIC_UNKNOWN', 'team': 0}]}
            self.assertEqual(project(raw, at=0, team=0)['heroes'], [])
