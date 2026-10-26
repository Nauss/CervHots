"""SYNTHETIC replay labels, never player names as hero identity."""
import unittest
import hashlib
import json
from cerveau.replay import project, _hero_vocabulary, _known, HEROES, ROOT


class ReplayHeroAliasTests(unittest.TestCase):
    def test_alias_collisions_fail_closed_independently_of_order(self):
        from cerveau import replay as module
        self.assertTrue(callable(getattr(module, '_hero_vocabulary', None)),
                        'collision-checked replay vocabulary missing')
        base = {'Lucio': 'lucio', 'Jaina': 'jaina'}
        rows = [{'alias': 'Lúcio', 'hero': 'Lucio'}, {'alias': 'LÚCIO', 'hero': 'Jaina'}]
        for order in (rows, rows[::-1]):
            vocabulary = module._hero_vocabulary(base, order)
            self.assertNotIn('lúcio', vocabulary)
        vocabulary = module._hero_vocabulary(base, [{'alias': 'Jaina', 'hero': 'Lucio'}])
        self.assertNotIn('jaina', vocabulary)
        self.assertEqual(module._hero_vocabulary(base, rows[:1])['lúcio'], 'Lucio')
        self.assertEqual(base, {'Lucio': 'lucio', 'Jaina': 'jaina'})

    def test_pinned_exact_display_name_reaches_projection(self):
        raw = {'meta': {'duration_s': 60},
               'players': [{'name': 'SYNTHETIC_PRIVATE', 'team': 1, 'hero': 'Lúcio'}]}
        result = project(raw, at=10, team=0)
        self.assertEqual(result['composition']['enemies'], ['Lucio'])
        self.assertEqual(result['heroes'], [{'hero': 'Lucio', 'team': 1}])
        self.assertNotIn('SYNTHETIC_PRIVATE', str(result))

    def test_provenance_is_byte_pinned_and_alias_is_from_same_source_row(self):
        manifest = json.loads((ROOT / 'cerveau/replay_hero_aliases.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['source']['commit'], '2dcbbf65f81bc3ce85926a5f90b6d8b44d1e4027')
        payload = (ROOT / manifest['source']['fixture']).read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest['source']['sha256'])
        source = json.loads(payload)
        self.assertEqual(manifest['aliases'], [{'alias': source['name'], 'hero': source['cHeroId']}])
        self.assertEqual(source['shortName'], 'lucio')

    def test_native_catalog_is_not_extended(self):
        catalog = json.loads((ROOT / 'hotstate/hero_ids.json').read_text(encoding='utf-8'))
        self.assertNotIn('Lúcio', catalog)
        base = _hero_vocabulary(catalog, [])
        replay_labels = {'lúcio', 'anub’arak', 'malthaël', 'balafré', 'bourbie', 'tyraël', 'impérius'}
        self.assertEqual({k: v for k, v in HEROES.items() if k not in replay_labels}, base)
        self.assertNotIn('lúcio', base)

    def test_unknown_and_unproven_localizations_never_become_aliases(self):
        for label in ('Malthàël', 'Baláfré', 'Bourbié', 'Anub‘arak', 'Tyràël', 'Impèrius',
                      'HeroLucio', 'Lùcio', ' Lúcio', 'Lúcio ', 'Lu\u0301cio', 'Lúci',
                      'SYNTHETIC_UNKNOWN', None, {}, 1):
            with self.subTest(label=label):
                self.assertIsNone(_known(label, HEROES))
        self.assertEqual(_known('LÚCIO', HEROES), 'Lucio')

    def test_player_name_is_never_used_as_hero_source(self):
        raw = {'players': [{'name': 'Lúcio', 'hero': 'SYNTHETIC_UNKNOWN', 'team': 0}]}
        self.assertEqual(project(raw, at=0, team=0)['heroes'], [])

    def test_same_target_duplicates_are_not_collisions_and_bad_targets_refuse(self):
        base = {'Lucio': 'lucio', 'Jaina': 'jaina'}
        rows = [{'alias': 'Lúcio', 'hero': 'Lucio'}] * 2
        self.assertEqual(_hero_vocabulary(base, rows)['lúcio'], 'Lucio')
        for row in ({'alias': 'Lúcio', 'hero': 'Unknown'},
                    {'alias': 'Lúcio', 'hero': 'lucio'},
                    {'alias': None, 'hero': 'Lucio'}, {'alias': '', 'hero': 'Lucio'}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                _hero_vocabulary(base, [row])

    def test_local_and_past_events_use_same_alias_without_future_or_xy(self):
        from cerveau.replay_debrief import build
        raw = {'meta': {'duration_s': 60, 'protocol_shim': True},
               'players': [{'id': 0, 'name': 'SYNTHETIC_PRIVATE', 'hero': 'Lúcio', 'team': 0}],
               'local_player': {'id': 0, 'hero': 'Lucio', 'team': 0},
               'timeline': {'hero_events': [
                   {'t': 1, 'type': 'spawn', 'player': 'SYNTHETIC_PRIVATE', 'hero': 'Lúcio', 'pos': [9, 8]},
                   {'t': 20, 'type': 'death', 'player': 'SYNTHETIC_PRIVATE', 'hero': 'Lúcio'}],
                   'stat_events': [{'t': 2, 'name': 'LevelUp', 'player': 'SYNTHETIC_PRIVATE',
                                    'hero': 'Lúcio', 'data': {'Level': 2}}]}}
        report = build(raw, at=10, team=0, perspective='player-team', allow_protocol_shim=True)
        self.assertEqual(report['state']['heroes'], [{'hero': 'Lucio', 'team': 0, 'alive': True, 'level': 2}])
        self.assertTrue(all(e['t'] <= 10 for e in report['state']['events']))
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(report))
        self.assertNotIn('"pos"', json.dumps(report))
        self.assertNotIn('"positions"', json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'protocole_exact_indisponible'):
            build(raw, at=10, team=0, perspective='player-team')
