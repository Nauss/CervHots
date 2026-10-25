"""Offline readiness, never permission to acquire a current game."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from unittest.mock import patch
import importlib.util
import sys
import subprocess

from cerveau import passive_session as product


class ReadinessTests(unittest.TestCase):
    def test_cli_ready_is_not_permission_and_preserves_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            player = root / 'private.txt'
            player.write_text('PRIVATE_SENTINEL\n', encoding='utf-8')
            before = player.read_bytes()
            output, stop = root / 'new-parent/session', root / 'new.STOP'
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    code = product.main(['--check-ready', '--collection', 'core',
                                         '--player-file', str(player), '--output-dir', str(output),
                                         '--stop-file', str(stop)])
                except SystemExit as exc:
                    code = exc.code
            self.assertEqual(code, 0)
            row = json.loads(stdout.getvalue())
            self.assertTrue(row['technical_ready'])
            self.assertFalse(row['current_permission'])
            self.assertIsNone(row['reader_active'])
            self.assertEqual(row['current_context'], 'unattested')
            self.assertIn('permission', stderr.getvalue().lower())
            self.assertNotIn('PRIVATE_SENTINEL', stdout.getvalue() + stderr.getvalue())
            self.assertNotIn(str(root), stdout.getvalue() + stderr.getvalue())
            self.assertEqual(player.read_bytes(), before)
            self.assertFalse(output.parent.exists())
            self.assertFalse(stop.exists())

    def invoke(self, root, *, player=None, output=None, stop=None, extra=()):
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ['--check-ready', '--collection', 'core', '--player-file',
                str(player if player is not None else root / 'private.txt'),
                '--output-dir', str(output if output is not None else root / 'new/session'),
                '--stop-file', str(stop if stop is not None else root / 'new.STOP'), *extra]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = product.main(argv)
        self.assertNotIn('PRIVATE_SENTINEL', stdout.getvalue() + stderr.getvalue())
        self.assertNotIn(str(root), stdout.getvalue() + stderr.getvalue())
        return code, json.loads(stdout.getvalue())

    def test_path_refusals_are_inspection_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            player = root / 'private.txt'
            player.write_text('PRIVATE_SENTINEL\n', encoding='utf-8')
            for path in (Path('relative'), root / 'bad:name', root / 'NUL', root / 'bad.',
                         root / 'bad*', root / '..' / 'elsewhere', Path('/')):
                with self.subTest(path=path):
                    code, row = self.invoke(root, output=path)
                    self.assertEqual(code, 2)
                    self.assertFalse(row['technical_ready'])
            for content in (b'', b'\n', b'X', b'PRIVATE_SENTINEL\x00', b'x' * 262):
                player.write_bytes(content)
                code, row = self.invoke(root)
                self.assertEqual(code, 1)
                self.assertEqual(row['checks']['identity'], 'unavailable')
                self.assertEqual(player.read_bytes(), content)
            player.unlink()  # test-owned fixture only
            self.assertEqual(self.invoke(root)[0], 1)
            player.write_text('PRIVATE_SENTINEL\n', encoding='utf-8')
            stop = root / 'new.STOP'
            stop.write_bytes(b'KEEP_STOP')
            self.assertEqual(self.invoke(root)[1]['checks']['stop'], 'present')
            self.assertEqual(self.invoke(root)[0], 1)
            self.assertEqual(stop.read_bytes(), b'KEEP_STOP')
            self.assertFalse((root / 'new').exists())
            old = root / 'old'
            old.mkdir()
            (old / 'events.jsonl').write_bytes(b'KEEP_OLD')
            self.assertEqual(self.invoke(root, output=old)[1]['checks']['output'], 'exists')
            self.assertEqual((old / 'events.jsonl').read_bytes(), b'KEEP_OLD')
            claimed = root / 'claimed'
            claimed.mkdir()
            (claimed / 'passive-session.lock').write_bytes(b'KEEP_CLAIM')
            self.assertEqual(self.invoke(root, output=claimed / 'session')[1]['checks']['output'], 'parent_claimed')
            self.assertEqual((claimed / 'passive-session.lock').read_bytes(), b'KEEP_CLAIM')

    def test_core_preflight_reuses_data_checks_without_backend_imports(self):
        real_import = product.importlib.import_module
        def guarded(name, *args, **kwargs):
            self.assertNotIn(name, ('hotstate.live', 'hotstate.reader', 'hotstate.native_context'))
            return real_import(name, *args, **kwargs)
        with patch.object(product.importlib, 'import_module', side_effect=guarded):
            row = product.preflight(core=True)
        self.assertTrue(row['ready'])
        self.assertGreater(row['profiles_checked'], 0)
        self.assertEqual(row['runtime'], 'supported')
        self.assertFalse(row['memory_opened'])

    def test_required_dependency_missing_and_optional_missing_are_distinct(self):
        real_spec = importlib.util.find_spec
        for absent, expected in (('ctypes', False), ('mpyq', True), ('heroprotocol', True)):
            with self.subTest(absent=absent):
                with patch('importlib.util.find_spec', side_effect=lambda name: None if name == absent else real_spec(name)):
                    row = product.preflight(core=True)
                self.assertEqual(row['ready'], expected)
                category = 'required_dependencies' if absent == 'ctypes' else 'optional_dependencies'
                self.assertEqual(row[category][absent], 'missing')
        for missing in ('mpyq', 'heroprotocol'):
            def broken(name):
                if name == missing:
                    raise ValueError('PRIVATE_SENTINEL')
                return real_spec(name)
            with patch('importlib.util.find_spec', side_effect=broken):
                row = product.preflight(core=True)
            self.assertTrue(row['ready'])
            self.assertEqual(row['optional_dependencies'][missing], 'missing')
        with patch.object(sys, 'platform', 'linux'):
            self.assertFalse(product.preflight(core=True)['ready'])
        with patch.object(product, 'ROOT', Path('nonexistent-product-data')):
            with self.assertRaises(ValueError):
                product.preflight(core=True)

    def test_preflight_failure_is_sanitized_stable_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'private.txt').write_text('PRIVATE_SENTINEL', encoding='utf-8')
            with patch.object(product, 'preflight', side_effect=RuntimeError('PRIVATE_SENTINEL')) as check:
                first = self.invoke(root)
                second = self.invoke(root)
            self.assertEqual(first, second)
            self.assertEqual(first[0], 1)
            self.assertEqual(first[1]['checks']['preflight'], 'unavailable')
            check.assert_called_with(core=True)

    def test_cli_contract_requires_core_and_anonymizes_parser_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'private.txt').write_text('PRIVATE_SENTINEL', encoding='utf-8')
            for extra in (('--collection', 'all'), ('--journal', str(root / 'PRIVATE_SENTINEL'))):
                code, row = self.invoke(root, extra=extra)
                self.assertEqual(code, 2)
                self.assertFalse(row['technical_ready'])
            for argv in (['--check-ready'], ['--check-ready', '--collection', 'PRIVATE_SENTINEL'],
                         ['--check-ready', '--PRIVATE_SENTINEL'], ['--check-ready', '--live']):
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    try:
                        code = product.main(argv)
                    except SystemExit as exc:
                        code = exc.code
                self.assertEqual(code, 2)
                self.assertNotIn('PRIVATE_SENTINEL', stdout.getvalue() + stderr.getvalue())
                row = json.loads(stdout.getvalue())
                self.assertEqual(row['exit_code'], 2)
                self.assertFalse(row['current_permission'])

    def test_cli_exports_closed_preflight_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'private.txt').write_text('PRIVATE_SENTINEL', encoding='utf-8')
            code, row = self.invoke(root)
            self.assertEqual(code, 0)
            self.assertEqual(row['preflight']['runtime'], 'supported')
            self.assertIn('mpyq', row['preflight']['optional_dependencies'])
            actual = product.preflight(core=True)
            actual.update(private='PRIVATE_SENTINEL')
            with patch.object(product, 'preflight', return_value=actual):
                self.assertEqual(self.invoke(root)[0], 0)
            with patch.object(product, 'preflight', return_value=dict(actual, ready=False)):
                self.assertEqual(self.invoke(root)[0], 1)

    def test_fresh_cli_forbids_imports_constructors_io_and_preserves_inputs(self):
        helper = Path(__file__).parent / 'helpers/readiness_guard.py'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            player = root / 'private.txt'
            player.write_text('PRIVATE_SENTINEL', encoding='utf-8')
            argv = ['--collection', 'core', '--player-file', str(player),
                    '--output-dir', str(root / 'new/session'), '--stop-file', str(root / 'new.STOP')]
            before = player.read_bytes()
            for mode in ('--check-ready', '--preflight'):
                for absent, expected in ((None, 0), ('mpyq', 0), ('heroprotocol', 0), ('ctypes', 1)):
                    with self.subTest(mode=mode, absent=absent):
                        command = [sys.executable, '-B', str(helper)]
                        if absent:
                            command.extend(['--absent', absent])
                        command.extend([mode, *argv])
                        done = subprocess.run(command, capture_output=True, text=True, timeout=30)
                        self.assertEqual(done.returncode, expected, done.stderr)
                        row = json.loads(done.stdout)
                        self.assertFalse(row['memory_opened'])
                        self.assertNotIn('PRIVATE_SENTINEL', done.stdout + done.stderr)
                        self.assertEqual(player.read_bytes(), before)
                        self.assertFalse((root / 'new').exists())
                        self.assertFalse((root / 'new.STOP').exists())

    def test_core_required_data_missing_cannot_hide_behind_other_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / 'hotstate/profiles'
            profiles.mkdir(parents=True)
            for name in ('98348.json', '98348-match.json', 'unrelated.json'):
                (profiles / name).write_text('{}', encoding='utf-8')
            with patch.object(product, 'ROOT', root):
                with self.assertRaises((ValueError, OSError)):
                    product.preflight(core=True)


if __name__ == '__main__':
    unittest.main()
