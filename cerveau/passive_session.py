"""Collecte native passive bornée. Défaut : préflight ; --status/--diagnose/--summarize : disque seul.

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
import secrets
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
    if (result['outcome'] == 'refused' and result['refusal'] is not None
            and result['refusal']['code'] == 'lecture_native_dechiree'):
        from hotstate.diagnostics import coherence_detail
        detail = coherence_detail(row.get('coherence'))
        if detail is not None:
            result['coherence'] = detail
    optional = row.get('optional_refusals', {})
    result['optional_refusals'] = {name: refusal(
        optional[name].get('code') if type(optional[name]) is dict else optional[name])
        for name in ('gameplay_clock', 'positions', 'visibility', 'objective',
                     'talents', 'local_cooldowns', 'battlefield') if name in optional}
    collection = row.get('collection')
    if type(collection) is str and collection in ('all', 'talents'):
        result['collection'] = collection
        result['not_selected'] = ([] if collection == 'all' else [
            'gameplay_clock', 'positions', 'visibility', 'objective', 'local_cooldowns', 'battlefield'])
    return result


def run_session(source_factory, stopped, emit, *, duration=300, interval=5,
                clock=time.monotonic, sleep=time.sleep, private_labels=()):
    from hotstate.native import NativeUnavailable
    from hotstate.diagnostics import exception_refusal
    from hotstate.reader import NativeBackendCloseError
    from .native_reader_guard import ReaderGuardError
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
    # Random per invocation, never derived from a raw name or reused on resume.
    session_token = secrets.token_hex(16)
    comparison = None

    def record(row):
        if row.get('event') == 'observation':
            row = dict(row, comparison=comparison)
        emit(dict(row, elapsed_s=round(clock() - started, 6), cycle=result['attempts'],
                  timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat()))

    journal = Journal(record, private_labels=private_labels)

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
                read_started = clock()
                state = source.read(pending.append)
                read_finished = clock()
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
            except NativeBackendCloseError:
                # The constructor failed after opening a handle and could not
                # establish closure. STOP must not downgrade this to inactive.
                raise Boundary('source_close_failed')
            except ReaderGuardError:
                boundary()
                raise Boundary('native_reader_unavailable')
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
                comparison = {
                    'session_token': session_token,
                    'map_id': ('DragonShire' if any(state.get(family, {}).get('map_id') == 'DragonShire'
                                                    for family in ('objective', 'talents')) else None),
                    'perspective': ('native_player' if state['meta'].get('source') == 'live'
                                    and state['meta'].get('native_status') == 'valide'
                                    else 'unknown'),
                    'clock_basis': 'host_monotonic',
                    'read_started_s': read_started, 'read_finished_s': read_finished}
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
    def __init__(self, player, *, collection='all'):
        if type(collection) is not str or collection not in ('all', 'talents'):
            raise ValueError('invalid_collection')
        self.collection = collection
        from .native_reader_guard import NativeReaderGuard
        from hotstate.native_context import NativeContextProbe
        from hotstate.reader import ProcessBackend, NativeBackendCloseError
        self.guard = NativeReaderGuard().acquire()
        self.backend = None
        self.probe = None
        try:
            self.probe = NativeContextProbe(player)
            self.backend = ProcessBackend()
        except NativeBackendCloseError:
            # Partial backend initialization could not establish OS closure.
            # Keep the kernel handle/local latch until this process exits.
            self.probe = None
            raise
        except BaseException:
            self.probe = None
            self.guard.release()
            raise

    def read(self, observe):
        self.guard.assert_owned()
        from hotstate.live import read_current
        from .state import snapshot
        from .runner import tactical_key
        mapping = {'triggers': {}}
        if self.collection != 'all':
            mapping['collection'] = self.collection
        return read_current(self.backend, mapping, context=self.probe,
                            project=snapshot, key=tactical_key, observe=observe)

    def close(self):
        if self.backend is None and self.guard.handle is None:
            return
        self.guard.assert_owned()
        # Invalidate context first; retain ownership and backend on close failure.
        self.probe = None
        if self.backend is not None:
            self.backend.close()
            self.backend = None
        self.guard.release()


def stop_requested(path):
    # Python3.14 Path.exists suppresses OSError: only absence permits continuation.
    try:
        path.stat()
    except FileNotFoundError:
        return False
    return True


@contextmanager
def session_lock(path):
    claim = secrets.token_hex(32)
    handle = path.open('x', encoding='ascii')
    try:
        handle.write(claim)
        handle.flush()
        yield
    finally:
        handle.close()
        # Path comparison followed by unlink is not an atomic ownership check.
        # Retain the claim even on clean exit: never mutate a possibly replaced
        # path. Resume requires a fresh parent after independent shutdown checks.
        # This marker is neither a current liveness proof nor a global lock.


def session_status(output):
    """Historical disk diagnostic, never a process/ownership/current attestation."""
    row = {'event': 'session_status', 'state': 'unknown', 'reason': 'ownership_unverified',
           'reader_active': None, 'recorded_reader_active': None,
           'current_permission': False, 'basis': 'historical_disk_only',
           'parent_lock': 'unknown', 'last_event': None}

    def read_record(path):
        with path.open('rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('record_too_large')
        result = json.loads(raw)
        if type(result) is not dict:
            raise ValueError('invalid_record')
        return result

    try:
        row['parent_lock'] = ('present_owner_unverified' if stop_requested(
            output.parent / 'passive-session.lock') else 'absent')
        output.stat()
    except FileNotFoundError:
        row.update(state='absent', reason='session_absent')
        return row
    except OSError:
        row['reason'] = 'disk_unavailable'
        return row
    try:
        latest = read_record(output / 'status.json')
        event = latest.get('event')
        if type(event) is str and event in (
                'initializing', 'acquisition', 'observation', 'refusal',
                'source_error', 'error', 'boundary', 'summary'):
            row['last_event'] = event
    except (OSError, ValueError, UnicodeError, RecursionError):
        pass
    try:
        summary = read_record(output / 'summary.json')
        reason = summary.get('reason')
        if (summary.get('event') == 'summary' and summary.get('reader_active') is False
                and type(reason) is str and reason in (
                    'stop_file', 'session_limit', 'session_changed', 'interrupted',
                    'failure_limit', 'software_error', 'native_reader_unavailable')):
            row.update(state='recorded_stopped', reason=reason, recorded_reader_active=False)
    except (OSError, ValueError, UnicodeError, RecursionError):
        pass
    return row


def bounded(low, high):
    def parse(raw):
        value = float(raw)
        if not math.isfinite(value) or not low <= value <= high:
            raise argparse.ArgumentTypeError('value_out_of_bounds')
        return value
    return parse


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    mode = result.add_mutually_exclusive_group()
    mode.add_argument('--live', action='store_true', help='explicit native read opt-in')
    mode.add_argument('--status', action='store_true', help='historical disk status only; no backend or current permission')
    mode.add_argument('--diagnose', action='store_true', help='offline bounded journal diagnosis; never validates HUD')
    mode.add_argument('--summarize', action='store_true', help='offline player summary of recorded native observations; never CURRENT')
    mode.add_argument('--report-html', action='store_true', help='rapport HTML autonome local et JSON minimisé ; historique uniquement')
    mode.add_argument('--preflight', action='store_true', help='local checks only (default)')
    result.add_argument('--journal', type=Path, help='absolute existing events.jsonl for --diagnose, --summarize or --report-html')
    result.add_argument('--report-dir', type=Path, help='absolute NEW offline report directory')
    result.add_argument('--visual-reference', type=Path, action='append', default=[],
                        help='explicit existing BMP or stored ZIP; diagnostics only, at most 8')
    result.add_argument('--player-file', type=Path, help='absolute private UTF8 identity file, not a label')
    result.add_argument('--output-dir', type=Path, help='absolute directory: new for --live, existing for --status')
    result.add_argument('--stop-file', type=Path, help='absolute cooperative STOP; never removed')
    result.add_argument('--max-seconds', type=bounded(1, 1800), default=300)
    result.add_argument('--interval', type=bounded(1, 300), default=5)
    result.add_argument('--collection', choices=('all', 'talents'), default='all',
                        help='talents: core + selected talents only; other optional families not attempted')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if not (args.diagnose or args.summarize or args.report_html) and (args.journal is not None or args.report_dir is not None or args.visual_reference):
        parser().error('--journal and --report-dir require --diagnose, --summarize or --report-html')
    if args.diagnose or args.summarize or args.report_html:
        if any(p is not None for p in (args.player_file, args.output_dir, args.stop_file)):
            parser().error('offline journal modes do not accept live/status paths')
        if any(p is None or not p.is_absolute() for p in (args.journal, args.report_dir)):
            parser().error('offline journal modes require absolute --journal and --report-dir')
        if (args.summarize or args.report_html) and args.visual_reference:
            parser().error('player journal views do not accept visual references')
        if len(args.visual_reference) > 8 or any(not p.is_absolute() for p in args.visual_reference):
            parser().error('--visual-reference requires at most 8 absolute paths')
        if args.report_html:
            from .session_html import run
        elif args.summarize:
            from .native_history import run
        else:
            from .session_diagnosis import run
        return run(args)
    if args.live and any(p is None or not p.is_absolute()
                         for p in (args.player_file, args.output_dir, args.stop_file)):
        parser().error('--live requires absolute --player-file, --output-dir and --stop-file')

    if args.status and (args.output_dir is None or not args.output_dir.is_absolute()):
        parser().error('--status requires absolute --output-dir')

    def report(row):
        print(json.dumps(row, ensure_ascii=True, allow_nan=False), flush=True)

    if args.status:
        row = session_status(args.output_dir)
        report(row)
        return 0 if row['state'] == 'recorded_stopped' else 1

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
                result = run_session(lambda: (NativeSource(player) if args.collection == 'all'
                                             else NativeSource(player, collection=args.collection)),
                                     lambda: stop_requested(args.stop_file), emit,
                                     duration=args.max_seconds, interval=args.interval,
                                     private_labels=(player,))
            summary = dict(result, event='summary', collection=args.collection,
                           chat_called=False, audio_enabled=False, single_match=True,
                           finished_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())
            if result['reason'] == 'native_reader_unavailable':
                summary.update(current_permission=False, recovery=(
                    'Envoyer le STOP cible au collecteur connu et attendre son retour terminal ; '
                    'si son arret est inconnu, suspendre la reprise. Conserver tous les claims ; '
                    'apres verification independante, utiliser un parent et un STOP neufs.'))
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
