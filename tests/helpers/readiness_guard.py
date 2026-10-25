"""Fresh-process guard for the real passive CLI; no product simulation mode.

Optional helper-only --absent MODULE injects discovery absence, not runtime data.
No game, reference, mutex or backend is opened, including in the success case.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import ctypes
import importlib.abc
import importlib.util
import os
from unittest.mock import patch


class ForbiddenLoader(importlib.abc.Loader):
    def create_module(self, spec):
        raise AssertionError('forbidden_live_import')

    def exec_module(self, module):
        raise AssertionError('forbidden_live_import')


class NoLiveImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ('hotstate.live', 'hotstate.reader', 'hotstate.native_context',
                        'cerveau.native_reader_guard') or fullname.split('.')[0] in (
                            'pyautogui', 'pynput', 'mss', 'tkinter', 'winrt', 'tts', 'mumble'):
            return importlib.util.spec_from_loader(fullname, ForbiddenLoader())
        return None


def forbidden(*args, **kwargs):
    raise AssertionError('forbidden_constructor')


def audit(event, args):
    if event.startswith(('socket.', 'subprocess.')) or event in ('os.system', 'os.startfile'):
        raise AssertionError('forbidden_external_io')
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(letter in mode for letter in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            raise AssertionError('forbidden_write')
    if event in ('os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.link', 'os.symlink'):
        raise AssertionError('forbidden_path_mutation')


argv = sys.argv[1:]
absent = None
if argv[:1] == ['--absent']:
    absent, argv = argv[1], argv[2:]
sys.meta_path.insert(0, NoLiveImports())
sys.addaudithook(audit)
real_spec = importlib.util.find_spec

def spec(name, *args, **kwargs):
    return None if name == absent else real_spec(name, *args, **kwargs)

with patch.object(ctypes, 'WinDLL', side_effect=forbidden), \
        patch('importlib.util.find_spec', side_effect=spec):
    from cerveau import passive_session
    with patch('cerveau.brain.Coach', side_effect=forbidden), \
            patch('grocoapi.GrocoClient', side_effect=forbidden), \
            patch.object(passive_session, 'NativeSource', side_effect=forbidden):
        raise SystemExit(passive_session.main(argv))
