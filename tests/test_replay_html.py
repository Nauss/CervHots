"""Rendu de la projection replay, fixtures SYNTHETIC uniquement."""
import io
import json
import os
import subprocess
from html.parser import HTMLParser
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cerveau import replay_debrief
from tests.test_replay_coach_boundary import replay


class ReplayHtmlTests(unittest.TestCase):
    def test_cli_report_is_same_projection_as_default_json(self):
        raw = replay()
        raw['meta'].update(build=1, protocol='protocol00001', protocol_shim=False)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'SYNTHETIC_PRIVATE.StormReplay'
            payload = b'MPQ\x1b SYNTHETIC ONLY'
            source.write_bytes(payload)
            destination = Path(tmp)/'report'
            argv = ['--replay', str(source), '--team', '0', '--perspective',
                    'player-team', '--at', '10']
            outputs = []
            with patch('hotstate.extract.extract', return_value=raw):
                for extra in ([], ['--report-dir', str(destination)]):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        self.assertEqual(replay_debrief.main(argv + extra), 0)
                    outputs.append(output.getvalue())
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual((destination/'report.json').read_text(encoding='utf-8'), outputs[0])
            html = (destination/'REPORT.html').read_text(encoding='utf-8')
            for word in ('Résumé', 'Faits autorisés', 'Inconnues', 'Protocole', 'Jaina', 'CURRENT'):
                self.assertIn(word, html)
            self.assertNotIn('SYNTHETIC_PRIVATE', html)
            self.assertEqual(source.read_bytes(), payload)
            self.assertEqual(sorted(p.name for p in destination.iterdir()), ['REPORT.html', 'report.json'])

    def test_private_future_and_xss_raw_sentinels_never_cross_projection(self):
        from cerveau.replay_html import render
        raw = replay()
        raw['meta'].update(build=1, protocol='protocol00001', protocol_shim=False)
        raw['players'][0]['account'] = 'SYNTHETIC_PRIVATE_ACCOUNT'
        raw['players'][0]['tag'] = '<script>alert("SYNTHETIC_PRIVATE_XSS")</script>'
        raw['final_score'] = 'SYNTHETIC_PRIVATE_FINAL'
        raw['timeline'].setdefault('stat_events', []).append({'t': 11, 'name': 'RavenCurseActivated'})
        report = replay_debrief.build(raw, at=10, team=0, perspective='player-team')
        html = render(report)
        for sentinel in ('SYNTHETIC_PRIVATE', 'RavenCurseActivated', 'positions', 'final_score'):
            self.assertNotIn(sentinel, html + json.dumps(report))
        # Défense supplémentaire : même les chaînes du rapport minimisé sont échappées.
        report['debrief_fr'] = '<script>alert("XSS")</script>\n<img src=x onerror=alert(1)>'
        report['state']['heroes'][0]['hero'] = '<svg onload="XSS">'
        report['knowledge']['objective'] = '<a href="https://invalid/">XSS</a>'
        html = render(report)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&quot;XSS&quot;', html)
        class Tags(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags = []
            def handle_starttag(self, tag, attrs):
                self.tags.append(tag)
                self.assert_safe(attrs)
            def assert_safe(self, attrs):
                if any(k in ('src', 'href') or k.startswith('on') for k, _ in attrs):
                    raise AssertionError('external resource or event handler')
        parsed = Tags()
        parsed.feed(html)
        self.assertFalse(set(parsed.tags) & {'script', 'img', 'svg', 'a', 'iframe', 'audio', 'link'})

    def test_existing_relative_missing_parent_and_source_outputs_are_refused(self):
        from cerveau.replay_html import publish
        raw = replay()
        raw['meta'].update(protocol_shim=False)
        report = replay_debrief.build(raw, at=10, team=0, perspective='player-team')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'source.StormReplay'
            source.write_bytes(b'MPQ\x1b SYNTHETIC')
            for destination in (root, source, root/'absent'/'report', Path('relative-report')):
                with self.subTest(destination=destination), self.assertRaises((OSError, ValueError)):
                    publish(report, destination)
            self.assertEqual(source.read_bytes(), b'MPQ\x1b SYNTHETIC')
            self.assertEqual(list(root.iterdir()), [source])

    def test_junction_output_and_ancestor_are_refused_without_mutation(self):
        if os.name != 'nt':
            self.skipTest('Windows junction')
        from cerveau.replay_html import publish
        raw = replay()
        raw['meta'].update(protocol_shim=False)
        report = replay_debrief.build(raw, at=10, team=0, perspective='player-team')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root/'target'
            target.mkdir()
            junction = root/'junction'
            made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(target)],
                                  capture_output=True)
            self.assertEqual(made.returncode, 0)
            try:
                for destination in (junction, junction/'report'):
                    with self.assertRaises((OSError, ValueError)):
                        publish(report, destination)
                self.assertEqual(list(target.iterdir()), [])
            finally:
                junction.rmdir()

    def test_symlink_destination_and_parent_are_refused(self):
        from cerveau.replay_html import publish
        raw = replay()
        raw['meta'].update(protocol_shim=False)
        report = replay_debrief.build(raw, at=10, team=0, perspective='player-team')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root/'target'
            target.mkdir()
            link = root/'link'
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                if getattr(exc, 'winerror', None) == 1314:
                    self.skipTest('Windows1314 : privilège symlink absent')
                raise
            for destination in (link, link/'report'):
                with self.assertRaises((OSError, ValueError)):
                    publish(report, destination)
            self.assertEqual(list(target.iterdir()), [])

    def test_refused_input_never_creates_html_and_errors_are_closed(self):
        raw = replay()
        raw['meta'].update(protocol_shim=False)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'SYNTHETIC_PRIVATE.StormReplay'
            source.write_bytes(b'MPQ\x1b SYNTHETIC')
            for case in ('missing', 'shim', 'duration', 'identity', 'existing'):
                destination = root/('report-' + case)
                if case == 'existing':
                    destination.mkdir()
                candidate = json.loads(json.dumps(raw))
                if case == 'shim':
                    candidate['meta']['protocol_shim'] = True
                if case == 'duration':
                    candidate['meta']['duration_s'] = None
                if case == 'identity':
                    candidate['local_player'] = {'id': 0, 'hero': 'Jaina', 'team': 1}
                out, err = io.StringIO(), io.StringIO()
                with patch('hotstate.extract.extract', return_value=candidate), redirect_stdout(out), redirect_stderr(err):
                    code = replay_debrief.main(['--replay', str(source if case != 'missing' else root/'absent'),
                        '--team', '0', '--at', '10', '--perspective', 'player-team',
                        '--report-dir', str(destination)])
                self.assertEqual(code, 1, case)
                self.assertEqual(out.getvalue(), '')
                self.assertNotIn('SYNTHETIC_PRIVATE', err.getvalue())
                self.assertEqual(json.loads(err.getvalue())['status'], 'refused')
                self.assertFalse((destination/'REPORT.html').exists())

    def test_partial_write_is_retained_and_cannot_be_resumed(self):
        from cerveau.replay_html import publish
        raw = replay()
        raw['meta'].update(protocol_shim=False)
        report = replay_debrief.build(raw, at=10, team=0, perspective='player-team')
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)/'partial'
            with patch('os.fsync', side_effect=OSError('SYNTHETIC_PRIVATE')):
                with self.assertRaises(OSError):
                    publish(report, destination)
            self.assertTrue(destination.is_dir())
            with self.assertRaises(OSError):
                publish(report, destination)


if __name__ == '__main__':
    unittest.main()
