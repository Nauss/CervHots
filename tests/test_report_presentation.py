"""Presentation-only SYNTHETIC context; never an attestation from journal bytes."""
from html.parser import HTMLParser
import os
from pathlib import Path
import tempfile
import unittest

from tests import test_offline_demo as demo_tests


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_body = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'body':
            self.in_body = True

    def handle_data(self, data):
        if self.in_body:
            self.parts.append(data)


def visible(html):
    parser = VisibleText()
    parser.feed(html)
    return ' '.join(' '.join(parser.parts).split())


class ReportPresentationTests(unittest.TestCase):
    def test_closed_context_rejects_arbitrary_text_and_cannot_attest_schema(self):
        from cerveau import session_html, session_catalog
        for renderer in (session_html.render, session_catalog.render):
            for context in ('<script>attack</script>', 'SYNTHETIC', 1, None, {'current': True}):
                with self.subTest(renderer=renderer.__module__, context=context):
                    with self.assertRaisesRegex(ValueError, 'invalid_presentation_context'):
                        renderer({}, synthetic=context)

    def test_context_does_not_mutate_report_and_dynamic_text_is_escaped(self):
        import copy
        from cerveau import session_html, session_catalog
        from cerveau.session_diagnosis import _diagnose
        from tests.test_core_timeline import long_series
        from tests.test_core_history import project
        records = long_series(1)
        report = dict(history=project(records),
            diagnosis=_diagnose(records, dict(state='complete', records=len(records))))
        attack = '<script>"& attack</script>'
        report['history']['core_timeline']['entries'][0]['journal_ordinal'] = attack
        catalog = dict(sessions=[dict(ordinal=1, state=attack, reason=attack, report=None)],
            discovery=dict(complete=False, limits_reached=[attack], state=attack, refusals=[attack]))
        for renderer, value in ((session_html.render, report), (session_catalog.render, catalog)):
            original = copy.deepcopy(value)
            generic = renderer(value)
            synthetic = renderer(value, synthetic=True)
            self.assertEqual(value, original)
            self.assertNotIn('<script>', synthetic)
            self.assertIn('&lt;script&gt;', synthetic)
            self.assertNotIn('SYNTHETIC — données fictives.', visible(generic))
            self.assertTrue(visible(synthetic).startswith('SYNTHETIC — données fictives.'))
            # Only a fixed presentation notice differs, not the generic schema.
            from cerveau.report_context import synthetic_notice
            self.assertEqual(synthetic.replace(synthetic_notice(True), '', 1), generic)

    @unittest.skipUnless(os.name == 'nt', 'secure Windows catalogue')
    def test_generic_catalog_does_not_infer_context_from_paths_or_record_markers(self):
        import contextlib
        import io
        import json
        from types import SimpleNamespace
        from cerveau import offline_demo, session_catalog, catalog_integrity
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'SYNTHETIC'
            source.mkdir()
            (source/'events.jsonl').write_text(''.join(json.dumps(r)+'\n'
                for r in offline_demo._records('zero')), encoding='utf-8')
            (source/'SYNTHETIC.txt').write_text('SYNTHETIC', encoding='utf-8')
            target = Path(tmp)/'catalog'
            args = SimpleNamespace(sessions_root=source, report_dir=target)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(session_catalog.run(args), 0)
                self.assertEqual(catalog_integrity.run(args), 0)
            pages = list(target.rglob('*.html'))
            self.assertEqual(len(pages), 2)
            for page in pages:
                html = page.read_text(encoding='utf-8')
                self.assertNotIn('SYNTHETIC — données fictives.', visible(html))
                self.assertIn('NON authentifié', visible(html))
            for path in target.rglob('*.json'):
                value = json.loads(path.read_text())
                self.assertNotIn('data_kind', value)
                self.assertNotIn('synthetic', value)

    def test_tables_have_keyboard_scroll_regions_not_document_overflow(self):
        from cerveau import session_html
        from cerveau.session_diagnosis import _diagnose
        from tests.test_core_timeline import long_series
        from tests.test_core_history import project
        records = long_series(3)
        html = session_html.render(dict(history=project(records),
            diagnosis=_diagnose(records, dict(state='complete', records=len(records)))))
        class Tables(HTMLParser):
            def __init__(self):
                super().__init__()
                self.regions = []
                self.table_regions = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'div':
                    self.regions.append(attrs)
                if tag == 'table':
                    self.table_regions.append(self.regions[-1] if self.regions else {})
            def handle_endtag(self, tag):
                if tag == 'div':
                    self.regions.pop()
        tables = Tables()
        tables.feed(html)
        self.assertEqual(len(tables.table_regions), 4)
        for attrs in tables.table_regions:
            self.assertEqual(attrs.get('class'), 'table-scroll')
            self.assertEqual(attrs.get('role'), 'region')
            self.assertEqual(attrs.get('tabindex'), '0')
            self.assertTrue(attrs.get('aria-label'))
        self.assertIn('.table-scroll{max-width:100%;min-width:0;overflow-x:auto}', html)
        self.assertNotIn('overflow:hidden', html)
        self.assertIn('défilement horizontal', visible(html))

    @unittest.skipUnless(os.name == 'nt', 'secure Windows demo publisher')
    def test_every_demo_html_retains_immediate_persistent_synthetic_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)/'innocent-name'
            result = demo_tests.OfflineDemoTests().invoke('--destination', destination)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            pages = sorted(destination.rglob('*.html'))
            self.assertEqual(len(pages), 8)  # index, three linked, four standalone
            for page in pages:
                with self.subTest(page=page.relative_to(destination)):
                    html = page.read_text(encoding='utf-8')
                    text = visible(html)
                    self.assertTrue(text.startswith('SYNTHETIC — données fictives.'), text[:160])
                    self.assertIn('Jamais CURRENT', text)
                    self.assertIn('position:sticky', html)
                    self.assertIn('top:0', html)
                    self.assertNotIn('<script', html)
            verified = demo_tests.OfflineDemoTests().invoke('--verify', destination)
            self.assertEqual(verified.returncode, 0, verified.stdout+verified.stderr)
