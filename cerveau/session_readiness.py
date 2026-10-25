"""Read-only preparation; no historical file or PID can attest live permission."""
from __future__ import annotations

import json
from pathlib import Path
import re
import stat
import sys

from .player_identity import read_player_label


def valid_path(path):
    """Conservative local Windows grammar; no share, ADS, device or traversal."""
    if not isinstance(path, Path) or not path.is_absolute() or path == Path(path.anchor):
        return False
    if path.anchor.startswith(('\\\\', '//')):
        return False
    for part in path.parts[1:]:
        if (part in ('.', '..') or part.endswith((' ', '.'))
                or re.search(r'[\x00-\x1f<>:"|?*]', part)
                or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part)):
            return False
    return True


def inspect_path(path):
    """lstat ancestors; missing parents are planned, never created/probed."""
    for parent in reversed((path, *path.parents)):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            return 'absent'
        if stat.S_ISLNK(info.st_mode) or getattr(parent, 'is_junction', lambda: False)():
            raise ValueError('ambiguous_path')
        if parent != path and not stat.S_ISDIR(info.st_mode):
            raise ValueError('parent_not_directory')
    return 'present'


def inspect_paths(args):
    paths = (args.player_file, args.output_dir, args.stop_file)
    checks = {'paths': 'invalid', 'identity': 'not_checked',
              'output': 'not_checked', 'stop': 'not_checked'}
    if not all(valid_path(path) for path in paths):
        return checks
    player, output, stop = paths
    if (len(set(paths)) != 3 or output in stop.parents or stop in output.parents
            or player in output.parents or player in stop.parents):
        return checks
    checks['paths'] = 'valid'
    try:
        checks['stop'] = inspect_path(stop)
        checks['output'] = ('exists' if inspect_path(output) == 'present' else
                            'parent_claimed' if inspect_path(output.parent / 'passive-session.lock') == 'present'
                            else 'new')
        if inspect_path(player) == 'present':
            read_player_label(player)
            checks['identity'] = 'valid_private_file'
        else:
            checks['identity'] = 'unavailable'
    except (OSError, ValueError, UnicodeError):
        checks['paths'] = 'unavailable'
        if checks['identity'] == 'not_checked':
            checks['identity'] = 'unavailable'
    return checks


def emit(checks, preflight_row, code):
    # Projection closed at this public boundary, even if preflight later grows.
    details = None
    if preflight_row is not None:
        details = {'runtime': preflight_row['runtime'] if preflight_row.get('runtime') in (
            'supported', 'unsupported') else 'unknown',
            'profiles_checked': preflight_row.get('profiles_checked')
            if type(preflight_row.get('profiles_checked')) is int else None}
        for category, names in (
                ('required_dependencies', ('ctypes', 'ctypes.wintypes', 'grocoapi',
                 'cerveau.state', 'cerveau.runner', 'cerveau.native_reader_guard',
                 'hotstate.live', 'hotstate.reader', 'hotstate.native_context')),
                ('optional_dependencies', ('mpyq', 'heroprotocol'))):
            original = preflight_row.get(category, {})
            details[category] = {name: original.get(name) if original.get(name) in (
                'available', 'missing') else 'unknown' for name in names}
    row = {'schema_version': 1, 'event': 'core_readiness', 'collection': 'core',
           'technical_ready': code == 0, 'current_permission': False,
           'current_context': 'unattested', 'reader_active': None,
           'basis': 'offline_inspection_only', 'checks': checks, 'exit_code': code,
           'preflight': details, 'memory_opened': False, 'mutex_acquired': False,
           'chat_called': False, 'audio_enabled': False, 'write_probe': False}
    print(json.dumps(row, sort_keys=True, ensure_ascii=True, allow_nan=False))
    print(('Prêt techniquement' if code == 0 else 'Contrôle technique refusé')
          + ' ; permission et contexte ACTUELS non attestés.', file=sys.stderr)
    return code


def invalid_arguments():
    return emit({'arguments': 'invalid'}, None, 2)


def run(args, preflight):
    if (args.collection != 'core' or args.journal is not None
            or args.report_dir is not None or args.visual_reference):
        return invalid_arguments()
    checks = inspect_paths(args)
    try:
        preflight_row = preflight(core=True)
        checks['preflight'] = 'ready' if preflight_row['ready'] is True else 'refused'
    except Exception:
        preflight_row = None
        checks['preflight'] = 'unavailable'
    ready = checks == {'paths': 'valid', 'identity': 'valid_private_file',
                       'output': 'new', 'stop': 'absent', 'preflight': 'ready'}
    code = 0 if ready else 2 if checks['paths'] == 'invalid' else 1
    return emit(checks, preflight_row, code)
