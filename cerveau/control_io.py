"""Bounded local no-follow handles for passive control metadata and STOP.

Windows handles deny write/delete sharing. POSIX uses relative directory FDs;
these do not prevent hostile ancestor renames. Neither path authenticates owner.
"""
from contextlib import contextmanager, ExitStack
import os
from pathlib import Path
import stat


def absolute(path):
    path = Path(path)
    if (not path.is_absolute() or len(str(path)) > 2048 or len(path.parts) > 64
            or path == Path(path.anchor) or '..' in path.parts):
        raise ValueError('unsafe_path')
    if os.name == 'nt':
        if len(path.drive) != 2 or path.drive[1] != ':':
            raise ValueError('local_path_required')
        for part in path.parts[1:]:
            stem = part.split('.')[0].upper()
            if (':' in part or part.endswith((' ', '.')) or
                    stem in {'CON', 'PRN', 'AUX', 'NUL',
                             *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}):
                raise ValueError('unsafe_path')
        import ctypes
        from ctypes import wintypes
        query = ctypes.WinDLL('kernel32', use_last_error=True).GetDriveTypeW
        query.argtypes = (wintypes.LPCWSTR,)
        query.restype = wintypes.UINT
        if query(path.anchor) not in (2, 3, 6):
            raise ValueError('local_drive_required')
    return path


def regular(info):
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, 'st_file_attributes', 0) & 0x400):
        raise ValueError('not_regular')


@contextmanager
def windows_handle(path, *, directory=False, create=False):
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    open_file = kernel.CreateFileW
    open_file.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                          ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    open_file.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    class Info(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD), ('creation', wintypes.FILETIME),
                    ('access', wintypes.FILETIME), ('write', wintypes.FILETIME),
                    ('volume', wintypes.DWORD), ('size_high', wintypes.DWORD),
                    ('size_low', wintypes.DWORD), ('links', wintypes.DWORD),
                    ('index_high', wintypes.DWORD), ('index_low', wintypes.DWORD)]
    inspect = kernel.GetFileInformationByHandle
    inspect.argtypes = (wintypes.HANDLE, ctypes.POINTER(Info))
    inspect.restype = wintypes.BOOL
    handle = open_file(str(path), 0x40000000 if create else 0x80000000, 1, None,
                       1 if create else 3, 0x00200000 | 0x02000000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    fd = None
    try:
        info = Info()
        if not inspect(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if (info.attributes & (0x400 | 0x40) or bool(info.attributes & 0x10) != directory
                or (not directory and info.links != 1)):
            raise ValueError('unsafe_object')
        if not directory:
            fd = msvcrt.open_osfhandle(handle, (os.O_WRONLY if create else os.O_RDONLY) | os.O_BINARY)
            handle = None
        yield fd
    finally:
        if fd is not None:
            os.close(fd)
        if handle is not None:
            close(handle)


@contextmanager
def parent(path):
    """Existing no-follow ancestors only; never mkdir or traverse a link."""
    with ExitStack() as stack:
        if os.name == 'nt':
            for ancestor in reversed((path.parent, *path.parent.parents)):
                stack.enter_context(windows_handle(ancestor, directory=True))
            if path.parent.resolve(strict=True) != path.parent:
                raise ValueError('noncanonical_parent')
            yield None
        else:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            fd = os.open(path.anchor, flags)
            stack.callback(os.close, fd)
            for part in path.parent.parts[1:]:
                fd = os.open(part, flags, dir_fd=fd)
                stack.callback(os.close, fd)
            yield fd


@contextmanager
def file_handle(path, parent_fd, *, create=False):
    if os.name == 'nt':
        with windows_handle(path, create=create) as fd:
            yield fd
    else:
        flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL if create else os.O_RDONLY | os.O_NONBLOCK)
        fd = os.open(path.name, flags | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            regular(os.fstat(fd))
            yield fd
        finally:
            os.close(fd)
