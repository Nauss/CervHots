"""Bounded private diagnostic recipe, silent; default is offline preflight.

Run from a frozen checkout. --live is the only route to memory/network IO.
No GUI, audio, raw trace or exported acquisition receipt. STOP is never removed.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from types import SimpleNamespace

from .diagnostics import Journal
from .runner import Pipeline, ROOT, knowledge_for
from hotstate.diagnostics import exception_refusal
from hotstate.native import NativeUnavailable


class Boundary(Exception):
    pass


def stop_requested(path):
    # Path.exists suppresses OSError on Python3.14. Only an absent STOP allows
    # continuation; permission/IO failures must propagate closed.
    try:
        path.stat()
    except FileNotFoundError:
        return False
    return True


def bounded(low, high):
    def parse(raw):
        value = float(raw)
        if not math.isfinite(value) or not low <= value <= high:
            raise argparse.ArgumentTypeError('value_out_of_bounds')
        return value
    return parse


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--live', action='store_true')
    result.add_argument('--coach-env-file', type=Path,
                        help='explicit absolute runtime config; values are never logged')
    result.add_argument('--player-file', type=Path, help='private local identity; never logged')
    result.add_argument('--output-dir', type=Path, help='private, unique absolute session directory')
    result.add_argument('--stop-file', type=Path, help='absolute STOP file; never removed by this tool')
    result.add_argument('--max-seconds', type=bounded(1, 1800), default=300)
    result.add_argument('--interval', type=bounded(15, 300), default=30)
    return result


def preflight():
    """Local dependencies only, no credentials/process/network/audio."""
    from etudes.rea.scripts.capture_talents_pipeline import runtime_dependencies
    from kb.briefing import DB
    runtime = runtime_dependencies()
    database = Path(DB).resolve()
    if not database.is_file():
        raise ValueError('kb_absent')
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('kb_invalid')
        connection.execute('SELECT slug FROM maps LIMIT 1').fetchone()
    profiles = list((ROOT / 'hotstate/profiles').glob('*.json'))
    for path in profiles:
        json.loads(path.read_text(encoding='utf-8'))
    from hotstate.protocols import load_protocol
    load_protocol()
    json.loads((ROOT / 'kb/data/map_timings.json').read_text(encoding='utf-8'))
    cache = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / 'Blizzard Entertainment/Battle.net/Cache'
    return {'event': 'preflight', 'ready': True, 'memory_opened': False, 'chat_called': False,
            'audio_enabled': False, 'runtime': runtime, 'kb_readable': True,
            'profiles_checked': len(profiles), 'map_cache_directory_present': cache.is_dir(),
            'cache_contents_qualified': False}


def configured_coach(env_file=None):
    from .brain import Coach
    from grocoapi import GrocoClient
    from grocoapi.client import _load_env_file
    if env_file is not None and (not env_file.is_absolute() or not env_file.is_file()):
        raise ValueError('runtime_config_unavailable')
    env = _load_env_file() if env_file is None else _load_env_file(env_file)
    model = os.environ.get('GROCO_MODEL', env.get('GROCO_MODEL'))
    effort = os.environ.get('GROCO_REASONING_EFFORT', env.get('GROCO_REASONING_EFFORT'))
    if not model:
        raise ValueError('model_not_configured')
    client = GrocoClient(base_url=os.environ.get('GROCO_API_URL', env.get('GROCO_API_URL')),
                        token=os.environ.get('GROCO_API_TOKEN', env.get('GROCO_API_TOKEN')))
    return Coach(client, model, timeout=20, min_confidence=0.75, reasoning_effort=effort)


def run_session(args, source_factory, coach_factory, emit, *, clock=time.monotonic,
                sleep=time.sleep, knowledge=knowledge_for, private_labels=()):
    started = clock()
    deadline = started + args.max_seconds
    cycle = 0
    def write(event):
        emit(dict(event, cycle=cycle, elapsed_s=round(clock() - started, 6)))
    journal = Journal(write, private_labels=private_labels)
    backend = read = pipeline = coach = binding = None

    def boundary():
        if stop_requested(args.stop_file):
            raise Boundary('stop_file')
        if clock() >= deadline:
            raise Boundary('session_limit')

    def close():
        nonlocal backend, read, pipeline, coach, binding
        owned, backend = backend, None
        read = pipeline = coach = binding = None
        if owned is not None:
            owned.close()
            journal.record('source_closed')

    try:
        while clock() < deadline:
            cycle += 1
            cycle_started = clock()
            try:
                boundary()
                if read is None:
                    journal.set_phase('open')
                    read, backend = source_factory(lambda event: journal.record(
                        event['event'], phase=journal.phase,
                        **{k: v for k, v in event.items() if k != 'event'}))
                    journal.set_phase('prevalidation')
                    boundary()
                    initial = read()
                    boundary()
                    binding = (initial.get('meta', {}).get('match_id'), initial.get('local_player'))
                    def guarded_read():
                        boundary()
                        current = read()
                        boundary()
                        if (current.get('meta', {}).get('match_id'), current.get('local_player')) != binding:
                            raise Boundary('session_changed')
                        return current
                    coach = coach_factory()
                    def guarded_knowledge(state):
                        result = knowledge(state)
                        boundary()
                        remaining = 20 - (clock() - cycle_started)
                        if remaining <= 0:
                            raise NativeUnavailable('etat_perime')
                        coach.timeout = min(remaining, deadline - clock())
                        return result
                    pipeline = Pipeline(coach, guarded_read, knowledge=guarded_knowledge,
                                        clock=clock, cooldown=15, max_age=20, journal=journal,
                                        checkpoint=boundary)
                    journal.record('session_bound')
                decision = pipeline.cycle()
                journal.outcome(decision)
                boundary()
            except NativeUnavailable as exc:
                journal.record('refusal', phase=journal.phase, **exception_refusal(exc))
                if coach is not None:
                    coach.history.clear()
                close()
            except Boundary as exc:
                reason = exc.args[0]
                journal.record('boundary', reason=reason)
                if coach is not None:
                    coach.history.clear()
                close()
                if reason != 'session_changed':
                    return 0
            except SystemExit as exc:
                # ProcessBackend currently exposes these two controlled messages.
                message = exc.args[0] if len(exc.args) == 1 else None
                code = ('source_absent' if message == 'processus HeroesOfTheStorm_x64.exe introuvable'
                        else 'source_denied' if type(message) is str and re.fullmatch(
                            r'OpenProcess impossible \([0-9]+\)', message) else 'software_error')
                journal.record('source_error', phase=journal.phase, code=code)
                close()
                if code == 'software_error':
                    return 1
            wake = min(clock() + args.interval, deadline)
            while clock() < wake:
                if stop_requested(args.stop_file):
                    journal.record('boundary', reason='stop_file')
                    return 0
                sleep(min(0.2, wake - clock()))
        journal.record('boundary', reason='session_limit')
        return 0
    except KeyboardInterrupt:
        journal.record('boundary', reason='interrupted')
        return 130
    except Exception:
        # No exception content, paths, API messages or prompt reaches the journal.
        journal.record('error', phase=journal.phase, code='software_error')
        return 1
    finally:
        close()


@contextmanager
def session_lock(path):
    handle = path.open('x', encoding='ascii')
    try:
        yield
    finally:
        handle.close()
        path.unlink()


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = preflight()
    except Exception:
        print(json.dumps({'event': 'preflight', 'ready': False, 'code': 'dependency_unavailable',
                          'memory_opened': False, 'chat_called': False, 'audio_enabled': False}))
        return 1
    try:
        # Constructor only: detect missing ignored worktree configuration before
        # any process acquisition. No health/models/chat request is made here.
        configured_coach(args.coach_env_file)
    except Exception:
        print(json.dumps({'event': 'preflight', 'ready': False, 'code': 'coach_configuration_unavailable',
                          'memory_opened': False, 'chat_called': False, 'audio_enabled': False}))
        return 1
    result['coach_configured'] = True
    if not args.live:
        print(json.dumps(result, allow_nan=False))
        return 0
    if any(p is None or not p.is_absolute() for p in (args.player_file, args.output_dir, args.stop_file)):
        parser().error('--live requires absolute --player-file, --output-dir and --stop-file')
    try:
        # STOP is checked before even reading the private identity.
        if stop_requested(args.stop_file):
            print(json.dumps({'event': 'boundary', 'reason': 'stop_file'}))
            return 0
        player = args.player_file.read_text(encoding='utf-8').strip()
        if not 2 <= len(player) <= 64 or '\n' in player or '\r' in player:
            raise ValueError('invalid_identity')
        args.output_dir.mkdir(parents=True, exist_ok=True)
        with session_lock(args.output_dir.parent / 'diagnostic-session.lock'):
            with (args.output_dir / 'events.jsonl').open('x', encoding='utf-8') as stream:
                def emit(event):
                    stream.write(json.dumps(event, ensure_ascii=True, allow_nan=False) + '\n')
                    stream.flush()
                from .__main__ import make_source
                source_args = SimpleNamespace(state=None, dump=None, at=None, team=None,
                                              map=None, allies=None, enemies=None, pid=None,
                                              player=player, live=True, watch=True, max_age=20)
                def source(observe):
                    source_args.observe = observe
                    return make_source(source_args)
                return run_session(args, source, lambda: configured_coach(args.coach_env_file),
                                   emit, private_labels=(player,))
    except Exception:
        print(json.dumps({'event': 'error', 'code': 'session_initialization_or_io'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
