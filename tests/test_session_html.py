"""SYNTHETIC records only; offline rendering is not native/HUD qualification."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cerveau import passive_session as product
from tests.test_native_history import observation, rows


class SessionHtmlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input' / 'events.jsonl'
        self.source.parent.mkdir()
        self.output = self.root / 'report'

    def invoke(self, records=None, suffix=b''):
        if records is not None:
            self.source.write_bytes(b''.join((json.dumps(r)+'\n').encode() for r in records)+suffix)
        before = self.source.read_bytes()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                patch.object(product, 'preflight', side_effect=AssertionError('no preflight')), \
                patch.object(product, 'NativeSource', side_effect=AssertionError('no native source')):
            code = product.main(['--report-html', '--journal', str(self.source),
                                 '--report-dir', str(self.output)])
        self.assertEqual(before, self.source.read_bytes())
        return code, out.getvalue(), err.getvalue()

    def test_failed_fsync_never_publishes_a_partial_directory(self):
        with patch('os.fsync', side_effect=OSError('SYNTHETIC disk failure')):
            code, stdout, _ = self.invoke(rows(observation()))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout)['event'], 'session_html_error')
        self.assertFalse(self.output.exists())
        self.assertEqual(set(p.name for p in self.root.iterdir()), {'input'})

    def test_later_refusal_is_visible_without_renewing_the_last_observation(self):
        records = rows(observation())
        records.insert(-1, dict(schema_version=1, sequence=3, cycle=2,
                                event='refusal', code='native_reader_unavailable'))
        records[-1].update(sequence=4, cycle=2)
        code, _, _ = self.invoke(records)
        self.assertEqual(code, 0)
        html = (self.output/'REPORT.html').read_text(encoding='utf-8')
        self.assertIn('Refus ou erreur après cette observation : oui', html)
        self.assertIn('Fenêtre de lecture originale', html)
        self.assertIn('0.005', html)

    def test_cli_creates_useful_minimized_self_contained_french_report(self):
        from cerveau.native_history import summarize
        from cerveau.session_diagnosis import diagnose
        code, stdout, stderr = self.invoke(rows(observation()))
        self.assertEqual(code, 0)
        result = json.loads((self.output/'report.json').read_text(encoding='utf-8'))
        html = (self.output/'REPORT.html').read_text(encoding='utf-8')
        self.assertEqual(result['history'], summarize(self.source))
        self.assertEqual(result['diagnosis']['counts'], diagnose(self.source)['counts'])
        self.assertEqual(json.loads(stdout), result)
        self.assertEqual(stderr, '')
        for expected in ('lang="fr"', 'NON authentifié', 'choix natif 2',
                         'Niveaux publics', 'Dernière observation', 'Non sélectionné',
                         'inconnu', 'Jamais CURRENT', 'Activité actuelle inconnue'):
            self.assertIn(expected, html)
        # Exact selected catalog identity is now an intentional, traced field.
        self.assertIn('BarbarianWarPaint', html)
        self.assertIn('documentaire seulement', html)
        for forbidden in ('<script', '<img', '<audio', '<iframe', 'https://', 'C:/', 'session_aaaaaaaaaaaa'):
            self.assertNotIn(forbidden, html)
        self.assertEqual(set(p.name for p in self.output.iterdir()), {'report.json', 'REPORT.html'})

    def test_selection_absent_invalid_unselected_and_refused_stay_distinct(self):
        for selection, expected in ((None, 'unknown'), (False, 'unknown'), ([], 'unknown'),
                                    ('invalid', 'unknown'), ('talents', 'not_selected')):
            with self.subTest(selection=selection):
                records = rows(observation())
                records[0]['collection'] = selection
                if selection == 'talents':
                    records[1]['available_fields'] = ['heroes']
                self.output = self.root / ('case-'+str(len(list(self.root.iterdir()))))
                code, _, _ = self.invoke(records)
                result = json.loads((self.output/'report.json').read_text())['history']
                self.assertEqual(code, 0)
                self.assertEqual(result['talents']['status'], expected)
                self.assertIsNone(result['talents']['local'])
                self.assertIsNone(result['talents']['original_age_s'])
                self.assertEqual(result['public_levels']['by_team'], [1, 2])
        obs = observation()
        obs['talents']['status'] = 'refused'
        self.output = self.root/'refused-family'
        self.invoke(rows(obs))
        self.assertIn('Refusé', (self.output/'REPORT.html').read_text(encoding='utf-8'))

    def test_qualified_synthetic_objective_is_french_without_invented_zero(self):
        obs = observation()
        obs['available_fields'].append('objective')
        obs['objective'] = dict(status='normalized', source='native_player',
            source_mission_t_s=41., age_s=.02, read_window_s=.01,
            family='dragon', value_status='exported', value=dict(phase='shrines',
                shrines=[dict(id=s, owner=None, state='unknown', contested=None) for s in ('sun', 'moon')],
                statue=dict(state='unknown', team=None, channeling=None),
                dragon=dict(state='unknown', team=None, remaining_s=None),
                start=dict(remaining_s=None, paused=False),
                respawn=dict(remaining_s=None, paused=False), warning=dict(remaining_s=None, paused=False)))
        records = rows(obs)
        records[0]['collection'] = 'all'
        code, _, _ = self.invoke(records)
        self.assertEqual(code, 0)
        result = json.loads((self.output/'report.json').read_text())
        self.assertEqual(result['history']['objective']['status'], 'normalized')
        self.assertIsNone(result['history']['objective']['value']['dragon']['remaining_s'])
        html = (self.output/'REPORT.html').read_text(encoding='utf-8')
        self.assertIn('Soleil', html)
        self.assertIn('Temps restant (s)', html)
        self.assertNotIn('remaining_s', html)

    def test_mixed_context_and_bad_talent_provenance_never_salvage_values(self):
        first, second = observation(1), observation(2)
        second['comparison']['session_token'] = 'f'*32
        code, _, _ = self.invoke(rows(first, second))
        self.assertEqual(code, 1)
        result = json.loads((self.output/'report.json').read_text())
        self.assertIsNone(result['history']['instant'])
        self.assertIsNone(result['history']['talents'])
        self.assertNotIn('choix natif', (self.output/'REPORT.html').read_text(encoding='utf-8'))
        self.output = self.root/'unknown-age'
        obs = observation()
        obs['talents']['age_s'] = None
        self.invoke(rows(obs))
        self.assertIsNone(json.loads((self.output/'report.json').read_text())['history']['talents']['local'])

    def test_truncated_oversize_and_invalid_stream_export_refusal_not_session_totals(self):
        for name, data, state in (
                ('truncated', b'{"event":', 'truncated'),
                ('oversize', b'x'*(4*2**20+1), 'limit_exceeded'),
                ('invalid', b'not json\n', 'invalid'),
                ('long-line', b'x'*65537+b'\n', 'limit_exceeded')):
            with self.subTest(name=name):
                self.source.write_bytes(data)
                self.output = self.root/name
                code, _, _ = self.invoke()
                self.assertEqual(code, 1)
                result = json.loads((self.output/'report.json').read_text())
                self.assertEqual(result['history']['journal']['state'], state)
                self.assertIsNone(result['diagnosis']['total_acquisitions'])
                self.assertIn('totaux de session inconnus', (self.output/'REPORT.html').read_text(encoding='utf-8'))

    def test_hostile_raw_values_are_dropped_and_every_rendered_value_is_escaped(self):
        from cerveau.session_html import build, render
        hostile = '<script>alert("SYNTHETIC_PRIVATE")</script>'
        obs = observation()
        obs.update(path='C:/SYNTHETIC_PRIVATE', player=hostile)
        obs['talents']['value']['players'][0]['tiers'][0]['label'] = hostile
        self.invoke(rows(obs))
        for file in self.output.iterdir():
            self.assertNotIn('SYNTHETIC_PRIVATE', file.read_text(encoding='utf-8'))
        # Renderer defense in depth: even a hostile already projected value is text.
        result = build(self.source)
        result['history']['talents']['local']['hero'] = hostile
        result['diagnosis']['refusal_codes'] = {hostile: 1}
        html = render(result)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&quot;', html)

    def test_one_bounded_read_and_byte_determinism(self):
        from cerveau import session_diagnosis
        with patch.object(session_diagnosis, '_bounded', wraps=session_diagnosis._bounded) as bounded:
            self.invoke(rows(observation()))
        self.assertEqual(bounded.call_count, 1)
        first = {p.name: p.read_bytes() for p in self.output.iterdir()}
        self.output = self.root/'repeat'
        self.invoke()
        self.assertEqual(first, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_existing_directory_file_and_overlap_are_never_modified(self):
        self.source.write_text('invalid\n')
        for name, directory in (('empty', True), ('occupied', True), ('file', False)):
            self.output = self.root/name
            if directory:
                self.output.mkdir()
                if name == 'occupied':
                    (self.output/'REPORT.html').write_text('SYNTHETIC sentinel')
            else:
                self.output.write_text('SYNTHETIC sentinel')
            before = ({p.name: p.read_bytes() for p in self.output.iterdir()} if directory else self.output.read_bytes())
            code, _, _ = self.invoke()
            self.assertEqual(code, 1)
            after = ({p.name: p.read_bytes() for p in self.output.iterdir()} if directory else self.output.read_bytes())
            self.assertEqual(before, after)
        self.output = self.source.parent/'nested'
        self.assertEqual(self.invoke()[0], 1)
        self.assertFalse(self.output.exists())

    def test_publication_race_refuses_even_a_competing_empty_directory(self):
        from cerveau import session_html
        original = session_html._rename_new
        def competitor(source, target):
            target.mkdir()
            return original(source, target)
        with patch.object(session_html, '_rename_new', side_effect=competitor):
            self.assertEqual(self.invoke(rows(observation()))[0], 1)
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertEqual(set(p.name for p in self.root.iterdir()), {'input', 'report'})

    def test_argument_guards_refuse_live_paths_visual_references_relative_and_other_modes(self):
        base = ['--report-html', '--journal', str(self.source), '--report-dir', str(self.output)]
        for extra in (['--live'], ['--summarize'], ['--diagnose'], ['--status'], ['--preflight'],
                      ['--player-file', str(self.root/'private')],
                      ['--output-dir', str(self.root/'live')],
                      ['--stop-file', str(self.root/'STOP')],
                      ['--visual-reference', str(self.root/'clip.zip')],
                      ['--journal', 'relative.jsonl'], ['--report-dir', 'relative']):
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                product.main(base+extra)
            self.assertEqual(raised.exception.code, 2)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
