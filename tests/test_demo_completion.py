"""SYNTHETIC local integrity, never native/HUD attestation."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from tests import test_offline_demo as fixtures
from cerveau import demo_integrity as integrity, offline_demo, session_catalog
from unittest.mock import patch
import copy
import hashlib
import subprocess
import sys
import time


@unittest.skipUnless(os.name == 'nt', 'Windows guarded publication')
class DemoCompletionTests(unittest.TestCase):
    invoke = fixtures.OfflineDemoTests.invoke

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root/'demo'

    def create(self):
        offline_demo.demonstrate(self.target)

    def check(self):
        result = self.invoke('--verify', self.target)
        self.assertEqual(result.stderr, '')
        return result.returncode, json.loads(result.stdout)

    def snapshot(self):
        return {p.relative_to(self.target).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.target.rglob('*') if p.is_file()}

    def test_each_output_is_bound_and_missing_truncated_or_changed_refuses(self):
        self.create()
        files = self.snapshot()
        marker = json.loads((self.target/integrity.MARKER).read_bytes())
        self.assertEqual(marker['files'], [dict(path=n, bytes=len(files[n][0]),
            sha256=hashlib.sha256(files[n][0]).hexdigest()) for n in integrity.NAMES])
        for name in integrity.NAMES:
            path = self.target/name
            raw = path.read_bytes()
            for changed in (raw[:-1], b'x'+raw[1:]):
                with self.subTest(name=name, mutation=len(changed)):
                    path.write_bytes(changed)
                    self.assertEqual(self.check()[0], 3)
            path.unlink()
            self.assertEqual(self.check()[0], 3)
            path.write_bytes(raw)
        self.assertEqual(self.check()[0], 0)

    def test_legacy_absent_marker_is_unverifiable_and_never_repaired(self):
        self.create()
        (self.target/integrity.MARKER).unlink()  # simulated lot30 layout
        before = self.snapshot()
        code, value = self.check()
        self.assertEqual(code, 4)
        self.assertEqual(value['state'], 'unverifiable')
        self.assertIn('legacy_or_interrupted', value['reason'])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.invoke('--destination', self.target).returncode, 1)
        self.assertEqual(before, self.snapshot())

    def test_closed_marker_schema_and_noncanonical_bytes_refuse(self):
        self.create()
        path = self.target/integrity.MARKER
        raw = path.read_bytes()
        good = json.loads(raw)
        mutations = [raw[:-1], b'null', b'[]', b'\xff', b'{',
            raw.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'),
            b' '* (integrity.MAX_MARKER_BYTES+1)]
        for key, value in (('schema_version', True), ('schema_version', 2),
                ('event', 'other'), ('data_kind', 'real'), ('extra', 1),
                ('files', None), ('files', good['files'][:-1]),
                ('files', good['files']+[good['files'][0]]),
                ('files', list(reversed(good['files'])))):
            changed = copy.deepcopy(good)
            changed[key] = value
            mutations.append(session_catalog._dump(changed).encode())
        for key, value in (('path', '../private'), ('path', 'C:/private'),
                ('path', 'reports/zero/html/REPORT.html:ads'), ('path', 'SYNTHETIC.txt.'),
                ('bytes', True), ('bytes', -1), ('bytes', integrity.MAX_FILE_BYTES+1),
                ('sha256', 'A'*64), ('extra', 'PRIVATE_SECRET')):
            changed = copy.deepcopy(good)
            changed['files'][0][key] = value
            mutations.append(session_catalog._dump(changed).encode())
        original = session_catalog._pin
        for raw in mutations:
            path.write_bytes(raw)
            opened = []
            def pin(p, **kw):
                opened.append(Path(p))
                return original(p, **kw)
            with patch.object(session_catalog, '_pin', side_effect=pin):
                code, result = self.check()
            self.assertEqual(code, 3)
            self.assertNotIn('PRIVATE_SECRET', json.dumps(result))
            # Verification happens in a fresh subprocess; directly validate no
            # untrusted inventory path reaches filesystem path construction.
            with patch.object(session_catalog, '_pin', side_effect=pin):
                with self.assertRaises((ValueError, UnicodeError)):
                    integrity.verify(self.target)
            self.assertTrue(all(p == path or p in (self.target, *self.target.parents) for p in opened))

    def test_each_fsync_failure_and_retry_preserves_partial_without_final_marker(self):
        # Includes every write, nested catalogue seal, and final demo seal.
        original = os.fsync
        calls = []
        def count(fd):
            calls.append(fd)
            return original(fd)
        with patch('os.fsync', side_effect=count):
            self.create()
        count_syncs = len(calls)
        # Existing diagnosis/summary CLI files close normally (no per-file fsync).
        # Exercise every sync actually performed, not an invented sync per file.
        self.assertGreater(count_syncs, 1)
        for failure in range(1, count_syncs+1):
            self.target = self.root/('partial-%02d' % failure)
            calls.clear()
            def fail(fd):
                calls.append(fd)
                if len(calls) == failure:
                    raise OSError('SYNTHETIC failure')
                return original(fd)
            with patch('os.fsync', side_effect=fail):
                with self.assertRaises((OSError, ValueError)):
                    self.create()
            self.assertFalse((self.target/integrity.MARKER).exists())
            self.assertEqual(self.check()[0], 4)
            before = self.snapshot()
            with self.assertRaises(ValueError):
                self.create()
            self.assertEqual(before, self.snapshot())
            # Released all parent/child guards, without deleting evidence.
            moved = self.target.with_name(self.target.name+'-released')
            self.target.rename(moved)

    def test_unexpected_component_outcomes_and_interruptions_never_seal(self):
        from cerveau import session_diagnosis, native_history, session_html, catalog_integrity
        cases = [(session_diagnosis, 'run'), (native_history, 'run'),
                 (session_html, 'build'), (session_catalog, 'run'),
                 (catalog_integrity, 'run')]
        for i, (module, method) in enumerate(cases):
            for exception in (OSError, KeyboardInterrupt):
                self.target = self.root/('failed-%d-%s' % (i, exception.__name__))
                with patch.object(module, method, side_effect=exception('SYNTHETIC')):
                    with self.assertRaises(exception):
                        self.create()
                self.assertFalse((self.target/integrity.MARKER).exists())
                self.assertEqual(self.check()[0], 4)

    def test_extra_hardlinks_oversize_and_concurrent_writer_refuse(self):
        self.create()
        for folder in integrity.TREE:
            extra = self.target/folder/'unexpected'
            extra.write_bytes(b'SYNTHETIC')
            self.assertEqual(self.check()[0], 3)
            extra.unlink()
        for name in ('demo.json', integrity.MARKER):
            path = self.target/name
            link = self.root/'hardlink'
            os.link(path, link)
            self.assertEqual(self.check()[0], 3)
            link.unlink()
        path = self.target/'demo.json'
        with path.open('r+b'):
            self.assertEqual(self.check()[0], 3)
        with path.open('r+b') as stream:
            stream.truncate(integrity.MAX_FILE_BYTES+1)
        self.assertEqual(self.check()[0], 3)

    def test_junctions_at_root_ancestor_and_each_nested_directory_refuse(self):
        self.create()
        alias = self.root/'alias'
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), str(self.target)], check=True, capture_output=True)
        try:
            self.assertEqual(self.invoke('--verify', alias).returncode, 3)
            self.assertEqual(self.invoke('--verify', alias/'reports').returncode, 3)
        finally:
            os.rmdir(alias)
        for folder in sorted(integrity.TREE):
            if not folder:
                continue
            path = self.target/folder
            moved = self.root/'moved'
            path.rename(moved)
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(path), str(moved)], check=True, capture_output=True)
            try:
                self.assertEqual(self.check()[0], 3)
            finally:
                os.rmdir(path)
                moved.rename(path)

    def test_verify_rejects_unsafe_paths_and_mixed_cli_options(self):
        self.create()
        for target in ('relative', '//server/share/demo', str(self.target/'..'/'demo'),
                       str(self.target)+':ads'):
            self.assertEqual(self.invoke('--verify', target).returncode, 3)
        for extra in (['--destination', self.root/'new'], ['--live'],
                      ['--player-file', 'PRIVATE_SECRET']):
            result = self.invoke('--verify', self.target, *extra)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            self.assertNotIn('PRIVATE_SECRET', result.stderr)
        self.assertFalse((self.root/'new').exists())

    def child(self, mode):
        ready, release = self.root/'ready', self.root/'release'
        helper = fixtures.ROOT/'tests/helpers/demo_integrity_synthetic.py'
        child = subprocess.Popen([sys._base_executable, '-B', str(helper), mode,
            str(self.target), str(ready), str(release)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def reap():
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)
        self.addCleanup(reap)
        deadline = time.monotonic()+20
        notice = None
        while child.poll() is None and time.monotonic() < deadline:
            try:
                notice = json.loads(ready.read_bytes())
                break
            except (OSError, ValueError):
                time.sleep(.01)
        self.assertIsNotNone(notice)
        self.assertEqual(notice['pid'], child.pid)
        return child, release

    def test_kill_after_full_final_marker_bytes_before_fsync_has_no_false_success(self):
        child, _ = self.child('publish-interrupt')
        self.assertTrue((self.target/'demo.json').is_file())
        self.assertEqual(self.check()[0], 3)
        child.kill()
        child.communicate(timeout=10)
        self.assertFalse((self.target/integrity.MARKER).exists())
        self.assertEqual(self.check()[0], 4)
        self.assertEqual(self.invoke('--destination', self.target).returncode, 1)

    def test_every_handle_is_held_through_verification_and_shared_reader_works(self):
        self.create()
        child, release = self.child('verify-held')
        for name in (*integrity.NAMES, integrity.MARKER):
            path = self.target/name
            with self.assertRaises(PermissionError):
                path.write_bytes(b'SYNTHETIC')
            with self.assertRaises(PermissionError):
                path.unlink()
        for folder in integrity.TREE:
            with self.assertRaises(PermissionError):
                (self.target/folder).rename(self.root/'moved')
        self.assertEqual(self.check()[0], 0)
        release.write_text('release')
        stdout, stderr = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual(json.loads(stdout)['state'], 'complete')

    def test_child_added_during_hashing_is_refused_by_final_reenumeration(self):
        self.create()
        child, release = self.child('verify-held')
        (self.target/'reports/zero/html/extra').write_text('SYNTHETIC')
        release.write_text('release')
        _, stderr = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 3, stderr)

    def test_notice_warns_that_html_and_nested_seal_do_not_complete_demo(self):
        self.create()
        notice = (self.target/'SYNTHETIC.txt').read_text(encoding='utf-8')
        self.assertIn('DEMO_COMPLETE.json', notice)
        self.assertIn('--verify', notice)
        self.assertIn('HTML', notice)

    def test_new_demo_is_sealed_and_verified_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'demo'
            self.assertEqual(self.invoke('--destination', target).returncode, 0)
            self.assertTrue((target/'DEMO_COMPLETE.json').is_file())
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in target.rglob('*') if p.is_file()}
            result = self.invoke('--verify', target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['state'], 'complete')
            self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
