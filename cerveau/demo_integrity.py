"""Bounded SYNTHETIC demo completion; reuses catalogue Windows primitives.

Not a directory transaction, signature, liveness or data-admissibility proof.
The fixed version-1 namespace includes sources, all reports and nested seal.
"""
from contextlib import ExitStack
import json
import os
import re
from pathlib import PurePosixPath

from . import catalog_integrity as integrity
from . import session_catalog as catalog

MARKER = 'DEMO_COMPLETE.json'
MAX_MARKER_BYTES = 16 * 1024
MAX_FILE_BYTES = 256 * 1024
MAX_BYTES = 512 * 1024


def _names():
    names = {'SYNTHETIC.txt', 'demo.json', 'catalog/COMPLETE.json',
             'catalog/INDEX.html', 'catalog/catalog.json'}
    for ordinal in (2, 3, 4):
        names.update('catalog/session-%03d/%s' % (ordinal, leaf)
                     for leaf in ('REPORT.html', 'report.json'))
    for case in ('absent', 'refused', 'unknown', 'zero'):
        names.add('synthetic-sessions/'+case+'/SYNTHETIC.txt')
        names.add('synthetic-sessions/'+case+('/status.json' if case == 'absent' else '/events.jsonl'))
        for mode, leaves in (('diagnosis', ('SUMMARY.txt', 'diagnosis.json')),
                             ('summary', ('SUMMARY.txt', 'history.json')),
                             ('html', ('REPORT.html', 'report.json'))):
            names.update('reports/'+case+'/'+mode+'/'+leaf for leaf in leaves)
    return tuple(sorted(names))


NAMES = _names()


def _tree():
    children = {'': {MARKER}}
    for name in NAMES:
        parts = PurePosixPath(name).parts
        for i, part in enumerate(parts):
            children.setdefault('/'.join(parts[:i]), set()).add(part)
    return children


TREE = _tree()


def _namespace(target, *, complete):
    for folder, children in sorted(TREE.items()):
        expected = children if folder or complete else children - {MARKER}
        integrity._children(target/folder, expected)


def _pin_tree(guards, target):
    for folder in sorted(TREE):
        if folder:
            guards.enter_context(catalog._pin(target/folder, directory=True))


def _inventory(guards, target):
    files, budget = [], [0]
    for name in NAMES:
        fd = guards.enter_context(catalog._pin(target/name))
        # Tighter demo bounds, then the common bounded handle hasher.
        size = os.fstat(fd).st_size
        if not 0 < size <= MAX_FILE_BYTES or budget[0] + size > MAX_BYTES:
            raise ValueError('demo_bytes_limit')
        size, digest = integrity._digest(fd, budget)
        files.append(dict(path=name, bytes=size, sha256=digest))
    return files


def _dump(files):
    return catalog._dump(dict(event='offline_demo_completion', schema_version=1,
                              data_kind='SYNTHETIC', files=files))


def _manifest(raw):
    value = json.loads(raw, object_pairs_hook=integrity._pairs)
    if (not isinstance(value, dict)
            or set(value) != {'event', 'schema_version', 'data_kind', 'files'}
            or value['event'] != 'offline_demo_completion'
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['data_kind'] != 'SYNTHETIC'
            or not isinstance(value['files'], list) or len(value['files']) != len(NAMES)):
        raise ValueError('demo_marker_schema')
    total = 0
    for name, item in zip(NAMES, value['files']):
        if (not isinstance(item, dict) or set(item) != {'path', 'bytes', 'sha256'}
                or item['path'] != name or type(item['bytes']) is not int
                or not 0 < item['bytes'] <= MAX_FILE_BYTES
                or not isinstance(item['sha256'], str)
                or re.fullmatch('[0-9a-f]{64}', item['sha256']) is None):
            raise ValueError('demo_file_schema')
        total += item['bytes']
    if total > MAX_BYTES or raw != _dump(value['files']).encode('utf-8'):
        raise ValueError('demo_marker_encoding_or_limit')
    return value['files']


def publish(target):
    """Called last under the producer's pinned ancestors; no writes after seal."""
    with ExitStack() as guards:
        _pin_tree(guards, target)
        _namespace(target, complete=False)
        files = _inventory(guards, target)
        _namespace(target, complete=False)
        text = _dump(files)
        if len(text.encode('utf-8')) > MAX_MARKER_BYTES:
            raise ValueError('demo_marker_limit')
        # Exclusive/no-sharing/delete-pending until actual flush + fsync.
        # All directories AND payload handles remain held through commitment.
        integrity._commit_marker(target/MARKER, text)


def verify(target):
    target = catalog._absolute(target)
    with ExitStack() as guards:
        catalog._ancestors(guards, target)
        target = target.resolve()
        try:
            fd = guards.enter_context(catalog._pin(target/MARKER))
        except FileNotFoundError:
            return 'unverifiable', 'demo_completion_absent_legacy_or_interrupted', 4
        size = os.fstat(fd).st_size
        if not 0 < size <= MAX_MARKER_BYTES:
            raise ValueError('demo_marker_limit')
        raw = os.read(fd, size + 1)
        if len(raw) != size:
            raise ValueError('demo_marker_changed')
        expected = _manifest(raw)
        _pin_tree(guards, target)
        _namespace(target, complete=True)
        files = _inventory(guards, target)
        if files != expected:
            raise ValueError('demo_file_changed')
        _namespace(target, complete=True)
        return 'complete', 'synthetic_local_integrity_only', 0


def run(target):
    try:
        state, reason, code = verify(target)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        state, reason, code = 'damaged_or_refused', 'demo_verification_refused', 3
    print(catalog._dump(dict(event='offline_demo_verification', schema_version=1,
        state=state, reason=reason, data_kind='SYNTHETIC', authenticated=False,
        current_permission=False, hud_validated=False)), end='')
    return code
