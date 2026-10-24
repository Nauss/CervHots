"""Synthetic collection contracts, never native/live qualification."""
import unittest
from unittest.mock import patch

from test_dragon_contract import packet
from cerveau.state import snapshot


def dragon_raw():
    raw, local = packet()
    raw['local_player'] = local
    raw['meta'].update(native_status='valide', map='Dragon Shire')
    raw['players'] = [{'id': i, 'team': i // 5,
                       'hero': 'stitches' if i == 0 else 'ragnaros'} for i in range(10)]
    raw['heroes'] = [dict(p, alive=True, level=10) for p in raw['players']]
    return raw


class ObjectiveQualificationTests(unittest.TestCase):
    def test_optional_refusal_preserves_core_with_explicit_user_state(self):
        raw = dragon_raw()
        raw.pop('objective')
        raw['meta']['optional_refusals'] = {'objective': 'recette_dragon_absente'}
        state = snapshot(raw)
        self.assertEqual(len(state['heroes']), 10)
        self.assertNotIn('objective', state)
        self.assertIn('objective_qualification', state, 'optional outcome is silently lost')
        self.assertEqual(state['objective_qualification'], {
            'status': 'refused', 'reason': {'code': 'recette_dragon_absente',
                                         'category': 'optional_unqualified'},
            'source': 'native_player', 'source_mission_t_s': None,
            'age_s': None, 'read_window_s': None})

    def test_valid_value_preserves_source_age_and_cache_never_refreshes_receipt(self):
        from hotstate.acquisition import issue
        raw = dragon_raw()
        with patch('hotstate.acquisition.time.monotonic', return_value=100.0):
            issue(raw['objective'], 99.75)
            first = snapshot(raw)
        self.assertEqual(first['objective_qualification']['status'], 'normalized')
        self.assertEqual(first['objective_qualification']['age_s'], 0.25)
        self.assertEqual(first['objective_qualification']['source_mission_t_s'], 123.5)
        self.assertEqual(first['objective_qualification']['read_window_s'], 0.01)
        self.assertIsNone(first['objective_qualification']['reason'])
        receipt = dict(raw['objective']['acquisition'])
        with patch('hotstate.acquisition.time.monotonic', return_value=100.5):
            second = snapshot(raw)
        self.assertEqual(second['objective_qualification']['age_s'], 0.75)
        self.assertEqual(raw['objective']['acquisition'], receipt)
        with patch('hotstate.acquisition.time.monotonic', return_value=101.0):
            expired = snapshot(raw)
        self.assertNotIn('objective', expired)
        self.assertEqual(expired['objective_qualification']['status'], 'rejected')
        self.assertIsNone(expired['objective_qualification']['age_s'])
        self.assertEqual(len(expired['heroes']), 10)

    def test_absent_packet_is_not_attempted_and_rejected_packet_is_explicit(self):
        raw = dragon_raw()
        raw.pop('objective')
        state = snapshot(raw)
        self.assertEqual(state['objective_qualification']['status'], 'not_attempted')
        self.assertIsNone(state['objective_qualification']['reason'])
        raw = dragon_raw()
        raw['objective'].pop('acquisition')
        state = snapshot(raw)
        self.assertEqual(state['objective_qualification']['status'], 'rejected')
        self.assertEqual(state['objective_qualification']['reason']['code'],
                         'objective_packet_rejected')

    def test_dragon_guard_codes_are_not_lost_in_unknown_refusal(self):
        from hotstate.diagnostics import refusal
        for code, category in (('profil_dragon_invalide', 'build'),
                               ('signature_dragon_invalide', 'build'),
                               ('perspective_dragon_incoherente', 'context_identity')):
            with self.subTest(code=code):
                raw = dragon_raw()
                raw.pop('objective')
                raw['meta']['optional_refusals'] = {'objective': code}
                q = snapshot(raw)['objective_qualification']
                self.assertEqual(q['reason'], {'code': code, 'category': category})
                self.assertEqual(refusal(code), q['reason'])

    def test_passive_observation_persists_refusal_without_stopping_core(self):
        from cerveau.passive_session import run_session
        from test_passive_session import Clock, SyntheticSource
        raw = dragon_raw()
        raw.pop('objective')
        raw['meta']['optional_refusals'] = {'objective': 'recette_dragon_absente'}
        state = snapshot(raw)
        source = SyntheticSource([state])
        rows = []
        clock = Clock()
        result = run_session(lambda: source, lambda: False, rows.append,
                             duration=1, interval=5, clock=clock, sleep=clock.sleep)
        self.assertEqual(result['accepted'], 1)
        self.assertTrue(source.closed)
        observation = next(r for r in rows if r['event'] == 'observation')
        self.assertIn('objective', observation, 'durable objective outcome missing')
        self.assertEqual(observation['objective']['status'], 'refused')
        self.assertEqual(observation['objective']['reason']['code'], 'recette_dragon_absente')
        self.assertIsNone(observation['objective']['value'])
        self.assertNotIn('Dragon Shire', str(rows))

    def test_durable_dragon_values_and_original_age_survive_without_private_fields(self):
        import copy
        from cerveau.diagnostics import Journal
        from hotstate.acquisition import issue
        raw = dragon_raw()
        raw['objective']['shrines'][0].update(
            state='unknown', owner=0, contested=None, capture_current_visible=False)
        with patch('hotstate.acquisition.time.monotonic', return_value=100.0):
            issue(raw['objective'], 99.75)
            state = snapshot(raw)
        expected = copy.deepcopy(state['objective'])
        expected.pop('t'); expected.pop('map_id')
        state['objective']['PRIVATE'] = 'PRIVATE'
        state['objective']['shrines'][0]['pointer'] = 'PRIVATE'
        state['objective_qualification']['receipt'] = 'PRIVATE'
        rows = []
        Journal(rows.append).observation(state)
        result = rows[0]['objective']
        self.assertEqual(result['status'], 'normalized')
        self.assertEqual(result['age_s'], 0.25)
        self.assertEqual(result['source_mission_t_s'], 123.5)
        self.assertEqual(result['read_window_s'], 0.01)
        self.assertEqual(result['family'], 'dragon')
        self.assertEqual(result['value'], expected)
        self.assertEqual(result['value']['shrines'][0]['owner'], 0)
        self.assertIsNone(result['value']['shrines'][0]['contested'])
        self.assertNotIn('PRIVATE', str(rows))
        self.assertNotIn('acquisition', str(rows))
        self.assertNotIn('a' * 64, str(rows))

    def test_preflight_announces_selected_collection_without_opening_process(self):
        from cerveau.passive_session import preflight
        with patch('hotstate.reader.ProcessBackend', side_effect=AssertionError('no process')):
            ready = preflight()
        self.assertIn('objective_collection', ready, 'collection support is undiscoverable')
        self.assertEqual(ready['objective_collection'], {
            'value_families': ['dragon'], 'qualification_only_maps': ['Volskaya'],
            'age_basis': 'original_receipt_at_normalization',
            'historical_replay_grants_permission': False})

    def test_real_native_optional_dragon_refusal_keeps_normalized_core(self):
        from test_current_visibility import VisibilityMemory
        from hotstate.native import NativeReader
        m = VisibilityMemory()
        m.context['meta']['map_id'] = 'DragonShire'
        with patch('hotstate.positions.PROFILE', m.position_profile), \
                patch('hotstate.match.PROFILE', m.match_profile):
            raw = NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)
        raw['meta'].update(m.context['meta'], source='live')
        state = snapshot(raw)
        self.assertEqual(len(state['heroes']), 10)
        self.assertNotIn('objective', state)
        self.assertEqual(state['objective_qualification']['status'], 'refused')
        self.assertEqual(state['objective_qualification']['reason']['code'], 'profil_dragon_invalide')

    def test_wrong_map_build_context_perspective_and_receipt_are_rejected(self):
        from hotstate.acquisition import issue
        import time
        for change in ('map', 'build', 'context', 'match', 'local', 'team', 'hero',
                       'source', 'diagnostic', 'future', 'stale', 'tamper', 'override'):
            with self.subTest(change=change):
                raw = dragon_raw()
                p = raw['objective']
                kwargs = {}
                if change == 'map': raw['meta']['map_id'] = 'UnknownMap'
                elif change == 'build': raw['meta']['native_build'] = 98349
                elif change == 'context': raw['meta']['context_source'] = 'replay'
                elif change == 'match': p['match_id'] = 'b' * 64
                elif change == 'local': p['local_id'] = 1
                elif change == 'team': p['team'] = 1
                elif change == 'hero': p['local_hero'] = 'ragnaros'
                elif change == 'source': raw['meta']['source'] = 'dump'
                elif change == 'diagnostic': p['status'] = 'diagnostic_unreleased'
                elif change == 'future': p['mission_t_s'] += 2
                elif change == 'stale': p['mission_t_s'] -= 2
                elif change == 'override': kwargs['map_name'] = 'UnknownMap'
                if change != 'tamper': issue(p, time.monotonic())
                else: p['shrines'][0]['owner'] = 1
                state = snapshot(raw, **kwargs)
                self.assertEqual(len(state['heroes']), 10)
                self.assertNotIn('objective', state)
                self.assertEqual(state['objective_qualification']['status'], 'rejected')
                self.assertEqual(state['objective_qualification']['reason']['code'], 'objective_packet_rejected')

    def test_qualification_age_is_not_a_new_tactical_key(self):
        import copy
        from cerveau.runner import tactical_key
        state = snapshot(dragon_raw())
        changed = copy.deepcopy(state)
        changed['objective_qualification']['age_s'] = .9
        self.assertEqual(tactical_key(state), tactical_key(changed))
        changed['objective']['shrines'][0]['owner'] = 1
        self.assertNotEqual(tactical_key(state), tactical_key(changed))

    def test_durable_schema_rejects_malformed_values_and_qualification(self):
        import copy
        from cerveau.objective_journal import objective_summary
        state = snapshot(dragon_raw())
        mutations = (
            lambda s: s['objective_qualification'].update(age_s=float('nan')),
            lambda s: s['objective_qualification'].update(age_s=1.01),
            lambda s: s['objective_qualification'].update(read_window_s=True),
            lambda s: s['objective_qualification'].update(source='PRIVATE'),
            lambda s: s['objective'].update(t=0),
            lambda s: s['objective'].update(shrines=[]),
            lambda s: s['objective'].update(statue='PRIVATE'),
            lambda s: s['objective']['shrines'][0].update(owner=True),
            lambda s: s['objective']['shrines'][0].update(state='PRIVATE'),
            lambda s: s['objective']['dragon'].update(remaining_s=float('inf')),
            lambda s: s['objective']['start'].update(paused=1),
            lambda s: s['objective'].pop('warning'),
        )
        for mutate in mutations:
            changed = copy.deepcopy(state)
            mutate(changed)
            row = objective_summary(changed)
            self.assertEqual(row['status'], 'rejected')
            self.assertIsNone(row['value'])
            self.assertIsNone(row['age_s'])
            self.assertNotIn('PRIVATE', str(row))

    def test_unselected_volskaya_preserves_qualification_without_claiming_value_export(self):
        from cerveau.objective_journal import objective_summary
        state = snapshot(dragon_raw())
        state['objective']['map_id'] = 'Volskaya'
        row = objective_summary(state)
        self.assertEqual(row['status'], 'normalized')
        self.assertEqual(row['value_status'], 'not_selected')
        self.assertIsNone(row['value'])
        self.assertEqual(row['source_mission_t_s'], 123.5)

    def test_stop_and_new_session_do_not_reuse_objective_or_emit_second_match(self):
        from cerveau.passive_session import run_session
        from test_passive_session import Clock, SyntheticSource
        from hotstate.acquisition import issue
        import time
        first = snapshot(dragon_raw())
        raw = dragon_raw()
        raw['meta']['match_id'] = 'b' * 64
        raw['objective']['match_id'] = 'b' * 64
        raw['objective']['shrines'][0]['owner'] = 1
        issue(raw['objective'], time.monotonic())
        second = snapshot(raw)
        source = SyntheticSource([first, second])
        rows = []; clock = Clock()
        result = run_session(lambda: source, lambda: False, rows.append,
                             duration=10, interval=5, clock=clock, sleep=clock.sleep)
        self.assertEqual(result['reason'], 'session_changed')
        self.assertEqual(result['accepted'], 1)
        values = [r['objective']['value'] for r in rows if r['event'] == 'observation']
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]['shrines'][0]['owner'], first['objective']['shrines'][0]['owner'])
        self.assertTrue(source.closed)
        # New invocation/new source accepts only the new match; no state/cache from the first loop.
        source = SyntheticSource([second]); rows = []; clock = Clock()
        result = run_session(lambda: source, lambda: source.calls > 0, rows.append,
                             duration=10, interval=5, clock=clock, sleep=clock.sleep)
        self.assertEqual(result['reason'], 'stop_file')
        self.assertEqual(result['accepted'], 0)
        self.assertFalse(any(r['event'] == 'observation' for r in rows))
        self.assertTrue(source.closed)
        source = SyntheticSource([second]); rows = []; clock = Clock()
        result = run_session(lambda: source, lambda: False, rows.append,
                             duration=1, interval=5, clock=clock, sleep=clock.sleep)
        self.assertEqual(result['accepted'], 1)
        value = next(r['objective']['value'] for r in rows if r['event'] == 'observation')
        self.assertEqual(value['shrines'][0]['owner'], 1)
        self.assertTrue(source.closed)

    def test_replay_reads_persisted_values_as_history_never_current_permission(self):
        import json
        import tempfile
        from pathlib import Path
        from cerveau import objective_journal
        from cerveau.diagnostics import Journal
        self.assertTrue(callable(getattr(objective_journal, 'replay', None)),
                        'reproducible historical replay missing')
        state = snapshot(dragon_raw())
        rows = []
        Journal(rows.append).observation(state)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'events.jsonl'
            path.write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
            replayed = []
            with patch('hotstate.reader.ProcessBackend', side_effect=AssertionError('no process')):
                result = objective_journal.replay(path, replayed.append)
        self.assertEqual(result, {'lines': 1, 'observations': 1, 'exported_values': 1})
        self.assertEqual(replayed[0]['mode'], 'historical_not_current')
        self.assertEqual(replayed[0]['objective'], rows[0]['objective'])
        self.assertNotIn('acquisition', str(replayed))
        with self.assertRaisesRegex(ValueError, 'aucun compteur'):
            snapshot(replayed[0])

    def test_replay_cli_is_exercised_without_game_and_sanitizes_errors(self):
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        from cerveau.diagnostics import Journal
        rows = []
        Journal(rows.append).observation(snapshot(dragon_raw()))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal.jsonl'
            path.write_text(json.dumps(rows[0]) + '\n', encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', '-m', 'cerveau.objective_journal',
                                     '--journal', str(path)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.strip(), 'CLI does not replay anything')
            replayed = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(replayed[0]['mode'], 'historical_not_current')
            self.assertEqual(replayed[-1]['event'], 'objective_replay_summary')
            self.assertEqual(replayed[-1]['exported_values'], 1)
            path.write_text('PRIVATE invalid JSON 0x12345678', encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', '-m', 'cerveau.objective_journal',
                                     '--journal', str(path)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn('PRIVATE', result.stdout + result.stderr)
            self.assertNotIn(str(path), result.stdout + result.stderr)

    def test_receipt_expiring_between_projection_and_qualification_is_removed(self):
        from hotstate.acquisition import issue
        raw = dragon_raw()
        issue(raw['objective'], 99.75)
        with patch('hotstate.acquisition.time.monotonic', side_effect=[100.0, 101.0]):
            state = snapshot(raw)
        self.assertNotIn('objective', state)
        self.assertEqual(state['objective_qualification']['status'], 'rejected')
        self.assertIsNone(state['objective_qualification']['age_s'])

    def test_replay_bounds_invalid_rows_and_old_journals_fail_closed(self):
        import json
        import tempfile
        from pathlib import Path
        from cerveau.objective_journal import replay
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal.jsonl'
            for content in ('null\n', '[]\n', 'PRIVATE', ' ' * 65537,
                            '{}\n' * 10001,
                            (json.dumps({'event': 'other', 'padding': 'x' * 60000}) + '\n') * 70):
                path.write_text(content, encoding='utf-8')
                with self.subTest(size=len(content)), self.assertRaises(ValueError):
                    replay(path, lambda row: None)
            path.write_text(json.dumps({'event': 'observation', 'objective': {
                'status': 'PRIVATE', 'source': 'PRIVATE',
                'reason': {'code': 'PRIVATE'}, 'value': {'pointer': 'PRIVATE'}}}) + '\n', encoding='utf-8')
            rows = []
            self.assertEqual(replay(path, rows.append)['exported_values'], 0)
            self.assertNotIn('PRIVATE', str(rows))
            self.assertEqual(rows[0]['objective']['status'], 'unknown')
            path.write_text('{"event":"observation"}\n{"event":"acquisition"}\n', encoding='utf-8')
            rows = []
            self.assertEqual(replay(path, rows.append),
                             {'lines': 2, 'observations': 1, 'exported_values': 0})
            self.assertEqual(rows[0]['objective']['status'], 'unknown')
            self.assertIsNone(rows[0]['objective']['value'])

    def test_existing_objective_native_guards_keep_their_closed_refusal_codes(self):
        import ast
        from pathlib import Path
        from hotstate.diagnostics import refusal
        root = Path(__file__).resolve().parents[1]
        missing = []
        for name in ('dragon.py', 'objectives.py'):
            tree = ast.parse((root / 'hotstate' / name).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
                        and isinstance(node.exc.func, ast.Name) and node.exc.func.id == 'NativeUnavailable'
                        and node.exc.args and isinstance(node.exc.args[0], ast.Constant)
                        and type(node.exc.args[0].value) is str):
                    code = node.exc.args[0].value
                    if refusal(code)['code'] != code:
                        missing.append(code)
        self.maxDiff = None
        self.assertEqual(sorted(set(missing)), [], 'existing native reasons collapse to unknown')


if __name__ == '__main__':
    unittest.main()
