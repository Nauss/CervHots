"""SYNTHETIC identities only. Documentary labels never qualify native choices."""
import hashlib
import json
import unittest
from unittest.mock import patch

from cerveau import talent_labels as labels

from cerveau import native_history
from tests.test_native_history import observation, rows


class SelectedTalentReportTests(unittest.TestCase):
    def project(self, obs):
        return native_history._summarize(rows(obs), dict(state='complete', sha256='a'*64))

    def test_missing_in_memory_integrity_hash_stays_unknown_not_reconstructed(self):
        result = native_history._summarize(rows(observation()), dict(state='complete'))
        self.assertIsNone(result['talents']['selected_details'][0]['selection_provenance']['journal_sha256'])

    def test_selected_identity_gets_trace_and_documentary_only_source(self):
        result = self.project(observation())
        self.assertIn('selected_details', result['talents'])
        detail = result['talents']['selected_details'][0]
        self.assertEqual(detail['tier'], 1)
        self.assertEqual(detail['slot'], 2)
        self.assertEqual(detail['catalog_id'], 'BarbarianWarPaint')
        self.assertEqual(detail['selection_provenance'], dict(
            journal_sha256='a'*64, sequence=2, build=98348, hero='sonya',
            key='/talents/value/players/0/tiers/0', basis='recorded_not_authenticated'))
        resolution = detail['resolution']
        self.assertIsNone(resolution['label'])
        self.assertEqual(resolution['status'], 'unknown')
        self.assertEqual(resolution['reason'], 'source_build_and_slot_unproven')
        self.assertEqual(resolution['missing_provenance'],
                         ['exact_build', 'native_slot_mapping', 'french_label'])
        match = resolution['source_match']
        self.assertEqual(match['label'], 'War Paint')
        self.assertEqual(match['language'], 'en')
        self.assertEqual(match['basis'], 'documentary_only_not_chosen_label')
        self.assertEqual(match['provenance']['version'], '2dcbbf65f81bc3ce85926a5f90b6d8b44d1e4027')
        self.assertEqual(match['provenance']['key'], '/talents/1/1/name')
        self.assertEqual(match['provenance']['identity_key'], '/talents/1/1/talentTreeId')
        text = native_history.readable(result)
        for expected in ('War Paint', 'documentaire seulement', 'build exact non attesté',
                         'correspondance slot natif non attestée', 'français absent', 'a'*64):
            self.assertIn(expected, text)
        self.assertFalse(result['hud_validated'])
        self.assertFalse(result['current_permission'])

    def test_enrichment_reuses_sanitized_tiers_and_never_reexports_raw_keys(self):
        obs = observation()
        tier = obs['talents']['value']['players'][0]['tiers'][0]
        # These forged optional fields are stripped by the established validator.
        tier.update(label='PRIVATE_FORGED', label_provenance={'path': 'PRIVATE_FORGED'},
                    options=[{'name': 'PRIVATE_FORGED'}], extra='PRIVATE_FORGED')
        result = self.project(obs)
        self.assertNotIn('PRIVATE_FORGED', json.dumps(result))
        # Even hostile non-selected rows must never be passed to the resolver.
        tier.update(status='unselected', slot=None, catalog_id=None)
        with patch.object(labels, 'resolve_selected', side_effect=AssertionError('not selected')):
            result = self.project(obs)
        self.assertEqual(result['talents']['selected_details'], [])

    def test_trace_indexes_raw_record_without_using_catalog_order_for_matching(self):
        obs = observation()
        players = obs['talents']['value']['players']
        local = players.pop(0)
        players.append(local)
        local['tiers'].insert(0, dict(tier=2, required_level=4, status='unknown', slot=None, catalog_id=None))
        result = self.project(obs)
        self.assertEqual(result['talents']['selected_details'][0]['selection_provenance']['key'],
                         '/talents/value/players/4/tiers/1')

    def test_unknown_or_unselected_options_never_create_selected_details(self):
        for state in ('unknown', 'unselected'):
            obs = observation()
            tier = obs['talents']['value']['players'][0]['tiers'][0]
            tier.update(status=state, slot=None, catalog_id=None)
            tier['offered'] = [{'catalog_id': 'BarbarianWarPaint', 'slot': 2}]
            result = self.project(obs)
            self.assertEqual(result['talents']['selected_details'], [])
            self.assertNotIn('War Paint', native_history.readable(result))

    def test_stale_unknown_build_missing_slot_and_hostile_key_remain_rejected(self):
        mutations = [lambda o: o['talents'].update(age_s=1.01),
                     lambda o: o['talents']['value'].update(build=99999),
                     lambda o: o['talents']['value']['players'][0]['tiers'][0].pop('slot'),
                     lambda o: o['talents']['value']['players'][0]['tiers'][0].update(catalog_id='../../PRIVATE_HOSTILE'),
                     lambda o: o['talents']['value']['players'][0].update(hero='arthas')]
        for mutate in mutations:
            with self.subTest(case=mutations.index(mutate)):
                obs = observation()
                mutate(obs)
                with patch.object(labels, 'resolve_selected', side_effect=AssertionError('must reject before lookup')):
                    result = self.project(obs)
                self.assertEqual(result['talents']['status'], 'rejected')
                self.assertIsNone(result['talents']['selected_details'])
                self.assertNotIn('PRIVATE_HOSTILE', json.dumps(result))


class PureDocumentaryResolverTests(unittest.TestCase):
    def setUp(self):
        self.tier = observation()['talents']['value']['players'][0]['tiers'][0]
        self.data = labels.source_bytes()

    def resolve(self, tier=None, data=None, build=98348, hero='sonya'):
        return labels.resolve_selected(build, hero, self.tier if tier is None else tier,
                                       self.data if data is None else data)

    def test_fixed_file_is_exact_and_source_pointer_reproduces_label(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), labels.SOURCE_SHA256)
        match = self.resolve()['source_match']
        value = json.loads(self.data)
        for part in match['provenance']['key'].strip('/').split('/'):
            value = value[int(part)] if type(value) is list else value[part]
        self.assertEqual(value, match['label'])
        self.assertIsNone(self.resolve()['label'])

    def test_unknown_build_or_hero_never_inherits_sonya_source(self):
        for build in (None, True, '98348', 91368, 99999):
            self.assertEqual(self.resolve(build=build)['reason'], 'build_unknown')
            self.assertIsNone(self.resolve(build=build)['source_match'])
        for hero in ('arthas', 'SONYA', '../../sonya', None, []):
            self.assertEqual(self.resolve(hero=hero)['reason'], 'hero_source_unavailable')

    def test_unselected_unknown_and_missing_slot_do_not_match(self):
        for state in ('unknown', 'unselected', 'offered', None):
            self.assertEqual(self.resolve(dict(self.tier, status=state))['reason'], 'selection_unknown')
        for slot in (None, True, 0, 33, '2'):
            self.assertEqual(self.resolve(dict(self.tier, slot=slot))['reason'], 'selected_identity_invalid')

    def test_hostile_keys_never_drive_file_paths_or_leak_values(self):
        for key in ('../../PRIVATE', '<script>PRIVATE</script>', 'a'*129, '\nPRIVATE', None, []):
            result = self.resolve(dict(self.tier, catalog_id=key))
            self.assertEqual(result['reason'], 'selected_identity_invalid')
            self.assertNotIn('PRIVATE', json.dumps(result))

    def test_source_absent_changed_oversized_or_newer_is_not_silently_trusted(self):
        for data in (b'', self.data+b' ', b'x'*65537, b'{"version":"98348"}'):
            self.assertEqual(self.resolve(data=data)['reason'], 'source_integrity_refused')
            self.assertIsNone(self.resolve(data=data)['source_match'])
        with patch('pathlib.Path.open', side_effect=FileNotFoundError):
            self.assertEqual(labels.source_bytes(), b'')

    def test_unknown_identity_or_wrong_required_level_never_uses_same_slot(self):
        for tier in (dict(self.tier, catalog_id='UnknownTalent'), dict(self.tier, required_level=4)):
            self.assertEqual(self.resolve(tier)['reason'], 'source_identity_absent')
        # A different native slot never grants a qualified label either.
        result = self.resolve(dict(self.tier, slot=1))
        self.assertIsNone(result['label'])
        self.assertIn('native_slot_mapping', result['missing_provenance'])

    def synthetic(self, source):
        """Test-only re-pin: never changes production bytes/pins or creates native proof."""
        data = json.dumps(source).encode()
        with patch.object(labels, 'SOURCE_SHA256', hashlib.sha256(data).hexdigest()):
            return self.resolve(data=data)

    def test_duplicate_identity_is_ambiguous_even_if_names_equal(self):
        source = json.loads(self.data)
        entry = source['talents']['1'][1]
        source['talents']['1'].append(dict(entry))
        result = self.synthetic(source)
        self.assertEqual(result['reason'], 'source_identity_ambiguous')
        self.assertIsNone(result['source_match'])

    def test_sort_and_array_order_never_identify_choice(self):
        source = json.loads(self.data)
        source['talents']['1'].reverse()
        for entry in source['talents']['1']:
            entry['sort'] = 999
        result = self.synthetic(source)
        self.assertEqual(result['source_match']['label'], 'War Paint')
        self.assertIsNone(result['label'])
        source['talents']['1'][1]['talentTreeId'] = 'UnknownTalent'
        self.assertEqual(self.synthetic(source)['reason'], 'source_identity_absent')

    def test_forged_build_french_or_selection_fields_cannot_promote_source(self):
        source = json.loads(self.data)
        source.update(build=98348, language='fr', native_validated=True)
        source['talents']['1'][1].update(slot=2, selected=True, label_fr='FAUX FRANCAIS')
        result = self.synthetic(source)
        self.assertIsNone(result['label'])
        self.assertEqual(result['source_match']['language'], 'en')
        self.assertEqual(result['source_match']['label'], 'War Paint')
        self.assertNotIn('FAUX FRANCAIS', json.dumps(result))

    def test_invalid_source_schema_or_hero_is_refused(self):
        for source in ([], {}, {'shortName': 'arthas'},
                       {'shortName': 'sonya', 'talents': []},
                       {'shortName': 'sonya', 'talents': {'1': [None]}}):
            result = self.synthetic(source)
            self.assertIsNone(result['source_match'])
        for name in ('', None, 'x'*161, 'War\nPaint'):
            source = json.loads(self.data)
            source['talents']['1'][1]['name'] = name
            self.assertEqual(self.synthetic(source)['reason'], 'source_schema_refused')
