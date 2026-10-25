"""SYNTHETIC only: bounded offline catalogue, never native qualification."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from cerveau import passive_session as cli
from cerveau import session_html
from tests.test_native_history import observation, rows


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'SYNTHETIC_PRIVATE'
        self.root.mkdir()
        self.output = self.base/'catalog'

    def journal(self, name='one', records=None, suffix=b''):
        path = self.root/name/'events.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b''.join((json.dumps(r)+'\n').encode() for r in
                                  (rows(observation()) if records is None else records))+suffix)
        return path

    def invoke(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), \
                patch.object(cli, 'preflight', side_effect=AssertionError('no preflight')), \
                patch.object(cli, 'NativeSource', side_effect=AssertionError('no native')):
            code = cli.main(['--catalog', '--sessions-root', str(self.root),
                             '--report-dir', str(self.output)])
        return code, json.loads(stdout.getvalue())

    def test_real_reports_are_independent_deterministic_and_minimized(self):
        self.assertIn('--catalog', cli.parser().format_help())
        a = self.journal('private & hostile')
        bad = rows(observation())
        bad[1]['comparison']['session_token'] = 'bad'
        b = self.journal('secret-folder', bad)
        before = {p: p.read_bytes() for p in (a, b)}
        code, result = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual([r['state'] for r in result['sessions']], ['recorded', 'refused'])
        self.assertFalse(result['current_permission'])
        for entry, source in zip(result['sessions'], (a, b)):
            report = self.output/entry['report']
            self.assertEqual(report.read_text(encoding='utf-8'), session_html.render(session_html.build(source)))
            self.assertEqual(json.loads(report.with_name('report.json').read_text()), session_html.build(source))
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        first = {str(p.relative_to(self.output)): p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
        self.output = self.base/'repeat'
        self.assertEqual(self.invoke()[1], result)
        self.assertEqual(first, {str(p.relative_to(self.output)): p.read_bytes() for p in self.output.rglob('*') if p.is_file()})
        text = json.dumps(result)+(self.output/'INDEX.html').read_text(encoding='utf-8')
        for forbidden in ('private & hostile', 'secret-folder', str(self.root), '<script', '<img', 'file:', 'https:', 'session_aaaaaaaaaaaa'):
            self.assertNotIn(forbidden, text)
        self.assertIn('NON authentifié', text)
        self.assertEqual(json.loads((self.output/'catalog.json').read_text()), result)

    def test_absent_truncated_unclosed_and_unreadable_are_distinct(self):
        from cerveau import session_catalog as cat
        (self.root/'a-missing').mkdir()
        (self.root/'a-missing'/'status.json').write_text('private never read')
        self.journal('b-truncated', suffix=b'{')
        self.journal('c-unclosed', rows(observation())[:-1])
        self.journal('d-unreadable')
        original = cat._read_report
        def denied(path, budget):
            if path.parent.name == 'd-unreadable':
                raise PermissionError('PRIVATE')
            return original(path, budget)
        with patch.object(cat, '_read_report', side_effect=denied):
            code, result = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual([r['state'] for r in result['sessions']], ['absent', 'incomplete', 'incomplete', 'unreadable'])
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_depth_entries_sessions_and_total_bytes_are_hard_limits(self):
        from cerveau import session_catalog as cat
        for constant, value, reason in (('MAX_DEPTH', 0, 'depth_limit'), ('MAX_ENTRIES', 1, 'entries_limit'),
                                        ('MAX_SESSIONS', 1, 'sessions_limit'), ('MAX_TOTAL_BYTES', 1, 'bytes_limit')):
            with self.subTest(constant=constant):
                self.journal('a')
                self.journal('b')
                self.output = self.base/constant
                with patch.object(cat, constant, value):
                    code, result = self.invoke()
                self.assertEqual(code, 1)
                self.assertFalse(result['discovery']['complete'])
                self.assertIn(reason, result['discovery']['limits_reached'])
                for entry in result['sessions']:
                    if entry['report']:
                        self.assertTrue((self.output/entry['report']).is_file())

    def test_output_overlap_existing_and_relative_arguments_refuse_without_mutation(self):
        self.journal()
        for target in (self.root/'nested', self.root, self.base, self.base/'existing'):
            if target.name == 'existing':
                target.mkdir()
            self.output = target
            self.assertEqual(self.invoke()[0], 1)
        for args in (['--catalog'], ['--catalog', '--sessions-root', 'relative', '--report-dir', str(self.output)],
                     ['--catalog', '--sessions-root', str(self.root), '--report-dir', 'relative'],
                     ['--catalog', '--sessions-root', str(self.root), '--report-dir', str(self.output), '--journal', str(self.root/'events.jsonl')],
                     ['--catalog', '--report-html'], ['--sessions-root', str(self.root)]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                cli.main(args)
            self.assertEqual(error.exception.code, 2)

    def test_partial_write_and_concurrent_target_never_publish_false_index(self):
        from cerveau import session_catalog as cat
        self.journal()
        with patch('os.fsync', side_effect=OSError('PRIVATE')):
            self.assertEqual(self.invoke()[0], 1)
        self.assertFalse((self.output/'INDEX.html').exists())
        self.assertFalse((self.output/'catalog.json').exists())
        self.output = self.base/'concurrent'
        original = cat._reserve
        def competitor(target):
            target.mkdir()
            (target/'sentinel').write_text('untouched')
            return original(target)
        with patch.object(cat, '_reserve', side_effect=competitor):
            self.assertEqual(self.invoke()[0], 1)
        self.assertEqual([p.name for p in self.output.iterdir()], ['sentinel'])
        self.assertEqual(set(p.name for p in self.base.iterdir()), {'SYNTHETIC_PRIVATE', 'catalog', 'concurrent'})

    @unittest.skipUnless(os.name == 'nt', 'real Windows reparse and sharing semantics')
    def test_real_windows_junction_is_not_followed_in_root_tree_or_output(self):
        self.journal('original')
        junction = self.root/'a-junction'
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(self.root/'original')], check=True, capture_output=True)
        self.addCleanup(lambda: os.rmdir(junction) if junction.exists() else None)
        code, result = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual([r['state'] for r in result['sessions']], ['blocked', 'recorded'])
        self.assertEqual(result['sessions'][0]['reason'], 'reparse_point')
        self.root = junction
        self.output = self.base/'root-link'
        self.assertEqual(self.invoke()[0], 1)
        self.root = self.base/'SYNTHETIC_PRIVATE'
        link_parent = self.base/'output-junction'
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(link_parent), str(self.root/'original')], check=True, capture_output=True)
        self.addCleanup(lambda: os.rmdir(link_parent) if link_parent.exists() else None)
        self.output = link_parent/'new'
        self.assertEqual(self.invoke()[0], 1)
        self.assertFalse((self.root/'original'/'new').exists())

    def test_no_sessions_and_discovery_refusals_are_explicit(self):
        code, result = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(result['discovery']['state'], 'no_sessions_found')
        self.assertEqual(result['sessions'], [])
        self.output = self.base/'unreadable-directory'
        from cerveau import session_catalog as cat
        original = os.scandir
        def denied(path):
            if Path(path) == self.root:
                raise PermissionError('SYNTHETIC_PRIVATE')
            return original(path)
        with patch.object(cat.os, 'scandir', side_effect=denied):
            code, result = self.invoke()
        self.assertEqual(code, 1)
        self.assertFalse(result['discovery']['complete'])
        self.assertEqual(result['discovery']['refusals'], ['directory_unavailable'])

    @unittest.skipUnless(os.name == 'nt', 'Windows handle protection')
    def test_pinned_directory_and_journal_cannot_be_substituted_or_written(self):
        from cerveau import session_catalog as cat
        source = self.journal()
        with cat._pin(source.parent, directory=True):
            with self.assertRaises(PermissionError):
                source.parent.rename(self.root/'moved')
        before = source.read_bytes()
        with cat._pin(source):
            with self.assertRaises(PermissionError):
                source.write_bytes(b'PRIVATE')
            with self.assertRaises(PermissionError):
                source.unlink()
        self.assertEqual(source.read_bytes(), before)

    @unittest.skipUnless(os.name == 'nt', 'Windows no-follow symlink')
    def test_file_symlink_is_not_ingested(self):
        self.journal('original')
        linked = self.root/'a-symlink'
        linked.mkdir()
        try:
            os.symlink(self.root/'original'/'events.jsonl', linked/'events.jsonl')
        except OSError as exc:
            self.skipTest('Windows symlink privilege unavailable: '+str(exc.winerror))
        code, result = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual([r['state'] for r in result['sessions']], ['blocked', 'recorded'])

    def test_hardlink_is_not_ingested(self):
        self.journal('original')
        hard = self.root/'b-hardlink'
        hard.mkdir()
        os.link(self.root/'original'/'events.jsonl', hard/'events.jsonl')
        code, result = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual([r['state'] for r in result['sessions']], ['unreadable', 'unreadable'])
        for entry in result['sessions']:
            self.assertIsNone(entry['report'])

    def test_parser_limits_unchanged_and_partial_fsync_abort_whole_transaction(self):
        from cerveau import session_catalog as cat
        source = self.journal()
        source.write_bytes(b'x'*(4*2**20+1))
        code, result = self.invoke()
        self.assertEqual(code, 1)
        report = json.loads((self.output/result['sessions'][0]['report']).with_name('report.json').read_text())
        self.assertEqual(report['history']['journal']['state'], 'limit_exceeded')
        self.assertEqual(report['history']['journal']['bytes_limit'], 4*2**20)
        self.assertLessEqual(result['discovery']['journal_bytes_charged'], cat.MAX_TOTAL_BYTES)
        self.output = self.base/'late-fsync'
        self.journal()
        fsync = os.fsync
        calls = []
        def late(fd):
            calls.append(fd)
            if len(calls) == 2:
                raise OSError('SYNTHETIC failure after one complete file')
            return fsync(fd)
        with patch('os.fsync', side_effect=late):
            self.assertEqual(self.invoke()[0], 1)
        self.assertFalse((self.output/'INDEX.html').exists())
        self.assertFalse((self.output/'catalog.json').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows output-junction substitution')
    def test_output_subdirectory_substitution_never_writes_private_target(self):
        self.journal()
        destination = self.base/'private-destination'
        destination.mkdir()
        original = Path.mkdir
        def substituted(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path.parent == self.output and path.name == 'session-001':
                path.rmdir()
                subprocess.run(['cmd', '/c', 'mklink', '/J', str(path), str(destination)],
                               check=True, capture_output=True)
            return result
        self.addCleanup(lambda: os.rmdir(self.output/'session-001')
                        if (self.output/'session-001').exists() else None)
        with patch.object(Path, 'mkdir', new=substituted):
            self.assertEqual(self.invoke()[0], 1)
        self.assertEqual(list(destination.iterdir()), [])
        self.assertFalse((self.output/'INDEX.html').exists())

    def test_unclosed_acquisition_only_stream_is_incomplete_not_a_complete_refusal(self):
        acquisition = rows(observation())[0]
        self.journal(records=[acquisition])
        code, result = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(result['sessions'][0]['state'], 'incomplete')

    def test_canonical_alias_overlap_is_refused_before_reservation(self):
        self.journal()
        original = Path.resolve
        def aliased(path, *args, **kwargs):
            if path == self.output.parent:
                return self.root
            return original(path, *args, **kwargs)
        with patch.object(Path, 'resolve', new=aliased):
            self.assertEqual(self.invoke()[0], 1)
        self.assertFalse(self.output.exists())

    def test_two_independent_valid_identities_do_not_merge_or_authorize_each_other(self):
        first = self.journal('a')
        other = observation()
        other['session'] = 'session_'+'c'*12
        other['comparison']['session_token'] = 'd'*32
        other['mission_t_s'] = 51.
        second = self.journal('b', rows(other))
        code, result = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual([r['state'] for r in result['sessions']], ['recorded', 'recorded'])
        for source, entry in zip((first, second), result['sessions']):
            report = json.loads((self.output/entry['report']).with_name('report.json').read_text())
            self.assertEqual(report, session_html.build(source))
        self.assertNotIn('session_'+ 'c'*12, json.dumps(result))

    def test_real_concurrent_cli_invocations_only_one_owns_the_output(self):
        import sys
        self.journal()
        helper = Path(__file__).parent/'helpers'/'native_history_offline.py'
        command = [sys.executable, '-B', str(helper), '--catalog', '--sessions-root',
                   str(self.root), '--report-dir', str(self.output)]
        children = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        for child in children:
            stdout, stderr = child.communicate(timeout=30)
            self.assertEqual(stderr, b'')
            self.assertIn(json.loads(stdout)['event'], ('session_catalog', 'session_catalog_error'))
        self.assertEqual(sorted(child.returncode for child in children), [0, 1])
        result = json.loads((self.output/'catalog.json').read_text())
        self.assertEqual(len(result['sessions']), 1)
        self.assertTrue((self.output/result['sessions'][0]['report']).is_file())

    def test_remote_drive_is_rejected_before_any_handle_or_output(self):
        from cerveau import session_catalog as cat
        with patch.object(cat, '_drive_type', return_value=4), \
                patch.object(cat, '_pin', side_effect=AssertionError('no remote open')):
            self.assertEqual(self.invoke()[0], 1)
        self.assertFalse(self.output.exists())

    def test_entry_enumeration_never_pulls_past_the_hard_cap(self):
        from cerveau import session_catalog as cat
        for i in range(6):
            (self.root/str(i)).write_bytes(b'')
        original = os.scandir
        pulled = []
        @contextlib.contextmanager
        def counted(path):
            with original(path) as iterator:
                def entries():
                    for entry in iterator:
                        if Path(path) == self.root:
                            pulled.append(entry.name)
                        yield entry
                yield entries()
        with patch.object(cat, 'MAX_ENTRIES', 3), patch.object(cat.os, 'scandir', side_effect=counted):
            code, result = self.invoke()
        self.assertEqual(code, 1)
        self.assertLessEqual(len(pulled), 3)
        self.assertEqual(result['discovery']['entries_examined'], len(pulled))

    def test_catalog_renderer_escapes_every_dynamic_text(self):
        from cerveau import session_catalog as cat
        self.journal()
        result = self.invoke()[1]
        result['sessions'][0]['reason'] = '<script>"hostile"</script>'
        rendered = cat.render(result)
        self.assertIn('&lt;script&gt;&quot;hostile&quot;&lt;/script&gt;', rendered)
        self.assertNotIn('<script>', rendered)


if __name__ == '__main__':
    unittest.main()
