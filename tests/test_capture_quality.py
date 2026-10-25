"""Fixtures exclusivement SYNTHETIC : aucune preuve HUD ou native."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest


def bmp(width=64, height=32, dark=False, mask=False):
    stride = (width * 3 + 3) // 4 * 4
    rows = []
    for y in reversed(range(height)):
        row = bytearray()
        for x in range(width):
            black = dark or (mask and 7 <= x < 39 and 5 <= y < 25)
            row.extend(b'\0\0\0' if black else b'\x70\x90\xc0')
        rows.append(bytes(row) + b'\0' * (stride - width * 3))
    data = b''.join(rows)
    return b'BM' + struct.pack('<IHHI', len(data)+54, 0, 0, 54) + struct.pack(
        '<IiiHHIIiiII', 40, width, height, 1, 24, 0, len(data), 0, 0, 0, 0) + data


class CaptureQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def image(self, name='synthetic.bmp', **kw):
        p = self.root / name
        p.write_bytes(bmp(**kw))
        return p

    def test_clear_pixels_missing_manual_reference_fail_closed(self):
        from cerveau import capture_quality as q
        result = q.diagnose([self.image()], roi=(0, 0, 64, 32))
        self.assertFalse(result['current_permission'])
        self.assertFalse(result['hud_validated'])
        self.assertEqual(result['spatial_comparisons'], 0)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['manual_reference']['state'], 'missing')
        self.assertIn('manual_reference_missing', result['reasons'])
        self.assertEqual(result['frames'][0]['near_black_fraction'], 0)
        self.assertFalse(result['comparable'])

    def test_black_and_offset_mask_are_quantified_but_not_claimed_as_proven_defect(self):
        from cerveau import capture_quality as q
        for options, fraction, rectangle in [({'dark': True}, 1, 1),
                ({'mask': True}, 640/2048, 640/2048), ({}, 0, 0)]:
            with self.subTest(options=options):
                p = self.image(**options)
                result = q.diagnose([p], roi=(0, 0, 64, 32))
                frame = result['frames'][0]
                self.assertAlmostEqual(frame['near_black_fraction'], fraction)
                self.assertAlmostEqual(frame['largest_near_black_rectangle_fraction'], rectangle)
                self.assertEqual(frame['state'], 'black_or_mask_suspected' if fraction else 'pixels_clear_not_attested')
                self.assertEqual(result['status'], 'unknown')
                self.assertFalse(result['comparable'])

    def test_invalid_pixels_and_roi_are_structured_refusals(self):
        from cerveau import capture_quality as q
        p = self.image()
        for roi in [(60, 0, 8, 32), (-1, 0, 4, 4), (0, 0, 0, 1)]:
            result = q.diagnose([p], roi=roi)
            self.assertEqual(result['status'], 'refused')
            self.assertIn('roi_out_of_bounds', result['reasons'])
        p.write_bytes(bmp()[:-1])
        result = q.diagnose([p], roi=(0, 0, 64, 32))
        self.assertIn('image_incomplete', result['reasons'])
        self.assertEqual(result['status'], 'refused')
        self.assertEqual(result['counts']['decoded'], 0)

    def clip(self, *, entries=None, extra=None, compressed=False, complete=True):
        import zipfile
        p = self.root / 'synthetic.zip'
        frames = entries if entries is not None else [dict(member=f'frame-{i:04d}.bmp',
            sha256=hashlib.sha256(bmp()).hexdigest(), started_s=1+i*.1,
            finished_s=1.01+i*.1) for i in range(3)]
        with zipfile.ZipFile(p, 'w', compression=zipfile.ZIP_DEFLATED if compressed else zipfile.ZIP_STORED) as z:
            for name in dict.fromkeys(e['member'] for e in frames):
                z.writestr(name, bmp())
            z.writestr('index.json', json.dumps(dict(complete=complete, frames=frames,
                clock_basis='host_monotonic', session_token='a'*32)))
            for name, data in (extra or {}).items():
                z.writestr(name, data)
        return p

    def test_archive_hash_crc_and_time_order_checked_without_extracting(self):
        from cerveau import capture_quality as q
        p = self.clip()
        result = q.diagnose([p], roi=(0, 0, 64, 32))
        self.assertEqual(result['counts']['decoded'], 3)
        self.assertEqual(result['inputs'][0]['timing']['state'], 'recorded_ordered')
        self.assertAlmostEqual(result['inputs'][0]['timing']['max_gap_s'], .09)
        self.assertFalse(result['comparable'])
        bad = [dict(member='frame-0000.bmp', sha256='0'*64)]
        result = q.diagnose([self.clip(entries=bad)], roi=(0, 0, 64, 32))
        self.assertEqual(result['status'], 'refused')
        self.assertIn('frame_hash', result['reasons'])

    def test_absent_reversed_and_discontinuous_time_are_not_qualified(self):
        from cerveau import capture_quality as q
        for times, expected in [([(None, None), (None, None)], 'missing'),
                ([(2, 2.01), (1, 1.01)], 'invalid'),
                ([(1, 1.01), (5, 5.01)], 'discontinuous')]:
            entries = [dict(member=f'frame-{i:04d}.bmp', sha256=hashlib.sha256(bmp()).hexdigest(),
                started_s=a, finished_s=b) for i, (a, b) in enumerate(times)]
            result = q.diagnose([self.clip(entries=entries)], roi=(0, 0, 64, 32))
            self.assertEqual(result['inputs'][0]['timing']['state'], expected)
            self.assertNotEqual(result['status'], 'diagnostic_only')
            self.assertFalse(result['comparable'])

    def test_zip_traversal_compression_oversize_and_directory_bomb_refused(self):
        from cerveau import capture_quality as q
        from unittest.mock import patch
        import zipfile
        for options in [dict(extra={'../outside': b'private'}), dict(compressed=True),
                        dict(extra={'segment-0000.jsonl': b'x'*(524289)})]:
            result = q.diagnose([self.clip(**options)], roi=(0, 0, 64, 32))
            self.assertEqual(result['status'], 'refused')
            self.assertIn('archive_limits', result['reasons'])
        self.assertFalse((self.root.parent/'outside').exists())
        p = self.root/'bomb.zip'
        with zipfile.ZipFile(p, 'w') as z:
            for i in range(1000):
                z.writestr(str(i), b'')
        with patch.object(q.zipfile, 'ZipFile', side_effect=AssertionError('preallocation guard')):
            result = q.diagnose([p], roi=(0, 0, 64, 32))
        self.assertEqual(result['status'], 'refused')
        self.assertIn('archive_directory', result['reasons'])
        p = self.root/'large.zip'
        with p.open('wb') as f:
            f.seek(17*2**20)
            f.write(b'x')
        self.assertIn('input_limit', q.diagnose([p], roi=(0, 0, 64, 32))['reasons'])

    def manual(self, capture, **changes):
        value = dict(schema_version=1, source='independent_manual',
            capture_sha256=[hashlib.sha256(capture.read_bytes()).hexdigest()], roi=[0, 0, 64, 32],
            identity=dict(session_token='a'*32, map_id='SYNTHETIC', perspective='player', evidence_sha256='b'*64),
            landmarks=dict(coordinate_system='roi_pixels', points=[[1, 1], [62, 30]], evidence_sha256='c'*64),
            stable_window=dict(started_s=.5, finished_s=2., margin_s=.01, stationary_attested=True),
            clock=dict(basis='host_monotonic', evidence_sha256='d'*64),
            provenance=dict(kind='independent_manual', evidence_sha256='e'*64),
            comparison_method=dict(kind='manual_spatial', evidence_sha256='f'*64))
        value.update(changes)
        p = self.root/'manual.json'
        p.write_text(json.dumps(value), encoding='utf-8')
        return p

    def test_complete_manual_contract_is_only_unverified_diagnostic_not_comparison(self):
        from cerveau import capture_quality as q
        p = self.clip()
        result = q.diagnose([p], roi=(0, 0, 64, 32), manual_reference=self.manual(p))
        self.assertEqual(result['manual_reference']['state'], 'provided_unverified')
        self.assertEqual(result['status'], 'diagnostic_only')
        self.assertEqual(result['reasons'], [])
        self.assertFalse(result['current_permission'])
        self.assertFalse(result['comparable'])
        self.assertFalse(result['hud_validated'])
        self.assertNotIn('session_token', json.dumps(result))

    def test_incomplete_wrong_hash_roi_or_moving_manual_reference_refuse_preflight(self):
        from cerveau import capture_quality as q
        p = self.clip()
        for changes in [dict(landmarks=None), dict(identity=None), dict(provenance=None),
                dict(clock=None), dict(comparison_method=None), dict(roi=[1, 1, 20, 20]),
                dict(capture_sha256=['0'*64]), dict(stable_window=dict(started_s=1., finished_s=1.1,
                margin_s=.01, stationary_attested=False))]:
            with self.subTest(changes=changes):
                result = q.diagnose([p], roi=(0, 0, 64, 32), manual_reference=self.manual(p, **changes))
                self.assertNotEqual(result['status'], 'diagnostic_only')
                self.assertFalse(result['comparable'])
                self.assertNotEqual(result['manual_reference']['state'], 'provided_unverified')

    def test_thresholds_sampling_and_insufficient_frames_are_explicit(self):
        from cerveau import capture_quality as q
        p = self.clip()
        result = q.diagnose([p], roi=(0, 0, 64, 32), max_frames=1, manual_reference=self.manual(p))
        self.assertEqual(result['counts']['decoded'], 1)
        self.assertEqual(result['counts']['uninspected'], 2)
        self.assertIn('sample_incomplete', result['reasons'])
        self.assertIn('frames_insufficient', result['reasons'])
        self.assertEqual(result['status'], 'unknown')
        masked = self.image(mask=True)
        result = q.diagnose([masked], roi=(0, 0, 64, 32), black_fraction=.9, rectangle_fraction=.9)
        self.assertEqual(result['frames'][0]['state'], 'pixels_clear_not_attested')
        for kwargs in [dict(max_frames=129), dict(max_frames=0), dict(black_level=256),
                dict(black_fraction=float('nan')), dict(rectangle_fraction=-1), dict(min_frames=0)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                q.diagnose([p], roi=(0, 0, 64, 32), **kwargs)
        with self.assertRaises(ValueError):
            q.diagnose([p]*9, roi=(0, 0, 64, 32))

    def test_cli_real_subprocess_is_offline_exclusive_and_json_minimized(self):
        import subprocess
        import sys
        p = self.clip()
        manual = self.manual(p)
        out = self.root/'reports'/'quality.json'
        # Source directory must be disjoint from report directory.
        sources = self.root/'sources'
        sources.mkdir()
        p = p.rename(sources/p.name)
        manual = manual.rename(sources/manual.name)
        argv = [sys.executable, '-B', '-m', 'cerveau.capture_quality', '--input', str(p),
                '--roi', '0', '0', '64', '32', '--manual-reference', str(manual), '--report-json', str(out)]
        run = subprocess.run(argv, capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result, json.loads(out.read_bytes()))
        self.assertEqual(result['status'], 'diagnostic_only')
        self.assertNotIn(str(sources), run.stdout.decode())
        before = out.read_bytes()
        refused = subprocess.run(argv, capture_output=True, timeout=20)
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(out.read_bytes(), before)
        argv[-1] = str(sources/'must-not-create.json')
        refused = subprocess.run(argv, capture_output=True, timeout=20)
        self.assertEqual(refused.returncode, 1)
        self.assertFalse((sources/'must-not-create.json').exists())

    def test_duplicate_inputs_cross_segment_time_and_geometry_changes_are_refused(self):
        from cerveau import capture_quality as q
        p = self.clip()
        result = q.diagnose([p, p], roi=(0, 0, 64, 32))
        self.assertEqual(result['status'], 'refused')
        self.assertIn('input_duplicate', result['reasons'])
        other = self.root/'other.zip'
        other.write_bytes(p.read_bytes())
        result = q.diagnose([p, other], roi=(0, 0, 64, 32))
        self.assertIn('segment_time_order', result['reasons'])
        self.assertEqual(result['status'], 'refused')
        other = self.image(name='different.bmp', width=65)
        result = q.diagnose([self.image(), other], roi=(0, 0, 64, 32))
        self.assertIn('dimensions_changed', result['reasons'])
        self.assertEqual(result['status'], 'refused')

    def test_manual_identity_must_match_recorded_capture_not_caller_claim(self):
        from cerveau import capture_quality as q
        p = self.clip()
        result = q.diagnose([p], roi=(0, 0, 64, 32), manual_reference=self.manual(p,
            identity=dict(session_token='0'*32, map_id='SYNTHETIC', perspective='player', evidence_sha256='b'*64)))
        self.assertNotEqual(result['status'], 'diagnostic_only')
        self.assertEqual(result['manual_reference']['fields']['identity'], 'invalid')

    def test_missing_contract_fields_remain_missing_and_do_not_default_to_zero(self):
        from cerveau import capture_quality as q
        p = self.clip()
        manual = self.manual(p)
        doc = json.loads(manual.read_bytes())
        del doc['landmarks']
        doc['stable_window']['margin_s'] = None
        manual.write_text(json.dumps(doc), encoding='utf-8')
        result = q.diagnose([p], roi=(0, 0, 64, 32), manual_reference=manual)
        self.assertEqual(result['manual_reference']['fields']['landmarks'], 'missing')
        self.assertEqual(result['manual_reference']['fields']['stable_window'], 'invalid')
        self.assertEqual(result['manual_reference']['calibration'], 'unknown')
        self.assertEqual(result['status'], 'unknown')

    def test_crc_corrupt_missing_member_and_invalid_index_never_leak_exception_data(self):
        from cerveau import capture_quality as q
        import zipfile
        p = self.clip()
        raw = bytearray(p.read_bytes())
        with zipfile.ZipFile(p) as z:
            member = z.getinfo('frame-0000.bmp')
            offset = member.header_offset+30+len(member.filename.encode())+len(member.extra)
        raw[offset+60] ^= 1
        p.write_bytes(raw)
        result = q.diagnose([p], roi=(0, 0, 64, 32))
        self.assertEqual(result['status'], 'refused')
        self.assertNotIn('Bad CRC', json.dumps(result))
        self.assertIsNone(result['counts']['declared'])
        self.assertIsNone(result['counts']['uninspected'])
        for index in [b'{"frames":[],"frames":[]}', b'{"frames":["PRIVATE_TOKEN"]}', b'not-json']:
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('index.json', index)
                z.writestr('frame-0000.bmp', bmp())
            result = q.diagnose([p], roi=(0, 0, 64, 32))
            self.assertEqual(result['status'], 'refused')
            self.assertNotIn('PRIVATE_TOKEN', json.dumps(result))

    def test_partial_clear_capture_cannot_pass_even_with_manual_attestation(self):
        from cerveau import capture_quality as q
        p = self.clip(complete=False)
        result = q.diagnose([p], roi=(0, 0, 64, 32), manual_reference=self.manual(p))
        self.assertEqual(result['status'], 'refused')
        self.assertIn('partial_reference', result['reasons'])
        p = self.clip().rename(self.root/'partial.zip.partial')
        self.assertIn('partial_reference', q.diagnose([p], roi=(0, 0, 64, 32))['reasons'])

    def test_roi_orientation_and_top_down_bmp_match(self):
        from cerveau import capture_quality as q
        data = bmp(mask=True)
        stride = 64*3
        top_down = bytearray(data[:54])
        struct.pack_into('<i', top_down, 22, -32)
        top_down += b''.join(data[54+y*stride:54+(y+1)*stride] for y in reversed(range(32)))
        p = self.root/'topdown.bmp'
        p.write_bytes(top_down)
        for image in [p, self.image(mask=True)]:
            result = q.diagnose([image], roi=(7, 5, 32, 20))
            self.assertEqual(result['frames'][0]['near_black_fraction'], 1)
            self.assertEqual(result['frames'][0]['largest_near_black_rectangle_fraction'], 1)

    def test_real_cli_never_imports_native_backend_or_constructs_api_coach(self):
        import subprocess
        import sys
        p = self.clip()
        script = self.root/'offline_guard.py'
        checkout = Path(__file__).resolve().parents[1]
        script.write_text('import sys, builtins\n'
            f'sys.path.insert(0, {str(checkout)!r})\n'
            'original = builtins.__import__\n'
            'def guarded(name, *args, **kwargs):\n'
            '    if name in ("hotstate.reader", "hotstate.live", "hotstate.native_context",\n'
            '                "cerveau.runner", "cerveau.objective_reference", "mpyq", "heroprotocol"):\n'
            '        raise AssertionError("forbidden offline dependency")\n'
            '    return original(name, *args, **kwargs)\n'
            'builtins.__import__ = guarded\n'
            'import cerveau, grocoapi\n'
            'def forbidden(*args, **kwargs):\n'
            '    raise AssertionError("forbidden constructor")\n'
            'cerveau.Coach.__init__ = forbidden\n'
            'grocoapi.GrocoClient.__init__ = forbidden\n'
            'from cerveau.capture_quality import main\n'
            'raise SystemExit(main())\n', encoding='utf-8')
        result = subprocess.run([sys.executable, '-I', '-B', str(script), '--input', str(p),
            '--roi', '0', '0', '64', '32', '--report-json', str(self.root.parent/(self.root.name+'-report.json'))],
            capture_output=True, timeout=20)
        report = self.root.parent/(self.root.name+'-report.json')
        self.addCleanup(report.unlink, missing_ok=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stderr, b'')
        self.assertEqual(json.loads(result.stdout)['status'], 'unknown')

    def test_manual_roi_types_and_input_error_attribution_fail_closed(self):
        from cerveau import capture_quality as q
        p = self.clip()
        for bad_roi in [[False, 0, 64, 32], [0., 0, 64, 32]]:
            result = q.diagnose([p], roi=(0, 0, 64, 32), manual_reference=self.manual(p, roi=bad_roi))
            self.assertEqual(result['manual_reference']['fields']['roi'], 'invalid')
            self.assertEqual(result['status'], 'unknown')
        missing = self.root/'missing.bmp'
        result = q.diagnose([missing], roi=(0, 0, 64, 32))
        self.assertEqual(result['inputs'][0]['state'], 'refused')
        self.assertEqual(result['inputs'][0]['reasons'], ['input_unavailable'])
        p = self.clip()
        other = self.root/'other.zip'
        other.write_bytes(p.read_bytes())
        result = q.diagnose([p, other], roi=(0, 0, 64, 32))
        self.assertEqual(result['inputs'][1]['state'], 'refused')
        self.assertEqual(result['inputs'][1]['reasons'], ['segment_time_order'])


if __name__ == '__main__':
    unittest.main()
