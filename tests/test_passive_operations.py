"""SYNTHETIC operational artifacts only; never open a game backend."""
import json
from pathlib import Path
import tempfile
import unittest

from cerveau import passive_session as product


class LockOwnershipTests(unittest.TestCase):
    def test_substitution_immediately_before_unlink_is_never_deleted(self):
        """ROGER interleaving: a comparison cannot authorize a later unlink."""
        from unittest.mock import patch
        unlink = Path.unlink
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'passive-session.lock'
            def substitute_then_unlink(path, *args, **kwargs):
                if path == lock:
                    path.write_text('SYNTHETIC_FOREIGN_OWNER', encoding='ascii')
                return unlink(path, *args, **kwargs)
            with patch.object(Path, 'unlink', substitute_then_unlink), product.session_lock(lock):
                pass
            self.assertTrue(lock.is_file(), 'TOCTOU release deleted substituted claim')

    def test_claim_is_retained_even_after_clean_exit_and_blocks_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'passive-session.lock'
            with product.session_lock(lock):
                original = lock.read_bytes()
            self.assertTrue(lock.is_file())
            self.assertEqual(lock.read_bytes(), original)
            with self.assertRaises(FileExistsError), product.session_lock(lock):
                self.fail('retained claim was silently reused')

    def test_foreign_lock_content_is_not_removed_on_release(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'passive-session.lock'
            with product.session_lock(lock):
                lock.write_text('SYNTHETIC_FOREIGN_OWNER', encoding='ascii')
            self.assertTrue(lock.is_file(), 'release deleted a foreign ownership claim')
            self.assertEqual(lock.read_text(), 'SYNTHETIC_FOREIGN_OWNER')


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name).resolve() / 'SYNTHETIC_SESSION'

    def invoke(self, *extra):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        stream = StringIO()
        with redirect_stdout(stream), \
                patch.object(product, 'preflight', side_effect=AssertionError('no preflight')), \
                patch.object(product, 'NativeSource', side_effect=AssertionError('no backend')):
            code = product.main(['--status', '--output-dir', str(self.output), *extra])
        return code, json.loads(stream.getvalue())

    def test_absent_session_has_nonzero_code_without_creating_anything(self):
        code, row = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(row['state'], 'absent')
        self.assertFalse(self.output.exists())
        self.assertFalse(row['current_permission'])


    def test_real_status_subprocess_never_imports_reader_or_needs_dependencies(self):
        import subprocess
        import sys
        script = ('import sys; from cerveau.passive_session import main; '
                  'code=main(sys.argv[1:]); '
                  'assert "hotstate.reader" not in sys.modules; raise SystemExit(code)')
        result = subprocess.run([sys.executable, '-B', '-c', script, '--status',
                                 '--output-dir', str(self.output)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['state'], 'absent')
        self.assertEqual(result.stderr, '')

    def test_real_parser_rejects_relative_missing_or_conflicting_modes(self):
        import subprocess
        import sys
        for argv in (['--status'], ['--status', '--output-dir', 'relative'],
                     ['--status', '--live'], ['--preflight', '--live']):
            with self.subTest(argv=argv):
                result = subprocess.run([sys.executable, '-B', '-m', 'cerveau.passive_session', *argv],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertNotIn('Traceback', result.stderr)

    def test_missing_summary_with_no_lock_is_not_proof_of_stopped_reader(self):
        self.output.mkdir()
        code, row = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(row['state'], 'unknown')
        self.assertEqual(row['parent_lock'], 'absent')
        self.assertIsNone(row['reader_active'])

    def test_closed_summary_is_historical_not_current_or_live_ownership(self):
        self.output.mkdir()
        (self.output / 'summary.json').write_text(json.dumps({
            'event': 'summary', 'reason': 'stop_file', 'reader_active': False,
            'PRIVATE': 'PRIVATE_SECRET'}))
        code, row = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(row['state'], 'recorded_stopped')
        self.assertEqual(row['reason'], 'stop_file')
        self.assertIsNone(row['reader_active'])
        self.assertFalse(row['recorded_reader_active'])
        self.assertFalse(row['current_permission'])
        self.assertNotIn('PRIVATE', json.dumps(row))

    def test_unfinished_stale_or_foreign_claim_stays_unknown_and_untouched(self):
        self.output.mkdir()
        claim = self.output.parent / 'passive-session.lock'
        claim.write_text('SYNTHETIC_FOREIGN_OWNER')
        (self.output / 'status.json').write_text(json.dumps({
            'event': 'acquisition', 'collector_pid': 99999999,
            'timestamp_utc': '2000-01-01T00:00:00Z', 'PRIVATE': 'SECRET'}))
        code, row = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(row['state'], 'unknown')
        self.assertEqual(row['parent_lock'], 'present_owner_unverified')
        self.assertEqual(row['last_event'], 'acquisition')
        self.assertIsNone(row['reader_active'])
        self.assertEqual(claim.read_text(), 'SYNTHETIC_FOREIGN_OWNER')
        self.assertNotIn('SECRET', json.dumps(row))


    def test_malformed_oversized_or_failed_close_summary_cannot_claim_stopped(self):
        self.output.mkdir()
        path = self.output / 'summary.json'
        for content in ('{', 'null', '[]', '[' * 30000 + '0' + ']' * 30000, 'x' * 65537,
                        json.dumps({'event': 'summary', 'reason': 'source_close_failed',
                                    'reader_active': None}),
                        json.dumps({'event': 'summary', 'reason': 'PRIVATE',
                                    'reader_active': False}),
                        json.dumps({'event': 'summary', 'reason': 'stop_file',
                                    'reader_active': 0})):
            with self.subTest(content=content[:30]):
                path.write_text(content)
                code, row = self.invoke()
                self.assertEqual(code, 1)
                self.assertEqual(row['state'], 'unknown')
                self.assertIsNone(row['recorded_reader_active'])
                self.assertNotIn('PRIVATE', json.dumps(row))

    def test_old_closed_session_does_not_attest_foreign_parent_lock(self):
        self.output.mkdir()
        claim = self.output.parent / 'passive-session.lock'
        claim.write_text('SYNTHETIC_NEW_SESSION_OWNER')
        (self.output / 'summary.json').write_text(json.dumps({
            'event': 'summary', 'reason': 'session_changed', 'reader_active': False}))
        code, row = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(row['state'], 'recorded_stopped')
        self.assertEqual(row['parent_lock'], 'present_owner_unverified')
        self.assertIsNone(row['reader_active'])
        self.assertTrue(claim.is_file())

    def test_status_io_denial_is_unknown_without_exception_details(self):
        from unittest.mock import patch
        with patch.object(Path, 'stat', side_effect=PermissionError('PRIVATE')):
            code, row = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(row['state'], 'unknown')
        self.assertEqual(row['reason'], 'disk_unavailable')
        self.assertNotIn('PRIVATE', json.dumps(row))


class RestartTests(unittest.TestCase):
    def test_targeted_stop_then_new_session_does_not_inherit_stop_or_binding(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from test_passive_session import SyntheticSource, synthetic_state, Clock
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            player = root / 'private.txt'
            player.write_text('SYNTHETIC_IDENTITY')
            original = product.run_session
            tokens = []
            sources = []
            for name, match in (('session-A', 'a'), ('session-B', 'b')):
                output, stop = root / name / 'session', root / (name + '.STOP')
                source = SyntheticSource([synthetic_state(match)])
                sources.append(source)
                clock = Clock()
                def run(factory, stopped, emit, **kwargs):
                    def persist(row):
                        emit(row)
                        if row['event'] == 'observation':
                            stop.touch()
                    return original(factory, stopped, persist, clock=clock, sleep=clock.sleep, **kwargs)
                argv = ['--live', '--player-file', str(player), '--output-dir', str(output),
                        '--stop-file', str(stop), '--max-seconds', '10']
                with patch.object(product, 'NativeSource', return_value=source), \
                        patch.object(product, 'run_session', side_effect=run), redirect_stdout(StringIO()):
                    self.assertEqual(product.main(argv), 0)
                summary = json.loads((output / 'summary.json').read_text())
                self.assertEqual(summary['reason'], 'stop_file')
                self.assertEqual(summary['accepted'], 1)
                self.assertTrue(stop.exists())
                rows = [json.loads(line) for line in (output / 'events.jsonl').read_text().splitlines()]
                tokens.append(next(r['comparison']['session_token'] for r in rows if r['event'] == 'observation'))
                # An old STOP must never be silently consumed/rearmed.
                with patch.object(product, 'NativeSource', side_effect=AssertionError('no backend')), \
                        redirect_stdout(StringIO()):
                    self.assertEqual(product.main(argv), 0)
                self.assertTrue(stop.exists())
            self.assertNotEqual(tokens[0], tokens[1])
            self.assertTrue(all(source.closed and source.calls == 1 for source in sources))
            for name in ('session-A', 'session-B'):
                self.assertTrue((root / name / 'passive-session.lock').is_file())

    def test_stale_claim_blocks_new_output_without_identity_or_backend(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            claim = root / 'passive-session.lock'
            claim.write_text('SYNTHETIC_STALE_OWNER')
            output = root / 'NEW'
            with patch('cerveau.player_identity.read_player_label', side_effect=AssertionError('no identity')), \
                    patch.object(product, 'NativeSource', side_effect=AssertionError('no backend')), \
                    redirect_stdout(StringIO()):
                code = product.main(['--live', '--player-file', str(root / 'private.txt'),
                                     '--output-dir', str(output), '--stop-file', str(root / 'NEW.STOP')])
            self.assertEqual(code, 1)
            self.assertFalse(output.exists())
            self.assertEqual(claim.read_text(), 'SYNTHETIC_STALE_OWNER')


if __name__ == '__main__':
    unittest.main()
