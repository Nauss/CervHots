"""SYNTHETIC receipts/transport only; never live semantic coverage."""
import unittest
from unittest.mock import patch
import test_capture_talents as fixtures
import test_talents_product as product
import test_talents_contract as contract
from cerveau.state import snapshot


class TalentDurableTests(unittest.TestCase):
    def test_normalization_retains_original_receipt_age_without_exporting_seal(self):
        m = product.TalentProductTests().fixture()
        with fixtures.TalentCollectorTests().options(m), \
                patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya', 'ragnaros'),)):
            raw = contract.TalentContractTests().raw(m)
            with patch('time.monotonic', return_value=100.25):
                clean = snapshot(raw)
        self.assertEqual(clean['talents_qualification'], {
            'status': 'normalized', 'source': 'native_player',
            'source_mission_t_s': raw['talents']['mission_t_s'],
            'age_s': .25, 'read_window_s': raw['talents']['read_window_s']})
        self.assertNotIn('acquisition', clean['talents'])


    def test_passive_journal_persists_actual_choices_and_unknown_labels_not_offers(self):
        from cerveau.diagnostics import Journal
        m = product.TalentProductTests().fixture()
        with fixtures.TalentCollectorTests().options(m), \
                patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya', 'ragnaros'),)):
            raw = contract.TalentContractTests().raw(m)
            clean = snapshot(raw)
            clean['talents']['offered'] = ['PRIVATE_OFFER']
            clean['talents']['players'][0]['tiers'][0]['label'] = 'UNPROVEN_LABEL'
            rows = []
            with patch('time.monotonic', return_value=300):
                Journal(rows.append).observation(clean)
        stored = rows[0].get('talents')
        self.assertIsNotNone(stored, 'selected talents missing from durable journal')
        self.assertEqual(stored['status'], 'normalized')
        self.assertEqual(stored['age_s'], 0)
        selected = stored['value']['players'][0]['tiers'][0]
        self.assertEqual(selected['catalog_id'], 'StitchesPatchworkCreation')
        self.assertEqual(selected['status'], 'selected')
        self.assertEqual(selected['label_status'], 'unknown')
        self.assertIsNone(selected['label'])
        self.assertIsNone(selected['label_provenance'])
        import json
        serialized = json.dumps(rows)
        for forbidden in ('PRIVATE_OFFER', 'UNPROVEN_LABEL', 'acquisition', 'seal', 'generation'):
            self.assertNotIn(forbidden, serialized)


    def test_replay_is_bounded_historical_and_keeps_age_without_issuing_receipts(self):
        import json
        import tempfile
        from pathlib import Path
        from cerveau import talents_journal
        self.assertTrue(callable(getattr(talents_journal, 'replay', None)), 'talent replay missing')
        m = product.TalentProductTests().fixture()
        with fixtures.TalentCollectorTests().options(m), \
                patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya', 'ragnaros'),)):
            raw = contract.TalentContractTests().raw(m)
            with patch('time.monotonic', return_value=100.4):
                clean = snapshot(raw)
            stored = talents_journal.talents_summary(clean)
            stored['value']['players'][0]['tiers'][0]['label'] = 'UNPROVEN'
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'SYNTHETIC.jsonl'
                path.write_text(json.dumps({'event': 'observation', 'talents': stored}) + '\n')
                rows = []
                with patch('hotstate.acquisition.issue', side_effect=AssertionError('no renewal')):
                    result = talents_journal.replay(path, rows.append)
                self.assertEqual(result['exported_values'], 1)
                self.assertEqual(rows[0]['mode'], 'historical_not_current')
                self.assertAlmostEqual(rows[0]['talents']['age_s'], .4)
                self.assertIsNone(rows[0]['talents']['value']['players'][0]['tiers'][0]['label'])
                self.assertNotIn('acquisition', json.dumps(rows))
                path.write_bytes(b' ' * 65537)
                with self.assertRaisesRegex(ValueError, 'journal_limit'):
                    talents_journal.replay(path, rows.append)


    def test_replay_cli_and_invalid_input_are_honest(self):
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout
        from pathlib import Path
        from cerveau import talents_journal
        self.assertTrue(callable(getattr(talents_journal, 'main', None)), 'talents CLI missing')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'SYNTHETIC.jsonl'
            path.write_text('{"event":"observation"}\n')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(talents_journal.main(['--journal', str(path)]), 0)
            self.assertEqual(json.loads(output.getvalue().splitlines()[0])['talents']['status'], 'unknown')
            path.write_text('not JSON PRIVATE')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(talents_journal.main(['--journal', str(path)]), 1)
            self.assertNotIn('PRIVATE', output.getvalue())
            self.assertNotIn(str(path), output.getvalue())


    def test_non_integer_build_is_rejected_at_normalization(self):
        m = product.TalentProductTests().fixture()
        with fixtures.TalentCollectorTests().options(m), \
                patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya', 'ragnaros'),)):
            raw = contract.TalentContractTests().raw(m)
            raw['meta']['native_build'] = 98348.0
            self.assertNotIn('talents', snapshot(raw))


    def test_export_refuses_float_build_instead_of_promoting_it_to_int(self):
        from cerveau.talents_journal import talents_summary, _value
        m = product.TalentProductTests().fixture()
        with fixtures.TalentCollectorTests().options(m), \
                patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya', 'ragnaros'),)):
            clean = snapshot(contract.TalentContractTests().raw(m))
            value = talents_summary(clean)['value']
            value['build'] = 98348.0
            with self.assertRaises(ValueError):
                _value(value)


    def test_existing_refusals_survive_durable_export_without_choice_inference(self):
        import copy
        from cerveau.talents_journal import talents_summary
        m = product.TalentProductTests().fixture()
        with fixtures.TalentCollectorTests().options(m), \
                patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya', 'ragnaros'),)):
            raw = contract.TalentContractTests().raw(m)
            for mutation in ('absent', 'offer_only', 'build', 'hero', 'match', 'generation', 'session', 'expired'):
                bad = copy.deepcopy(raw)
                if mutation == 'absent':
                    bad.pop('talents')
                elif mutation == 'offer_only':
                    bad['talents'] = {'offered': [{'catalog_id': 'PRIVATE_OFFER'}]}
                elif mutation == 'build':
                    bad['meta']['native_build'] = 98349
                elif mutation == 'hero':
                    bad['talents']['local_hero'] = 'sonya'
                elif mutation == 'match':
                    bad['meta']['match_id'] = 'b' * 64
                elif mutation == 'generation':
                    bad['perspective']['allied_generations']['5'] = 2
                elif mutation == 'session':
                    bad['talents']['native_session'] = 'b' * 64
                from hotstate.acquisition import issue
                if mutation in ('hero', 'session'):
                    issue(bad['talents'], 100)
                if mutation == 'generation':
                    issue(bad['perspective'], 100)
                with self.subTest(mutation=mutation), patch('time.monotonic', return_value=102 if mutation == 'expired' else 100):
                    exported = talents_summary(snapshot(bad))
                    self.assertIsNone(exported['value'])
                    self.assertIsNone(exported['age_s'])
                    self.assertIn(exported['status'], ('rejected', 'not_attempted'))
            refused = copy.deepcopy(raw)
            refused.pop('talents')
            refused['meta']['optional_refusals'] = {'talents': 'talent_recipe_scope_unqualified'}
            self.assertEqual(talents_summary(snapshot(refused))['status'], 'refused')

    def test_native_reset_and_absent_choices_are_not_previous_choice_or_offered_option(self):
        from cerveau.talents_journal import talents_summary
        m = product.TalentProductTests().fixture()
        with fixtures.TalentCollectorTests().options(m), \
                patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya', 'ragnaros'),)):
            before = talents_summary(snapshot(contract.TalentContractTests().raw(m)))
            self.assertEqual(before['value']['players'][0]['tiers'][0]['status'], 'selected')
            # Physical synthetic persisted index cleared, no inferred choice from Hero catalog.
            m.pack(m.module_base + 0x3677a30 + 6 * 128 + 4, 'I', 0xffffffff)
            after = talents_summary(snapshot(contract.TalentContractTests().raw(m)))
            tier = after['value']['players'][0]['tiers'][0]
            self.assertEqual(tier['status'], 'unselected')
            self.assertIsNone(tier['catalog_id'])
            self.assertIsNone(tier['slot'])
            self.assertIsNone(tier['label'])
            self.assertEqual(after['value']['players'][0]['tiers'][1]['status'], 'unknown')
            self.assertIsNone(after['value']['players'][1]['tiers'])

    def test_durable_export_rechecks_roster_and_rejects_enemy_rows(self):
        import copy
        from cerveau.talents_journal import talents_summary
        m = product.TalentProductTests().fixture()
        with fixtures.TalentCollectorTests().options(m), \
                patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya', 'ragnaros'),)):
            clean = snapshot(contract.TalentContractTests().raw(m))
            for mutation in ('enemy', 'duplicate', 'hero', 'choice_above_level', 'unknown_with_choice', 'wrong_time'):
                bad = copy.deepcopy(clean)
                row = bad['talents']['players'][0]
                if mutation == 'enemy':
                    row['id'] = 0
                elif mutation == 'duplicate':
                    bad['talents']['players'][1] = row
                elif mutation == 'hero':
                    row['hero'] = 'sonya'
                elif mutation == 'choice_above_level':
                    row['tiers'][0]['required_level'] = 30
                elif mutation == 'unknown_with_choice':
                    row['status'] = 'unknown'
                else:
                    bad['talents']['t'] += 1
                with self.subTest(mutation=mutation):
                    self.assertEqual(talents_summary(bad)['status'], 'rejected')
                    self.assertIsNone(talents_summary(bad)['value'])


    def test_session_replacement_stops_and_resume_never_carries_choices_or_age(self):
        import copy
        from cerveau import passive_session
        from test_passive_session import Clock, SyntheticSource
        m = product.TalentProductTests().fixture()
        with fixtures.TalentCollectorTests().options(m), \
                patch('time.monotonic', return_value=100), \
                patch('hotstate.talents.VALIDATED_SCOPES', (('Volskaya', 'ragnaros'),)):
            clean = snapshot(contract.TalentContractTests().raw(m))
            other = copy.deepcopy(clean)
            other['meta']['match_id'] = 'b' * 64
            rows = []
            clock = Clock()
            source = SyntheticSource([clean, other])
            result = passive_session.run_session(lambda: source, lambda: False, rows.append,
                duration=10, interval=1, clock=clock, sleep=clock.sleep)
            self.assertEqual(result['reason'], 'session_changed')
            self.assertTrue(source.closed)
            observations = [r for r in rows if r['event'] == 'observation']
            self.assertEqual(len(observations), 1)
            self.assertEqual(observations[0]['talents']['status'], 'normalized')
            # New invocation: no talents acquired. No replay, prior selection or age reused.
            other.pop('talents')
            other['talents_qualification'] = {'status': 'not_attempted', 'source': 'native_player'}
            resumed = []
            clock = Clock()
            source = SyntheticSource([other])
            result = passive_session.run_session(lambda: source, lambda: False, resumed.append,
                duration=1, interval=1, clock=clock, sleep=clock.sleep)
            self.assertEqual(result['accepted'], 1)
            self.assertTrue(source.closed)
            row = next(r for r in resumed if r['event'] == 'observation')
            self.assertIsNone(row['talents']['value'])
            self.assertIsNone(row['talents']['age_s'])
            self.assertNotEqual(row['comparison']['session_token'], observations[0]['comparison']['session_token'])
            self.assertNotEqual(row['session'], observations[0]['session'])


    def test_committed_synthetic_example_is_reexecutable_not_current(self):
        from pathlib import Path
        from cerveau.talents_journal import replay
        rows = []
        result = replay(Path(__file__).resolve().parents[1] / 'examples/talents/SYNTHETIC/events.jsonl', rows.append)
        self.assertEqual(result, {'lines': 3, 'observations': 3, 'exported_values': 3})
        self.assertEqual([r['talents']['value']['players'][0]['tiers'][0]['status'] for r in rows],
                         ['selected', 'unselected', 'unknown'])
        self.assertTrue(all(r['mode'] == 'historical_not_current' and r['talents']['age_s'] == .25 for r in rows))

    def test_malformed_replay_never_reconstructs_values_or_receipts(self):
        import copy
        import json
        import tempfile
        from pathlib import Path
        from cerveau.talents_journal import replay
        fixture = Path(__file__).resolve().parents[1] / 'examples/talents/SYNTHETIC/events.jsonl'
        original = json.loads(fixture.read_text().splitlines()[0])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'SYNTHETIC.jsonl'
            for mutation in ('build', 'role', 'empty', 'duplicate', 'age', 'no_qualification', 'offer_only'):
                row = copy.deepcopy(original)
                p = row['talents']['value']
                if mutation == 'build':
                    p['build'] = 98349
                elif mutation == 'role':
                    p['local_slot'] = 1
                elif mutation == 'empty':
                    p['players'] = []
                elif mutation == 'duplicate':
                    p['players'][1] = p['players'][0]
                elif mutation == 'age':
                    row['talents']['age_s'] = -1
                elif mutation == 'no_qualification':
                    row['talents'].pop('status')
                else:
                    p['players'][0]['tiers'] = [{'offered': 'SyntheticSelectedTalent'}]
                path.write_text(json.dumps(row) + '\n')
                rows = []
                with self.subTest(mutation=mutation), patch('hotstate.acquisition.issue', side_effect=AssertionError('no receipt')):
                    result = replay(path, rows.append)
                    self.assertEqual(result['exported_values'], 0)
                    self.assertIsNone(rows[0]['talents']['value'])
                    self.assertIsNone(rows[0]['talents']['age_s'])


if __name__ == '__main__':
    unittest.main()
