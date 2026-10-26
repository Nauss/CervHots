"""SYNTHETIC parent-handshake regressions, not historical-cause evidence."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import time
import tempfile
import unittest
from unittest.mock import Mock, patch

import test_passive_lifecycle_process as lifecycle


class HandshakeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='cervhots-handshake-')
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'ready.json'
        self.path.write_text('{"ready": true}', encoding='utf-8')
        self.parent = lifecycle.PassiveLifecycleProcessTests()
        self.parent.diagnostics = Mock(return_value={'child.stderr': 'SYNTHETIC diagnostic'})
        self.child = Mock()
        self.child.poll.return_value = None

    def test_present_file_transient_permission_error_then_readable(self):
        self.assertTrue(self.path.is_file())
        denied = PermissionError(13, 'SYNTHETIC sharing denial', str(self.path))
        with patch.object(Path, 'read_text', side_effect=[denied, '{"ready": true}']) as read:
            self.assertEqual(self.parent.wait_file(self.path, self.child), {'ready': True})
        self.assertEqual(read.call_count, 2)
        self.child.poll.assert_called()

    def test_absent_then_published(self):
        self.path.unlink()
        with patch.object(lifecycle.time, 'sleep', side_effect=lambda _: self.path.write_text('{}')):
            self.assertEqual(self.parent.wait_file(self.path, self.child), {})

    def assert_bounded_failure(self, read_error=None):
        clock = [100.0]
        def advance(seconds):
            self.assertEqual(seconds, .02, 'do not mask readiness with longer sleeps')
            clock[0] += seconds
        with patch.object(lifecycle.time, 'perf_counter', side_effect=lambda: clock[0]), \
                patch.object(lifecycle.time, 'sleep', side_effect=advance) as sleep:
            if read_error is None:
                self.path.unlink()
                with self.assertRaisesRegex(AssertionError, 'bounded handshake expired.*FileNotFoundError.*SYNTHETIC diagnostic'):
                    self.parent.wait_file(self.path, self.child, timeout=.05)
            else:
                with patch.object(Path, 'read_text', side_effect=read_error) as read:
                    with self.assertRaisesRegex(AssertionError, 'bounded handshake expired.*PermissionError.*last denial.*SYNTHETIC diagnostic'):
                        self.parent.wait_file(self.path, self.child, timeout=.05)
                self.assertEqual(read.call_count, 4)
        self.assertEqual(sleep.call_count, 3)
        self.assertLessEqual(clock[0] - 100, .05 + .02)

    def test_absence_expires_with_diagnostics_in_budget(self):
        self.assert_bounded_failure()

    def test_persistent_permission_expires_with_last_diagnostic_in_budget(self):
        self.assert_bounded_failure(PermissionError(13, 'last denial', str(self.path)))

    def test_child_exit_during_unreadable_handshake_is_not_retried(self):
        self.child.poll.return_value = 17
        with patch.object(Path, 'read_text', side_effect=PermissionError(13, 'last denial')), \
                patch.object(lifecycle.time, 'sleep') as sleep:
            with self.assertRaisesRegex(AssertionError, 'child exited.*PermissionError.*last denial.*SYNTHETIC diagnostic'):
                self.parent.wait_file(self.path, self.child)
        sleep.assert_not_called()

    def test_child_exit_before_publication_is_not_retried(self):
        self.path.unlink()
        self.child.poll.return_value = 17
        with self.assertRaisesRegex(AssertionError, 'child exited.*FileNotFoundError.*SYNTHETIC diagnostic'):
            self.parent.wait_file(self.path, self.child)

    def test_invalid_json_fails_explicitly_without_retry(self):
        self.path.write_text('{', encoding='utf-8')
        with patch.object(lifecycle.time, 'sleep') as sleep:
            with self.assertRaises(json.JSONDecodeError):
                self.parent.wait_file(self.path, self.child)
        sleep.assert_not_called()

    def test_other_os_error_is_not_retried(self):
        with patch.object(Path, 'read_text', side_effect=IsADirectoryError('not a handshake')), \
                patch.object(lifecycle.time, 'sleep') as sleep:
            with self.assertRaises(IsADirectoryError):
                self.parent.wait_file(self.path, self.child)
        sleep.assert_not_called()

    def test_real_clock_permission_timeout_is_bounded(self):
        started = time.perf_counter()
        with patch.object(Path, 'read_text', side_effect=PermissionError('persistent real clock')):
            with self.assertRaisesRegex(AssertionError, 'bounded handshake expired.*persistent real clock'):
                self.parent.wait_file(self.path, self.child, timeout=.05)
        elapsed = time.perf_counter() - started
        self.assertGreaterEqual(elapsed, .05)
        self.assertLess(elapsed, 1.0)

    @unittest.skipUnless(os.name == 'nt', 'real Windows sharing denial')
    def test_real_windows_exclusive_handle_then_readable(self):
        # Controlled OS reproduction, NOT a claim about the historical publisher.
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        create.restype = wintypes.HANDLE
        close = kernel.CloseHandle
        close.argtypes = (wintypes.HANDLE,)
        close.restype = wintypes.BOOL
        handle = create(str(self.path), 0x80000000, 0, None, 3, 0, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        held = [True]
        def release(_=None):
            if held[0]:
                self.assertTrue(close(handle))
                held[0] = False
        self.addCleanup(release)
        self.assertTrue(self.path.is_file())
        with self.assertRaises(PermissionError):
            self.path.read_text(encoding='utf-8')
        with patch.object(lifecycle.time, 'sleep', side_effect=release) as sleep:
            self.assertEqual(self.parent.wait_file(self.path, self.child), {'ready': True})
        sleep.assert_called_once_with(.02)
        self.child.poll.assert_called_once()


if __name__ == '__main__':
    unittest.main()
