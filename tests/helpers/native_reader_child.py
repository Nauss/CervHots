"""Offline subprocess fixture: patches only native transport; never opens a game."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cerveau import passive_session as product
from cerveau.native_reader_guard import NativeReaderGuard
from hotstate.reader import NativeBackendCloseError

parent = Path(sys.argv[1])
parent.mkdir(parents=True, exist_ok=True)
action = sys.argv[2]

def event(name):
    with (parent / 'transport.jsonl').open('a', encoding='ascii') as stream:
        stream.write(json.dumps({'event': name}) + '\n')

class Backend:
    def __init__(self):
        event('open')
        if action == 'init_error':
            raise RuntimeError('SYNTHETIC_INIT_ERROR')
        if action == 'init_close_error':
            raise NativeBackendCloseError('SYNTHETIC_UNCERTAIN')
    def close(self):
        event('close')
        if action == 'close_error':
            raise OSError('SYNTHETIC_UNCERTAIN')
        if action == 'close_hold':
            print('CLOSING', flush=True)
            sys.stdin.readline()

try:
    with ExitStack() as stack:
        stack.enter_context(patch('hotstate.reader.ProcessBackend', Backend))
        stack.enter_context(patch('hotstate.native_context.NativeContextProbe'))
        if action.startswith('cli_'):
            output = parent / 'new'
            player = parent / 'identity.txt'
            stop = parent / 'STOP'
            player.write_text('SYNTHETIC_PLAYER', encoding='utf-8')
            if action == 'cli_stop':
                stop.touch()
            if action in ('cli_stop', 'cli_status', 'cli_preflight', 'cli_diagnose'):
                stack.enter_context(patch.object(NativeReaderGuard, 'acquire',
                                                side_effect=AssertionError('NO_READER_GUARD')))
            if action == 'cli_status':
                argv = ['--status', '--output-dir', str(output)]
            elif action == 'cli_preflight':
                argv = ['--preflight']
            elif action == 'cli_diagnose':
                (parent / 'input').mkdir()
                journal = parent / 'input' / 'SYNTHETIC.jsonl'
                journal.write_text('{"schema_version":1,"sequence":1,"cycle":1,"event":"boundary","reason":"stop_file"}\n', encoding='ascii')
                argv = ['--diagnose', '--journal', str(journal), '--report-dir', str(parent / 'diagnosis')]
            else:
                argv = ['--live', '--player-file', str(player), '--output-dir', str(output),
                        '--stop-file', str(stop), '--max-seconds', '1']
            raise SystemExit(product.main(argv))
        with product.session_lock(parent / 'passive-session.lock'):
            source = product.NativeSource('SYNTHETIC_PLAYER')
            print('OWNED', flush=True)
            command = sys.stdin.readline().strip() if action in ('hold', 'close_error') else 'close'
            if command == 'crash':
                os._exit(37)  # only this explicitly spawned synthetic child
            source.close()
    print('CLOSED', flush=True)
except Exception as exc:
    print(type(exc).__name__, flush=True)
    if action in ('close_error', 'init_close_error'):
        print('UNCERTAIN', flush=True)
        sys.stdin.readline()  # keep owner alive while a second process attempts
    raise SystemExit(1)
