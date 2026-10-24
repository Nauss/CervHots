"""Collecte native passive bornée. Sans --live : préflight local uniquement.

Aucun Coach, API, audio, GUI, OCR ou export de lectures brutes.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib
import datetime as dt
import math
import os
import json
import re
import time
from pathlib import Path

from .diagnostics import Journal


ROOT = Path(__file__).resolve().parent.parent


class Boundary(Exception):
    pass


def measured_acquisition(row):
    """Rebuild the live observer's schema; no arbitrary fields cross this boundary."""
    from hotstate.diagnostics import refusal
    result = {'phase': 'read',
              'stage': row.get('stage') if row.get('stage') in (
                  'snapshot', 'context_recheck', 'normalize', 'key') else 'unknown',
              'outcome': row.get('outcome') if row.get('outcome') in (
                  'accepted', 'refused', 'error') else 'unknown'}
    for name, limit in (('elapsed_ms', 3600000), ('reads', 8192), ('bytes_requested', 2**20)):
        value = row.get(name)
        if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= limit:
            result[name] = value
    reason = row.get('refusal')
    result['refusal'] = None if reason is None else refusal(
        reason.get('code') if type(reason) is dict else reason)
    optional = row.get('optional_refusals', {})
    result['optional_refusals'] = {name: refusal(
        optional[name].get('code') if type(optional[name]) is dict else optional[name])
        for name in ('gameplay_clock', 'positions', 'visibility', 'objective',
                     'talents', 'local_cooldowns', 'battlefield') if name in optional}
    return result


def run_session(source_factory, stopped, emit, *, duration=300, interval=5,
                clock=time.monotonic, sleep=time.sleep, private_labels=()):
    from hotstate.native import NativeUnavailable
    from hotstate.diagnostics import exception_refusal
    if any(type(v) not in (int, float) or not math.isfinite(v) or not low <= v <= high
           for v, low, high in ((duration, 1, 1800), (interval, 1, 300))):
        raise ValueError('invalid_limits')
    started = clock()
    deadline = started + duration
    source = None
    binding = None
    mission = None
    result = {'accepted': 0, 'refused': 0, 'attempts': 0, 'failures': 0,
              'reason': 'session_limit'}
    journal = Journal(lambda row: emit(dict(row, elapsed_s=round(clock() - started, 6),
                                            cycle=result['attempts'],
                                            timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat())),
                      private_labels=private_labels)

    def boundary():
        if stopped():
            raise Boundary('stop_file')
        if clock() >= deadline:
            raise Boundary('session_limit')

    phase = 'prepare'
    try:
        while True:
            boundary()
            pending = []
            result['attempts'] += 1
            try:
                if source is None:
                    phase = 'open'
                    source = source_factory()
                boundary()
                phase = 'read'
                state = source.read(pending.append)
            except SystemExit as exc:
                boundary()
                message = exc.args[0] if len(exc.args) == 1 else None
                code = ('source_absent' if message == 'processus HeroesOfTheStorm_x64.exe introuvable'
                        else 'source_denied' if type(message) is str and re.fullmatch(
                            r'OpenProcess impossible \([0-9]+\)', message) else 'software_error')
                result['failures'] += 1
                journal.record('source_error', phase='open', code=code)
                if code == 'software_error':
                    raise Boundary('software_error')
                if result['failures'] >= 12:
                    raise Boundary('failure_limit')
            except NativeUnavailable as exc:
                boundary()
                reason = exception_refusal(exc)
                for row in pending:
                    boundary()
                    journal.record('acquisition', **measured_acquisition(row))
                result['refused'] += 1
                if reason['category'] != 'menu':
                    result['failures'] += 1
                boundary()
                journal.record('refusal', phase=phase, **reason)
                if binding is not None and reason['code'] in (
                        'aucune_simulation_active', 'contexte_natif_partie_changee',
                        'contexte_natif_dechire', 'partie_native_incoherente',
                        'partie_native_absente', 'partie_application_non_active'):
                    raise Boundary('session_changed')
                if result['failures'] >= 12:
                    raise Boundary('failure_limit')
            except Boundary:
                raise
            except Exception:
                boundary()
                for row in pending:
                    boundary()
                    journal.record('acquisition', **measured_acquisition(row))
                boundary()
                journal.record('error', phase=phase, code='software_error')
                raise Boundary('software_error')
            else:
                boundary()
                current = (state['meta']['match_id'], json.dumps(state['local_player'], sort_keys=True),
                           state['ally_team'], state['meta'].get('map'))
                now_mission = state['meta']['t_s']
                for row in pending:
                    boundary()
                    journal.record('acquisition', **measured_acquisition(row))
                if binding is not None and (current != binding or now_mission < mission):
                    raise Boundary('session_changed')
                binding, mission = current, now_mission
                boundary()
                journal.observation(state)
                result['accepted'] += 1
            wake = min(deadline, clock() + interval)
            while clock() < wake:
                boundary()
                sleep(min(.2, wake - clock()))
    except Boundary as exc:
        result['reason'] = exc.args[0]
    except KeyboardInterrupt:
        result['reason'] = 'interrupted'
    except Exception:
        # Exceptions can contain private names, addresses and paths. Never stringify.
        result['reason'] = 'software_error'
    finally:
        if source is not None:
            try:
                source.close()
            except Exception:
                result['reason'] = 'source_close_failed'
    result['reader_active'] = None if result['reason'] == 'source_close_failed' else False
    journal.record('boundary', reason=result['reason'])
    return result


def preflight():
    """Dependencies and product data only; never discover/open a game process."""
    from .state import snapshot
    from .runner import tactical_key
    from hotstate.live import read_current
    from hotstate.protocols import load_protocol
    module = importlib.import_module('mpyq')
    if not callable(getattr(module, 'MPQArchive', None)):
        raise ValueError('dependency_unavailable')
    profiles = sorted((ROOT / 'hotstate/profiles').glob('*.json'))
    if not profiles:
        raise ValueError('profiles_unavailable')
    for path in profiles:
        json.loads(path.read_text(encoding='utf-8'))
    load_protocol()
    return {'event': 'preflight', 'ready': True, 'memory_opened': False,
            'chat_called': False, 'audio_enabled': False,
            'profiles_checked': len(profiles), 'single_match': True,
            'objective_collection': {
                'value_families': ['dragon'], 'qualification_only_maps': ['Volskaya'],
                'age_basis': 'original_receipt_at_normalization',
                'historical_replay_grants_permission': False}}


class NativeSource:
    """One process/probe lifetime; no rebinding or receipt caching across sessions."""
    def __init__(self, player):
        from hotstate.native_context import NativeContextProbe
        from hotstate.reader import ProcessBackend
        self.probe = NativeContextProbe(player)
        self.backend = ProcessBackend()

    def read(self, observe):
        from hotstate.live import read_current
        from .state import snapshot
        from .runner import tactical_key
        return read_current(self.backend, {'triggers': {}}, context=self.probe,
                            project=snapshot, key=tactical_key, observe=observe)

    def close(self):
        owned, self.backend = self.backend, None
        # Invalidate all in-process native context and acquired readsets, even on IO errors.
        self.probe = None
        if owned is not None:
            owned.close()


def stop_requested(path):
    # Python3.14 Path.exists suppresses OSError: only absence permits continuation.
    try:
        path.stat()
    except FileNotFoundError:
        return False
    return True


@contextmanager
def session_lock(path):
    handle = path.open('x', encoding='ascii')
    try:
        yield
    finally:
        try:
            handle.close()
        finally:
            path.unlink()


def bounded(low, high):
    def parse(raw):
        value = float(raw)
        if not math.isfinite(value) or not low <= value <= high:
            raise argparse.ArgumentTypeError('value_out_of_bounds')
        return value
    return parse


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--live', action='store_true', help='explicit native read opt-in')
    result.add_argument('--player-file', type=Path, help='absolute private UTF8 identity file, not a label')
    result.add_argument('--output-dir', type=Path, help='new absolute directory; never reused')
    result.add_argument('--stop-file', type=Path, help='absolute cooperative STOP; never removed')
    result.add_argument('--max-seconds', type=bounded(1, 1800), default=300)
    result.add_argument('--interval', type=bounded(1, 300), default=5)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if args.live and any(p is None or not p.is_absolute()
                         for p in (args.player_file, args.output_dir, args.stop_file)):
        parser().error('--live requires absolute --player-file, --output-dir and --stop-file')

    def report(row):
        print(json.dumps(row, ensure_ascii=True, allow_nan=False), flush=True)

    try:
        if args.live and stop_requested(args.stop_file):
            report({'event': 'boundary', 'reason': 'stop_file'})
            return 0
        ready = preflight()
    except Exception:
        report({'event': 'preflight', 'ready': False, 'code': 'dependency_or_stop_io',
                'memory_opened': False, 'chat_called': False, 'audio_enabled': False})
        return 1
    if not args.live:
        report(ready)
        return 0
    try:
        from .player_identity import read_player_label
        if stop_requested(args.stop_file):
            report({'event': 'boundary', 'reason': 'stop_file'})
            return 0
        args.output_dir.parent.mkdir(parents=True, exist_ok=True)
        with session_lock(args.output_dir.parent / 'passive-session.lock'):
            args.output_dir.mkdir(exist_ok=False)
            if stop_requested(args.stop_file):
                report({'event': 'boundary', 'reason': 'stop_file'})
                return 0
            def status(row):
                pending = args.output_dir / 'status.pending'
                with pending.open('x', encoding='utf-8') as stream:
                    json.dump(row, stream, ensure_ascii=True, allow_nan=False)
                os.replace(pending, args.output_dir / 'status.json')
            status({'event': 'initializing', 'collector_pid': os.getpid(),
                    'timestamp_utc': dt.datetime.now(dt.timezone.utc).isoformat()})
            if stop_requested(args.stop_file):
                report({'event': 'boundary', 'reason': 'stop_file'})
                return 0
            player = read_player_label(args.player_file)
            with (args.output_dir / 'events.jsonl').open('x', encoding='utf-8') as stream:
                def emit(row):
                    stream.write(json.dumps(row, ensure_ascii=True, allow_nan=False) + '\n')
                    stream.flush()
                    status(row)
                result = run_session(lambda: NativeSource(player),
                                     lambda: stop_requested(args.stop_file), emit,
                                     duration=args.max_seconds, interval=args.interval,
                                     private_labels=(player,))
            summary = dict(result, event='summary',
                           chat_called=False, audio_enabled=False, single_match=True,
                           finished_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())
            with (args.output_dir / 'summary.json').open('x', encoding='utf-8') as stream:
                json.dump(summary, stream, ensure_ascii=True, allow_nan=False)
            status(summary)
            report(summary)
            return (130 if result['reason'] == 'interrupted' else
                    0 if result['reason'] in ('stop_file', 'session_limit', 'session_changed') else 1)
    except KeyboardInterrupt:
        report({'event': 'boundary', 'reason': 'interrupted'})
        return 130
    except Exception:
        report({'event': 'error', 'code': 'session_initialization_or_io'})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
