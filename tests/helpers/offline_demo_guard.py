"""Garde d'import fraîche pour le vrai module produit (tests uniquement)."""
import importlib.abc
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class Refuse(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = ('grocoapi', 'cerveau.brain', 'hotstate.reader',
            'hotstate.live', 'socket', 'urllib.request',
            'http.client', 'tts', 'mumblebot', 'webbrowser', 'subprocess')
        if any(fullname == name or fullname.startswith(name+'.') for name in forbidden):
            raise AssertionError('import interdit: '+fullname)


sys.meta_path.insert(0, Refuse())


def forbidden(*args, **kwargs):
    raise AssertionError('construction/permission native interdite')


# Les validateurs documentaires importent ces décodeurs purs pour leurs
# constantes ; ils ne sont pas le backend OS hotstate.reader (import interdit).
from hotstate.native import NativeReader
from hotstate.native_context import NativeContextProbe
import hotstate.acquisition
NativeReader.__init__ = forbidden
NativeContextProbe.__init__ = forbidden
hotstate.acquisition.issue = forbidden
runpy.run_module('cerveau.offline_demo', run_name='__main__')
