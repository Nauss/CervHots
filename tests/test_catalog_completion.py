"""SYNTHETIC disk publication checks; no historical/native qualification."""
import hashlib
import json
import contextlib
import io
import copy
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from cerveau import catalog_integrity as integrity
from tests import test_session_catalog as fixtures
from cerveau import passive_session as cli


class CompletionPublicationTests(unittest.TestCase):
    setUp = fixtures.CatalogTests.setUp
    journal = fixtures.CatalogTests.journal
    invoke = fixtures.CatalogTests.invoke

    def verify(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(['--verify-catalog', '--report-dir', str(self.output)])
        return code, json.loads(stdout.getvalue())

    def test_verifier_distinguishes_complete_legacy_and_damaged_read_only(self):
        self.assertIn('--verify-catalog', cli.parser().format_help())
        self.journal()
        self.assertEqual(self.invoke()[0], 0)
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.output.rglob('*') if p.is_file()}
        code, value = self.verify()
        self.assertEqual(code, 0)
        self.assertEqual(value['state'], 'complete')
        self.assertFalse(value['authenticated'])
        self.assertFalse(value['current_permission'])
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
        (self.output/'INDEX.html').write_bytes(b'tampered')
        self.assertEqual(self.verify()[0], 3)
        (self.output/'COMPLETE.json').unlink()
        code, value = self.verify()
        self.assertEqual(code, 4)
        self.assertEqual(value['state'], 'unverifiable')

    def test_truncated_marker_at_json_boundary_is_refused(self):
        self.journal()
        self.invoke()
        marker = self.output/'COMPLETE.json'
        raw = marker.read_bytes()
        self.assertTrue(raw.endswith(b'\n'))
        marker.write_bytes(raw[:-1])
        self.assertIsInstance(json.loads(marker.read_bytes()), dict)
        self.assertEqual(self.verify()[0], 3, 'a truncated final newline is not a complete marker')
        marker.write_bytes(raw)
        self.assertEqual(self.verify()[0], 0)

    def test_marker_requires_canonical_key_order(self):
        self.journal()
        self.invoke()
        marker = self.output/'COMPLETE.json'
        value = json.loads(marker.read_bytes())
        reordered = dict(files=value['files'], schema_version=1, event=value['event'])
        marker.write_bytes(integrity.catalog._dump(reordered).encode('utf-8'))
        self.assertEqual(self.verify()[0], 3)

    def test_refusals_absence_and_empty_discovery_can_be_complete_publications(self):
        for case in ('refused', 'absent', 'empty'):
            with self.subTest(case=case):
                self.output = self.base/case
                if case == 'refused':
                    self.journal(records=[])
                elif case == 'absent':
                    (self.root/'one'/'events.jsonl').unlink()
                    (self.root/'one'/'status.json').write_text('SYNTHETIC private not exported')
                else:
                    (self.root/'one'/'status.json').unlink()
                self.assertEqual(self.invoke()[0], 1)
                self.assertEqual(self.verify()[0], 0)

    def test_each_payload_or_marker_fsync_failure_prevents_valid_marker(self):
        self.journal()
        for failure in range(1, 6):
            with self.subTest(failure=failure):
                self.output = self.base/('fail-%d' % failure)
                original = os.fsync
                calls = []
                def failed(fd):
                    calls.append(fd)
                    if len(calls) == failure:
                        raise OSError('SYNTHETIC flush failure')
                    return original(fd)
                with patch('os.fsync', side_effect=failed):
                    self.assertEqual(self.invoke()[0], 1)
                self.assertFalse((self.output/'COMPLETE.json').exists())
                self.assertEqual(self.verify()[0], 4)

    def test_marker_schema_attacks_refuse_without_opening_injected_paths(self):
        self.journal()
        self.invoke()
        marker = self.output/'COMPLETE.json'
        good = json.loads(marker.read_bytes())
        mutations = []
        def changed(key, value):
            item = copy.deepcopy(good)
            item[key] = value
            mutations.append(json.dumps(item).encode())
        for version in (0, 2, True, '1', None):
            changed('schema_version', version)
        changed('event', 'other')
        changed('extra', 'private')
        changed('files', None)
        changed('files', good['files'] * 34)
        changed('files', good['files'] + [good['files'][0]])
        changed('files', list(reversed(good['files'])))
        changed('files', good['files'][:-1])
        for path in ('../secret', 'C:/private', 'session-001/../../secret',
                     'session-065/REPORT.html', 'session-000/REPORT.html',
                     'session-1/REPORT.html', 'session-001\\REPORT.html',
                     'INDEX.HTML', 'INDEX.html:stream', 'INDEX.html.', '', None):
            item = copy.deepcopy(good)
            item['files'][0]['path'] = path
            mutations.append(json.dumps(item).encode())
        for key, value in (('bytes', -1), ('bytes', True), ('bytes', 2**50),
                           ('bytes', 1.5), ('sha256', 'A'*64), ('sha256', None),
                           ('private', 'secret')):
            item = copy.deepcopy(good)
            item['files'][0][key] = value
            mutations.append(json.dumps(item).encode())
        mutations.extend((b'{', b'null', b'[]', b'\xff',
                          marker.read_bytes().replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'),
                          b' ' * (integrity.MAX_MARKER_BYTES+1)))
        original = integrity.catalog._pin
        for raw in mutations:
            with self.subTest(raw=raw[:100]):
                marker.write_bytes(raw)
                opened = []
                def pinned(path, **kwargs):
                    opened.append(Path(path))
                    return original(path, **kwargs)
                with patch.object(integrity.catalog, '_pin', side_effect=pinned):
                    code, value = self.verify()
                self.assertEqual(code, 3)
                self.assertNotIn('private', json.dumps(value))
                self.assertTrue(all(p == marker or p in (self.output, *self.output.parents) for p in opened))
        marker.write_bytes(integrity.catalog._dump(good).encode('utf-8'))
        self.assertEqual(self.verify()[0], 0)

    def test_missing_truncated_modified_extra_and_hardlinked_payloads_refuse(self):
        self.journal()
        self.invoke()
        payload = self.output/'session-001'/'REPORT.html'
        data = payload.read_bytes()
        for content in (b'', data[:-1], b'x'+data[1:]):
            with self.subTest(size=len(content)):
                payload.write_bytes(content)
                self.assertEqual(self.verify()[0], 3)
        payload.unlink()
        self.assertEqual(self.verify()[0], 3)
        payload.write_bytes(data)
        extra = self.output/'unexpected-private'
        extra.write_bytes(b'never read')
        self.assertEqual(self.verify()[0], 3)
        extra.unlink()
        os.link(payload, self.base/'hardlink')
        self.assertEqual(self.verify()[0], 3)
        (self.base/'hardlink').unlink()
        self.assertEqual(self.verify()[0], 0)
        os.link(self.output/'COMPLETE.json', self.base/'marker-hardlink')
        self.assertEqual(self.verify()[0], 3)

    def test_physical_oversized_file_and_aggregate_manifest_limits(self):
        self.journal()
        self.invoke()
        payload = self.output/'INDEX.html'
        with payload.open('r+b') as stream:
            stream.truncate(integrity.MAX_FILE_BYTES+1)
        self.assertEqual(self.verify()[0], 3)
        names = ['INDEX.html', 'catalog.json']
        for ordinal in range(1, 65):
            names += ['session-%03d/%s' % (ordinal, leaf) for leaf in ('REPORT.html','report.json')]
        value = dict(event='session_catalog_completion',schema_version=1,
                     files=[dict(path=n,bytes=integrity.MAX_FILE_BYTES,sha256='0'*64) for n in sorted(names)])
        with self.assertRaises(ValueError):
            integrity._manifest(json.dumps(value).encode())
        value['files'] = value['files'][:2]
        value['files'][0]['bytes'] = 0
        with patch.object(integrity, 'MAX_BYTES', 1), self.assertRaises(ValueError):
            integrity._manifest(json.dumps(value).encode())

    def test_verifier_cli_is_offline_and_rejects_all_other_options(self):
        self.journal()
        self.invoke()
        helper = Path(__file__).parent/'helpers'/'native_history_offline.py'
        command = [sys.executable, '-B', str(helper), '--verify-catalog', '--report-dir', str(self.output)]
        result = subprocess.run(command, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['state'], 'complete')
        for extra in (['--max-seconds=1800'], ['--interval','300'], ['--collection=all'],
                      ['--sessions-root', str(self.root)], ['--journal', str(self.root/'one/events.jsonl')],
                      ['--output-dir',str(self.output)], ['--stop-file',str(self.base/'STOP')],
                      ['--player-file',str(self.base/'private')], ['--visual-reference',str(self.base/'x.bmp')],
                      ['--live'], ['--catalog'], ['--status'], ['--check-ready'], ['--report-html']):
            with self.subTest(extra=extra):
                result = subprocess.run(command+extra, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, b'')
        for args in (['--verify-catalog'], ['--verify-catalog','--report-dir','relative']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                cli.main(args)
            self.assertEqual(error.exception.code, 2)

    def _child(self, mode):
        helper = Path(__file__).parent/'helpers'/'catalog_integrity_synthetic.py'
        ready, release = self.base/'ready', self.base/'release'
        child = subprocess.Popen([sys._base_executable, '-B', str(helper), mode, str(self.root),
                                  str(self.output), str(ready), str(release)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def reap():
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)
        self.addCleanup(reap)
        deadline = time.monotonic()+15
        notice = None
        while child.poll() is None and time.monotonic() < deadline:
            try:
                notice = json.loads(ready.read_bytes())
                break
            except (OSError, ValueError):
                time.sleep(.01)
        self.assertIsNotNone(notice, 'SYNTHETIC child must reach actual held-handle barrier')
        self.assertEqual(notice['pid'], child.pid, 'terminate only the exact executing Python process')
        return child, release

    @unittest.skipUnless(os.name == 'nt', 'physical Windows sharing semantics')
    def test_killed_publisher_at_full_marker_write_leaves_no_valid_marker(self):
        self.journal()
        child, release = self._child('publish-interrupt')
        self.assertTrue((self.output/'INDEX.html').is_file())
        self.assertEqual(self.verify()[0], 3)  # delete-pending writer refuses read
        child.kill()
        child.communicate(timeout=10)
        self.assertFalse((self.output/'COMPLETE.json').exists())
        self.assertEqual(self.verify()[0], 4)

    @unittest.skipUnless(os.name == 'nt', 'physical Windows sharing semantics')
    def test_verifier_holds_every_file_and_directory_until_result(self):
        self.journal()
        self.invoke()
        child, release = self._child('verify-held')
        for payload in (p for p in self.output.rglob('*') if p.is_file()):
            with self.assertRaises(PermissionError):
                payload.write_bytes(b'SYNTHETIC mutation')
            with self.assertRaises(PermissionError):
                payload.unlink()
        for directory in (self.output, self.output/'session-001'):
            with self.assertRaises(PermissionError):
                directory.rename(self.base/'moved')
        self.assertEqual(self.verify()[0], 0)  # real simultaneous shared reader
        release.write_text('release')
        stdout, stderr = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual(json.loads(stdout)['state'], 'complete')

    @unittest.skipUnless(os.name == 'nt', 'physical concurrent Windows namespace mutation')
    def test_file_added_during_verification_is_not_ignored(self):
        self.journal()
        self.invoke()
        child, release = self._child('verify-held')
        (self.output/'unexpected').write_bytes(b'SYNTHETIC race')
        release.write_text('release')
        stdout, stderr = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 3, stderr)
        self.assertEqual(json.loads(stdout)['state'], 'damaged_or_refused')

    @unittest.skipUnless(os.name == 'nt', 'physical Windows writer sharing semantics')
    def test_existing_concurrent_writer_is_refused(self):
        self.journal()
        self.invoke()
        with (self.output/'catalog.json').open('r+b'):
            self.assertEqual(self.verify()[0], 3)
        self.assertEqual(self.verify()[0], 0)

    @unittest.skipUnless(os.name == 'nt', 'physical Windows junction')
    def test_verification_never_follows_root_or_report_directory_junction(self):
        self.journal()
        self.invoke()
        original = self.output
        alias = self.base/'junction'
        subprocess.run(['cmd','/c','mklink','/J',str(alias),str(original)], check=True, capture_output=True)
        try:
            self.output = alias
            self.assertEqual(self.verify()[0], 3)
        finally:
            os.rmdir(alias)
            self.output = original
        folder = self.output/'session-001'
        moved = self.base/'moved'
        folder.rename(moved)
        subprocess.run(['cmd','/c','mklink','/J',str(folder),str(moved)], check=True, capture_output=True)
        try:
            self.assertEqual(self.verify()[0], 3)
        finally:
            os.rmdir(folder)
        moved.rename(folder)
        self.assertEqual(self.verify()[0], 0)

    @unittest.skipUnless(os.name == 'nt', 'Windows no-follow symlink')
    def test_verifier_refuses_actual_symlink_marker(self):
        self.journal()
        self.invoke()
        marker = self.output/'COMPLETE.json'
        original = self.base/'saved-marker'
        marker.rename(original)
        try:
            os.symlink(original, marker)
        except OSError as exc:
            if exc.winerror != 1314:
                raise
            self.skipTest('Windows symlink privilege unavailable: '+str(exc.winerror))
        self.assertEqual(self.verify()[0], 3)

    def test_final_marker_lists_exact_synced_generated_files(self):
        self.journal()
        self.assertEqual(self.invoke()[0], 0)
        marker = self.output/'COMPLETE.json'
        self.assertTrue(marker.is_file(), 'finished publication requires final marker')
        value = json.loads(marker.read_bytes())
        self.assertEqual(set(value), {'event', 'schema_version', 'files'})
        self.assertEqual(value['event'], 'session_catalog_completion')
        self.assertEqual(value['schema_version'], 1)
        expected = []
        for p in sorted(self.output.rglob('*'), key=lambda p: p.relative_to(self.output).as_posix()):
            if p.is_file() and p != marker:
                data = p.read_bytes()
                expected.append(dict(path=p.relative_to(self.output).as_posix(), bytes=len(data),
                                     sha256=hashlib.sha256(data).hexdigest()))
        self.assertEqual(value['files'], expected)
        self.assertNotIn(str(self.root), marker.read_text())
