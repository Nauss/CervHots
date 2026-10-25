"""Execute the real module with network/audio/native construction forbidden.

Explicit replay argv only; this helper never discovers personal replay folders.
"""
import builtins
from contextlib import ExitStack
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import cerveau.brain
import grocoapi

original_import = builtins.__import__
FORBIDDEN = ('tts', 'mumblebot', 'hotstate.reader', 'hotstate.native', 'hotstate.live')


def guarded_import(name, *args, **kwargs):
    if any(name == prefix or name.startswith(prefix + '.') for prefix in FORBIDDEN):
        raise AssertionError('forbidden backend import')
    return original_import(name, *args, **kwargs)


with ExitStack() as stack:
    stack.enter_context(patch('builtins.__import__', side_effect=guarded_import))
    for target in ('socket.socket', 'socket.create_connection',
                   'grocoapi.GrocoClient.__init__', 'cerveau.brain.Coach.__init__',
                   'pathlib.Path.home', 'pathlib.Path.rglob', 'pathlib.Path.glob'):
        stack.enter_context(patch(target, side_effect=AssertionError('forbidden side effect')))
    sys.argv = ['cerveau.replay_debrief', *sys.argv[1:]]
    runpy.run_module('cerveau.replay_debrief', run_name='__main__')
