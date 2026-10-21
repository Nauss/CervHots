"""Strictly synthetic private-label regressions; no backend or coach IO."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cerveau import diagnostic_session as session
from cerveau.player_identity import MAX_LABEL_BYTES, read_player_label


class LabelTests(unittest.TestCase):
    def test_utf8_and_bom_single_line_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'label.txt'
            for raw in (b'SYNTHETIC_ONLY', b'SYNTHETIC_ONLY\n',
                        b'\xef\xbb\xbfSYNTHETIC_ONLY\r\n',
                        ('\ufeff' + '\u00e9' * 64).encode('utf-8')):
                with self.subTest(format_bytes=len(raw)):
                    path.write_bytes(raw)
                    expected = '\u00e9' * 64 if b'SYNTHETIC' not in raw else 'SYNTHETIC_ONLY'
                    self.assertEqual(read_player_label(path), expected)

    def test_absent_empty_ambiguous_encoding_and_bounds_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'label.txt'
            with self.assertRaisesRegex(ValueError, '^private_identity_unavailable$'):
                read_player_label(path)
            invalid = [b'', b' ', b'A', b'A' * 65, b'A' * (MAX_LABEL_BYTES + 1),
                       b'\xffSYNTHETIC_ONLY', b'SYNTHETIC_ONLY\n\n',
                       b'SYNTHETIC_ONLY\r', b'SYNTHETIC_ONLY\nOTHER_SYNTHETIC',
                       b' SYNTHETIC_ONLY', b'SYNTHETIC_ONLY ', b'SYNTHETIC_ONLY\x00',
                       b'SYNTHETIC_ONLY\t', 'SYNTHETIC\u2028ONLY'.encode(),
                       'SYNTHETIC\ufeffONLY'.encode()]
            for raw in invalid:
                path.write_bytes(raw)
                with self.subTest(case=invalid.index(raw)):
                    with self.assertRaisesRegex(ValueError, '^private_identity_unavailable$'):
                        read_player_label(path)
            with self.assertRaises(ValueError):
                read_player_label(Path(tmp))

    def test_hostile_io_is_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'label.txt'
            path.write_bytes(b'SYNTHETIC_ONLY')
            for method in ('stat', 'open'):
                with patch.object(Path, method, side_effect=OSError('SYNTHETIC_ONLY')):
                    with self.assertRaises(ValueError) as error:
                        read_player_label(path)
                    self.assertEqual(str(error.exception), 'private_identity_unavailable')
                    self.assertTrue(error.exception.__suppress_context__)

    def test_read_is_bounded_even_if_file_grows_after_stat(self):
        from io import BytesIO
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'label.txt'
            path.write_bytes(b'SYNTHETIC_ONLY')
            stream = BytesIO(b'A' * (MAX_LABEL_BYTES + 100))
            with patch.object(Path, 'open', return_value=stream):
                with self.assertRaises(ValueError):
                    read_player_label(path)


class IdentityIntegrationTests(unittest.TestCase):
    def test_native_guard_still_refuses_absent_ambiguous_different_build_and_signature(self):
        from test_native_context import TypedContextMemory, NativeContextTests
        from hotstate.native import NativeUnavailable
        for case in ('absent', 'ambiguous', 'different', 'build', 'signature'):
            memory = TypedContextMemory()
            probe = memory.probe('OTHER_SYNTHETIC' if case == 'different' else 'OWNER_TEST')
            if case == 'absent':
                memory.native_string(memory.config + 8, '')
            elif case == 'ambiguous':
                memory.pack(memory.slots + 8 + 6 * 3880, 'BBB', 2, 1, 0)
            elif case == 'build':
                probe.profile = dict(probe.profile, build=1)
            elif case == 'signature':
                memory.put(memory.module_base + 0x777700, b'BAD')
            with self.subTest(case=case), NativeContextTests().options(memory):
                with self.assertRaises(NativeUnavailable):
                    probe.observe_native(memory, native_profile=memory.profile)
                self.assertEqual(probe.finish(), {})

    def test_stop_precedes_label_read_and_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stop = root / 'STOP'
            stop.touch()
            with patch.object(session, 'preflight', return_value={'ready': True}), \
                    patch.object(session, 'configured_coach'), \
                    patch.object(session, 'read_player_label') as read, \
                    patch.object(session, 'run_session') as run, redirect_stdout(StringIO()):
                code = session.main(['--live', '--player-file', str(root / 'absent'),
                                     '--output-dir', str(root / 'session'), '--stop-file', str(stop)])
            self.assertEqual(code, 0)
            read.assert_not_called()
            run.assert_not_called()

    def test_bom_label_is_passed_only_in_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'label.txt'
            path.write_bytes(b'\xef\xbb\xbfSYNTHETIC_ONLY\r\n')
            output = StringIO()
            with patch.object(session, 'preflight', return_value={'ready': True}), \
                    patch.object(session, 'configured_coach'), \
                    patch.object(session, 'run_session', return_value=0) as run, redirect_stdout(output):
                code = session.main(['--live', '--player-file', str(path),
                                     '--output-dir', str(root / 'session'),
                                     '--stop-file', str(root / 'STOP')])
            self.assertEqual(code, 0)
            self.assertEqual(run.call_args.kwargs['private_labels'], ('SYNTHETIC_ONLY',))
            self.assertNotIn('SYNTHETIC_ONLY', output.getvalue())
            self.assertEqual((root / 'session/events.jsonl').read_bytes(), b'')

    def test_multiline_label_rejected_before_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            label = root / 'player.txt'
            label.write_bytes(b'SYNTHETIC_ONLY\n\n')
            output = StringIO()
            with patch.object(session, 'preflight', return_value={'ready': True}), \
                    patch.object(session, 'configured_coach'), \
                    patch.object(session, 'run_session', return_value=0) as run, \
                    redirect_stdout(output):
                code = session.main(['--live', '--player-file', str(label),
                                     '--output-dir', str(root / 'session'),
                                     '--stop-file', str(root / 'STOP')])
            self.assertEqual(code, 1)
            run.assert_not_called()
            self.assertFalse((root / 'session').exists())
            self.assertNotIn('SYNTHETIC_ONLY', output.getvalue())


if __name__ == '__main__':
    unittest.main()
