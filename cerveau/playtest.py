"""Session coach manuelle : préflight hors ligne par défaut, --live explicite."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .passive_session import OfflineArgumentParser, bounded, preflight as native_preflight


def parser():
    result = OfflineArgumentParser(description=__doc__, allow_abbrev=False)
    result.add_argument('--live', action='store_true')
    result.add_argument('--player-file', type=Path)
    result.add_argument('--coach-env-file', type=Path)
    result.add_argument('--output-dir', type=Path)
    result.add_argument('--stop-file', type=Path)
    result.add_argument('--max-seconds', type=bounded(1, 1800), default=300)
    result.add_argument('--interval', type=bounded(15, 300), default=30)
    result.add_argument('--collection', choices=('positions', 'all'), default='positions')
    result.add_argument('--coach-mode', choices=('reactive', 'macro', 'free'), default='reactive',
                        help='reactive : alerte factuelle sans API, sinon texte libre strict')
    voice = result.add_mutually_exclusive_group()
    voice.add_argument('--mumble', action='store_true', help='activation MANUELLE de la voix')
    voice.add_argument('--wav', action='store_true', help='fichiers WAV seulement, sans lecture')
    return result


def run_session(args, source_factory, coach_factory, emit, *, stopped=None,
                clock=time.monotonic, sleep=time.sleep, knowledge=None,
                synthesize=None, deliver=None, private_labels=()):
    """One protected source, no rebind; all output uses the existing Pipeline."""
    from .passive_session import Boundary, measured_acquisition, stop_requested
    from .runner import Pipeline, knowledge_for
    from .diagnostics import Journal
    from hotstate.native import NativeUnavailable
    from hotstate.diagnostics import exception_refusal
    from hotstate.reader import NativeBackendCloseError
    from .native_reader_guard import ReaderGuardError
    stopped = stopped or (lambda: stop_requested(args.stop_file))
    started = clock()
    deadline = started + args.max_seconds
    result = dict(accepted_reads=0, refused_reads=0, positions_available=0, coach_attempts=0,
                  fact_decisions=0, proposals=0, proposals_refused=0, expired=0, not_sent=0,
                  speech_synthesized=0, wav_produced=0, mumble_sent=0, reason='session_limit')
    source = pipeline = binding = None
    last_mission = None
    failures = 0

    def record(row):
        event = row['event']
        if event == 'coach_response':
            result['coach_attempts'] += 1
        elif event == 'fact_decision':
            result['fact_decisions'] += 1
        elif event == 'proposal':
            result['proposals' if row['speaking'] else 'proposals_refused'] += 1
        elif event == 'outcome':
            if row['reason'] == 'périmé':
                result['expired'] += 1
            elif row['reason'] == 'non_diffusé':
                result['not_sent'] += 1
        emit(dict(row, elapsed_s=round(clock() - started, 6)))
    journal = Journal(record, private_labels=private_labels)

    def boundary():
        if stopped():
            raise Boundary('stop_file')
        if clock() >= deadline:
            raise Boundary('session_limit')

    def read():
        nonlocal binding, last_mission
        boundary()
        pending = []
        try:
            state = source.read(pending.append)
        finally:
            boundary()
            for row in pending:
                journal.record('acquisition', **measured_acquisition(row))
                boundary()
        current = (state['meta']['match_id'], state['local_player'], state['ally_team'],
                   state['meta'].get('map'), state['meta'].get('map_id'), state['composition'])
        mission = state['meta']['t_s']
        if binding is not None and (current != binding or mission < last_mission):
            raise Boundary('session_changed')
        binding, last_mission = current, mission
        result['accepted_reads'] += 1
        if 'positions' in state:
            result['positions_available'] += 1
        if pipeline is not None and getattr(args, 'coach_mode', 'free') in ('macro', 'reactive'):
            if pipeline.coach.observe(state):
                journal.record('macro_episode_rearmed', cause='complete_safe_current_observation')
                boundary()
        return state

    def guarded_knowledge(state):
        value = (knowledge or knowledge_for)(state)
        boundary()
        return value

    def synth(decision):
        boundary()
        speech = synthesize(decision)
        boundary()
        result['speech_synthesized'] += 1
        journal.record('speech_synthesized')
        return speech

    def send(decision, speech, valid):
        boundary()
        if deliver is None:
            journal.record('delivery', mode='silent', sent=False, reason='silent_mode')
            return False  # Silent display is NOT a voice delivery or remembered advice.
        accepted = deliver(decision, speech, valid)
        if accepted:
            field = 'mumble_sent' if args.mumble else 'wav_produced'
            result[field] += 1
        journal.record('delivery', mode='mumble' if args.mumble else 'wav', sent=bool(accepted))
        return accepted

    try:
        boundary()
        source = source_factory()
        boundary()
        while True:
            boundary()
            cycle_started = clock()
            try:
                if pipeline is None:
                    initial = read()
                    boundary()
                    journal.observation(initial)
                    boundary()
                    coach = coach_factory()
                    boundary()
                    policy = None
                    if getattr(args, 'coach_mode', 'free') == 'macro':
                        from .macro import MacroCoach, MacroPolicy
                        if not isinstance(coach, MacroCoach):
                            coach = MacroCoach(coach.client, coach.model, coach.timeout,
                                coach.min_confidence, coach.reasoning_effort)
                        policy = MacroPolicy()
                        from .macro import facts
                        journal.record('macro_mode', intent='outnumbered',
                                       facts=facts(initial))
                    elif getattr(args, 'coach_mode', 'free') == 'reactive':
                        from .reactive import ReactiveCoach, ReactivePolicy
                        coach = ReactiveCoach(coach.client, coach.model, coach.timeout,
                            coach.min_confidence, coach.reasoning_effort)
                        policy = ReactivePolicy()
                    pipeline = Pipeline(coach, read, knowledge=guarded_knowledge,
                        synthesize=synth if synthesize else None, deliver=send,
                        clock=clock, journal=journal, checkpoint=boundary, intent_policy=policy,
                        mode=getattr(args, 'coach_mode', 'free'),
                        request_budget=lambda: deadline - clock())
                decision = pipeline.cycle()
                journal.outcome(decision)
                boundary()
                failures = 0
            except NativeUnavailable as exc:
                boundary()
                result['refused_reads'] += 1
                reason = exception_refusal(exc)
                journal.record('refusal', phase=journal.phase, **reason)
                boundary()
                failures += 1
                if binding is not None and (reason['category'] == 'context_identity' or reason['code'] in (
                        'aucune_simulation_active', 'contexte_natif_partie_changee',
                        'contexte_natif_dechire', 'partie_native_incoherente',
                        'partie_native_absente', 'partie_application_non_active',
                        'perspective_native_incoherente')):
                    raise Boundary('session_changed')
                if failures >= 12:
                    raise Boundary('failure_limit')
            # Start-to-start cadence: no extra interval after an API wait, and
            # no queued catch-up cycles when a whole attempt exceeds interval.
            wake = min(deadline, cycle_started + args.interval)
            while clock() < wake:
                boundary()
                sleep(min(.2, wake - clock()))
    except Boundary as exc:
        result['reason'] = exc.args[0]
    except ReaderGuardError:
        result['reason'] = 'native_reader_unavailable'
    except NativeBackendCloseError:
        result['reason'] = 'source_close_failed'
    except KeyboardInterrupt:
        result['reason'] = 'interrupted'
    except SystemExit:
        result['reason'] = 'source_unavailable'
    except Exception:
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


def main(argv=None):
    try:
        args = parser().parse_args(argv)
    except (ValueError, TypeError):
        print(json.dumps(dict(event='playtest_error', reason='invalid_arguments')))
        return 2
    try:
        from hotstate.position_maps import PLAYER_RECIPE_MAPS, SUPPORTED_MAPS
        row = dict(native_preflight(core=True), event='playtest_preflight',
                   collection=args.collection, coach_mode=args.coach_mode,
                   mode='mumble' if args.mumble else 'wav' if args.wav else 'silent',
                   current_permission=False, coach_configuration='unchecked',
                   positions_maps=list(SUPPORTED_MAPS),
                   positions_player_recipe_maps=list(PLAYER_RECIPE_MAPS), native_build=98348)
        from .runner import ROOT
        row['kb_present'] = (ROOT / 'kb/data/kb.db').is_file()
        if args.live:
            return live_main(args, row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
        return 0 if row['ready'] else 1
    except Exception:
        print(json.dumps(dict(event='playtest_error', reason='preflight_failed')))
        return 1


def live_main(args, preflight_row):
    """Explicit manual path only. Never called by default or offline preflight."""
    from . import passive_session
    from .diagnostic_session import configured_coach
    from .player_identity import read_player_label
    from .session_control import record_control
    from .session_readiness import inspect_paths
    checks = inspect_paths(args)
    if (checks != dict(paths='valid', identity='valid_private_file', output='new', stop='absent')
            or not preflight_row['ready'] or not preflight_row['kb_present']):
        print(json.dumps(dict(event='playtest_error', reason='preparation_refused', checks=checks)))
        return 1
    bot = None
    try:
        if passive_session.stop_requested(args.stop_file):
            print(json.dumps(dict(event='boundary', reason='stop_file')))
            return 0
        player = read_player_label(args.player_file)
        args.output_dir.parent.mkdir(parents=True, exist_ok=True)
        with passive_session.session_lock(args.output_dir.parent / 'passive-session.lock'):
            args.output_dir.mkdir(exist_ok=False)
            record_control(args.output_dir, args.stop_file)
            with (args.output_dir / 'events.jsonl').open('x', encoding='utf-8') as stream:
                def emit(event):
                    raw = json.dumps(event, ensure_ascii=True, allow_nan=False)
                    stream.write(raw + '\n')
                    stream.flush()
                    print(raw, flush=True)
                emit(dict(event='playtest_start', collection=args.collection,
                          coach_mode=args.coach_mode, mode=preflight_row['mode']))
                synthesize = deliver = None
                if args.wav or args.mumble:
                    def synthesize(decision):
                        from tts import synthesize as piper
                        return piper(decision.texte, model='piper', style=decision.style)
                    wav_index = 0
                    def deliver(decision, speech, valid):
                        nonlocal bot, wav_index
                        if not valid():
                            return False
                        if args.wav:
                            wav_index += 1
                            # Session output is new, never overwrite another session.
                            speech.save_wav(args.output_dir / f'advice-{wav_index:04d}.wav')
                            return True
                        if bot is None:
                            from grocoapi.client import _load_env_file
                            from mumblebot import MumbleBot
                            env = (_load_env_file() if args.coach_env_file is None
                                   else _load_env_file(args.coach_env_file))
                            import os
                            def config(key, default):
                                return os.environ.get(key, env.get(key, default))
                            bot = MumbleBot(config('MUMBLE_HOST', '127.0.0.1'),
                                int(config('MUMBLE_PORT', '64738')), config('MUMBLE_USER', 'Coach'),
                                config('MUMBLE_PASSWORD', ''), config('MUMBLE_CHANNEL', ''))
                            bot.connect(timeout=3, attempts=1)
                        from .voice import send_to_mumble
                        return send_to_mumble(bot, speech, valid)
                summary = run_session(args,
                    lambda: passive_session.NativeSource(player, collection=args.collection),
                    lambda: configured_coach(args.coach_env_file), emit,
                    synthesize=synthesize, deliver=deliver, private_labels=(player,))
                summary.update(event='summary', collection=args.collection,
                               coach_mode=args.coach_mode, mode=preflight_row['mode'])
                with (args.output_dir / 'summary.json').open('x', encoding='utf-8') as summary_file:
                    json.dump(summary, summary_file, ensure_ascii=True, allow_nan=False)
                emit(summary)
                return (130 if summary['reason'] == 'interrupted' else
                        0 if summary['reason'] in ('stop_file', 'session_limit', 'session_changed') else 1)
    except KeyboardInterrupt:
        return 130
    except Exception:
        print(json.dumps(dict(event='playtest_error', reason='initialization_or_io_failed')))
        return 1
    finally:
        if bot is not None:
            bot.disconnect()


if __name__ == '__main__':
    raise SystemExit(main())
