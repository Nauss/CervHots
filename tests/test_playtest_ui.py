"""SYNTHETIC panel tests: subprocesses mocked, never game/API/audio."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock


class PanelTests(unittest.TestCase):
    def setUp(self):
        from cerveau.playtest_ui import Controller
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.python = self.root/'python.exe'
        self.python.touch()
        self.identity = self.root/'private.txt'
        self.identity.write_text('SYNTHETIC-PRIVATE', encoding='utf-8')
        self.child = Mock()
        self.child.poll.return_value = None
        self.spawn = Mock(return_value=self.child)
        self.stop = Mock(return_value={'state': 'published'})
        self.panel = Controller(self.root, self.python, self.root/'scratch',
                                popen=self.spawn, request_stop=self.stop)

    def test_no_autostart_and_preflight_has_no_live_or_identity(self):
        self.spawn.assert_not_called()
        self.assertFalse((self.root/'out').exists())
        self.panel.check()
        argv = self.spawn.call_args.args[0]
        self.assertEqual(argv, [str(self.python), '-B', '-m', 'cerveau.playtest'])
        self.assertNotIn('--live', argv)
        self.assertEqual(self.spawn.call_args.kwargs['env']['TMPDIR'], str(self.root/'scratch'))
        self.child.poll.return_value = 0
        self.panel.poll()

    def test_voice_confirmation_cancel_never_spawns(self):
        confirm = Mock(return_value=False)
        self.assertFalse(self.panel.start(self.identity, voice=True, confirm=confirm))
        confirm.assert_called_once_with()
        self.spawn.assert_not_called()
        self.assertFalse((self.root/'out').exists())

    def test_voice_manual_argv_private_file_new_paths_and_no_overlap(self):
        self.assertTrue(self.panel.start(self.identity, voice=True, confirm=lambda: True))
        argv = self.spawn.call_args.args[0]
        self.assertIn('--mumble', argv)
        self.assertIn('--player-file', argv)
        self.assertEqual(argv[argv.index('--max-seconds')+1], '1800')
        self.assertNotIn('SYNTHETIC-PRIVATE', ' '.join(argv))
        first = self.panel.output
        self.assertFalse(self.panel.start(self.identity, confirm=lambda: True))
        self.assertFalse(self.panel.check())
        self.assertEqual(self.spawn.call_count, 1)
        self.panel.stop()
        self.stop.assert_called_once_with(self.panel.output, self.panel.stop_file)
        self.child.terminate.assert_not_called()
        self.child.kill.assert_not_called()
        self.child.poll.return_value = 0
        self.panel.poll()
        self.child.poll.return_value = None
        self.assertTrue(self.panel.start(self.identity, confirm=lambda: True))
        self.assertNotEqual(first, self.panel.output)
        self.assertNotIn('--mumble', self.spawn.call_args.args[0])
        self.child.poll.return_value = 0
        self.panel.poll()

    def test_stop_retries_until_registered_control_without_killing(self):
        self.panel.start(self.identity)
        self.stop.side_effect = [{'state': 'refused'}, {'state': 'published'}]
        self.panel.stop()
        self.panel.poll()
        self.assertEqual(self.stop.call_count, 2)
        self.assertFalse(self.panel.start(self.identity))
        self.child.poll.return_value = 0
        self.panel.poll()

    def test_spawn_error_closes_log_and_does_not_claim_running(self):
        self.spawn.side_effect = OSError('SYNTHETIC failure')
        self.assertFalse(self.panel.start(self.identity))
        self.assertFalse(self.panel.running)
        self.assertIsNone(self.panel.log)

    def test_explicit_operator_scratch_default_not_agent_profile(self):
        from cerveau.playtest_ui import operator_scratch
        value = operator_scratch({'LOCALAPPDATA': str(self.root)})
        self.assertTrue(value.is_absolute())
        self.assertEqual(value.relative_to(self.root).parts,
                         ('hermes', 'operator-playtest', 'cache', 'scratch'))
        self.assertEqual(operator_scratch({'CERVHOTS_SCRATCH': str(self.root)}), self.root)
        with self.assertRaises(ValueError):
            operator_scratch({'CERVHOTS_SCRATCH': 'relative'})

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows Tk CMD smoke')
    def test_real_cmd_opens_tk_buttons_without_autostart(self):
        import os
        import subprocess
        import sys
        root = Path(__file__).resolve().parents[1]
        # Test-only child hook closes the REAL Tk panel, never presses Start.
        hook = self.root/'sitecustomize.py'
        hook.write_text('''import socket, subprocess, tkinter as tk
def forbidden(*a, **k):
    raise AssertionError('SYNTHETIC no subprocess/network/audio')
socket.socket.connect = forbidden
subprocess.Popen = forbidden
original = tk.Tk
def create(*a, **k):
    window = original(*a, **k)
    def inspect():
        labels = [w.cget('text') for w in window.winfo_children() if isinstance(w, tk.Button)]
        assert len(labels) == 5, labels
        assert 'Arrêter' in labels
        assert 'Démarrer voix Mumble' in labels
        print('SYNTHETIC_TK_OPEN_NO_AUTOSTART', flush=True)
        window.destroy()
    window.after(350, inspect)
    return window
tk.Tk = create
''', encoding='utf-8')
        env = dict(os.environ, CERVHOTS_PYTHON=sys.executable, PYTHONPATH=str(self.root))
        env.pop('CERVHOTS_SCRATCH', None)
        run = subprocess.run(['cmd.exe', '/d', '/c', str(root/'tools/playtest-panel.cmd')],
            cwd=root, env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
        self.assertIn('SYNTHETIC_TK_OPEN_NO_AUTOSTART', run.stdout)


if __name__ == '__main__':
    unittest.main()
