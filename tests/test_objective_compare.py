"""SYNTHETIC independent reference fixtures; never live qualification."""
import importlib.util
import unittest


class ComparisonTests(unittest.TestCase):
    def test_product_comparison_exists_separately_from_self_replay(self):
        self.assertIsNotNone(importlib.util.find_spec('cerveau.objective_compare'),
                             'independent comparison command missing')

    def test_collector_binds_one_session_and_measures_source_bracket_without_refresh(self):
        from cerveau.passive_session import run_session
        from cerveau.state import snapshot
        from test_objective_collection import dragon_raw
        from test_passive_session import Clock, SyntheticSource
        state = snapshot(dragon_raw())
        age = state['objective_qualification']['age_s']
        tokens = []
        for unused in range(2):
            clock = Clock(); rows = []
            source = SyntheticSource([state])
            run_session(lambda: source, lambda: False, rows.append, duration=1,
                        clock=clock, sleep=clock.sleep)
            row = next(r for r in rows if r['event'] == 'observation')
            self.assertIn('comparison', row, 'no independent session/clock binding')
            c = row['comparison']
            self.assertEqual(c['map_id'], 'DragonShire')
            self.assertEqual(c['perspective'], 'native_player')
            self.assertEqual(c['clock_basis'], 'host_monotonic')
            self.assertEqual(c['read_started_s'], 10)
            self.assertEqual(c['read_finished_s'], 10)
            self.assertEqual(row['objective']['age_s'], age)
            self.assertRegex(c['session_token'], r'^[0-9a-f]{32}$')
            tokens.append(c['session_token'])
        self.assertNotEqual(tokens[0], tokens[1], 'resumption reused correlation token')

    def test_exact_independent_stable_public_phase_and_divergence(self):
        from cerveau import objective_compare as product
        self.assertTrue(callable(getattr(product, 'compare', None)), 'comparison API missing')
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            paths, reference = fixture(Path(tmp))
            result = product.compare(**paths)
            phase = next(r for r in result['fields'] if r['field'] == 'phase')
            self.assertEqual(phase['status'], 'compared')
            self.assertEqual(result['counts'], {'compared': 1, 'divergent': 0, 'non_comparable': 4})
            self.assertFalse(result['current_permission'])
            self.assertEqual(result['mode'], 'historical_not_current')
            self.assertEqual(result['dataset'], 'synthetic')
            reference['samples'][0]['value'] = 'waiting'
            save(paths['references'], reference)
            result = product.compare(**paths)
            self.assertEqual(result['counts']['divergent'], 1)

    def test_fail_closed_against_independent_reference_and_clock_adversaries(self):
        import copy
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        from cerveau.objective_compare import compare
        cases = (
            ('wrong_match', lambda r: r['binding'].update(session_token='f' * 32), 'clip_binding_mismatch'),
            ('wrong_map', lambda r: r['binding'].update(map_id=None), 'binding_mismatch'),
            ('wrong_perspective', lambda r: r['binding'].update(perspective='observer'), 'binding_mismatch'),
            ('not_same_match', lambda r: r['provenance'].update(same_match=False), 'provenance_unqualified'),
            ('not_same_player', lambda r: r['provenance'].update(same_player_perspective=False), 'provenance_unqualified'),
            ('ocr', lambda r: r['provenance'].update(transcription='ocr'), 'provenance_unqualified'),
            ('self_replay', lambda r: r['provenance'].update(kind='journal_replay'), 'provenance_unqualified'),
            ('replay_clock', lambda r: r['clock'].update(basis='replay'), 'clock_unqualified'),
            ('wall_clock', lambda r: r['clock'].update(basis='utc'), 'clock_unqualified'),
            ('unknown_uncertainty', lambda r: r['clock'].update(uncertainty_s=None), 'clock_unqualified'),
            ('wide_uncertainty', lambda r: r['clock'].update(uncertainty_s=.251), 'clock_unqualified'),
            ('stale', lambda r: r['samples'][0].update(stable_from_s=1, stable_to_s=2), 'time_not_contained'),
            ('point_frame', lambda r: r['samples'][0].update(stable_from_s=10, stable_to_s=10), 'time_not_contained'),
            ('overlap_only', lambda r: r['samples'][0].update(stable_from_s=10, stable_to_s=11), 'time_not_contained'),
            ('unknown_time', lambda r: r['samples'][0].update(stable_from_s=None), 'time_unknown'),
            ('unknown_value', lambda r: r['samples'][0].update(value=None), 'value_unknown'),
            ('ambiguous', lambda r: r['samples'].append(copy.deepcopy(r['samples'][0])), 'reference_ambiguous'),
            ('absent_cycle', lambda r: r['samples'][0].update(cycle=99), 'observation_missing'),
            ('wrong_digest', lambda r: r.update(journal_sha256='0' * 64), 'journal_digest_mismatch'),
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths, initial = fixture(Path(tmp))
            for name, mutate, reason in cases:
                r = copy.deepcopy(initial); mutate(r); save(paths['references'], r)
                with self.subTest(case=name):
                    result = compare(**paths)
                    phase = next(row for row in result['fields'] if row['field'] == 'phase')
                    self.assertEqual(phase['status'], 'non_comparable')
                    self.assertEqual(phase['reason'], reason)
                    self.assertEqual(result['counts']['compared'], 0)
            save(paths['references'], initial)
            for artifact in ('evidence', 'match_link', 'clock_evidence'):
                with self.subTest(artifact=artifact):
                    changed = dict(paths); changed[artifact] = None
                    self.assertEqual(compare(**changed)['fields'][0]['reason'], 'evidence_unverified')
            original = paths['journal'].read_text(encoding='utf-8')
            rows = [json.loads(line) for line in original.splitlines()]
            observation = next(row for row in rows if row['event'] == 'observation')
            mutations = (
                ('old_journal', lambda o: o.pop('comparison'), 'binding_missing'),
                ('unknown_clock', lambda o: o['comparison'].update(read_started_s=None), 'native_time_unknown'),
                ('wide_window', lambda o: o['comparison'].update(read_started_s=8), 'native_uncertainty'),
                ('backwards', lambda o: o['comparison'].update(read_started_s=11), 'native_time_unknown'),
                ('stale_receipt', lambda o: o['objective'].update(age_s=1.1), 'objective_unavailable'),
                ('unknown_native', lambda o: o['objective']['value'].update(phase='unknown'), 'value_unknown'),
                ('unknown_source', lambda o: o['objective'].update(source_mission_t_s=None), 'objective_unavailable'),
                ('duplicate_cycle', lambda o: None, 'observation_ambiguous'),
            )
            for name, mutate, reason in mutations:
                changed = copy.deepcopy(rows)
                o = next(row for row in changed if row['event'] == 'observation'); mutate(o)
                if name == 'duplicate_cycle': changed.append(copy.deepcopy(o))
                paths['journal'].write_text(''.join(json.dumps(row) + '\n' for row in changed), encoding='utf-8')
                r = copy.deepcopy(initial)
                r['journal_sha256'] = hashlib.sha256(paths['journal'].read_bytes()).hexdigest()
                refresh_witness(paths, r)
                save(paths['references'], r)
                with self.subTest(native=name):
                    result = compare(**paths)
                    self.assertEqual(result['fields'][0]['status'], 'non_comparable')
                    self.assertEqual(result['fields'][0]['reason'], reason)

    def test_closed_schema_limits_and_private_input_never_escape(self):
        import copy
        import tempfile
        from pathlib import Path
        from cerveau.objective_compare import compare
        with tempfile.TemporaryDirectory() as tmp:
            paths, initial = fixture(Path(tmp))
            mutations = (
                lambda r: r.update(PRIVATE='0x12345678'),
                lambda r: r['provenance'].update(PRIVATE='PRIVATE'),
                lambda r: r['clock'].update(PRIVATE='PRIVATE'),
                lambda r: r['binding'].update(PRIVATE='PRIVATE'),
                lambda r: r['samples'][0].update(PRIVATE='PRIVATE'),
                lambda r: r['samples'][0].update(value='PRIVATE'),
                lambda r: r['samples'][0].update(field='PRIVATE'),
                lambda r: r['samples'][0].update(field='sun.owner', value=True),
                lambda r: r['samples'][0].update(cycle=True),
                lambda r: r['samples'][0].update(stable_from_s=float('nan')),
                lambda r: r['binding'].update(session_token='PRIVATE'),
                lambda r: r.update(dataset='PRIVATE'),
                lambda r: r.update(schema_version=True),
                lambda r: r.update(samples=r['samples'] * 129),
                lambda r: r.pop('binding'),
            )
            for index, mutate in enumerate(mutations):
                r = copy.deepcopy(initial); mutate(r); save(paths['references'], r)
                with self.subTest(case=index), self.assertRaisesRegex(ValueError, '^invalid_reference$'):
                    compare(**paths)
            paths['references'].write_text('{"schema_version":1,"schema_version":1}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'duplicate_json_key'):
                compare(**paths)
            paths['references'].write_bytes(b' ' * 65537)
            with self.assertRaisesRegex(ValueError, 'reference_limit'):
                compare(**paths)
            save(paths['references'], initial)
            for body in (b'null\n', b'[]\n', b' ' * 65537, b'{}\n' * 10001, b' ' * (4 * 2**20 + 1)):
                paths['journal'].write_bytes(body)
                with self.subTest(bytes=len(body)), self.assertRaises(ValueError):
                    compare(**paths)

    def test_cli_help_comparison_and_sanitized_failure_without_backend(self):
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            paths, reference = fixture(Path(tmp))
            command = [sys.executable, '-B', '-m', 'cerveau.objective_compare']
            help_result = subprocess.run(command + ['--help'], capture_output=True, text=True, timeout=30)
            self.assertEqual(help_result.returncode, 0)
            self.assertIn('--references', help_result.stdout)
            args = [item for key, path in paths.items() for item in ('--' + key.replace('_', '-'), str(path))]
            result = subprocess.run(command + args, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.strip(), 'comparison CLI has no output')
            row = json.loads(result.stdout)
            self.assertEqual(row['counts']['compared'], 1)
            self.assertEqual(row['dataset'], 'synthetic')
            paths['references'].write_text('PRIVATE invalid 0x12345678', encoding='utf-8')
            result = subprocess.run(command + args, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['code'], 'invalid_or_unavailable_comparison')
            self.assertNotIn('PRIVATE', result.stdout + result.stderr)
            self.assertNotIn(str(paths['references']), result.stdout + result.stderr)

    def test_owner_team_mapping_unknown_and_context_gaps_do_not_gain_comparability(self):
        import copy
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        from cerveau.objective_compare import compare
        with tempfile.TemporaryDirectory() as tmp:
            paths, r = fixture(Path(tmp))
            r['samples'][0].update(field='sun.owner', value='neutral')
            save(paths['references'], r)
            result = compare(**paths)
            self.assertEqual(next(x for x in result['fields'] if x['field'] == 'sun.owner')['status'], 'compared')
            original = paths['journal'].read_text(encoding='utf-8')
            rows = [json.loads(x) for x in original.splitlines()]
            obs = next(x for x in rows if x['event'] == 'observation')
            obs['objective']['value']['shrines'][0]['owner'] = 0
            r['samples'][0]['value'] = 0
            paths['journal'].write_text(''.join(json.dumps(x) + '\n' for x in rows), encoding='utf-8')
            r['journal_sha256'] = hashlib.sha256(paths['journal'].read_bytes()).hexdigest()
            refresh_witness(paths, r)
            save(paths['references'], r)
            result = compare(**paths)
            owner = next(x for x in result['fields'] if x['field'] == 'sun.owner')
            self.assertEqual(owner['reason'], 'team_mapping_unqualified')
            self.assertEqual(owner['status'], 'non_comparable')
            # Same token in an untrusted merged journal cannot hide another session alias.
            extra = copy.deepcopy(obs); extra['cycle'] = 2; extra['session'] = 'session_ffffffffffff'
            rows.append(extra)
            paths['journal'].write_text(''.join(json.dumps(x) + '\n' for x in rows), encoding='utf-8')
            r['journal_sha256'] = hashlib.sha256(paths['journal'].read_bytes()).hexdigest()
            save(paths['references'], r)
            self.assertEqual(compare(**paths)['fields'][0]['reason'], 'journal_context_ambiguous')
            # Artifact named evidence containing the journal is self-reference, not independent.
            r['provenance']['evidence_sha256'] = r['journal_sha256']; save(paths['references'], r)
            changed = dict(paths, evidence=paths['journal'])
            self.assertEqual(compare(**changed)['fields'][0]['reason'], 'self_reference')

    def test_every_observation_must_preserve_the_unique_match_binding(self):
        import copy
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        from cerveau.objective_compare import compare
        with tempfile.TemporaryDirectory() as tmp:
            paths, initial = fixture(Path(tmp))
            original = [json.loads(line) for line in paths['journal'].read_bytes().splitlines()]
            obs = next(row for row in original if row['event'] == 'observation')
            mutations = (
                ('other_match_unlinked', lambda row: (row.update(session='session_other_match'), row.pop('comparison'))),
                ('same_alias_unlinked', lambda row: row.pop('comparison')),
                ('null_binding', lambda row: row.update(comparison=None)),
                ('malformed_binding', lambda row: row.update(comparison=[])),
                ('other_map', lambda row: row['comparison'].update(map_id='VolskayaFoundry')),
                ('other_perspective', lambda row: row['comparison'].update(perspective='observer')),
                ('missing_token', lambda row: row['comparison'].pop('session_token')),
                ('missing_session', lambda row: row.pop('session')),
            )
            for name, mutate in mutations:
                with self.subTest(case=name):
                    rows = copy.deepcopy(original)
                    extra = copy.deepcopy(obs); extra['cycle'] = 2; mutate(extra)
                    rows.append(extra)
                    paths['journal'].write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
                    reference = copy.deepcopy(initial)
                    reference['journal_sha256'] = hashlib.sha256(paths['journal'].read_bytes()).hexdigest()
                    refresh_witness(paths, reference)
                    save(paths['references'], reference)
                    result = compare(**paths)
                    self.assertEqual(result['counts'], {'compared': 0, 'divergent': 0, 'non_comparable': 5})
                    self.assertTrue(all(row['reason'] == 'journal_context_ambiguous' for row in result['fields']))
                    self.assertTrue(all(row['native'] is None and row['reference'] is None for row in result['fields']))
                    self.assertFalse(result['current_permission'])

    def test_clip_metadata_is_verified_not_just_operator_supplied_timestamps(self):
        import copy
        import hashlib
        import tempfile
        import zipfile
        import json
        from pathlib import Path
        from cerveau.objective_compare import compare
        with tempfile.TemporaryDirectory() as tmp:
            paths, initial = fixture(Path(tmp))
            r = copy.deepcopy(initial); r['clock']['uncertainty_s'] = .001; save(paths['references'], r)
            self.assertEqual(compare(**paths)['fields'][0]['reason'], 'clock_unqualified')
            r = copy.deepcopy(initial); r['samples'][0]['boundary_uncertainty_s'] = .001; save(paths['references'], r)
            self.assertEqual(compare(**paths)['fields'][0]['reason'], 'reference_resolution_unqualified')
            with zipfile.ZipFile(paths['evidence']) as archive:
                members = {name: archive.read(name) for name in archive.namelist()}
            index = json.loads(members['index.json'])
            index['session_token'] = 'f' * 32
            members['index.json'] = json.dumps(index).encode()
            with zipfile.ZipFile(paths['evidence'], 'w') as archive:
                for name, body in members.items(): archive.writestr(name, body)
            paths['clock_evidence'].write_bytes(members['index.json'])
            r = copy.deepcopy(initial)
            for name in ('evidence', 'clock_evidence'):
                r['provenance'][name + '_sha256'] = hashlib.sha256(paths[name].read_bytes()).hexdigest()
            save(paths['references'], r)
            self.assertEqual(compare(**paths)['fields'][0]['reason'], 'clip_binding_mismatch')

    def test_same_match_witness_is_closed_and_bound_not_an_arbitrary_hashed_file(self):
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        from cerveau.objective_compare import compare
        with tempfile.TemporaryDirectory() as tmp:
            paths, r = fixture(Path(tmp))
            witness = json.loads(paths['match_link'].read_bytes())
            witness['same_uninterrupted_match'] = False
            save(paths['match_link'], witness)
            r['provenance']['match_link_sha256'] = hashlib.sha256(paths['match_link'].read_bytes()).hexdigest()
            save(paths['references'], r)
            self.assertEqual(compare(**paths)['fields'][0]['reason'], 'match_link_unqualified')


def refresh_witness(paths, reference):
    import hashlib
    import json
    w = json.loads(paths['match_link'].read_bytes())
    w['journal_sha256'] = reference['journal_sha256']
    save(paths['match_link'], w)
    reference['provenance']['match_link_sha256'] = hashlib.sha256(paths['match_link'].read_bytes()).hexdigest()


def save(path, value):
    import json
    path.write_text(json.dumps(value), encoding='utf-8')


def fixture(directory):
    import hashlib
    import json
    from cerveau.passive_session import run_session
    from cerveau.state import snapshot
    from test_objective_collection import dragon_raw
    from test_passive_session import Clock, SyntheticSource
    state = snapshot(dragon_raw())
    source = SyntheticSource([state]); clock = Clock(); rows = []
    run_session(lambda: source, lambda: False, rows.append, duration=1,
                clock=clock, sleep=clock.sleep)
    journal = directory / 'synthetic-events.jsonl'
    journal.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    observation = next(r for r in rows if r['event'] == 'observation')
    paths = {'journal': journal, 'references': directory / 'synthetic-reference.json'}
    provenance = {'kind': 'hud_video', 'transcription': 'manual',
                  'same_match': True, 'same_player_perspective': True}
    for name in ('evidence', 'match_link', 'clock_evidence'):
        paths[name] = directory / (name + '.synthetic')
        if name != 'evidence':
            paths[name].write_bytes(('SYNTHETIC ' + name).encode())
    from cerveau.objective_reference import record_clip
    clip_clock = Clock(); clip_clock.value = 8.5
    def synthetic_capture():
        clip_clock.sleep(.01)
        return b'SYNTHETIC_NOT_A_REAL_IMAGE'
    with_file = directory / 'evidence.synthetic'
    record_clip(synthetic_capture, with_file, lambda: False,
                observation['comparison']['session_token'], duration=3, interval=.05,
                clock=clip_clock, sleep=clip_clock.sleep)
    import zipfile
    with zipfile.ZipFile(with_file) as archive:
        paths['clock_evidence'].write_bytes(archive.read('index.json'))
    match_witness = {'schema_version': 1, 'dataset': 'synthetic',
                     'session_token': observation['comparison']['session_token'],
                     'map_id': 'DragonShire', 'perspective': 'native_player',
                     'scenario': 'private_local_9bots', 'same_uninterrupted_match': True,
                     'identity_verified_privately': True,
                     'journal_sha256': hashlib.sha256(journal.read_bytes()).hexdigest(),
                     'evidence_sha256': hashlib.sha256(paths['evidence'].read_bytes()).hexdigest()}
    save(paths['match_link'], match_witness)
    for name in ('evidence', 'match_link', 'clock_evidence'):
        provenance[name + '_sha256'] = hashlib.sha256(paths[name].read_bytes()).hexdigest()
    reference = {'schema_version': 1, 'dataset': 'synthetic',
                 'journal_sha256': hashlib.sha256(journal.read_bytes()).hexdigest(),
                 'binding': {k: observation['comparison'][k]
                             for k in ('session_token', 'map_id', 'perspective')},
                 'provenance': provenance,
                 'clock': {'basis': 'host_monotonic', 'uncertainty_s': .01},
                 'samples': [{'cycle': 1, 'field': 'phase', 'value': 'shrines',
                              'stable_from_s': 9, 'stable_to_s': 11,
                              'boundary_uncertainty_s': .07}]}
    save(paths['references'], reference)
    return paths, reference


if __name__ == '__main__':
    unittest.main()
