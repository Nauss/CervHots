"""Bounded Windows-local catalogue composed from the existing historical renderer.

No discovery outside one explicit tree, no identities shared between reports.
Windows directory/read handles deny write/delete while their paths are used.
Other platforms fail closed until equivalent no-follow traversal is implemented.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from html import escape
import json
import os
from pathlib import Path
import stat

from . import session_html

MAX_DEPTH = 4
MAX_ENTRIES = 1024
MAX_SESSIONS = 64
MAX_TOTAL_BYTES = 16 * 2**20
JOURNAL_BYTES = 4 * 2**20


class ReparsePoint(ValueError):
    pass


class ByteLimit(ValueError):
    pass


def _drive_type(path):
    if os.name != 'nt':
        raise OSError('secure_traversal_unavailable')
    import ctypes
    from ctypes import wintypes
    query = ctypes.WinDLL('kernel32', use_last_error=True).GetDriveTypeW
    query.argtypes = (wintypes.LPCWSTR,)
    query.restype = wintypes.UINT
    return query(path.anchor)


def _absolute(path):
    # No UNC/network paths, device namespaces, ADS or lexical parent escapes.
    path = Path(path)
    if (not path.is_absolute() or len(path.drive) != 2 or path.drive[1] != ':'
            or any(part in ('.', '..') or ':' in part for part in path.parts[1:])
            or path == Path(path.anchor)):
        raise ValueError('local_absolute_path_required')
    if _drive_type(path) not in (2, 3, 6):  # removable, fixed, RAM; never mapped remote
        raise ValueError('local_drive_required')
    return path


@contextmanager
def _pin(path, *, directory=False):
    """Open the reparse object itself, inspect the HANDLE, and deny mutation.

    Ancestors must already be pinned. No path-based reopen of a journal follows
    this check. FILE_SHARE_READ alone also refuses an existing writing handle.
    """
    if os.name != 'nt':
        raise OSError('secure_traversal_unavailable')
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
    class Info(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD), ('creation', wintypes.FILETIME),
                    ('access', wintypes.FILETIME), ('write', wintypes.FILETIME),
                    ('volume', wintypes.DWORD), ('size_high', wintypes.DWORD),
                    ('size_low', wintypes.DWORD), ('links', wintypes.DWORD),
                    ('index_high', wintypes.DWORD), ('index_low', wintypes.DWORD)]
    info_fn = kernel.GetFileInformationByHandle
    info_fn.argtypes = (wintypes.HANDLE, ctypes.POINTER(Info))
    info_fn.restype = wintypes.BOOL
    handle = create(str(path), 0x80000000, 1, None, 3,
                    0x00200000 | 0x02000000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    fd = None
    try:
        info = Info()
        if not info_fn(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if info.attributes & 0x400:
            raise ReparsePoint('reparse_point')
        if bool(info.attributes & 0x10) != directory:
            raise ValueError('not_regular')
        if not directory:
            if info.links != 1:
                raise ValueError('hardlink_refused')
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            handle = None  # fd owns the handle from here onward.
        yield fd
    finally:
        if fd is not None:
            os.close(fd)
        if handle is not None:
            close(handle)


def _ancestors(stack, path):
    for parent in reversed((path, *path.parents)):
        stack.enter_context(_pin(parent, directory=True))


class _HandlePath:
    """The existing bounded parser reads only this already opened handle."""
    def __init__(self, fd):
        self.fd = fd

    def stat(self):
        return os.fstat(self.fd)

    def open(self, mode):
        if mode != 'rb':
            raise ValueError('read_only')
        return os.fdopen(os.dup(self.fd), mode)


def _read_report(path, budget):
    with _pin(path) as fd:
        snapshot = _HandlePath(fd)
        size = snapshot.stat().st_size
        charged = min(size, JOURNAL_BYTES + 1)
        if charged > MAX_TOTAL_BYTES - budget['bytes']:
            raise ByteLimit('bytes_limit')
        budget['bytes'] += charged
        return session_html.build(snapshot)


def _state(report):
    history = report['history']
    integrity = history['journal']['state']
    if integrity == 'unavailable':
        return 'unreadable'
    if (integrity in ('empty', 'truncated') or history['reason'] == 'session_closure_unknown'
            or (integrity == 'complete' and report['diagnosis']['counts']['boundaries'] == 0)):
        return 'incomplete'
    return 'recorded' if history['state'] == 'recorded_observation' else 'refused'


def _dump(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2)+'\n'


def render(result):
    rows = []
    for entry in result['sessions']:
        # URL is reconstructed from our ordinal, NEVER from any input text.
        link = ('<a href="session-%03d/REPORT.html">Rapport individuel</a>' % entry['ordinal']
                if entry['report'] is not None else 'Aucun rapport')
        cells = (str(entry['ordinal']), entry['state'], entry['reason'] or 'aucun')
        rows.append('<tr>'+''.join('<td>'+escape(str(c), quote=True)+'</td>' for c in cells)
                    +'<td>'+link+'</td></tr>')
    discovery = result['discovery']
    limits = ', '.join(discovery['limits_reached']) or 'aucune limite atteinte'
    refusals = ', '.join(discovery['refusals']) or 'aucun'
    return '''<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Catalogue local des sessions</title>
<style>body{background:#11151d;color:#e6ebf4;font:16px/1.6 system-ui;margin:2em auto;padding:0 1em;max-width:960px}table{border-collapse:collapse;width:100%}td,th{padding:.5em;text-align:left;border-bottom:1px solid #465268}a{color:#adcfff}.notice{border-left:4px solid #f4c673;padding:1em}td{overflow-wrap:anywhere}</style>
</head><body><h1>Sessions enregistrées — catalogue local</h1>
<p class="notice">Historique NON authentifié. Jamais CURRENT, ni validation HUD, ni conseil.
Chaque session est indépendante ; un succès n’autorise aucune autre session. Activité actuelle inconnue.</p>
<p>Découverte complète : '''+('oui' if discovery['complete'] else 'non')+'''. Limites : '''+escape(limits)+'''.</p>
<p>État de découverte : '''+escape(discovery['state'])+'''. Refus de parcours : '''+escape(refusals)+'''.</p>
<p>États : recorded = observation historique ; refused = refusée ; incomplete = incomplète ;
absent = journal absent ; unreadable = illisible ; blocked = lien/objet refusé ; limit = borne atteinte.
Un répertoire sans marqueur n’établit pas une session. Aucun nom ni chemin source n’est affiché.</p>
<table><thead><tr><th>Ordinal local</th><th>État</th><th>Motif</th><th>Rapport</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table>
<p>Bornes : profondeur 4, 1024 entrées, 64 sessions/objets signalés, 16 Mio de journaux lus au total.
Parseur par journal inchangé : 4 Mio, 10000 lignes, 64 Kio/ligne. Ordre lexical local, pas ordre temporel.
Sans script, image, audio, réseau ni navigateur automatique. Inconnu n’est pas zéro.</p></body></html>
'''


def _write(path, text):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


def _catalog(root, stage, output_guards):
    entries = []
    reports = []
    budget = {'entries': 0, 'bytes': 0}
    limits = set()
    refusals = set()

    def add(state, reason, report=None):
        if len(entries) >= MAX_SESSIONS:
            limits.add('sessions_limit')
            return False
        ordinal = len(entries)+1
        relative = None
        if report is not None:
            folder = stage/('session-%03d' % ordinal)
            reports.append((folder, report))
            relative = folder.name+'/REPORT.html'
        entries.append(dict(ordinal=ordinal, state=state, reason=reason, report=relative))
        return True

    def visit(directory, depth):
        if len(entries) >= MAX_SESSIONS:
            limits.add('sessions_limit')
            return
        try:
            with _pin(directory, directory=True):
                children = []
                # Never list an unbounded directory, nor select an OS-order prefix.
                with os.scandir(directory) as iterator:
                    for child in iterator:
                        budget['entries'] += 1
                        if budget['entries'] >= MAX_ENTRIES:
                            limits.add('entries_limit')
                            return
                        children.append(child.name)
                children.sort()
                markers = set(children).intersection(('events.jsonl', 'status.json', 'summary.json'))
                if markers:
                    source = directory/'events.jsonl'
                    if 'events.jsonl' not in markers:
                        add('absent', 'journal_absent')
                    else:
                        try:
                            report = _read_report(source, budget)
                        except ReparsePoint:
                            add('blocked', 'reparse_point')
                        except ByteLimit:
                            limits.add('bytes_limit')
                            add('limit', 'bytes_limit')
                        except (OSError, ValueError):
                            add('unreadable', 'journal_unavailable')
                        else:
                            add(_state(report), report['history']['reason'], report)
                for name in children:
                    if budget['entries'] >= MAX_ENTRIES:
                        return
                    child = directory/name
                    try:
                        info = child.lstat()
                        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                            if name != 'events.jsonl':
                                refusals.add('reparse_point')
                                add('blocked', 'reparse_point')
                        elif stat.S_ISDIR(info.st_mode):
                            if depth >= MAX_DEPTH:
                                limits.add('depth_limit')
                            else:
                                visit(child, depth+1)
                    except OSError:
                        refusals.add('entry_unavailable')
                        add('unreadable', 'entry_unavailable')
        except ReparsePoint:
            refusals.add('reparse_point')
            add('blocked', 'reparse_point')
        except OSError:
            refusals.add('directory_unavailable')
            add('unreadable', 'directory_unavailable')

    visit(root, 0)
    # Output failures propagate to the transaction, never become input refusals.
    for folder, report in reports:
        folder.mkdir()
        output_guards.enter_context(_pin(folder, directory=True))
        _write(folder/'report.json', _dump(report))
        _write(folder/'REPORT.html', session_html.render(report))
    return dict(event='session_catalog', schema_version=1, basis='historical_not_current',
                authenticated=False, current_permission=False, hud_validated=False,
                discovery=dict(complete=not limits and not refusals,
                               state=('partial' if limits or refusals else
                                      'finished' if entries else 'no_sessions_found'),
                               refusals=sorted(refusals), limits_reached=sorted(limits),
                               entries_examined=min(budget['entries'], MAX_ENTRIES),
                               journal_bytes_charged=budget['bytes'],
                               bounds=dict(depth=MAX_DEPTH, entries=MAX_ENTRIES,
                                           sessions=MAX_SESSIONS, total_bytes=MAX_TOTAL_BYTES)),
                sessions=entries)


def _reserve(target):
    """Exclusive claim: retain a partial output on failure; never reuse/delete it."""
    target.mkdir()


def run(args):
    try:
        root, target = _absolute(args.sessions_root), _absolute(args.report_dir)
        if root.is_relative_to(target) or target.is_relative_to(root):
            raise ValueError('overlap')
        with ExitStack() as guards:
            # Existing absolute ancestors only; no implicit path creation.
            _ancestors(guards, root)
            _ancestors(guards, target.parent)
            # Canonicalize only AFTER no-follow ancestor handles are held. This
            # also closes Windows 8.3 aliases without following a reparse point.
            canonical_root = root.resolve()
            canonical_target = target.parent.resolve()/target.name
            if (canonical_root.is_relative_to(canonical_target)
                    or canonical_target.is_relative_to(canonical_root)):
                raise ValueError('overlap')
            if os.path.lexists(target):
                raise ValueError('output_exists')
            _reserve(target)
            with _pin(target, directory=True):
                result = _catalog(root, target, guards)
                # All referenced individual files have completed write + fsync.
                # Indexes are exclusive and last. They never claim absent reports,
                # even if a crash interrupts their own writes. No rename requires
                # weakening the parent's no-write/no-delete sharing protection.
                _write(target/'catalog.json', _dump(result))
                _write(target/'INDEX.html', render(result))
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(_dump(dict(event='session_catalog_error', code='output_or_input_refused',
                         current_permission=False)).strip())
        return 1
    print(_dump(result).strip())
    return (0 if result['discovery']['complete'] and result['sessions']
            and all(e['state'] == 'recorded' for e in result['sessions']) else 1)
