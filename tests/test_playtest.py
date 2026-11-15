"""SYNTHETIC offline acceptance; no game, external HTTP or audible output."""
import contextlib
import io
import json
import copy
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class PlaytestPreflightTests(unittest.TestCase):
    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows CMD launcher')
    def test_launcher_requires_explicit_scratch_and_runs_silent_preflight(self):
        import os
        import subprocess
        import sys
        root = Path(__file__).resolve().parents[1]
        launcher = root/'tools/playtest.cmd'
        env = dict(os.environ, CERVHOTS_PYTHON=sys.executable)
        env.pop('CERVHOTS_SCRATCH', None)
        def run():
            return subprocess.run(['cmd.exe', '/d', '/c', str(launcher), 'preflight'],
                cwd=root, env=env, capture_output=True, text=True, timeout=30)
        refused = run()
        self.assertEqual(refused.returncode, 2)
        self.assertIn('CERVHOTS_SCRATCH', refused.stdout)
        env['CERVHOTS_SCRATCH'] = 'relative-scratch'
        self.assertEqual(run().returncode, 2)
        with tempfile.TemporaryDirectory() as directory:
            env['CERVHOTS_SCRATCH'] = directory
            accepted = run()
        self.assertEqual(accepted.returncode, 0, accepted.stdout+accepted.stderr)
        row = json.loads(accepted.stdout)
        for key in ('memory_opened', 'chat_called', 'audio_enabled'):
            self.assertFalse(row[key])
        self.assertEqual(row['mode'], 'silent')
        self.assertNotIn('profiles\\cody', launcher.read_text())

    def test_invalid_arguments_never_echo_private_tokens(self):
        from cerveau import playtest
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = playtest.main(['--unknown-private-option', 'SYNTHETIC_PRIVATE_TOKEN'])
        self.assertEqual(code, 2)
        self.assertNotIn('SYNTHETIC_PRIVATE_TOKEN', stdout.getvalue()+stderr.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())['reason'], 'invalid_arguments')

    def test_default_preflight_never_constructs_source_coach_or_audio(self):
        from cerveau import playtest
        with contextlib.ExitStack() as stack:
            for name in ('cerveau.passive_session.NativeSource',
                         'cerveau.diagnostic_session.configured_coach',
                         'grocoapi.client._load_env_file', 'socket.create_connection'):
                stack.enter_context(patch(name, side_effect=AssertionError('forbidden')))
            stdout = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            code = playtest.main([])
        row = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertFalse(row['memory_opened'])
        self.assertFalse(row['chat_called'])
        self.assertFalse(row['audio_enabled'])
        self.assertEqual(row['mode'], 'silent')
        self.assertEqual(row['collection'], 'positions')


class PlaytestWaitingTests(unittest.TestCase):
    def test_mumble_connects_before_waiting_for_game_without_audio(self):
        from cerveau import playtest
        from types import ModuleType
        calls = []
        bot = SimpleNamespace(connect=lambda **kw: calls.append('connect'),
                              disconnect=lambda: calls.append('disconnect'))
        module = ModuleType('mumblebot')
        module.MumbleBot = lambda *a: bot
        def run(*args, **kwargs):
            self.assertEqual(calls, ['connect'])
            return dict(reason='session_limit', reader_active=False)
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            identity = parent/'identity.txt'
            identity.write_text('SYNTHETIC_IDENTITY', encoding='utf-8')
            args = playtest.parser().parse_args(['--live', '--mumble',
                '--player-file', str(identity), '--output-dir', str(parent/'session'),
                '--stop-file', str(parent/'STOP')])
            with patch.dict('sys.modules', {'mumblebot': module}), patch(
                    'grocoapi.client._load_env_file', return_value={}), patch(
                    'cerveau.playtest.run_session', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
                result = playtest.live_main(args, dict(ready=True, kb_present=True, mode='mumble'))
        self.assertEqual(result, 0)
        self.assertEqual(calls, ['connect', 'disconnect'])

    def test_matchmaking_waits_until_session_deadline(self):
        from cerveau.playtest import run_session
        from hotstate.native import NativeUnavailable
        now = [0.]
        closed = []
        def read(observe):
            raise NativeUnavailable('aucune_simulation_active')
        source = SimpleNamespace(read=read, close=lambda: closed.append(True))
        args = SimpleNamespace(max_seconds=600, interval=15, mumble=False)
        def sleep(seconds):
            now[0] += seconds
        result = run_session(args, lambda: source,
            lambda: self.fail('No coach before a match'), lambda row: None,
            stopped=lambda: False, clock=lambda: now[0], sleep=sleep)
        self.assertEqual(result['reason'], 'session_limit')
        self.assertGreater(result['refused_reads'], 12)
        self.assertEqual(closed, [True])

    def test_real_read_errors_still_hit_failure_limit(self):
        from cerveau.playtest import run_session
        from hotstate.native import NativeUnavailable
        now = [0.]
        def read(observe):
            raise NativeUnavailable('lecture_native_dechiree')
        source = SimpleNamespace(read=read, close=lambda: None)
        args = SimpleNamespace(max_seconds=600, interval=15, mumble=False)
        def sleep(seconds):
            now[0] += seconds
        result = run_session(args, lambda: source, lambda: None, lambda row: None,
            stopped=lambda: False, clock=lambda: now[0], sleep=sleep)
        self.assertEqual(result['reason'], 'failure_limit')
        self.assertEqual(result['refused_reads'], 12)


class PlaytestSyntheticTests(unittest.TestCase):
    """Real native collector/normalizer/Coach/Pipeline, local HTTP, fake audio."""
    def exercise(self, scenario='accepted', collection='positions', mode='free', cli=False,
                 cli_audio='mumble'):
        from cerveau import playtest
        from cerveau.passive_session import NativeSource
        from cerveau.brain import Coach
        from grocoapi import GrocoClient
        from test_capture_visibility_pipeline import FixtureProcess
        import test_day_composition as composition
        received, rows, opened, sends, syntheses = [], [], [], [], []
        cli_paths = {}
        stop = [scenario == 'stop_before_open']
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                if scenario == 'stop_before_send':
                    if cli_paths:
                        from cerveau.session_control import request_stop
                        request = request_stop(cli_paths['output'], cli_paths['stop'])
                        owner.assertEqual(request['state'], 'published')
                    stop[0] = True
                if scenario == 'movement':
                    # Change only coordinates on the next real normalized read.
                    owner.move = True
                if scenario == 'expired':
                    owner.now += 21
                payload = {'parler': True, 'texte': 'Regroupez-vous avant le prochain combat.',
                           'priorite': 2, 'confiance': .9, 'sujet': 'groupe', 'style': 'calme'}
                if scenario == 'rejected':
                    payload['confiance'] = .5
                if mode == 'macro':
                    payload = {'intent': 'outnumbered', 'confiance': .9}
                raw = json.dumps({'choices': [{'message': {'content': json.dumps(payload)}}]}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.addCleanup(thread.join, 2)
        fixture = composition.DayCompositionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.now, self.move = 0., False
        if mode in ('macro', 'reactive'):
            from hotstate.native import NativeReader
            native = NativeReader(fixture.memory, profile=fixture.memory.profile)
            for slot in range(1, 11):
                unit = native.unit_pointer(native.value(native.player_pointer(slot)+0x58), slot)
                fixture.memory.pack(unit+0x39, 'B', 0)
            ally = next(p['id'] for p in fixture.memory.context['players']
                        if p['team'] == fixture.memory.context['local_player']['team'])
            unit = native.unit_pointer(native.value(native.player_pointer(ally+1)+0x58), ally+1)
            fixture.memory.pack(unit+0x39, 'B', 6)
        class Backend(FixtureProcess):
            fail_close = scenario == 'close_error'
            def close(self):
                if self.fail_close:
                    self.fail_close = False
                    raise OSError('SYNTHETIC close uncertainty')
                self.closed = True
        def source():
            backend = Backend(fixture.memory)
            with patch('hotstate.reader.ProcessBackend', return_value=backend), patch(
                    'hotstate.native_context.NativeContextProbe', return_value=fixture.memory.probe()):
                real = NativeSource('SYNTHETIC_PRIVATE_IDENTITY', collection=collection)
            read = real.read
            def changed(observe):
                decided = received or any(r['event'] == 'fact_decision' for r in rows)
                if scenario == 'core_refused' or (scenario == 'core_refused_recheck' and decided):
                    from hotstate.native import NativeUnavailable
                    raise NativeUnavailable('lecture_native_dechiree')
                if scenario == 'identity_refused' and decided:
                    from hotstate.native import NativeUnavailable
                    raise NativeUnavailable('identite_locale_native_incoherente')
                if owner.move:
                    fixture.memory.position(7, 80.25, 150.5)
                if scenario == 'ally_return' and decided:
                    fixture.memory.pack(unit+0x39, 'B', 0)
                state = read(observe)
                if scenario == 'stop_after_read':
                    stop[0] = True
                if scenario == 'match_changed' and len([r for r in rows if r['event'] == 'acquisition']) >= 1:
                    state = copy.deepcopy(state)
                    state['meta']['match_id'] = 'f'*64
                return state
            real.read = changed
            opened.append(real)
            return real
        def emit(row):
            rows.append(row)
            if mode == 'reactive' and scenario == 'movement' and row['event'] == 'fact_decision':
                owner.move = True
            if scenario == 'io_error' and row['event'] == 'coach_input':
                raise OSError('SYNTHETIC journal failure')
            if scenario == 'slow_prepared' and row['event'] == 'coach_attempt':
                self.now += 21
            if scenario == 'stop_before_llm' and row['event'] == 'coach_input':
                stop[0] = True
            if (scenario == 'stop_at_final_check' and row['event'] == 'freshness'
                    and sum(r['event'] == 'freshness' for r in rows) == 3):
                stop[0] = True
        def synthesize(decision):
            syntheses.append(decision)
            return SimpleNamespace(pcm=b'SYNTHETIC-PCM', duration_s=0)
        def deliver(decision, speech, valid):
            if not valid() or scenario == 'not_sent':
                return False
            sends.append(speech.pcm)
            return True
        def sleep(seconds):
            self.now += seconds
        with tempfile.TemporaryDirectory() as directory, patch('grocoapi.client._load_env_file', return_value={}):
            client = GrocoClient(base_url=f'http://127.0.0.1:{server.server_port}', token='SYNTHETIC-TOKEN')
            if mode == 'macro':
                from cerveau.macro import MacroCoach
                coach = MacroCoach(client, 'SYNTHETIC-model')
            else:
                coach = Coach(client, 'SYNTHETIC-model')
            args = SimpleNamespace(max_seconds=25, interval=30, collection=collection,
                coach_mode=mode, mumble=True, wav=False, stop_file=Path(directory)/'STOP')
            from hotstate.native import NativeUnavailable
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch('hotstate.reader.ProcessBackend.__init__',
                    side_effect=AssertionError('OS game construction forbidden')))
                if scenario in ('positions_refused', 'positions_refused_recheck'):
                    from hotstate.positions import AlliedPositions
                    original_positions_read = AlliedPositions.read
                    def positions_read(reader, *a, **kw):
                        if scenario == 'positions_refused' or received or any(r['event'] == 'fact_decision' for r in rows):
                            raise NativeUnavailable('recette_positions_absente')
                        return original_positions_read(reader, *a, **kw)
                    stack.enter_context(patch('hotstate.positions.AlliedPositions.read',
                        new=positions_read))
                if not cli:
                    def knowledge(state):
                        if scenario == 'slow_knowledge':
                            self.now += 21
                        return 'SYNTHETIC offline KB'
                    result = playtest.run_session(args, source, lambda: coach, emit,
                        stopped=lambda: stop[0], clock=lambda: self.now, sleep=sleep,
                        knowledge=knowledge, synthesize=synthesize,
                        deliver=deliver)
                else:
                    import sys
                    from types import ModuleType
                    parent = Path(directory)
                    identity = parent/'SYNTHETIC-identity.txt'
                    identity.write_text('SYNTHETIC_PRIVATE_IDENTITY', encoding='utf-8')
                    config = parent/'SYNTHETIC-runtime.conf'
                    cli_paths.update(output=parent/'session', stop=parent/'STOP')
                    config.write_text('GROCO_MODEL=SYNTHETIC-model\nGROCO_API_TOKEN=SYNTHETIC-TOKEN\n'
                        + f'GROCO_API_URL=http://127.0.0.1:{server.server_port}\n', encoding='utf-8')
                    # Inject only knowledge/runtime facilities. The real CLI,
                    # private-file/control/publication/source/configured_coach,
                    # Pipeline and voice.send_to_mumble are exercised.
                    (parent/'kb/data').mkdir(parents=True)
                    (parent/'kb/data/kb.db').write_bytes(b'SYNTHETIC-KB-PRESENCE-ONLY')
                    tts = ModuleType('tts')
                    tts.__path__ = [str(Path(__file__).resolve().parents[1]/'tts')]
                    stack.enter_context(patch.dict(sys.modules, {'tts': tts}))
                    from tts.speech import Speech
                    def fake_piper(text, **kwargs):
                        syntheses.append(text)
                        return Speech(text, 'SYNTHETIC', 'SYNTHETIC', b'\x00'*480)
                    tts.synthesize = fake_piper
                    class FakeBot:
                        def __init__(self, *args):
                            self._lost = False
                            self.mumble = SimpleNamespace(users=SimpleNamespace(myself=object()),
                                send_audio=SimpleNamespace(add_sound=self.add_sound), is_alive=lambda: True)
                        def connect(self, **kwargs): pass
                        def disconnect(self): pass
                        def wait_for_quiet(self, **kwargs): return True
                        def add_sound(self, pcm):
                            sends.append(pcm)
                            event = threading.Event()
                            event.set()
                            return event
                    stack.enter_context(patch.dict(sys.modules, {'mumblebot': SimpleNamespace(MumbleBot=FakeBot)}))
                    stack.enter_context(patch('cerveau.runner.ROOT', parent))
                    stack.enter_context(patch('cerveau.passive_session.NativeSource', side_effect=lambda *a, **k: source()))

                    # Outer patch denies all default secret loading. Only the
                    # generated SYNTHETIC config is read by the real parser.
                    from grocoapi import client as client_module
                    def synthetic_env(path=None):
                        if path != config:
                            return {}
                        return dict(line.split('=', 1) for line in config.read_text().splitlines())
                    stack.enter_context(patch.object(client_module, '_load_env_file', side_effect=synthetic_env))
                    loop = playtest.run_session
                    def session(cli_args, factory, coach_factory, persist, **kwargs):
                        def tee(row):
                            emit(row)
                            persist(row)
                        return loop(cli_args, factory, coach_factory, tee,
                            clock=lambda: self.now, sleep=sleep, stopped=lambda: stop[0],
                            knowledge=lambda state: 'SYNTHETIC offline KB', **kwargs)
                    stack.enter_context(patch.object(playtest, 'run_session', side_effect=session))
                    stdout = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    audio_args = [] if cli_audio == 'silent' else ['--'+cli_audio]
                    code = playtest.main(['--live', *audio_args, '--coach-mode', mode,
                        '--collection', collection, '--player-file', str(identity),
                        '--coach-env-file', str(config), '--output-dir', str(parent/'session'),
                        '--stop-file', str(parent/'STOP'), '--max-seconds', '25'])
                    self.assertEqual(code, 0, stdout.getvalue())
                    result = json.loads((parent/'session/summary.json').read_text())
                    persisted = [json.loads(line) for line in (parent/'session/events.jsonl').read_text().splitlines()]
                    self.assertTrue(any(r['event'] == 'coach_input' for r in persisted))
                    if cli_audio == 'wav':
                        import wave
                        with wave.open(str(parent/'session/advice-0001.wav'), 'rb') as wav:
                            self.assertEqual(wav.getframerate(), 48000)
                            self.assertEqual(wav.getnframes(), 240)
        if scenario == 'close_error':
            self.assertIsNone(result['reader_active'])
            self.assertIsNotNone(opened[0].guard.handle)
            opened[0].close()  # Test-only recovery after the injected uncertainty.
        self.assertTrue(all(s.backend is None and s.guard.handle is None for s in opened))
        text = json.dumps(rows)
        for forbidden in ('SYNTHETIC_PRIVATE_IDENTITY', 'SYNTHETIC-TOKEN', 'acquisition_seal', 'monotonic_s'):
            self.assertNotIn(forbidden, text)
        fixture.doCleanups()
        server.shutdown()
        thread.join(2)
        import os
        if os.environ.get('CERVHOTS_SYNTHETIC_LOG_DIR'):
            out = Path(os.environ['CERVHOTS_SYNTHETIC_LOG_DIR'])
            out.mkdir(parents=True, exist_ok=True)
            suffix = '-cli-'+cli_audio if cli else ''
            with (out/f'SYNTHETIC-{mode}-{collection}-{scenario}{suffix}.jsonl').open('x', encoding='utf-8') as stream:
                for row in [dict(event='provenance', basis='SYNTHETIC_NOT_LIVE_NOT_AUDIO',
                                 http_received=len(received), fake_sends=len(sends)), *rows,
                            dict(result, event='summary')]:
                    stream.write(json.dumps(row, ensure_ascii=True)+'\n')
        return result, rows, received, sends, syntheses, coach

    def test_real_cli_reactive_voice_routes_native_facts_to_fake_audio_without_http(self):
        for scenario in ('accepted', 'movement', 'positions_refused', 'positions_refused_recheck'):
            with self.subTest(scenario=scenario):
                result, rows, received, sends, syntheses, _ = self.exercise(
                    scenario, mode='reactive', cli=True)
                self.assertEqual((result['mumble_sent'], received, len(sends), len(syntheses)),
                                 (1, [], 1, 1))
                self.assertEqual((result['fact_decisions'], result['coach_attempts']), (1, 0))
                self.assertTrue(any(r['event']=='intent_revalidation' and r['accepted'] for r in rows))

    def test_real_cli_reactive_stop_life_and_core_guard_still_block_fake_audio(self):
        for scenario in ('stop_at_final_check', 'ally_return', 'core_refused_recheck', 'identity_refused'):
            with self.subTest(scenario=scenario):
                result, _, received, sends, _, _ = self.exercise(scenario, mode='reactive', cli=True)
                self.assertEqual((result['mumble_sent'], received, sends), (0, [], []))

    def test_accepted_real_http_and_anonymized_journal_exact_positions(self):
        result, rows, requests, sends, syntheses, coach = self.exercise()
        self.assertEqual(len(requests), 1)
        state = json.loads(requests[0]['messages'][1]['content'])['etat']
        recorded = next(r for r in rows if r['event'] == 'coach_input')
        self.assertEqual(recorded['coverage']['allies_expected'], 5)
        self.assertEqual(recorded['coverage']['positions_acquired'], 5)
        self.assertEqual(recorded['coverage']['positions']['t'], state['positions']['t'])
        self.assertEqual(recorded['coverage']['positions']['heroes'],
            [dict(slot=h['id'], team=h['team'], x=h['x'], y=h['y'], u=h['u'], v=h['v'])
             for h in state['positions']['heroes']])
        self.assertEqual(result['coach_attempts'], 1)
        self.assertEqual(result['mumble_sent'], 1)
        self.assertEqual(len(sends), 1)
        self.assertEqual(len(syntheses), 1)
        self.assertEqual(len(coach.history), 1)

    def test_all_explicit_reaches_same_pipeline(self):
        result, rows, requests, sends, syntheses, coach = self.exercise(collection='all')
        self.assertEqual(len(requests), 1)
        state = json.loads(requests[0]['messages'][1]['content'])['etat']
        self.assertEqual(state['meta']['collection'], 'all')
        self.assertIn('talents', state)
        self.assertIn('local_cooldowns', state)
        self.assertTrue(next(r for r in rows if r['event'] == 'coach_input')['coverage']['map_supported'])

    def test_stop_before_open_and_before_llm(self):
        for scenario in ('stop_before_open', 'stop_before_llm'):
            with self.subTest(scenario=scenario):
                result, rows, requests, sends, syntheses, coach = self.exercise(scenario)
                self.assertEqual(result['reason'], 'stop_file')
                self.assertEqual(requests, [])
                self.assertEqual(sends, [])
                self.assertEqual(len(coach.history), 0)

    def test_stop_before_send_and_match_change_never_rebind(self):
        for scenario, reason in (('stop_before_send', 'stop_file'), ('stop_at_final_check', 'stop_file'),
                                 ('match_changed', 'session_changed')):
            with self.subTest(scenario=scenario):
                result, rows, requests, sends, syntheses, coach = self.exercise(scenario)
                self.assertEqual(result['reason'], reason)
                self.assertEqual(sends, [])
                self.assertEqual(len(coach.history), 0)

    def test_rejected_expired_moving_not_sent_never_remember(self):
        for scenario, reason in (('rejected', 'confiance_insuffisante'), ('expired', 'périmé'),
                                 ('movement', 'périmé'), ('not_sent', 'non_diffusé')):
            with self.subTest(scenario=scenario):
                result, rows, requests, sends, syntheses, coach = self.exercise(scenario)
                self.assertTrue(any(r.get('event') == 'outcome' and r.get('reason') == reason for r in rows), rows)
                self.assertEqual(sends, [])
                self.assertEqual(len(coach.history), 0)
                if scenario == 'movement':
                    self.assertTrue(any('positions' in r.get('changed_fields', []) for r in rows))

    def test_positions_refusal_visible_in_http_and_journal(self):
        result, rows, requests, sends, syntheses, coach = self.exercise('positions_refused')
        state = json.loads(requests[0]['messages'][1]['content'])['etat']
        self.assertNotIn('positions', state)
        coverage = next(r for r in rows if r['event'] == 'coach_input')['coverage']
        self.assertEqual(coverage['positions_status'], 'refused')
        self.assertIsNone(coverage['positions'])

    def test_macro_optional_positions_refused_initially_keeps_only_factual_advice(self):
        from cerveau.macro import TEXT
        result, rows, requests, sends, syntheses, coach = self.exercise('positions_refused', mode='macro')
        self.assertEqual(len(requests), 1)
        state = json.loads(requests[0]['messages'][1]['content'])['etat']
        self.assertNotIn('positions', state)
        coverage = next(r['coverage'] for r in rows if r['event'] == 'coach_input')
        self.assertEqual(coverage['positions_status'], 'refused')
        self.assertIsNone(coverage['positions_acquired'])
        self.assertEqual(syntheses[0].texte, TEXT)
        self.assertEqual(len(sends), 1)
        self.assertEqual(len(coach.history), 1)
        self.assertEqual(result['mumble_sent'], 1)

    def test_macro_optional_positions_refused_at_recheck_keeps_only_factual_advice(self):
        from cerveau.macro import TEXT
        result, rows, requests, sends, syntheses, coach = self.exercise('positions_refused_recheck', mode='macro')
        self.assertEqual(len(requests), 1)
        self.assertIn('positions', json.loads(requests[0]['messages'][1]['content'])['etat'])
        self.assertEqual(syntheses[0].texte, TEXT)
        self.assertEqual(len(sends), 1)
        self.assertEqual(len(coach.history), 1)
        self.assertEqual(result['mumble_sent'], 1)
        self.assertEqual(result['expired'], 0)
        self.assertTrue(any('positions' in r.get('changed_fields', []) for r in rows))
        self.assertTrue(any('positions' in r.get('optional_refusals', {}) for r in rows))

    def test_macro_required_core_refusal_never_delivers(self):
        for scenario, http_count in (('core_refused', 0), ('core_refused_recheck', 1)):
            with self.subTest(scenario=scenario):
                result, rows, requests, sends, syntheses, coach = self.exercise(scenario, mode='macro')
                self.assertEqual(len(requests), http_count)
                self.assertEqual(sends, [])
                self.assertEqual(len(coach.history), 0)
                self.assertEqual(result['mumble_sent'], 0)

    def test_macro_local_http_movement_delivered_and_ally_return_cancelled(self):
        for scenario, expected in (('movement', 1), ('ally_return', 0), ('stop_before_send', 0)):
            with self.subTest(scenario=scenario):
                result, rows, requests, sends, syntheses, coach = self.exercise(scenario, mode='macro')
                self.assertEqual(len(requests), 1)
                self.assertEqual(len(sends), expected)
                self.assertEqual(len(coach.history), expected)
                self.assertEqual(result['mumble_sent'], expected)
                self.assertTrue(any(r['event'] == 'macro_mode' for r in rows))

    def test_real_cli_manual_macro_voice_with_fake_piper_and_fake_mumble(self):
        result, rows, requests, sends, syntheses, coach = self.exercise('movement', mode='macro', cli=True)
        self.assertEqual(result['mumble_sent'], 1)
        self.assertEqual(len(sends), 1)
        self.assertEqual(len(requests), 1)

    def test_real_cli_stop_request_while_http_in_flight_cannot_send(self):
        result, rows, requests, sends, syntheses, coach = self.exercise('stop_before_send', mode='macro', cli=True)
        self.assertEqual(result['reason'], 'stop_file')
        self.assertEqual(sends, [])
        self.assertEqual(result['mumble_sent'], 0)

    def test_close_uncertainty_is_not_reported_inactive(self):
        result, rows, requests, sends, syntheses, coach = self.exercise('close_error')
        self.assertEqual(result['reason'], 'source_close_failed')
        self.assertIsNone(result['reader_active'])

    def test_stop_after_read_and_journal_error_close_source_without_http(self):
        for scenario, reason in (('stop_after_read', 'stop_file'), ('io_error', 'software_error')):
            with self.subTest(scenario=scenario):
                result, rows, requests, sends, syntheses, coach = self.exercise(scenario)
                self.assertEqual(result['reason'], reason)
                self.assertEqual(requests, [])
                self.assertEqual(sends, [])

    def test_identity_refusal_after_binding_stops_instead_of_retrying(self):
        result, rows, requests, sends, syntheses, coach = self.exercise('identity_refused')
        self.assertEqual(result['reason'], 'session_changed')
        self.assertEqual(sends, [])

    def test_slow_knowledge_does_not_request_llm_with_old_input(self):
        for scenario in ('slow_knowledge', 'slow_prepared'):
            with self.subTest(scenario=scenario):
                result, rows, requests, sends, syntheses, coach = self.exercise(scenario)
                self.assertEqual(requests, [])
                self.assertEqual(result['coach_attempts'], 0)
                self.assertEqual(result['expired'], 1)

    def test_real_cli_silent_and_wav_file_are_not_mumble_delivery(self):
        for audio in ('silent', 'wav'):
            with self.subTest(audio=audio):
                result, rows, requests, sends, syntheses, coach = self.exercise('movement',
                    mode='macro', cli=True, cli_audio=audio)
                self.assertEqual(result['mumble_sent'], 0)
                self.assertEqual(result['wav_produced'], 1 if audio == 'wav' else 0)
                self.assertEqual(result['not_sent'], 1 if audio == 'silent' else 0)
                self.assertEqual(sends, [])
                self.assertEqual(len(syntheses), 1 if audio == 'wav' else 0)


if __name__ == '__main__':
    unittest.main()
