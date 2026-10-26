"""Reexecutable real-process passive lifecycle, exclusively SYNTHETIC.

Run sequentially (the real Windows reader mutex is deliberately shared):
  python -B -m unittest discover -s tests -p test_passive_lifecycle_process.py -v
No live/native/HUD, physical cost, map or CURRENT qualification is claimed.
"""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tests/helpers/passive_lifecycle_child.py'


@unittest.skipUnless(os.name == 'nt', 'Windows exact process handles and reader mutex')
class PassiveLifecycleProcessTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='cervhots-lifecycle-')).resolve()
        self.children = []
        self.commands = []
        self.addCleanup(self.cleanup)

    @staticmethod
    def creation(child):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        query = kernel.GetProcessTimes
        query.argtypes = (wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4))
        query.restype = wintypes.BOOL
        stamps = [wintypes.FILETIME() for _ in range(4)]
        if not query(int(child._handle), *(ctypes.byref(s) for s in stamps)):
            raise ctypes.WinError(ctypes.get_last_error())
        return (stamps[0].dwHighDateTime << 32) | stamps[0].dwLowDateTime

    def start(self, name, mode='normal', old=None, *, parent=None):
        parent = self.root / name if parent is None else parent
        parent.mkdir(exist_ok=True)
        stdout = (self.root / (name + '.stdout')).open('wb')
        stderr = (self.root / (name + '.stderr')).open('wb')
        # Avoid Windows venv redirectors: the Popen PID must be the interpreter
        # that calls main, not a launcher. Keep installed dependency paths.
        executable = getattr(sys, '_base_executable', sys.executable)
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(str(p) for p in sys.path if p)
        argv = [executable, '-B', str(HELPER), str(parent), mode]
        if old is not None:
            argv.append(str(old))
        child = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        self.children.append((child, self.creation(child), parent, stdout, stderr))
        self.commands.append(dict(argv=argv, pid=child.pid, creation=self.children[-1][1]))
        runtime = self.wait_file(parent / 'runtime.json', child)
        self.assertEqual(runtime['pid'], child.pid, 'venv redirector is not an owned interpreter')
        for value in (*runtime['env_temp'].values(), runtime['effective_temp']):
            self.assertEqual(Path(value), Path(tempfile.gettempdir()))
        return child, parent

    def wait_file(self, path, child, timeout=12):
        deadline = time.perf_counter() + timeout
        last_error = None
        while True:
            # Existence is not readiness: Windows can deny the actual open.
            # Retry only handshake absence/access, never malformed JSON or CLI IO.
            try:
                return json.loads(path.read_text(encoding='utf-8'))
            except (FileNotFoundError, PermissionError) as error:
                last_error = error
            if child.poll() is not None:
                self.fail('child exited before %s (last read: %r): %s' %
                          (path.name, last_error, self.diagnostics()))
            if time.perf_counter() >= deadline:
                self.fail('bounded handshake expired for %s (last read: %r): %s' %
                          (path.name, last_error, self.diagnostics()))
            time.sleep(.02)

    def diagnostics(self):
        return {p.name: p.read_text(encoding='utf-8', errors='replace')[-4096:]
                for p in self.root.glob('*.stderr')}

    def finish(self, child, expected):
        self.assertEqual(child.wait(timeout=12), expected, self.diagnostics())
        self.assertEqual(self.creation(child), next(c for p, c, *_ in self.children if p is child))

    def cli(self, name, *argv, expected=0):
        command = [getattr(sys, '_base_executable', sys.executable), '-B',
                   '-m', 'cerveau.passive_session', *map(str, argv)]
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(str(p) for p in sys.path if p)
        # Disk-only children have a bounded wait too. Popen retains the exact
        # Windows process handle; timeout cleanup never resolves a PID by name.
        out_path, err_path = self.root / (name + '.stdout'), self.root / (name + '.stderr')
        with out_path.open('wb') as out, err_path.open('wb') as err:
            child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=out, stderr=err)
            created = self.creation(child)
            try:
                code = child.wait(timeout=12)
            finally:
                if child.poll() is None:
                    self.assertEqual(self.creation(child), created)
                    child.terminate()
                    child.wait(timeout=5)
            self.commands.append(dict(argv=command, pid=child.pid, creation=created, code=code))
        self.assertEqual(code, expected, err_path.read_text())
        self.assertEqual(err_path.read_bytes(), b'')
        return json.loads(out_path.read_text())

    def stop(self, parent, name, *, output=None, target=None, expected=0):
        row = self.cli(name, '--request-stop', '--output-dir', output or parent / 'session',
                       '--stop-file', target or parent / 'STOP-SYNTHETIC', expected=expected)
        self.assertIsNone(row['reader_active'])
        self.assertFalse(row['current_permission'])
        return row

    @staticmethod
    def inventory(parent):
        return {p.relative_to(parent).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(),
                p.stat().st_mtime_ns) for p in parent.rglob('*') if p.is_file()}

    def assert_closed(self, parent):
        self.assertTrue((parent / 'source-closed.json').is_file(),
                        'terminal return without attested source.close')
        closed = json.loads((parent / 'source-closed.json').read_text())
        self.assertEqual(closed, dict(backend_none=True, probe_none=True, guard_released=True))
        self.assertTrue((parent / 'backend-closed.json').is_file())
        summary = json.loads((parent / 'session/summary.json').read_text())
        self.assertEqual(summary['reason'], 'stop_file')
        self.assertFalse(summary['reader_active'])
        self.assertGreaterEqual(summary['accepted'], 1)
        self.assertEqual(summary['attempts'], summary['accepted'])
        self.assertTrue((parent / 'passive-session.lock').is_file())
        status = self.cli(parent.name + '-status', '--status', '--output-dir', parent / 'session')
        self.assertEqual(status['state'], 'recorded_stopped')
        self.assertIsNone(status['reader_active'])
        self.assertFalse(status['current_permission'])

    def test_targeted_stop_terminal_close_then_independent_restart_and_foreign_receipt(self):
        first, a = self.start('A')
        old_observation = self.wait_file(a / 'observation-1.json', first)
        self.assertTrue((a / 'session/control.json').is_file())
        self.assertEqual(self.stop(a, 'A-stop')['state'], 'published')
        self.finish(first, 0)
        self.assert_closed(a)
        old_files = self.inventory(a)

        second, b = self.start('B', old=a / 'SYNTHETIC-receipt.json')
        new_observation = self.wait_file(b / 'observation-1.json', second)
        self.assertNotEqual(json.loads((a / 'first-read-context.json').read_text()),
                            json.loads((b / 'first-read-context.json').read_text()))
        self.assertNotEqual(old_observation['session'], new_observation['session'])
        self.assertNotEqual(old_observation['comparison']['session_token'],
                            new_observation['comparison']['session_token'])
        receipt = json.loads((b / 'foreign-receipt.json').read_text())
        self.assertEqual(receipt, dict(same_process_fresh=True, foreign_fresh=False,
                                     foreign_projected=False, age_forced_s=0))
        self.assertNotEqual((a / 'session/control.json').read_bytes(),
                            (b / 'session/control.json').read_bytes())
        self.assertEqual(self.stop(a, 'old-output-new-target', target=b / 'STOP-SYNTHETIC',
                                   expected=1)['state'], 'refused')
        # Byte-for-byte copied old control is not valid at a different output.
        fake = self.root / 'copied-control'
        fake.mkdir()
        (fake / 'control.json').write_bytes((a / 'session/control.json').read_bytes())
        self.assertEqual(self.stop(a, 'copied-control-refusal', output=fake,
                                   target=b / 'STOP-SYNTHETIC', expected=1)['state'], 'refused')
        self.assertEqual(self.stop(a, 'old-stop')['state'], 'already_present')
        self.assertFalse((b / 'STOP-SYNTHETIC').exists())
        # A second persisted read after the old STOP attempts demonstrates the
        # successor kept running, rather than relying on a historical status.
        self.wait_file(b / 'observation-2.json', second)
        self.assertIsNone(second.poll())
        self.assertEqual(self.inventory(a), old_files)
        self.assertEqual(self.stop(b, 'B-stop')['state'], 'published')
        self.finish(second, 0)
        self.assert_closed(b)
        self.assertEqual(self.inventory(a), old_files)

    def test_interruption_before_control_publication_never_opens_source_and_retains_claim(self):
        for mode in ('interrupt-before-control', 'interrupt-partial-control'):
            with self.subTest(mode=mode):
                child, parent = self.start(mode, mode)
                self.wait_file(parent / 'before-control.json', child)
                self.assertEqual(self.stop(parent, mode + '-stop', expected=1)['state'], 'refused')
                self.assertFalse((parent / 'STOP-SYNTHETIC').exists())
                (parent / 'interrupt').touch(exist_ok=False)
                self.finish(child, 130)
                self.assertFalse((parent / 'source-opened.json').exists())
                self.assertFalse((parent / 'session/summary.json').exists())
                claim = (parent / 'passive-session.lock').read_bytes()
                status = self.cli(mode + '-status', '--status', '--output-dir', parent / 'session', expected=1)
                self.assertEqual(status['state'], 'unknown')
                self.assertIsNone(status['reader_active'])
                self.assertFalse(status['current_permission'])
                # CLI reuse of the retained parent refuses, without repairing
                # old control, deleting the claim, or opening a source.
                result = self.cli(mode + '-reuse', '--live', '--player-file', parent / 'SYNTHETIC-identity.txt',
                    '--output-dir', parent / 'new', '--stop-file', parent / 'NEW-STOP', expected=1)
                self.assertEqual(result, dict(event='error', code='session_initialization_or_io'))
                self.assertEqual((parent / 'passive-session.lock').read_bytes(), claim)
                self.assertFalse((parent / 'new').exists())

    def test_uncertain_close_is_not_terminal_proof_and_blocks_fresh_process_until_exit(self):
        owner, a = self.start('uncertain', 'close-error')
        self.wait_file(a / 'observation-1.json', owner)
        self.stop(a, 'uncertain-stop')
        terminal = self.wait_file(a / 'terminal.json', owner)
        self.assertEqual(terminal['code'], 1)
        self.assertFalse(terminal['guard_released'])
        self.assertFalse(terminal['backend_none'])
        self.assertFalse((a / 'backend-closed.json').exists())
        self.assertFalse((a / 'source-closed.json').exists())
        summary = json.loads((a / 'session/summary.json').read_text())
        self.assertEqual(summary['reason'], 'source_close_failed')
        self.assertIsNone(summary['reader_active'])
        status = self.cli('uncertain-status', '--status', '--output-dir', a / 'session', expected=1)
        self.assertEqual(status['state'], 'unknown')
        self.assertIsNone(status['reader_active'])
        self.assertIsNone(status['recorded_reader_active'])
        self.assertFalse(status['current_permission'])
        contender, b = self.start('contender')
        self.finish(contender, 1)
        refused = json.loads((b / 'session/summary.json').read_text())
        self.assertEqual(refused['reason'], 'native_reader_unavailable')
        self.assertEqual(refused['accepted'], 0)
        self.assertFalse((b / 'source-opened.json').exists())
        self.assertIsNone(owner.poll())
        (a / 'release-uncertain-process').touch(exist_ok=False)
        self.finish(owner, 1)
        # Process exit releases exclusion, but does NOT retroactively confirm
        # backend close or authorize an automatic retry of an unknown live run.
        successor, c = self.start('after-independent-exit')
        self.wait_file(c / 'observation-1.json', successor)
        self.stop(c, 'after-exit-stop')
        self.finish(successor, 0)
        self.assert_closed(c)
        self.assertFalse((a / 'backend-closed.json').exists())

    def cleanup(self):
        cleanup = []
        preserved = False
        try:
            for child, created, parent, stdout, stderr in self.children:
                if child.poll() is None:
                    # Only these exact owned handles/creation identities. No
                    # global STOP, PID search, old job or other process touched.
                    self.assertEqual(self.creation(child), created)
                    for name in ('STOP-SYNTHETIC', 'interrupt', 'release-uncertain-process'):
                        (parent / name).touch(exist_ok=True)
                    try:
                        child.wait(timeout=4)
                    except subprocess.TimeoutExpired:
                        self.assertEqual(self.creation(child), created)
                        child.terminate()
                        child.wait(timeout=5)
                cleanup.append(dict(pid=child.pid, creation=created, code=child.returncode, waited=True))
                stdout.close()
                stderr.close()
                child._handle.Close()
            (self.root / 'processes.json').write_text(json.dumps(dict(
                commands=self.commands, cleanup=cleanup), indent=2), encoding='utf-8')
            destination = os.environ.get('CERVHOTS_LIFECYCLE_EVIDENCE')
            if destination:
                # Preserve ignored/generated evidence before any scratch cleanup.
                dest = Path(destination) / self.id().rsplit('.', 1)[-1]
                shutil.copytree(self.root, dest)
            preserved = True
        finally:
            # Never erase a failed preservation or cleanup. No worktree cleanup;
            # only this test's own scratch directory after confirmed child exit.
            if preserved:
                self.children.clear()
                shutil.rmtree(self.root)


if __name__ == '__main__':
    unittest.main()
