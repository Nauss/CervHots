"""Real historical CLI, with acquisition/network/Coach/audio forbidden.

Used on synthetic tests AND immutable explicitly supplied real journals. No scan.
"""
import builtins
import json
from contextlib import ExitStack
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cerveau import passive_session
import cerveau.brain
import hotstate.native  # noqa: F401 -- preload guard targets before socket prohibition
import hotstate.native_context  # noqa: F401 -- imports are not native construction

original_import = builtins.__import__


def guarded_import(name, *args, **kwargs):
    if any(name == prefix or name.startswith(prefix+'.') for prefix in ('tts','mumblebot','hotstate.live')):
        raise AssertionError('forbidden live/audio import')
    return original_import(name, *args, **kwargs)


# Test-only mutations are in memory. Never persist/export a copy of journal rows.
case = None
if len(sys.argv) > 2 and sys.argv[1] == '--mutate-case':
    case = sys.argv[2]
    del sys.argv[1:3]
    if case not in ('truncated', 'mixed_session', 'missing_binding', 'foreign_perspective',
                    'unknown_age', 'not_selected'):
        raise ValueError('unknown synthetic adversary')
import cerveau.session_diagnosis
bounded = cerveau.session_diagnosis._bounded


def mutated_read(path, limit):
    data = bounded(path, limit)
    if case == 'truncated':
        return data + b'{"event":"observation"'
    records = [json.loads(line) for line in data.splitlines()]
    observations = [r for r in records if r.get('event') == 'observation']
    if case == 'mixed_session':
        observations[0]['session'] = 'session_' + 'f'*12
    elif case == 'missing_binding':
        observations[0].pop('comparison', None)
    elif case == 'foreign_perspective':
        observations[0]['comparison']['perspective'] = 'observer'
    elif case == 'unknown_age':
        observations[-1]['talents']['age_s'] = None
    elif case == 'not_selected':
        observations[-1]['available_fields'] = ['heroes']
    return b''.join((json.dumps(r)+'\n').encode() for r in records)


with ExitStack() as stack:
    if case is not None:
        stack.enter_context(patch('cerveau.session_diagnosis._bounded', side_effect=mutated_read))
    stack.enter_context(patch('builtins.__import__', side_effect=guarded_import))
    for target in ('socket.socket','socket.create_connection','subprocess.Popen','os.system',
                   'grocoapi.GrocoClient.__init__','cerveau.brain.Coach.__init__',
                   'hotstate.reader.ProcessBackend.__init__','hotstate.native.NativeReader.__init__',
                   'hotstate.native_context.NativeContextProbe.__init__','hotstate.acquisition.issue',
                   'cerveau.passive_session.preflight','cerveau.passive_session.NativeSource',
                   'pathlib.Path.home','pathlib.Path.glob','pathlib.Path.rglob'):
        stack.enter_context(patch(target, side_effect=AssertionError('forbidden side effect')))
    raise SystemExit(passive_session.main(sys.argv[1:]))
