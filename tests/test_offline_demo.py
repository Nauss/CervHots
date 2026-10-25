"""Démonstration SYNTHETIC : aucun jeu, réseau, compte ou son."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OfflineDemoTests(unittest.TestCase):
    def test_help_does_not_import_api_or_game(self):
        probe = ROOT/'tests/helpers/offline_demo_guard.py'
        result = subprocess.run([sys.executable, '-B', str(probe), '--help'],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SYNTHETIC', result.stdout)
        self.assertIn('--destination', result.stdout)

    def invoke(self, *args):
        return subprocess.run([sys.executable, '-B', str(ROOT/'tests/helpers/offline_demo_guard.py'), *map(str, args)],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8')

    @unittest.skipUnless(os.name == 'nt', 'catalogue sécurisé Windows uniquement')
    def test_end_to_end_synthetic_states_and_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp)/'first', Path(tmp)/'second'
            for target in (first, second):
                result = self.invoke('--destination', target)
                self.assertEqual(result.returncode, 0, result.stderr+result.stdout)
                self.assertEqual(result.stderr, '')
                summary = json.loads(result.stdout)
                self.assertEqual(summary['data_kind'], 'SYNTHETIC')
                self.assertFalse(summary['current_permission'])
                self.assertEqual(summary['verification']['state'], 'complete')
                self.assertTrue((target/'SYNTHETIC.txt').is_file())
                def history(case):
                    return json.loads((target/'reports'/case/'summary/history.json').read_text())
                zero = history('zero')['local_cooldowns']['value']['abilities'][0]
                self.assertEqual(zero['remaining_s'], 0)
                self.assertIsNone(zero['charges_available'])
                self.assertEqual(zero['cast_legality'], 'unknown')
                self.assertEqual(history('unknown')['local_cooldowns']['status'], 'unknown')
                self.assertIsNone(history('unknown')['local_cooldowns']['value'])
                self.assertEqual(history('refused')['state'], 'refused')
                self.assertNotEqual(history('absent')['state'], 'recorded_observation')
                catalogue = json.loads((target/'catalog/catalog.json').read_text())
                self.assertEqual([s['state'] for s in catalogue['sessions']],
                    ['absent', 'refused', 'recorded', 'recorded'])
                self.assertEqual(summary['commands'][-2]['exit_code'], 1)
                self.assertEqual(summary['commands'][-1]['exit_code'], 0)
            def files(target):
                return {str(p.relative_to(target)): p.read_bytes() for p in target.rglob('*') if p.is_file()}
            self.assertEqual(files(first), files(second))
            self.assertLess(sum(map(len, files(first).values())), 512*1024)

    def test_bad_arguments_never_echo_identity_or_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'new'
            for arguments in ([], ['--player-file', 'PRIVATE_SECRET'],
                    ['--destination', target, '--live'],
                    ['--destination', target, '--collection=core'],
                    ['--dest', target], ['--destination']):
                with self.subTest(arguments=arguments):
                    result = self.invoke(*arguments)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, '')
                    self.assertNotIn('PRIVATE_SECRET', result.stderr)
                    self.assertFalse(target.exists())

    @unittest.skipUnless(os.name == 'nt', 'sécurité chemins Windows')
    def test_existing_directory_and_file_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root/'existing'; folder.mkdir()
            sentinel = folder/'sentinel'; sentinel.write_bytes(b'unchanged')
            file = root/'file'; file.write_bytes(b'unchanged')
            for target in (folder, file):
                result = self.invoke('--destination', target)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
            self.assertEqual(sentinel.read_bytes(), b'unchanged')
            self.assertEqual(file.read_bytes(), b'unchanged')
            self.assertEqual([p.name for p in folder.iterdir()], ['sentinel'])

    @unittest.skipUnless(os.name == 'nt', 'sécurité chemins Windows')
    def test_missing_parent_relative_parent_escape_and_network_refuse_without_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for target in (root/'missing'/'new', Path('relative-new'),
                    root/'..'/'escape', Path('//server/share/new')):
                result = self.invoke('--destination', target)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, '')
            self.assertEqual(list(root.iterdir()), [])

    @unittest.skipUnless(os.name == 'nt', 'jonctions Windows réelles')
    def test_real_junction_destination_and_ancestor_are_never_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root/'untouched'; private.mkdir()
            link = root/'junction'
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(private)],
                check=True, capture_output=True)
            try:
                for target in (link, link/'new'):
                    result = self.invoke('--destination', target)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertEqual(result.stdout, '')
                self.assertEqual(list(private.iterdir()), [])
            finally:
                os.rmdir(link)

    @unittest.skipUnless(os.name == 'nt', 'liens Windows réels')
    def test_dangling_symlink_is_refused_without_follow_or_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); link = root/'link'; missing = root/'missing'
            try:
                os.symlink(missing, link, target_is_directory=True)
            except OSError as exc:
                self.skipTest('privilège symlink Windows absent : '+str(exc.winerror))
            self.assertEqual(self.invoke('--destination', link).returncode, 1)
            self.assertTrue(link.is_symlink())
            self.assertFalse(missing.exists())

    @unittest.skipUnless(os.name == 'nt', 'réservation Windows réelle')
    def test_simultaneous_real_cli_contenders_have_exactly_one_winner(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'new'
            command = [sys.executable, '-B', str(ROOT/'tests/helpers/offline_demo_guard.py'),
                '--destination', str(target)]
            children = [subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE) for _ in range(2)]
            outputs = [child.communicate(timeout=30) for child in children]
            self.assertEqual(sorted(child.returncode for child in children), [0, 1], outputs)
            self.assertEqual(json.loads((target/'demo.json').read_text())['verification']['state'], 'complete')

    @unittest.skipUnless(os.name == 'nt', 'publication Windows')
    def test_io_failure_keeps_partial_and_releases_directory_handles(self):
        from unittest.mock import patch
        from cerveau import offline_demo, session_catalog
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'partial'
            original = session_catalog._write
            def failing(path, text):
                if path.name == 'status.json':
                    raise OSError('injected PRIVATE_SECRET')
                return original(path, text)
            with patch.object(session_catalog, '_write', side_effect=failing):
                with self.assertRaises(OSError):
                    offline_demo.demonstrate(target)
            self.assertTrue((target/'SYNTHETIC.txt').exists())
            self.assertFalse((target/'demo.json').exists())
            self.assertEqual(self.invoke('--destination', target).returncode, 1)
            target.rename(Path(tmp)/'released')

    def test_public_coach_api_is_backward_compatible_and_unknown_attributes_raise(self):
        import cerveau
        from cerveau.brain import Coach, Decision
        self.assertIs(cerveau.Coach, Coach)
        self.assertIs(cerveau.Decision, Decision)
        with self.assertRaises(AttributeError):
            getattr(cerveau, 'not_a_public_name')


if __name__ == '__main__':
    unittest.main()
