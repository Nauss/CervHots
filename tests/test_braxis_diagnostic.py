"""Synthetic-only diagnostic tests: never opens the game."""
import unittest

try:
    from hotstate import braxis
except ImportError:
    braxis = None


class CausalMeasurementTests(unittest.TestCase):
    def test_scoped_absence_is_not_unattempted_coverage(self):
        self.assertIsNotNone(braxis, 'product causal measurement is missing')
        result = braxis.measure({
            'compiler': {'status': 'refused', 'reason': 'compiler_root_null', 'requests': 1},
            'type': {'status': 'refused', 'reason': 'named_type_absent', 'requests': 10},
            'frames.6003': {'status': 'not_attempted', 'reason': 'whole_budget', 'requests': 0},
            'frames.6007': {'status': 'observed', 'requests': 4},
        })
        self.assertEqual(result['scoped_absences'], ['compiler', 'type'])
        self.assertEqual(result['unattempted'], ['frames.6003'])
        self.assertEqual(result['observed_metadata'], ['frames.6007'])
        self.assertFalse(result['global_absence_proven'])
        self.assertIsNone(result['objective'])
        self.assertFalse(result['coach'])
        self.assertEqual(result['gates'], {'B1': 'unproven', 'B2': 'unproven', 'B3': 'unproven'})


class Sparse:
    module_base = 0x10000000
    module_size = 73064448

    def __init__(self):
        self.data = {}
        self.calls = []

    def put(self, address, data):
        self.data.update({address + i: b for i, b in enumerate(data)})

    def u(self, address, value):
        import struct
        self.put(address, struct.pack('<Q', value))

    def read_memory(self, address, size):
        self.calls.append((address, size))
        try:
            return bytes(self.data[address + i] for i in range(size))
        except KeyError:
            return None


def functions_memory():
    import struct
    m = Sparse()
    m.u(m.module_base + 0x3b8c918, 0)
    # Empty aggregate bucket is a scoped lookup miss, not global absence.
    m.u(m.module_base + 0x412c8a0 + (braxis.decoders.hash_name(braxis.decoders.SIG) & 255) * 8, 0)
    table = 0x20000
    m.u(m.module_base + 0x3b8c5c8, table)
    for i, (index, name) in enumerate(braxis.FUNCTIONS):
        address = 0x40000 + i * 0x1000
        m.u(table + index * 8, address)
        record = bytearray(112)
        struct.pack_into('<IIQ', record, 0x58, len(name) * 4, 2, address + 0x100)
        m.put(address, record)
        m.put(address + 0x100, name.encode())
    return m


class IndependentFramesTests(unittest.TestCase):
    def test_bad_first_frame_does_not_hide_later_frames(self):
        self.assertTrue(hasattr(braxis, 'diagnose'), 'independent product channels missing')
        m = functions_memory()
        m.put(0x40000 + 0x100, b'X')
        channels = braxis.diagnose(braxis.WholeTx(m))
        self.assertEqual(channels['type']['reason'], 'named_type_absent')
        self.assertEqual(channels['compiler']['reason'], 'compiler_root_null')
        self.assertEqual(channels['frames.6003']['reason'], 'frame_wrong_function')
        for index in (6007, 6122):
            self.assertEqual(channels[f'frames.{index}']['status'], 'observed')
            self.assertGreater(channels[f'frames.{index}']['requests'], 0)
        self.assertEqual(channels['frames.6003']['requests'], 4)


class WholeTests(unittest.TestCase):
    def test_build_failure_marks_every_channel_unattempted(self):
        self.assertTrue(hasattr(braxis, 'collect'), 'guarded collector missing')
        result = braxis.collect(Sparse())
        self.assertEqual(result['build']['status'], 'refused')
        self.assertEqual(result['physical_requests'], 1)
        self.assertTrue(all(row['status'] == 'not_attempted' for row in result['channels'].values()))
        self.assertEqual(result['measurement']['scoped_absences'], [])
        self.assertEqual(len(result['measurement']['unattempted']), 9)
        self.assertIsNone(result['measurement']['objective'])

    def test_read_finishing_late_is_costed_and_refused(self):
        clock = [0.0]
        m = Sparse()
        def read(a, n):
            clock[0] = .126
            return b'\0' * n
        m.read_memory = read
        tx = braxis.WholeTx(m, clock=lambda: clock[0])
        row = braxis.run_channel(tx, lambda t: t.read(0x20000, 8))
        self.assertEqual(row['status'], 'refused')
        self.assertEqual(row['reason'], 'whole_time')
        self.assertEqual((row['requests'], row['bytes_requested']), (1, 8))
        later = braxis.run_channel(tx, lambda t: t.read(0x20000, 8))
        self.assertEqual(later['status'], 'not_attempted')
        self.assertEqual(later['requests'], 0)

    def test_budget_exhaustion_is_not_absence(self):
        tx = braxis.WholeTx(Sparse())
        tx.limit_reads = 0
        rows = braxis.diagnose(tx)
        self.assertEqual(braxis.measure(rows)['scoped_absences'], [])
        self.assertEqual(len(braxis.measure(rows)['unattempted']), 5)
        self.assertEqual(tx.bytes, 0)


class SessionTests(unittest.TestCase):
    def test_stop_before_open_never_constructs_backend(self):
        import tempfile
        from pathlib import Path
        try:
            from hotstate import braxis_diagnostic as cli
        except ImportError:
            cli = None
        self.assertIsNotNone(cli, 'bounded operator command missing')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stop = root / 'STOP'
            stop.touch()
            def forbidden():
                self.fail('backend opened despite STOP')
            result = cli.run_session(root / 'new', [stop], seconds=1, interval=1,
                                     max_attempts=1, player_label='SYNTHETIC', backend_factory=forbidden)
            self.assertEqual(result['stop_reason'], 'STOP')
            self.assertEqual(result['attempts'], 0)
            self.assertFalse((root / 'new').exists())
    def test_failed_build_is_recorded_once_and_backend_closed(self):
        import json
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        self.assertTrue(hasattr(cli, 'public_attempt'), 'sanitized measured persistence missing')
        m = Sparse()
        m.closed = False
        m.close = lambda: setattr(m, 'closed', True)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'new'
            summary = cli.run_session(out, [Path(directory) / 'STOP'], seconds=1,
                                     interval=1, max_attempts=1, player_label='SYNTHETIC',
                                     backend_factory=lambda: m)
            self.assertEqual(summary['attempts'], 1)
            self.assertEqual(summary['persisted'], 1)
            self.assertEqual(summary['stop_reason'], 'build_refused')
            self.assertTrue(m.closed)
            raw = json.loads((out / 'PRIVATE/readsets.jsonl').read_text())
            public = json.loads((out / 'attempts.jsonl').read_text())
            self.assertEqual(raw['physical_requests'], 1)
            self.assertEqual(public['channels']['type']['status'], 'not_attempted')
            self.assertNotIn('reads', public)
            self.assertNotIn('module_base', public)
            self.assertNotIn('SYNTHETIC', json.dumps(public))
            self.assertEqual(json.loads((out / 'summary.json').read_text()), summary)
            with self.assertRaises(FileExistsError):
                cli.run_session(out, [], seconds=1, interval=1, max_attempts=1,
                                player_label='SYNTHETIC', backend_factory=lambda: m)

    def test_stop_during_acquisition_discards_pending_bytes(self):
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        m = Sparse()
        m.closed = False
        m.close = lambda: setattr(m, 'closed', True)
        with tempfile.TemporaryDirectory() as directory:
            stop = Path(directory) / 'STOP'
            original = m.read_memory
            def read(a, n):
                stop.touch()
                return original(a, n)
            m.read_memory = read
            out = Path(directory) / 'new'
            result = cli.run_session(out, [stop], seconds=1, interval=1, max_attempts=1,
                                     player_label='SYNTHETIC', backend_factory=lambda: m)
            self.assertEqual(result['persisted'], 0)
            self.assertEqual(result['discarded'], 1)
            self.assertEqual(result['stop_reason'], 'STOP')
            self.assertTrue(m.closed)
            self.assertEqual((out / 'PRIVATE/readsets.jsonl').read_text(), '')


class OfflineCommandTests(unittest.TestCase):
    def test_preflight_is_disk_only_and_does_not_print_label(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        self.assertTrue(hasattr(cli, 'main'), 'offline CLI missing')
        with tempfile.TemporaryDirectory() as directory:
            player = Path(directory) / 'identity.txt'
            player.write_text('PRIVATE_SYNTHETIC_LABEL', encoding='utf-8')
            stdout = io.StringIO()
            def forbidden():
                self.fail('preflight opened backend')
            with contextlib.redirect_stdout(stdout):
                result = cli.main(['--preflight', '--player-file', str(player)], backend_factory=forbidden)
            self.assertEqual(result, 0)
            self.assertNotIn('PRIVATE_SYNTHETIC_LABEL', stdout.getvalue())
            payload = json.loads(stdout.getvalue())
            self.assertFalse(payload['backend_opened'])
            self.assertTrue(payload['private_identity_loaded'])
            self.assertEqual(payload['limits'], {'seconds': .125, 'reads': 8192, 'bytes': 1048576})
            self.assertIn('hotstate/braxis.py', payload['source_hashes'])


    def test_replay_retains_missing_channels_without_invented_bytes(self):
        from hotstate import braxis_diagnostic as cli
        self.assertTrue(hasattr(cli, 'replay_channels'), 'exact offline replay missing')
        m = functions_memory()
        tx = braxis.WholeTx(m)
        result = braxis.run_channel(tx, braxis.decoders.named_type)
        row = {'kind': 'type', 'module_base': m.module_base, 'reads': tx.reads,
               'status': result['status'], 'result': {'reason': result['reason']}}
        replay = cli.replay_channels([row])
        self.assertEqual(replay['channels']['type']['reason'], 'named_type_absent')
        self.assertEqual(replay['channels']['type']['requests'], 1)
        self.assertEqual(replay['channels']['compiler']['status'], 'not_recorded')
        self.assertEqual(replay['channels']['frames.6003']['status'], 'not_recorded')
        self.assertFalse(replay['build_verified_by_replay'])
        self.assertIsNone(replay['objective'])
        import copy
        extra = copy.deepcopy(row)
        extra['reads'] *= 2
        with self.assertRaisesRegex(ValueError, 'unconsumed'):
            cli.replay_channels([extra])
        missing = copy.deepcopy(row)
        missing['reads'] = []
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            cli.replay_channels([missing])

    def test_live_cli_requires_operator_scope_before_open(self):
        import contextlib
        import io
        from hotstate import braxis_diagnostic as cli
        def forbidden():
            self.fail('unscoped live opened backend')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['--live'], backend_factory=forbidden), 2)


    def test_cli_replay_and_guarded_stop_are_executable(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            player = root / 'player.txt'
            player.write_text('SYNTHETIC', encoding='utf-8')
            stop = root / 'STOP'
            stop.touch()
            def forbidden():
                self.fail('STOP path opened backend')
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(['--live', '--operator-private-game', '--player-file', str(player),
                                 '--out', str(root / 'new'), '--stop', str(stop)], backend_factory=forbidden)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())['stop_reason'], 'STOP')
            m = functions_memory()
            tx = braxis.WholeTx(m)
            observed = braxis.run_channel(tx, braxis.decoders.named_type)
            path = root / 'trace.jsonl'
            path.write_text(json.dumps({'kind': 'type', 'module_base': m.module_base,
                                        'reads': tx.reads, 'status': observed['status'],
                                        'result': {'reason': observed['reason']}}) + '\n')
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(['--replay', str(path)], backend_factory=forbidden)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())['channels']['type']['reason'], 'named_type_absent')


class BoundaryTests(unittest.TestCase):
    def test_decode_finishing_after_budget_is_not_observed(self):
        now = [0.0]
        tx = braxis.WholeTx(Sparse(), clock=lambda: now[0])
        def slow(t):
            now[0] = .126
            return {'synthetic': 'metadata'}
        row = braxis.run_channel(tx, slow)
        self.assertEqual(row['status'], 'refused')
        self.assertEqual(row['reason'], 'whole_time')
        self.assertNotIn('result', row)

    def test_unknown_context_after_channels_cannot_qualify_holdout(self):
        from unittest.mock import patch
        self.assertTrue(hasattr(braxis, 'recheck_context'), 'final context bracket missing')
        m = functions_memory()
        with patch.object(braxis, 'verify_build', return_value={'build': 98348}), \
                patch.object(braxis, 'read_clock', return_value=12.0), \
                patch.object(braxis, 'read_context', return_value={'meta': {'map_id': 'BraxisHoldout'}}):
            result = braxis.collect(m, player_label='SYNTHETIC')
        self.assertEqual(result['target_map'], 'unknown')
        self.assertEqual(result['channels']['context_after']['status'], 'refused')
        self.assertIsNone(result['objective'])


class RecordedAttemptTests(unittest.TestCase):
    def test_new_whole_trace_can_replay_each_metadata_channel(self):
        from hotstate import braxis_diagnostic as cli
        self.assertTrue(hasattr(cli, 'replay_attempt'), 'product readset replay missing')
        m = functions_memory()
        tx = braxis.WholeTx(m)
        channels = braxis.diagnose(tx)
        raw = {'schema': 'braxis-causal-v1', 'module_base': m.module_base,
               'channels': channels, 'reads': tx.reads}
        replay = cli.replay_attempt(raw)
        self.assertEqual(replay['channels']['type']['reason'], 'named_type_absent')
        self.assertEqual(replay['channels']['compiler']['reason'], 'compiler_root_null')
        self.assertEqual(replay['channels']['frames.6003']['status'], 'observed')
        self.assertEqual(replay['channels']['frames.6007']['status'], 'observed')
        self.assertEqual(replay['channels']['frames.6122']['status'], 'observed')
        self.assertFalse(replay['build_verified_by_replay'])
        self.assertEqual(replay['perspective'], 'not_recorded')
        self.assertIsNone(replay['mission_clock'])
        self.assertNotIn('reads', replay)
        self.assertNotIn('record_hex', str(replay))


class AdditionalBoundaryTests(unittest.TestCase):
    def test_context_disk_failure_does_not_abort_independent_metadata(self):
        from unittest.mock import patch
        def unavailable(tx):
            raise OSError('PRIVATE_SYNTHETIC_PATH')
        tx = braxis.WholeTx(functions_memory())
        row = braxis.run_channel(tx, unavailable)
        self.assertEqual(row['status'], 'refused')
        self.assertEqual(row['reason'], 'diagnostic_dependency_unavailable')
        channels = braxis.diagnose(tx)
        self.assertEqual(channels['frames.6122']['status'], 'observed')
        self.assertNotIn('PRIVATE_SYNTHETIC', str(row))

    def test_previously_bound_identity_lost_stops_without_publishing_second_attempt(self):
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        m = Sparse()
        m.close = lambda: None
        now = [0.0]
        def sleep(amount):
            now[0] += amount
        calls = []
        def synthetic(backend, **kwargs):
            raw = braxis.collect(Sparse())
            raw['build']['status'] = 'observed'
            if not calls:
                raw['channels']['context'] = {'status': 'observed', 'result': {'meta': {'match_id': 'SYNTHETIC_ID_A'}}}
            calls.append(True)
            return raw
        with tempfile.TemporaryDirectory() as directory:
            result = cli.run_session(Path(directory) / 'new', [], seconds=10, interval=1,
                                     max_attempts=3, player_label='SYNTHETIC', backend_factory=lambda: m,
                                     clock=lambda: now[0], sleep=sleep, collect_attempt=synthetic)
            self.assertEqual(result['stop_reason'], 'context_lost')
            self.assertEqual(result['attempts'], 2)
            self.assertEqual(result['persisted'], 1)
            self.assertEqual(result['discarded'], 1)


class ReadAccountingTests(unittest.TestCase):
    def test_insufficient_remaining_bytes_is_unattempted_not_absent(self):
        tx = braxis.WholeTx(Sparse())
        tx.limit_bytes = 7
        row = braxis.run_channel(tx, lambda t: t.read(0x20000, 8))
        self.assertEqual(row['status'], 'not_attempted')
        self.assertEqual(row['reason'], 'whole_budget')
        self.assertEqual(row['requests'], 0)
        self.assertEqual(row['bytes_requested'], 0)

    def test_duplicate_and_failed_reads_are_not_deduplicated(self):
        m = Sparse()
        m.put(0x20000, b'12345678')
        tx = braxis.WholeTx(m)
        tx.read(0x20000, 8)
        tx.read(0x20000, 8)
        failed = braxis.run_channel(tx, lambda t: t.read(0x30000, 8))
        self.assertEqual(failed['status'], 'refused')
        self.assertEqual(failed['requests'], 1)
        self.assertEqual((len(tx.reads), tx.bytes), (3, 24))
        self.assertEqual(len(m.calls), 3)


class SessionLedgerTests(unittest.TestCase):
    def test_session_records_utc_and_separate_public_persistence(self):
        import datetime
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        m = Sparse()
        m.close = lambda: None
        with tempfile.TemporaryDirectory() as directory:
            summary = cli.run_session(Path(directory) / 'new', [], seconds=1, interval=1,
                                      max_attempts=1, player_label='SYNTHETIC', backend_factory=lambda: m)
            self.assertIn('started_at_utc', summary)
            self.assertIn('finished_at_utc', summary)
            for field in ('started_at_utc', 'finished_at_utc'):
                self.assertIsNotNone(datetime.datetime.fromisoformat(summary[field]).tzinfo)
            self.assertEqual(summary['public_persisted'], 1)
            self.assertEqual(summary['persisted'], 1)

    def test_backend_system_exit_is_not_reported_as_attempt_limit(self):
        import json
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        def missing():
            raise SystemExit('SYNTHETIC_PROCESS_MISSING')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'new'
            with self.assertRaises(SystemExit):
                cli.run_session(out, [], seconds=1, interval=1, max_attempts=1,
                                player_label='SYNTHETIC', backend_factory=missing)
            summary = json.loads((out / 'summary.json').read_text())
            self.assertEqual(summary['stop_reason'], 'diagnostic_error')
            self.assertEqual(summary['attempts'], 0)
            self.assertNotIn('SYNTHETIC_PROCESS_MISSING', str(summary))


class SyntheticCharacterization(unittest.TestCase):
    """Immediately-green safety characterization, NOT additional historical RED."""
    def test_invalid_addresses_never_reach_transport(self):
        m = Sparse()
        tx = braxis.WholeTx(m)
        for address, size in ((True, 8), (0, 8), (0x20000, False), (0x20000, 65537),
                              (0x800000000000, 8), (0x20000, -1)):
            with self.subTest(address=address, size=size), self.assertRaises(ValueError):
                tx.read(address, size)
        self.assertEqual(m.calls, [])

    def test_transport_os_error_is_costed(self):
        m = Sparse()
        def failed(a, n):
            raise OSError('PRIVATE_SYNTHETIC_ERROR')
        m.read_memory = failed
        tx = braxis.WholeTx(m)
        row = braxis.run_channel(tx, lambda t: t.read(0x20000, 8))
        self.assertEqual(row['reason'], 'transport_error')
        self.assertEqual((row['requests'], row['bytes_requested']), (1, 8))
        self.assertNotIn('PRIVATE_SYNTHETIC_ERROR', str(row))

    def test_missing_or_non_atomic_context_costs_no_fake_reads(self):
        for rolling, expected in ((False, 'private_player_label_missing'),
                                  (True, 'contexte_natif_capture_non_atomique')):
            m = Sparse()
            m.recorded_non_atomic = rolling
            tx = braxis.WholeTx(m)
            with self.assertRaisesRegex(ValueError, expected):
                braxis.read_context(tx, None)
            self.assertEqual(tx.reads, [])

    def test_frame_publication_mutation_is_refused(self):
        m = functions_memory()
        original = m.read_memory
        count = [0]
        def changing(a, n):
            if a == m.module_base + 0x3b8c5c8:
                count[0] += 1
                if count[0] == 2:
                    return (0x30000).to_bytes(8, 'little')
            return original(a, n)
        m.read_memory = changing
        row = braxis.run_channel(braxis.WholeTx(m), lambda t: braxis.frame(t, *braxis.FUNCTIONS[0]))
        self.assertEqual(row['reason'], 'frame_publication_changed')

    def test_replay_rejects_request_result_and_duplicate_forgery(self):
        import copy
        from hotstate import braxis_diagnostic as cli
        m = functions_memory()
        tx = braxis.WholeTx(m)
        row = braxis.run_channel(tx, braxis.decoders.named_type)
        original = {'kind': 'type', 'module_base': m.module_base, 'reads': tx.reads,
                    'status': row['status'], 'result': {'reason': row['reason']}}
        for change in ('request', 'result', 'duplicate'):
            rows = [copy.deepcopy(original)]
            if change == 'request':
                rows[0]['reads'][0]['size'] = 7
            elif change == 'result':
                rows[0]['result']['reason'] = 'SYNTHETIC_FORGERY'
            else:
                rows *= 2
            with self.subTest(change=change), self.assertRaises(ValueError):
                cli.replay_channels(rows)

    def test_public_schema_removes_arbitrary_private_refusal(self):
        from hotstate import braxis_diagnostic as cli
        raw = braxis.collect(Sparse())
        raw['channels']['type'] = {'status': 'refused', 'reason': 'PRIVATE_SYNTHETIC_LABEL',
                                   'requests': 1, 'result': {'address': 123, 'record_hex': 'secret'}}
        public = cli.public_attempt(raw)
        self.assertEqual(public['channels']['type']['reason'], 'diagnostic_refused')
        self.assertNotIn('PRIVATE_SYNTHETIC_LABEL', str(public))
        self.assertNotIn('record_hex', str(public))
        self.assertNotIn('module_base', str(public))

    def test_deadline_crossed_by_acquisition_discards_private_and_public_rows(self):
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        now = [0.0]
        m = Sparse()
        m.close = lambda: None
        def delayed(memory, **kwargs):
            result = braxis.collect(memory)
            now[0] = 2
            return result
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'new'
            result = cli.run_session(out, [], seconds=1, interval=1, max_attempts=1,
                                     player_label='SYNTHETIC', backend_factory=lambda: m,
                                     clock=lambda: now[0], collect_attempt=delayed)
            self.assertEqual(result['stop_reason'], 'duration')
            self.assertEqual((result['attempts'], result['persisted'], result['public_persisted']), (1, 0, 0))
            self.assertEqual(result['physical_requests'], 1)

    def test_changed_identity_discards_second_attempt(self):
        import tempfile
        from pathlib import Path
        from hotstate import braxis_diagnostic as cli
        now, count = [0.0], [0]
        m = Sparse()
        m.close = lambda: None
        def sleep(amount):
            now[0] += amount
        def synthetic(memory, **kwargs):
            raw = braxis.collect(Sparse())
            raw['build']['status'] = 'observed'
            count[0] += 1
            raw['channels']['context'] = {'status': 'observed', 'result': {'meta': {'match_id': f'SYNTHETIC_{count[0]}'}}}
            return raw
        with tempfile.TemporaryDirectory() as directory:
            result = cli.run_session(Path(directory) / 'new', [], seconds=10, interval=1, max_attempts=3,
                                     player_label='SYNTHETIC', backend_factory=lambda: m,
                                     clock=lambda: now[0], sleep=sleep, collect_attempt=synthetic)
            self.assertEqual(result['stop_reason'], 'match_changed')
            self.assertEqual((result['attempts'], result['persisted'], result['discarded']), (2, 1, 1))

    def test_session_numeric_bounds_refuse_before_backend(self):
        from hotstate import braxis_diagnostic as cli
        for seconds, interval, attempts in ((0, 1, 1), (121, 1, 1), (float('nan'), 1, 1),
                                            (1, 0, 1), (1, 1, 61), (True, 1, 1), (1, 1, True)):
            with self.subTest(seconds=seconds, interval=interval, attempts=attempts), self.assertRaises(ValueError):
                cli.run_session('UNUSED', [], seconds=seconds, interval=interval,
                                max_attempts=attempts, player_label='SYNTHETIC',
                                backend_factory=lambda: self.fail('invalid bounds opened backend'))


    def test_stop_during_private_flush_prevents_public_emission(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from hotstate import braxis_diagnostic as cli
        m = Sparse()
        m.close = lambda: None
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stop = root / 'STOP'
            original = Path.open
            class SlowPrivate:
                def __init__(self, stream):
                    self.stream = stream
                def __enter__(self):
                    self.stream.__enter__()
                    return self
                def __exit__(self, *args):
                    return self.stream.__exit__(*args)
                def write(self, text):
                    return self.stream.write(text)
                def flush(self):
                    self.stream.flush()
                    stop.touch()
            def opened(path, *args, **kwargs):
                stream = original(path, *args, **kwargs)
                return SlowPrivate(stream) if path.name == 'readsets.jsonl' else stream
            out = root / 'new'
            with patch.object(Path, 'open', opened):
                summary = cli.run_session(out, [stop], seconds=1, interval=1, max_attempts=1,
                                          player_label='SYNTHETIC', backend_factory=lambda: m)
            self.assertEqual(summary['stop_reason'], 'STOP')
            self.assertEqual((summary['persisted'], summary['public_persisted']), (1, 0))
            self.assertEqual((out / 'attempts.jsonl').read_text(), '')


class ScopedFunctionAbsenceTests(unittest.TestCase):
    def test_null_function_slot_is_scoped_absence_not_unattempted(self):
        m = functions_memory()
        m.u(0x20000 + 6122 * 8, 0)
        channels = braxis.diagnose(braxis.WholeTx(m))
        measured = braxis.measure(channels)
        self.assertIn('frames.6122', measured['scoped_absences'])
        self.assertNotIn('frames.6122', measured['unattempted'])
        self.assertIn('frames.6007', measured['observed_metadata'])
        self.assertFalse(measured['global_absence_proven'])


    def test_replay_does_not_hide_null_surplus_row(self):
        from hotstate import braxis_diagnostic as cli
        memory = cli.ExactMemory(0x10000000, [None])
        with self.assertRaisesRegex(ValueError, 'unconsumed'):
            memory.finish()


if __name__ == '__main__':
    unittest.main()
