"""Offline product diagnostic: synthetic records, never native qualification."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import hashlib
import struct
import subprocess
import sys
import zipfile
import unittest
from unittest.mock import patch

from cerveau import passive_session as product


def record(sequence, event, cycle=1, **fields):
    return dict(schema_version=1, sequence=sequence, event=event, cycle=cycle, **fields)


class DiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.session = self.root / 'session'
        self.session.mkdir()
        self.journal = self.session / 'events.jsonl'

    def write_rows(self, rows):
        self.journal.write_bytes(b''.join((json.dumps(r) + '\n').encode() for r in rows))

    def invoke(self, *extra, name='report'):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error), \
                patch.object(product, 'preflight', side_effect=AssertionError('offline only')), \
                patch.object(product, 'NativeSource', side_effect=AssertionError('no native source')):
            code = product.main(['--diagnose', '--journal', str(self.journal),
                                 '--report-dir', str(self.root / name), *extra])
        return code, json.loads(output.getvalue()), error.getvalue()

    def test_real_entrypoint_counts_refusal_once_and_never_claims_comparison(self):
        self.write_rows([
            record(1, 'acquisition', outcome='refused', refusal={'code': 'lecture_native_dechiree'}),
            record(2, 'refusal', code='lecture_native_dechiree'),
            record(3, 'acquisition', 2, outcome='accepted'),
            record(4, 'observation', 2, available_fields=['heroes']),
            record(5, 'boundary', 2, reason='stop_file')])
        before = self.journal.read_bytes()
        code, result, readable = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(result['counts']['acquisitions'], 2)
        self.assertEqual(result['counts']['observations'], 1)
        self.assertEqual(result['counts']['refused_cycles'], 1)
        self.assertEqual(result['counts']['refusal_events'], 1)
        self.assertEqual(result['counts']['boundaries'], 1)
        self.assertEqual(result['stop']['recorded_reason'], 'stop_file')
        self.assertIsNone(result['stop']['reader_active'])
        self.assertEqual(result['evidence']['status'], 'non_comparable')
        self.assertFalse(result['hud_validated'])
        self.assertFalse(result['current_permission'])
        self.assertEqual(result['spatial_comparisons'], 0)
        self.assertEqual(result['normalized_fields']['heroes'], 1)
        self.assertIn('NON COMPARABLE', readable)
        self.assertEqual(json.loads((self.root/'report/diagnosis.json').read_text()), result)
        self.assertEqual((self.root/'report/SUMMARY.txt').read_text(), readable)
        self.assertEqual(self.journal.read_bytes(), before)

    def test_truncated_suffix_reports_prefix_only_and_unknown_total(self):
        self.write_rows([record(1, 'observation')])
        with self.journal.open('ab') as stream:
            stream.write(b'{"event":"observation"')
        code, result, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(result['journal']['state'], 'truncated')
        self.assertEqual(result['counts']['observations'], 1)
        self.assertEqual(result['counts_scope'], 'valid_prefix_only')
        self.assertIsNone(result['total_acquisitions'])

    def test_complete_json_without_newline_is_not_a_closed_record(self):
        self.journal.write_bytes(json.dumps(record(1, 'observation')).encode())
        code, result, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(result['journal']['state'], 'truncated')
        self.assertEqual(result['counts']['observations'], 0)

    def test_invalid_duplicate_nonfinite_sequence_and_schema_are_refused(self):
        cases = [b'null\n', b'[]\n', b'{"event":"observation","event":"boundary"}\n',
                 b'{"value":NaN}\n', b'{"value":Infinity}\n',
                 (json.dumps(record(2, 'observation'))+'\n').encode(),
                 (json.dumps(dict(record(1, 'observation'), schema_version=2))+'\n').encode()]
        for i, data in enumerate(cases):
            with self.subTest(i=i):
                self.journal.write_bytes(data)
                code, result, _ = self.invoke(name=f'bad-{i}')
                self.assertEqual(code, 1)
                self.assertEqual(result['journal']['state'], 'invalid')
                self.assertIsNone(result['total_acquisitions'])

    def test_empty_missing_and_bounded_read_have_no_known_totals(self):
        self.journal.write_bytes(b'')
        code, result, _ = self.invoke(name='empty')
        self.assertEqual(code, 1)
        self.assertEqual(result['journal']['state'], 'empty')
        self.assertIsNone(result['total_acquisitions'])
        self.journal.unlink()
        code, result, _ = self.invoke(name='absent')
        self.assertEqual(code, 1)
        self.assertEqual(result['journal']['state'], 'unavailable')
        self.journal.write_bytes(b'x' * 65537 + b'\n')
        code, result, _ = self.invoke(name='large')
        self.assertEqual(code, 1)
        self.assertEqual(result['journal']['state'], 'limit_exceeded')

    def test_unknown_codes_extra_fields_and_open_failures_are_not_exported_or_zero_cost(self):
        secret = 'PRIVATE_NAME_AND_SECRET'
        self.write_rows([record(1, 'source_error', code=secret),
                         record(2, 'refusal', code=secret),
                         record(3, 'observation', 2, available_fields=['heroes', secret],
                                objective={'status': secret}, secret=secret)])
        code, result, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result['refusal_codes'], {'unknown_refusal': 1})
        self.assertEqual(result['counts']['source_errors'], 1)
        self.assertEqual(result['counts']['unmeasured_cycles'], 2)
        self.assertEqual(result['families']['objective']['unknown'], 1)
        self.assertEqual(result['families']['positions']['unknown'], 1)
        self.assertEqual(result['unknown_fields'], 1)
        self.assertIsNone(result['costs']['reads']['maximum'])
        self.assertEqual(result['costs']['reads']['missing'], 0)
        self.assertEqual(result['stop']['recorded_reason'], 'unknown')

    def test_duplicate_acquisition_is_not_a_valid_complete_journal(self):
        self.write_rows([record(1, 'acquisition', outcome='accepted'),
                         record(2, 'acquisition', outcome='refused')])
        code, result, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(result['journal']['state'], 'invalid')

    def test_existing_output_and_output_inside_session_are_refused_without_changes(self):
        self.write_rows([record(1, 'boundary', reason='stop_file')])
        output = self.root / 'report'
        output.mkdir()
        (output/'diagnosis.json').write_text('unchanged')
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = product.main(['--diagnose', '--journal', str(self.journal),
                                 '--report-dir', str(output)])
            self.assertEqual(code, 1)
            code = product.main(['--diagnose', '--journal', str(self.journal),
                                 '--report-dir', str(self.session/'new')])
            self.assertEqual(code, 1)
        self.assertEqual((output/'diagnosis.json').read_text(), 'unchanged')
        self.assertFalse((self.session/'new').exists())

    def test_metadata_availability_and_optional_refusals_are_distinct_from_normalization(self):
        comparison = dict(session_token='a'*32, map_id='Volskaya', perspective='native_player',
                          clock_basis='host_monotonic', read_started_s=100., read_finished_s=100.02)
        self.write_rows([
            record(1, 'acquisition', outcome='accepted', reads=12, bytes_requested=48,
                   elapsed_ms=25, optional_refusals={'objective': {'code': 'native_channel_unqualified'}}),
            record(2, 'observation', available_fields=['heroes', 'positions'],
                   mission_t_s=30., elapsed_s=2., timestamp_utc='2026-10-25T03:00:00+00:00',
                   session='session_'+'1'*12, map='map_'+'2'*12, comparison=comparison,
                   positions=dict(status='normalized', source='native_player', age_s=.03,
                                  read_window_s=.02, source_mission_t_s=30.)),
            record(3, 'observation', 2, available_fields=['heroes']),
            record(4, 'boundary', 2, reason='stop_file')])
        _, result, text = self.invoke()
        self.assertEqual(result['metadata']['host_read_bounds'], {'available': 1, 'missing_or_invalid': 1})
        self.assertEqual(result['metadata']['mission_clock'], {'available': 1, 'missing_or_invalid': 1})
        self.assertEqual(result['metadata']['utc_clock'], {'available': 1, 'missing_or_invalid': 1})
        self.assertEqual(result['metadata']['identity_binding'], {'available': 1, 'missing_or_invalid': 1})
        self.assertEqual(result['identity']['state'], 'incomplete_or_mixed')
        self.assertEqual(result['family_provenance']['positions']['original_age_window'],
                         {'available': 1, 'missing_or_invalid': 1})
        self.assertEqual(result['families']['positions'], {'normalized': 1, 'unknown': 1})
        self.assertEqual(result['optional_refusals']['objective'], {'unknown_refusal': 1})
        self.assertEqual(result['costs']['reads']['maximum'], 12)
        self.assertIn('Familles', text)
        self.assertIn('host_read_bounds', text)
        self.assertEqual(result['evidence']['missing_requirements'],
                         ['independent_visual_identity', 'calibrated_spatial_reference',
                          'independent_stable_time_interval'])

    def test_malformed_fields_never_crash_or_leak_and_missing_cost_stays_null(self):
        self.write_rows([record(1, 'acquisition', outcome=['PRIVATE'], optional_refusals=None,
                                stage={}, refusal=[], reads='PRIVATE'),
                         record(2, 'observation', comparison=[], available_fields=None,
                                objective={'status': [], 'source': 'PRIVATE'}),
                         record(3, 'PRIVATE')])
        code, result, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertEqual(result['counts']['unknown_events'], 1)
        self.assertEqual(result['costs']['reads'], {'maximum': None, 'missing': 1})

    def test_current_receipts_not_reissued_even_for_complete_single_binding(self):
        comparison = dict(session_token='a'*32, map_id='Volskaya', perspective='native_player',
                          clock_basis='host_monotonic', read_started_s=1., read_finished_s=1.1)
        self.write_rows([record(1, 'observation', session='session_'+'a'*12, map='map_'+'b'*12,
                                comparison=comparison)])
        _, result, _ = self.invoke()
        self.assertEqual(result['identity']['state'], 'single_recorded_binding')
        self.assertEqual(result['evidence']['status'], 'non_comparable')
        self.assertFalse(result['current_permission'])

    def bmp(self, black=False, masked=False):
        width = height = 64
        pixels = b''.join(bytes((0, 0, 0) if black or (masked is True and x < 32)
                          or (masked == 'offset' and 24 <= x < 48 and 24 <= y < 48) else (40, 100, 200))
                          for y in range(height) for x in range(width))
        return (struct.pack('<2sIHHI', b'BM', 54+len(pixels), 0, 0, 54)
                + struct.pack('<IiiHHIIiiII', 40, width, height, 1, 24, 0, len(pixels), 0, 0, 0, 0)
                + pixels)

    def clip(self, path, *, black=False, masked=False, partial=False, wrong_hash=False):
        frame = self.bmp(black=black, masked=masked)
        index = dict(complete=not partial, clock_basis='host_monotonic', frames=[
            dict(member='frame-00000.bmp', started_s=10., finished_s=10.1,
                 sha256='0'*64 if wrong_hash else hashlib.sha256(frame).hexdigest())])
        with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_STORED) as z:
            z.writestr('frame-00000.bmp', frame)
            z.writestr('index.json', json.dumps(index))

    def test_explicit_pixels_missing_black_masked_and_nonblack_never_give_spatial_pass(self):
        self.write_rows([record(1, 'boundary', reason='stop_file')])
        cases = [('missing.bmp', None, 'unavailable'),
                 ('black.bmp', self.bmp(black=True), 'black_or_masked_suspected'),
                 ('masked.bmp', self.bmp(masked=True), 'black_or_masked_suspected'),
                 ('offset.bmp', self.bmp(masked='offset'), 'black_or_masked_suspected'),
                 ('partial.bmp.partial', self.bmp(), 'partial_reference'),
                 ('color.bmp', self.bmp(), 'pixels_decoded_not_attested'),
                 ('broken.bmp', self.bmp()[:-1], 'invalid_or_unsupported')]
        for i, (name, data, expected) in enumerate(cases):
            with self.subTest(name=name):
                p = self.root/name
                if data is not None:
                    p.write_bytes(data)
                code, result, text = self.invoke('--visual-reference', str(p), name=f'visual-{i}')
                self.assertEqual(code, 0)
                reference = result['evidence']['references'][0]
                self.assertEqual(reference['state'], expected)
                self.assertEqual(reference['stable_time_reference'], 'not_supplied')
                self.assertEqual(result['spatial_comparisons'], 0)
                self.assertFalse(result['hud_validated'])
                self.assertIn('non_comparable', text)

    def test_zip_integrity_temporal_bounds_partial_and_hash_are_only_diagnostics(self):
        self.write_rows([record(1, 'boundary', reason='stop_file')])
        for i, (options, expected) in enumerate([
                ({}, 'pixels_decoded_not_attested'),
                ({'partial': True}, 'partial_reference'),
                ({'wrong_hash': True}, 'invalid_or_unsupported'),
                ({'masked': True}, 'black_or_masked_suspected')]):
            p = self.root/f'clip-{i}.zip'
            self.clip(p, **options)
            before = p.read_bytes()
            _, result, _ = self.invoke('--visual-reference', str(p), name=f'clip-report-{i}')
            ref = result['evidence']['references'][0]
            self.assertEqual(ref['state'], expected)
            self.assertEqual(ref['spatial_status'], 'non_comparable')
            self.assertEqual(p.read_bytes(), before)

    def test_zip_slip_compression_and_member_size_are_refused_without_extracting(self):
        self.write_rows([record(1, 'boundary', reason='stop_file')])
        for i, (name, data, compression) in enumerate([
                ('../outside.bmp', b'private', zipfile.ZIP_STORED),
                ('frame-00000.bmp', b'0' * 100, zipfile.ZIP_DEFLATED),
                ('frame-00000.bmp', b'0' * 524289, zipfile.ZIP_STORED)]):
            p = self.root/f'unsafe-{i}.zip'
            with zipfile.ZipFile(p, 'x', compression=compression) as z:
                z.writestr(name, data)
            _, result, _ = self.invoke('--visual-reference', str(p), name=f'unsafe-report-{i}')
            self.assertEqual(result['evidence']['references'][0]['state'], 'invalid_or_unsupported')
        self.assertFalse((self.root/'outside.bmp').exists())

    def test_diagnostic_arguments_cannot_be_ignored_by_live_or_default_mode(self):
        cases = [[], ['--live'], ['--status'], ['--preflight']]
        with contextlib.redirect_stderr(io.StringIO()):
            for mode in cases:
                with self.subTest(mode=mode), self.assertRaises(SystemExit) as exc:
                    product.main([*mode, '--journal', str(self.journal)])
                self.assertEqual(exc.exception.code, 2)
            for extra in (['--player-file', str(self.root/'private')],
                          ['--output-dir', str(self.session)],
                          ['--stop-file', str(self.root/'STOP')]):
                with self.assertRaises(SystemExit) as exc:
                    product.main(['--diagnose', '--journal', str(self.journal),
                                  '--report-dir', str(self.root/'report'), *extra])
                self.assertEqual(exc.exception.code, 2)

    def test_partial_filename_and_missing_temporal_frame_reference_remain_explicit(self):
        self.write_rows([record(1, 'boundary', reason='stop_file')])
        p = self.root/'clip.zip.partial'
        self.clip(p)
        _, result, _ = self.invoke('--visual-reference', str(p))
        self.assertEqual(result['evidence']['references'][0]['state'], 'partial_reference')

    def test_archive_directory_entry_count_is_bounded_before_zipfile_parsing(self):
        self.write_rows([record(1, 'boundary', reason='stop_file')])
        p = self.root/'many.zip'
        with zipfile.ZipFile(p, 'x') as z:
            for i in range(402):
                z.writestr(f'frame-{i:05d}.bmp', b'')
        with patch('cerveau.session_diagnosis.zipfile.ZipFile',
                   side_effect=AssertionError('must reject before central directory allocation')):
            _, result, _ = self.invoke('--visual-reference', str(p))
        self.assertEqual(result['evidence']['references'][0]['state'], 'invalid_or_unsupported')

    def test_huge_integer_in_cost_is_invalid_not_an_unhandled_overflow(self):
        self.write_rows([record(1, 'acquisition', outcome='accepted', reads=10**1000)])
        code, result, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(result['journal']['state'], 'invalid')

    def test_real_subprocess_needs_only_stdlib_and_never_constructs_coach_or_imports_backend(self):
        self.write_rows([record(1, 'boundary', reason='stop_file')])
        script = self.root/'offline.py'
        checkout = Path(__file__).resolve().parents[1]
        script.write_text(
            'import builtins, sys\n'
            f'sys.path.insert(0, {str(checkout)!r})\n'
            'original = builtins.__import__\n'
            'def guarded(name, *args, **kwargs):\n'
            '    if name in ("hotstate.reader", "hotstate.live", "hotstate.native_context",\n'
            '                "cerveau.runner", "mpyq", "heroprotocol"):\n'
            '        raise AssertionError("forbidden dependency")\n'
            '    return original(name, *args, **kwargs)\n'
            'builtins.__import__ = guarded\n'
            '# Existing cerveau.__init__ imports brain: import is not construction/IO.\n'
            'import cerveau, grocoapi\n'
            'def forbidden(*args, **kwargs):\n'
            '    raise AssertionError("forbidden constructor")\n'
            'cerveau.Coach.__init__ = forbidden\n'
            'grocoapi.GrocoClient.__init__ = forbidden\n'
            'from cerveau.passive_session import main\n'
            'raise SystemExit(main())\n', encoding='utf-8')
        result = subprocess.run([sys.executable, '-I', '-B', str(script), '--diagnose',
                                 '--journal', str(self.journal), '--report-dir', str(self.root/'subprocess')],
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['counts']['boundaries'], 1)

    def test_missing_frame_times_do_not_accept_declared_hud_or_complete_flags(self):
        self.write_rows([record(1, 'boundary', reason='stop_file')])
        p, frame = self.root/'declarative.zip', self.bmp()
        with zipfile.ZipFile(p, 'x') as z:
            z.writestr('frame-00000.bmp', frame)
            z.writestr('index.json', json.dumps(dict(complete=True, hud_validated=True,
                same_player=True, frames=[dict(member='frame-00000.bmp',
                sha256=hashlib.sha256(frame).hexdigest())])))
        _, result, _ = self.invoke('--visual-reference', str(p))
        ref = result['evidence']['references'][0]
        self.assertEqual(ref['frame_time_bounds'], 'missing_or_invalid')
        self.assertEqual(ref['stable_time_reference'], 'not_supplied')
        self.assertEqual(ref['independent_identity'], 'unverified')
        self.assertFalse(result['hud_validated'])

    def test_global_file_record_and_reference_limits_are_enforced(self):
        with self.journal.open('wb') as stream:
            stream.seek(4 * 2**20)
            stream.write(b'x')
        code, result, _ = self.invoke(name='file-limit')
        self.assertEqual(code, 1)
        self.assertEqual(result['journal']['state'], 'limit_exceeded')
        self.write_rows([record(i, 'boundary') for i in range(1, 10002)])
        code, result, _ = self.invoke(name='record-limit')
        self.assertEqual(code, 1)
        self.assertEqual(result['journal']['state'], 'limit_exceeded')
        self.assertEqual(result['counts']['boundaries'], 10000)
        self.write_rows([record(1, 'boundary')])
        p = self.root/'oversized.zip'
        with p.open('wb') as stream:
            stream.seek(17 * 2**20)
            stream.write(b'x')
        _, result, _ = self.invoke('--visual-reference', str(p), name='reference-limit')
        ref = result['evidence']['references'][0]
        self.assertEqual(ref['state'], 'invalid_or_unsupported')
        self.assertIsNone(ref['frames_inspected'])

    def test_untrusted_directory_count_cannot_hide_an_oversized_directory(self):
        from cerveau.session_diagnosis import visual_reference
        p = self.root/'forged.zip'
        with zipfile.ZipFile(p, 'x') as z:
            for i in range(1500):
                z.writestr(f'frame-{i:05d}.bmp', b'')
        data = bytearray(p.read_bytes())
        offset = data.rfind(b'PK\x05\x06')
        struct.pack_into('<HH', data, offset+8, 2, 2)
        p.write_bytes(data)
        with patch('cerveau.session_diagnosis.zipfile.ZipFile',
                   side_effect=AssertionError('directory must be bounded before parsing')):
            result = visual_reference(p)
        self.assertEqual(result['state'], 'invalid_or_unsupported')
