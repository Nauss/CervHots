"""Débrief hors ligne : fixtures exclusivement SYNTHETIC, aucun compte réel."""
import copy
import importlib
import json
import unittest
import io
import tempfile
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from tests.test_replay_coach_boundary import replay


class DebriefTests(unittest.TestCase):
    def test_public_debrief_reuses_projection_without_private_or_future_data(self):
        self.assertIsNotNone(importlib.util.find_spec('cerveau.replay_debrief'),
                             'commande débrief autonome manquante')
        module = importlib.import_module('cerveau.replay_debrief')
        raw = replay()
        raw['meta'].update(build=1, protocol='protocol00001', protocol_shim=False)
        raw['timeline']['hero_events'].append(
            {'t': 20, 'type': 'death', 'player': 'SYNTHETIC_PRIVATE_ALLY'})
        raw['final_score'] = {'private': 'SYNTHETIC_PRIVATE_FUTURE'}
        original = copy.deepcopy(raw)
        result = module.build(raw, at=10, team=0, perspective='player-team')
        self.assertEqual(result, module.build(raw, at=10, team=0, perspective='player-team'))
        self.assertEqual(raw, original)
        text = json.dumps(result, ensure_ascii=False)
        self.assertNotIn('SYNTHETIC_PRIVATE', text)
        self.assertNotIn('positions', text)
        self.assertNotIn('final_score', text)
        self.assertEqual(result['state']['heroes'][0]['alive'], True)
        self.assertIn('Jaina', result['debrief_fr'])
        self.assertIn('équipe 0', result['debrief_fr'])
        self.assertIn('historique', result['debrief_fr'])
        self.assertEqual(result['knowledge']['source'], 'kb/data/map_timings.json')
        self.assertIsNotNone(result['knowledge']['objective'])

    def test_ambiguous_selection_duration_and_shim_are_refused(self):
        from cerveau.replay_debrief import build
        baseline = replay()
        baseline['meta'].update(build=1, protocol='protocol00001', protocol_shim=False)
        for field, value in [('duration_s', None), ('duration_s', True),
                             ('duration_s', float('nan')), ('duration_s', -1),
                             ('protocol_shim', True), ('protocol_shim', None)]:
            with self.subTest(field=field, value=value):
                raw = copy.deepcopy(baseline)
                raw['meta'][field] = value
                with self.assertRaises(ValueError):
                    build(raw, at=10, team=0, perspective='player-team')
        for options in [dict(at=None, team=0, perspective='player-team'),
                        dict(at=-1, team=0, perspective='player-team'),
                        dict(at=901, team=0, perspective='player-team'),
                        dict(at=float('inf'), team=0, perspective='player-team'),
                        dict(at=True, team=0, perspective='player-team'),
                        dict(at=10, team=None, perspective='player-team'),
                        dict(at=10, team=True, perspective='player-team'),
                        dict(at=10, team=2, perspective='player-team'),
                        dict(at=10, team=0, perspective=None),
                        dict(at=10, team=0, perspective='observer')]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                build(baseline, **options)

    def test_shim_partial_catalog_and_unknown_fields_remain_explicit(self):
        from cerveau.replay_debrief import build
        raw = replay()
        raw['meta'].update(build=98348, protocol='protocol91756', protocol_shim=True,
                           map='SYNTHETIC_PRIVATE_UNKNOWN_MAP')
        raw['players'][1]['hero'] = 'SYNTHETIC_PRIVATE_UNKNOWN_HERO'
        raw['timeline'] = {}
        report = build(raw, at=10, team=0, perspective='player-team', allow_protocol_shim=True)
        self.assertTrue(report['provenance']['protocol_shim'])
        self.assertEqual(report['provenance']['fidelity'], 'unverified_protocol_shim')
        self.assertIsNone(report['knowledge']['objective'])
        self.assertIsNone(report['map'])
        self.assertEqual(report['coverage']['roster_slots'], 2)
        self.assertEqual(report['coverage']['recognized_heroes'], 1)
        self.assertIsNone(report['state']['heroes'][0]['alive'])
        self.assertIsNone(report['state']['heroes'][0]['level'])
        self.assertIsNone(report['coverage']['objective_state'])
        self.assertIn('incomplète', report['debrief_fr'])
        self.assertIn('SHIM', report['debrief_fr'])
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(report))

    def test_public_objective_announcements_are_not_current_objective_state(self):
        from cerveau.replay_debrief import build
        raw = replay()
        raw['meta'].update(build=1, protocol='protocol00001', protocol_shim=False)
        raw['timeline']['stat_events'] = [
            {'t': 2, 'name': 'TributeCollected', 'data': {'TeamID': 8192}},
            {'t': 11, 'name': 'RavenCurseActivated', 'data': {'TeamID': 8192}}]
        report = build(raw, at=10, team=0, perspective='player-team')
        self.assertIn('TributeCollected', report['debrief_fr'])
        self.assertNotIn('RavenCurseActivated', json.dumps(report))
        self.assertIsNone(report['coverage']['objective_state'])

    def test_cli_requires_explicit_selection_before_opening_any_source(self):
        from cerveau import replay_debrief as module
        self.assertTrue(callable(getattr(module, 'main', None)), 'CLI locale manquante')
        for argv in [[], ['--replay', 'private.StormReplay'],
                     ['--replay', 'private.StormReplay', '--team', '0', '--at', '1'],
                     ['--replay', 'private.StormReplay', '--team', '0', '--at', '-1',
                      '--perspective', 'player-team'],
                     ['--replay', 'private.StormReplay', '--team', '2', '--at', '1',
                      '--perspective', 'player-team'],
                     ['--replay', 'private.StormReplay', '--team', '0', '--at', 'nan',
                      '--perspective', 'player-team'],
                     ['--replay', 'private.StormReplay', '--team', '0', '--at', '1',
                      '--perspective', 'observer']]:
            with self.subTest(argv=argv), patch('hotstate.extract.extract') as extract:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    module.main(argv)
                self.assertEqual(caught.exception.code, 2)
                extract.assert_not_called()

    def test_cli_is_local_read_only_minimized_and_deterministic(self):
        from cerveau import replay_debrief as module
        self.assertTrue(callable(getattr(module, 'main', None)), 'CLI locale manquante')
        raw = replay()
        raw['meta'].update(build=1, protocol='protocol00001', protocol_shim=False)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'SYNTHETIC_PRIVATE.StormReplay'
            payload = b'MPQ\x1b SYNTHETIC TEST ONLY'
            path.write_bytes(payload)
            argv = ['--replay', str(path), '--team', '0', '--at', '10',
                    '--perspective', 'player-team']
            outputs = []
            with ExitStack() as stack:
                for target in ['socket.socket', 'socket.create_connection',
                               'grocoapi.GrocoClient.__init__', 'cerveau.brain.Coach.__init__']:
                    stack.enter_context(patch(target, side_effect=AssertionError('forbidden IO')))
                stack.enter_context(patch('hotstate.extract.extract', return_value=raw))
                for _ in range(2):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        self.assertEqual(module.main(argv), 0)
                    outputs.append(output.getvalue())
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(path.read_bytes(), payload)
            report = json.loads(outputs[0])
            self.assertRegex(report['provenance']['replay_sha256'], '^[a-f0-9]{64}$')
            self.assertNotIn('SYNTHETIC_PRIVATE', outputs[0])
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), [path.name])

    def test_invalid_file_refused_before_decoder_without_echoing_private_path(self):
        from cerveau.replay_debrief import main
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'SYNTHETIC_PRIVATE.StormReplay'
            path.write_bytes(b'SYNTHETIC_PRIVATE not an MPQ')
            output, error = io.StringIO(), io.StringIO()
            with patch('hotstate.extract.extract') as extract:
                with redirect_stdout(output), redirect_stderr(error):
                    code = main(['--replay', str(path), '--team', '0', '--at', '10',
                                 '--perspective', 'player-team'])
                extract.assert_not_called()
            self.assertEqual(code, 1)
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(json.loads(error.getvalue())['reason'], 'fichier_replay_invalide')
            self.assertNotIn('SYNTHETIC_PRIVATE', error.getvalue())

    def test_decoder_errors_changed_inputs_and_oversize_files_fail_closed(self):
        from cerveau.replay_debrief import main
        for case in ('decoder', 'changed', 'empty', 'oversize', 'missing', 'directory'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'SYNTHETIC_PRIVATE.StormReplay'
                if case == 'directory':
                    path.mkdir()
                elif case != 'missing':
                    path.write_bytes(b'' if case == 'empty' else b'MPQ\x1b SYNTHETIC')
                raw = replay()
                raw['meta'].update(build=1, protocol='protocol00001', protocol_shim=False)
                def decode(_):
                    if case == 'decoder':
                        raise ValueError('SYNTHETIC_PRIVATE_DECODER_ERROR')
                    if case == 'changed':
                        path.write_bytes(b'MPQ\x1b CHANGED SYNTHETIC')
                    return raw
                out, err = io.StringIO(), io.StringIO()
                with patch('hotstate.extract.extract', side_effect=decode), \
                        patch('cerveau.replay_debrief.MAX_REPLAY_BYTES', 4 if case == 'oversize' else 1024), \
                        redirect_stdout(out), redirect_stderr(err):
                    self.assertEqual(main(['--replay', str(path), '--team', '0', '--at', '10',
                                           '--perspective', 'player-team']), 1)
                self.assertEqual(out.getvalue(), '')
                self.assertEqual(json.loads(err.getvalue())['status'], 'refused')
                self.assertNotIn('SYNTHETIC_PRIVATE', err.getvalue())

    def test_conflicting_local_identity_is_not_overridden_by_team_flag(self):
        from cerveau.replay_debrief import build
        raw = replay()
        raw['meta'].update(build=1, protocol='protocol00001', protocol_shim=False)
        raw['local_player'] = {'id': 0, 'hero': 'Jaina', 'team': 0}
        with self.assertRaises(ValueError):
            build(raw, at=10, team=1, perspective='player-team')

    def test_untrusted_metadata_cannot_cross_provenance_boundary(self):
        from cerveau.replay_debrief import build
        raw = replay()
        raw['meta'].update(build={'secret': 'SYNTHETIC_PRIVATE'},
                           protocol='SYNTHETIC_PRIVATE', protocol_shim=False)
        result = build(raw, at=10, team=0, perspective='player-team')
        self.assertIsNone(result['provenance']['build'])
        self.assertIsNone(result['provenance']['protocol'])
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
