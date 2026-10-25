"""Windows kernel exclusion for cooperating passive NativeSource instances.

No disk proof, PID inference, stale-lock deletion or game permission. The fixed
Global name spans terminal sessions; default Windows ACL failures refuse access.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
import os
import threading

MUTEX_NAME = r'Global\CervHots.PassiveNativeReader.v1'
_LOCAL = threading.Lock()
# Keep uncertain ownership alive until process exit, even if a source is dropped.
_HELD = set()


class ReaderGuardError(RuntimeError):
    """Closed failure: native reader ownership was not safely established/released."""


class NativeReaderGuard:
    def __init__(self):
        self.handle = None
        self.owner = None
        self.kernel = None

    def acquire(self):
        if threading.current_thread() is not threading.main_thread():
            raise ReaderGuardError('native_reader_main_thread_required')
        if not _LOCAL.acquire(blocking=False):
            raise ReaderGuardError('native_reader_unavailable')
        try:
            if os.name != 'nt':
                raise ReaderGuardError('native_reader_unsupported')
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateMutexW.argtypes = [wt.LPVOID, wt.BOOL, wt.LPCWSTR]
            kernel.CreateMutexW.restype = wt.HANDLE
            kernel.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
            kernel.WaitForSingleObject.restype = wt.DWORD
            kernel.ReleaseMutex.argtypes = [wt.HANDLE]
            kernel.ReleaseMutex.restype = wt.BOOL
            kernel.CloseHandle.argtypes = [wt.HANDLE]
            kernel.CloseHandle.restype = wt.BOOL
            self.kernel = kernel
            self.handle = kernel.CreateMutexW(None, False, MUTEX_NAME)
            if not self.handle:
                raise ReaderGuardError('native_reader_unavailable')
            outcome = kernel.WaitForSingleObject(self.handle, 0)
            if outcome != 0:  # timeout, WAIT_FAILED, unexpected, or WAIT_ABANDONED
                # WAIT_ABANDONED transfers ownership, but is NOT accepted here.
                if outcome == 0x80 and not kernel.ReleaseMutex(self.handle):
                    raise ReaderGuardError('native_reader_ownership_uncertain')
                if not kernel.CloseHandle(self.handle):
                    raise ReaderGuardError('native_reader_ownership_uncertain')
                self.handle = None
                raise ReaderGuardError('native_reader_unavailable')
            self.owner = threading.get_ident()
            _HELD.add(self)
            return self
        except BaseException as exc:
            if self.handle:
                # Any uncertain API/cleanup outcome latches this process closed.
                _HELD.add(self)
            else:
                _LOCAL.release()
            if isinstance(exc, Exception):
                raise ReaderGuardError('native_reader_unavailable') from None
            raise

    def assert_owned(self):
        if self.handle is None or threading.get_ident() != self.owner:
            raise ReaderGuardError('native_reader_ownership_uncertain')

    def release(self):
        if self.handle is None:
            return
        self.assert_owned()
        if not self.kernel.ReleaseMutex(self.handle):
            raise ReaderGuardError('native_reader_ownership_uncertain')
        # ReleaseMutex established release; CloseHandle must still succeed before
        # permitting another source in this process. On uncertainty retain _LOCAL.
        if not self.kernel.CloseHandle(self.handle):
            raise ReaderGuardError('native_reader_ownership_uncertain')
        self.handle = None
        _HELD.remove(self)
        _LOCAL.release()
