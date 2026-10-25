"""Local disk consistency only, never authentication or CURRENT permission."""
from contextlib import ExitStack
import hashlib
import json
import os
import re

from . import session_catalog as catalog

MARKER = 'COMPLETE.json'
MAX_FILES = 130
MAX_FILE_BYTES = 4 * 2**20
MAX_BYTES = 64 * 2**20
MAX_MARKER_BYTES = 32 * 2**10


def _digest(fd, budget):
    size = os.fstat(fd).st_size
    if size > MAX_FILE_BYTES or size > MAX_BYTES - budget[0]:
        raise ValueError('catalog_bytes_limit')
    budget[0] += size
    digest = hashlib.sha256()
    remaining = size
    while remaining:
        block = os.read(fd, min(remaining, 65536))
        if not block:
            raise ValueError('short_read')
        digest.update(block)
        remaining -= len(block)
    if os.read(fd, 1):
        raise ValueError('changed_file')
    return size, digest.hexdigest()


def _commit_marker(path, text):
    """An exclusive Windows handle, delete-pending until flush/fsync succeeds.

    Process termination before commit deletes the incomplete marker. Never alter
    a pre-existing marker. No directory rename and no weakened sharing flags.
    """
    if os.name != 'nt':
        raise OSError('secure_publication_unavailable')
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    disposition = kernel.SetFileInformationByHandle
    disposition.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    disposition.restype = wintypes.BOOL
    class DeleteInfo(ctypes.Structure):
        _fields_ = [('delete', wintypes.BOOL)]
    handle = create(str(path), 0x80000000 | 0x40000000 | 0x10000, 0, None, 1,
                    0x00200000, None)  # CREATE_NEW; no sharing
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    stream = None
    try:
        pending = DeleteInfo(True)
        if not disposition(handle, 4, ctypes.byref(pending), ctypes.sizeof(pending)):
            raise ctypes.WinError(ctypes.get_last_error())
        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
        stream = os.fdopen(fd, 'wb')
        stream.write(text.encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())
        pending.delete = False
        if not disposition(handle, 4, ctypes.byref(pending), ctypes.sizeof(pending)):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        if stream is not None:
            stream.close()
        else:
            close(handle)


def publish(target, result):
    names = ['INDEX.html', 'catalog.json']
    for entry in result['sessions']:
        if entry['report'] is not None:
            folder = 'session-%03d' % entry['ordinal']
            names.extend((folder+'/REPORT.html', folder+'/report.json'))
    with ExitStack() as guards:
        files, budget = [], [0]
        for name in sorted(names):
            fd = guards.enter_context(catalog._pin(target/name))
            size, digest = _digest(fd, budget)
            files.append(dict(path=name, bytes=size, sha256=digest))
        text = catalog._dump(dict(event='session_catalog_completion', schema_version=1, files=files))
        if len(text.encode('utf-8')) > MAX_MARKER_BYTES:
            raise ValueError('marker_limit')
        _commit_marker(target/MARKER, text)


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate_key')
        value[key] = item
    return value


def _manifest(raw):
    value = json.loads(raw, object_pairs_hook=_pairs)
    if (not isinstance(value, dict) or set(value) != {'event', 'schema_version', 'files'}
            or value['event'] != 'session_catalog_completion'
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or not isinstance(value['files'], list) or not 2 <= len(value['files']) <= MAX_FILES):
        raise ValueError('marker_schema')
    names, total = [], 0
    for item in value['files']:
        if not isinstance(item, dict) or set(item) != {'path', 'bytes', 'sha256'}:
            raise ValueError('file_schema')
        name = item['path']
        if not isinstance(name, str):
            raise ValueError('file_name')
        if name not in ('INDEX.html', 'catalog.json'):
            match = re.fullmatch(r'session-([0-9]{3})/(REPORT\.html|report\.json)', name)
            if match is None or not 1 <= int(match[1]) <= catalog.MAX_SESSIONS:
                raise ValueError('file_name')
        if (type(item['bytes']) is not int or not 0 <= item['bytes'] <= MAX_FILE_BYTES
                or not isinstance(item['sha256'], str)
                or re.fullmatch('[0-9a-f]{64}', item['sha256']) is None):
            raise ValueError('file_metadata')
        total += item['bytes']
        names.append(name)
    if (total > MAX_BYTES or names != sorted(set(names))
            or not {'INDEX.html', 'catalog.json'}.issubset(names)):
        raise ValueError('file_inventory')
    folders = {name.split('/')[0] for name in names if '/' in name}
    expected = {'INDEX.html', 'catalog.json'}
    for folder in folders:
        expected.update((folder+'/REPORT.html', folder+'/report.json'))
    if set(names) != expected:
        raise ValueError('report_pair')
    # Exact producer bytes, including the final newline. A truncated suffix that
    # happens to remain valid JSON must not become a completed publication.
    canonical = dict(event='session_catalog_completion', schema_version=1,
                     files=[dict(path=item['path'], bytes=item['bytes'], sha256=item['sha256'])
                            for item in value['files']])
    if raw != catalog._dump(canonical).encode('utf-8'):
        raise ValueError('marker_encoding')
    return value


def _children(path, expected):
    # Refuse extras as well as missing entries. Never follow an enumerated name.
    # Cap iterator pulls, including a single excess entry, before sorting anything.
    found = set()
    with os.scandir(path) as iterator:
        for child in iterator:
            if child.name not in expected or child.name in found:
                raise ValueError('unexpected_entry')
            found.add(child.name)
    if found != expected:
        raise ValueError('missing_entry')


def verify(target):
    target = catalog._absolute(target)
    with ExitStack() as guards:
        catalog._ancestors(guards, target)
        # Canonical alias resolution only with every ancestor pinned.
        target = target.resolve()
        try:
            fd = guards.enter_context(catalog._pin(target/MARKER))
        except FileNotFoundError:
            return 'unverifiable', 'marker_absent', 4
        size = os.fstat(fd).st_size
        if not 0 < size <= MAX_MARKER_BYTES:
            raise ValueError('marker_limit')
        raw = os.read(fd, size + 1)
        if len(raw) != size:
            raise ValueError('marker_changed')
        value = _manifest(raw)
        folders = {item['path'].split('/')[0] for item in value['files'] if '/' in item['path']}
        _children(target, {MARKER, 'INDEX.html', 'catalog.json'} | folders)
        for folder in sorted(folders):
            directory = target/folder
            guards.enter_context(catalog._pin(directory, directory=True))
            _children(directory, {'REPORT.html', 'report.json'})
        budget = [0]
        for item in value['files']:
            # Only validated closed names reach path construction. Keep ALL file
            # handles until the result: no earlier file can change mid-verification.
            fd = guards.enter_context(catalog._pin(target/item['path']))
            size, digest = _digest(fd, budget)
            if size != item['bytes'] or digest != item['sha256']:
                raise ValueError('file_changed')
        # Directory sharing pins names against substitution, not child creation.
        # Recheck the closed namespace after hashing, with every file still held.
        _children(target, {MARKER, 'INDEX.html', 'catalog.json'} | folders)
        for folder in sorted(folders):
            _children(target/folder, {'REPORT.html', 'report.json'})
        return 'complete', 'local_integrity_only', 0


def run(args):
    try:
        state, reason, code = verify(args.report_dir)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        state, reason, code = 'damaged_or_refused', 'local_verification_refused', 3
    print(catalog._dump(dict(event='session_catalog_verification', schema_version=1,
                            state=state, reason=reason, basis='historical_not_current',
                            authenticated=False, current_permission=False,
                            hud_validated=False)).strip())
    return code
