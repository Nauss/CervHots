"""Real OS ownership, synthetic backend only: no game discovery or physical read."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

HELPER = Path(__file__).parent / 'helpers' / 'native_reader_child.py'

@unittest.skipUnless(os.name == 'nt', 'Windows kernel protocol')
class NativeReaderProcessTests(unittest.TestCase):
    def child(self, parent, action='close'):
        return subprocess.Popen([sys.executable, '-B', str(HELPER), str(parent), action],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)

    def finish(self, child, command='close', *, diagnostic=False):
        out, err = child.communicate(command + '\n', timeout=30)
        if diagnostic:
            self.assertIn('Diagnostic historique', err)
        else:
            self.assertEqual(err, '')
        return out

    def test_other_parent_refused_before_backend_open_then_normal_exit_releases(self):
        with tempfile.TemporaryDirectory() as root:
            a, b, c = (Path(root) / name for name in ('A', 'B', 'C'))
            owner = self.child(a, 'hold')
            try:
                self.assertEqual(owner.stdout.readline().strip(), 'OWNED')
                claim = (a / 'passive-session.lock').read_bytes()
                contender = self.child(b)
                out = self.finish(contender)
                self.assertEqual(contender.returncode, 1, out)
                self.assertIn('ReaderGuardError', out)
                self.assertFalse((b / 'transport.jsonl').exists(), 'backend opened under another parent')
            finally:
                self.finish(owner)
            self.assertEqual(owner.returncode, 0)
            successor = self.child(c)
            self.assertIn('CLOSED', self.finish(successor))
            self.assertEqual(successor.returncode, 0)
            self.assertEqual((a / 'passive-session.lock').read_bytes(), claim)
            self.assertEqual((a / 'transport.jsonl').read_text().splitlines(),
                             ['{"event": "open"}', '{"event": "close"}'])

    def test_crash_releases_os_ownership_without_mutating_claim(self):
        with tempfile.TemporaryDirectory() as root:
            a, b = (Path(root) / name for name in ('A', 'B'))
            owner = self.child(a, 'hold')
            self.assertEqual(owner.stdout.readline().strip(), 'OWNED')
            claim = (a / 'passive-session.lock').read_bytes()
            self.finish(owner, 'crash')
            self.assertEqual(owner.returncode, 37)
            successor = self.child(b)
            self.assertIn('CLOSED', self.finish(successor))
            self.assertEqual(successor.returncode, 0)
            self.assertEqual((a / 'passive-session.lock').read_bytes(), claim)
            self.assertEqual((a / 'transport.jsonl').read_text().splitlines(), ['{"event": "open"}'])

    def test_initialization_error_releases_guard_for_another_parent(self):
        with tempfile.TemporaryDirectory() as root:
            broken = self.child(Path(root) / 'broken', 'init_error')
            self.assertIn('RuntimeError', self.finish(broken))
            self.assertEqual(broken.returncode, 1)
            successor = self.child(Path(root) / 'next')
            self.assertIn('CLOSED', self.finish(successor))
            self.assertEqual(successor.returncode, 0)

    def test_guard_refusal_has_actionable_product_reason(self):
        from cerveau import passive_session as product
        from cerveau.native_reader_guard import ReaderGuardError
        def refused():
            raise ReaderGuardError('PRIVATE')
        rows = []
        result = product.run_session(refused, lambda: False, rows.append, duration=1)
        self.assertEqual(result['reason'], 'native_reader_unavailable')
        self.assertEqual(result['accepted'], 0)
        self.assertNotIn('PRIVATE', str(rows))

    def test_partial_backend_initialization_close_failure_stays_unknown(self):
        from cerveau import passive_session as product
        from hotstate.reader import NativeBackendCloseError
        def uncertain():
            raise NativeBackendCloseError('PRIVATE')
        result = product.run_session(uncertain, lambda: False, lambda row: None, duration=1)
        self.assertEqual(result['reason'], 'source_close_failed')
        self.assertIsNone(result['reader_active'])

    def test_backend_close_uncertainty_is_not_a_success(self):
        from unittest.mock import MagicMock
        from hotstate.reader import ProcessBackend
        backend = ProcessBackend.__new__(ProcessBackend)
        backend.k32 = MagicMock()
        backend.k32.CloseHandle.return_value = False
        backend.handle = 123
        with self.assertRaises(OSError):
            backend.close()
        self.assertEqual(backend.handle, 123)

    def test_non_main_thread_cannot_own_a_source(self):
        from cerveau import passive_session as product
        from unittest.mock import patch
        import threading
        outcomes = []
        def attempt():
            try:
                source = product.NativeSource('SYNTHETIC')
            except Exception as exc:
                outcomes.append(type(exc).__name__)
            else:
                source.close()
                outcomes.append('OPENED')
        with patch('hotstate.reader.ProcessBackend'), patch('hotstate.native_context.NativeContextProbe'):
            worker = threading.Thread(target=attempt)
            worker.start(); worker.join(10)
        self.assertEqual(outcomes, ['ReaderGuardError'])

    def test_read_and_close_from_non_owner_thread_are_refused_before_backend(self):
        from cerveau import passive_session as product
        import threading
        outcomes = []
        with patch('hotstate.reader.ProcessBackend') as backend, \
                patch('hotstate.native_context.NativeContextProbe'), \
                patch('hotstate.live.read_current') as read:
            source = product.NativeSource('SYNTHETIC')
            try:
                def attempt():
                    for operation in (lambda: source.read(lambda row: None), source.close):
                        try:
                            operation()
                        except Exception as exc:
                            outcomes.append(type(exc).__name__)
                        else:
                            outcomes.append('UNSAFE')
                thread = threading.Thread(target=attempt)
                thread.start(); thread.join(10)
                self.assertEqual(outcomes, ['ReaderGuardError', 'ReaderGuardError'])
                read.assert_not_called()
                backend.return_value.close.assert_not_called()
            finally:
                source.close()

    def test_real_cli_contender_reports_recovery_without_backend_or_permission(self):
        import json
        with tempfile.TemporaryDirectory() as root:
            owner = self.child(Path(root) / 'A', 'hold')
            try:
                self.assertEqual(owner.stdout.readline().strip(), 'OWNED')
                parent = Path(root) / 'B'
                contender = self.child(parent, 'cli_live')
                out = self.finish(contender)
                self.assertEqual(contender.returncode, 1, out)
                summary = json.loads((parent / 'new' / 'summary.json').read_text())
                self.assertEqual(summary['reason'], 'native_reader_unavailable')
                self.assertEqual(summary['accepted'], 0)
                self.assertIn('STOP', summary['recovery'])
                self.assertFalse(summary['current_permission'])
                self.assertFalse((parent / 'transport.jsonl').exists())
                from cerveau import passive_session as product
                from cerveau.session_diagnosis import diagnose
                status = product.session_status(parent / 'new')
                self.assertEqual(status['state'], 'recorded_stopped')
                self.assertEqual(status['reason'], 'native_reader_unavailable')
                self.assertIsNone(status['reader_active'])
                self.assertFalse(status['current_permission'])
                diagnosis = diagnose(parent / 'new' / 'events.jsonl')
                self.assertEqual(diagnosis['stop']['recorded_reason'], 'native_reader_unavailable')
                self.assertFalse(diagnosis['current_permission'])
            finally:
                self.finish(owner)

    def test_non_reader_cli_modes_and_preexisting_stop_do_not_acquire(self):
        with tempfile.TemporaryDirectory() as root:
            owner = self.child(Path(root) / 'A', 'hold')
            try:
                self.assertEqual(owner.stdout.readline().strip(), 'OWNED')
                for mode, expected in (('stop', 0), ('status', 1), ('preflight', 0), ('diagnose', 0)):
                    with self.subTest(mode=mode):
                        parent = Path(root) / mode
                        child = self.child(parent, 'cli_' + mode)
                        out = self.finish(child, diagnostic=(mode == 'diagnose'))
                        self.assertEqual(child.returncode, expected, out)
                        self.assertNotIn('NO_READER_GUARD', out)
                        self.assertFalse((parent / 'transport.jsonl').exists())
                        self.assertFalse((parent / 'passive-session.lock').exists())
                        if mode == 'stop':
                            self.assertTrue((parent / 'STOP').is_file())
                            self.assertFalse((parent / 'new').exists())
            finally:
                self.finish(owner)

    def test_uncertain_closure_keeps_exclusion_until_process_exit(self):
        for action in ('close_error', 'init_close_error'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as root:
                owner = self.child(Path(root) / 'A', action)
                try:
                    if action == 'close_error':
                        self.assertEqual(owner.stdout.readline().strip(), 'OWNED')
                        owner.stdin.write('close\n'); owner.stdin.flush()
                    self.assertIn('Error', owner.stdout.readline().strip())
                    self.assertEqual(owner.stdout.readline().strip(), 'UNCERTAIN')
                    contender = self.child(Path(root) / 'B')
                    self.assertIn('ReaderGuardError', self.finish(contender))
                    self.assertEqual(contender.returncode, 1)
                    self.assertFalse((Path(root) / 'B' / 'transport.jsonl').exists())
                finally:
                    self.finish(owner, 'exit')
                successor = self.child(Path(root) / 'C')
                self.assertIn('CLOSED', self.finish(successor))
                self.assertEqual(successor.returncode, 0)

    def test_simultaneous_processes_have_exactly_one_backend_owner(self):
        with tempfile.TemporaryDirectory() as root:
            children = [self.child(Path(root) / str(i), 'hold') for i in range(5)]
            try:
                statuses = [child.stdout.readline().strip() for child in children]
                self.assertEqual(statuses.count('OWNED'), 1, statuses)
                self.assertEqual(statuses.count('ReaderGuardError'), 4, statuses)
                opened = list(Path(root).glob('*/transport.jsonl'))
                self.assertEqual(len(opened), 1)
            finally:
                for child in children:
                    self.finish(child)

    def test_guard_is_held_until_backend_close_returns(self):
        with tempfile.TemporaryDirectory() as root:
            owner = self.child(Path(root) / 'A', 'close_hold')
            try:
                self.assertEqual(owner.stdout.readline().strip(), 'OWNED')
                self.assertEqual(owner.stdout.readline().strip(), 'CLOSING')
                contender = self.child(Path(root) / 'B')
                self.assertIn('ReaderGuardError', self.finish(contender))
                self.assertEqual(contender.returncode, 1)
                self.assertFalse((Path(root) / 'B' / 'transport.jsonl').exists())
            finally:
                self.finish(owner)
            successor = self.child(Path(root) / 'C')
            self.assertIn('CLOSED', self.finish(successor))
            self.assertEqual(successor.returncode, 0)

    def test_same_process_recursion_cannot_open_a_second_backend(self):
        from cerveau import passive_session as product
        from cerveau.native_reader_guard import ReaderGuardError
        with patch('hotstate.reader.ProcessBackend') as backend, \
                patch('hotstate.native_context.NativeContextProbe'):
            source = product.NativeSource('SYNTHETIC')
            try:
                with self.assertRaises(ReaderGuardError):
                    product.NativeSource('SYNTHETIC')
                self.assertEqual(backend.call_count, 1)
            finally:
                source.close()
            source.close()  # idempotent; does not release another owner's mutex
            with self.assertRaises(ReaderGuardError):
                source.read(lambda row: None)

    def test_acquisition_failures_never_claim_ownership(self):
        import threading
        from cerveau import native_reader_guard as guard
        for handle, wait in ((None, 0), (123, 258), (123, 0xffffffff), (123, 42), (123, 0x80)):
            with self.subTest(handle=handle, wait=wait):
                kernel = MagicMock()
                kernel.CreateMutexW.return_value = handle
                kernel.WaitForSingleObject.return_value = wait
                kernel.ReleaseMutex.return_value = True
                kernel.CloseHandle.return_value = True
                latch, held = threading.Lock(), set()
                with patch.object(guard, '_LOCAL', latch), patch.object(guard, '_HELD', held), \
                        patch.object(guard.ctypes, 'WinDLL', return_value=kernel):
                    with self.assertRaises(guard.ReaderGuardError):
                        guard.NativeReaderGuard().acquire()
                    self.assertFalse(latch.locked())
                    self.assertEqual(held, set())
                if handle:
                    kernel.CloseHandle.assert_called_once_with(handle)
                else:
                    kernel.WaitForSingleObject.assert_not_called()

    def test_acquisition_uncertainty_retains_local_latch_and_handle(self):
        import threading
        from cerveau import native_reader_guard as guard
        for wait, release, close in ((0x80, False, True), (258, True, False)):
            with self.subTest(wait=wait):
                kernel = MagicMock()
                kernel.CreateMutexW.return_value = 123
                kernel.WaitForSingleObject.return_value = wait
                kernel.ReleaseMutex.return_value = release
                kernel.CloseHandle.return_value = close
                latch, held = threading.Lock(), set()
                with patch.object(guard, '_LOCAL', latch), patch.object(guard, '_HELD', held), \
                        patch.object(guard.ctypes, 'WinDLL', return_value=kernel):
                    instance = guard.NativeReaderGuard()
                    with self.assertRaises(guard.ReaderGuardError):
                        instance.acquire()
                    self.assertTrue(latch.locked())
                    self.assertIn(instance, held)
                    self.assertEqual(instance.handle, 123)

    def test_abandoned_existing_mutex_is_refused_not_a_permission(self):
        import ctypes
        from ctypes import wintypes as wt
        from cerveau.native_reader_guard import MUTEX_NAME
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [wt.LPVOID, wt.BOOL, wt.LPCWSTR]
        kernel.CreateMutexW.restype = wt.HANDLE
        kernel.CloseHandle.argtypes = [wt.HANDLE]
        kernel.CloseHandle.restype = wt.BOOL
        with tempfile.TemporaryDirectory() as root:
            owner = self.child(Path(root) / 'A', 'hold')
            keeper = None
            try:
                self.assertEqual(owner.stdout.readline().strip(), 'OWNED')
                keeper = kernel.CreateMutexW(None, False, MUTEX_NAME)
                self.assertTrue(keeper)
                self.finish(owner, 'crash')
                contender = self.child(Path(root) / 'B')
                self.assertIn('ReaderGuardError', self.finish(contender))
                self.assertEqual(contender.returncode, 1)
                self.assertFalse((Path(root) / 'B' / 'transport.jsonl').exists())
                successor = self.child(Path(root) / 'C')
                self.assertIn('CLOSED', self.finish(successor))
                self.assertEqual(successor.returncode, 0)
            finally:
                if owner.poll() is None:
                    self.finish(owner)
                if keeper:
                    self.assertTrue(kernel.CloseHandle(keeper))
