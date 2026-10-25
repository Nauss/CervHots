"""Diagnostic borné de pixels historiques ; jamais une qualification HUD."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import zipfile
from pathlib import Path
import stat
import struct

IMAGE_BYTES = 8 * 2**20


def _read(path, limit):
    with Path(path).open('rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('input_not_regular')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('input_limit')
    return data


def _image(data, roi, black_level=8, black_fraction=.15, rectangle_fraction=.08):
    if len(data) < 54 or len(data) > IMAGE_BYTES or data[:2] != b'BM':
        raise ValueError('image_format')
    size, offset = struct.unpack_from('<I4xI', data, 2)
    header, width, signed_height, planes, bits, compression = struct.unpack_from('<IiiHHI', data, 14)
    height = abs(signed_height)
    if (header not in (40, 108, 124) or not 1 <= width <= 1920 or not 1 <= height <= 1080
            or planes != 1 or bits not in (24, 32) or compression != 0
            or not 14 + header <= offset <= 4096):
        raise ValueError('image_format')
    stride = ((width * bits + 31) // 32) * 4
    if size != len(data) or offset + stride * height != len(data):
        raise ValueError('image_incomplete')
    if (type(roi) not in (tuple, list) or len(roi) != 4
            or any(type(v) is not int for v in roi)):
        raise ValueError('roi_invalid')
    x, y, w, h = roi
    if min(x, y) < 0 or min(w, h) <= 0 or x + w > width or y + h > height:
        raise ValueError('roi_out_of_bounds')
    black = largest = 0
    heights = [0] * w
    for row in range(y, y+h):
        stored_y = row if signed_height < 0 else height - 1 - row
        for col in range(x, x+w):
            start = offset + stored_y * stride + col * (bits // 8)
            near_black = max(data[start:start+3]) <= black_level
            black += near_black
            heights[col-x] = heights[col-x] + 1 if near_black else 0
        # Largest all-near-black axis-aligned rectangle: O(pixels), O(width).
        # No tile alignment assumption; still not proof of an overlay/defect.
        stack = []
        for i, value in enumerate(heights + [0]):
            left = i
            while stack and stack[-1][1] > value:
                left, old_height = stack.pop()
                largest = max(largest, old_height * (i-left))
            if not stack or stack[-1][1] < value:
                stack.append((left, value))
    suspect = black / (w*h) >= black_fraction or largest / (w*h) >= rectangle_fraction
    return {'width': width, 'height': height, 'roi_pixels': w*h,
            'near_black_fraction': black / (w*h),
            'largest_near_black_rectangle_fraction': largest / (w*h),
            'state': 'black_or_mask_suspected' if suspect else 'pixels_clear_not_attested'}


def _number(value):
    return type(value) in (int, float) and 0 <= value <= 1e12 and math.isfinite(value)


def _json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('json_duplicate_key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def _timing(entries, max_gap_s):
    previous, first, missing, invalid, max_gap = None, None, False, False, None
    for entry in entries:
        start, end = entry.get('started_s'), entry.get('finished_s')
        if start is None or end is None:
            missing = True
            previous = None
            continue
        if not _number(start) or not _number(end) or end < start:
            invalid = True
            previous = None
            continue
        if first is None:
            first = start
        if previous is not None:
            gap = start - previous
            invalid |= gap < 0
            max_gap = gap if max_gap is None else max(gap, max_gap)
        previous = end
    state = ('invalid' if invalid else 'missing' if missing else
             'discontinuous' if max_gap is not None and max_gap > max_gap_s else 'recorded_ordered')
    return {'state': state, 'max_gap_s': max_gap,
            'started_s': first if not missing and not invalid else None,
            'finished_s': previous if not missing and not invalid else None}


def _archive(data):
    # Reject ZIP64, multidisk and oversized directories BEFORE ZipFile allocation.
    end = data.rfind(b'PK\x05\x06', max(0, len(data)-65557))
    if end < 0 or len(data)-end < 22:
        raise ValueError('archive_directory')
    _, disk, directory_disk, disk_count, count, size, offset, comment = struct.unpack_from('<4s4H2IH', data, end)
    if (disk or directory_disk or disk_count != count or not 2 <= count <= 401
            or size > 65536 or offset + size != end or end + 22 + comment != len(data)):
        raise ValueError('archive_directory')
    archive = zipfile.ZipFile(io.BytesIO(data))
    try:
        members = archive.infolist()
        if (len(members) != count or len({m.filename for m in members}) != count
                or sum(m.file_size for m in members) > 17 * 2**20
                or any(m.compress_type != zipfile.ZIP_STORED or m.flag_bits & 1
                       or m.file_size != m.compress_size or m.file_size > (
                           IMAGE_BYTES if m.filename.endswith('.bmp') else 128*1024 if m.filename == 'index.json' else 512*1024)
                       or not re.fullmatch(r'index\.json|frame-[0-9]{4,8}\.bmp|segment-[0-9]{4,8}\.(?:jsonl|seal\.json)', m.filename)
                       for m in members)):
            raise ValueError('archive_limits')
        index = _json(archive.read('index.json'))
        if type(index) is not dict or type(index.get('frames')) is not list or not 1 <= len(index['frames']) <= 400:
            raise ValueError('invalid_index')
        entries, names, previous = index['frames'], set(), None
        for entry in entries:
            if type(entry) is not dict or type(entry.get('member')) is not str:
                raise ValueError('invalid_frame')
            name = entry['member']
            if not re.fullmatch(r'frame-[0-9]{4,8}\.bmp', name) or name in names:
                raise ValueError('frame_order')
            number = int(name[6:-4])
            if previous is not None and number != previous + 1:
                raise ValueError('frame_order')
            previous = number
            names.add(name)
            # Read/hash exactly the same bounded bytes, CRC checked by ZipFile.
            if hashlib.sha256(archive.read(name)).hexdigest() != entry.get('sha256'):
                raise ValueError('frame_hash')
        if names != {m.filename for m in members if m.filename.endswith('.bmp')}:
            raise ValueError('unindexed_frame')
        for member in members:
            if member.filename not in names and member.filename != 'index.json':
                archive.read(member)  # CRC only; no private/native metadata projection.
        return archive, index
    except BaseException:
        archive.close()
        raise


def _manual(path, roi, sources, tokens):
    fields = ('capture_sha256', 'roi', 'identity', 'landmarks', 'stable_window',
              'clock', 'provenance', 'comparison_method')
    result = {'state': 'missing', 'sha256': None,
              'fields': {key: 'missing' for key in fields}, 'calibration': 'unknown'}
    if path is None:
        return result
    try:
        data = _read(path, 64*1024)
        result['sha256'] = hashlib.sha256(data).hexdigest()
        doc = _json(data)
        if (type(doc) is not dict or type(doc.get('schema_version')) is not int
                or doc['schema_version'] != 1 or doc.get('source') != 'independent_manual'
                or set(doc) - set(fields) - {'schema_version', 'source'}):
            raise ValueError('manual_schema')
        values = result['fields']
        for key in fields:
            values[key] = 'missing' if key not in doc else 'unknown' if doc[key] is None else 'invalid'
        def evidence(value):
            return (type(value) is dict and type(value.get('evidence_sha256')) is str
                    and re.fullmatch('[0-9a-f]{64}', value['evidence_sha256']))
        if doc.get('capture_sha256') == [s['sha256'] for s in sources] and all(s['sha256'] for s in sources):
            values['capture_sha256'] = 'provided_unverified'
        if (type(doc.get('roi')) is list and all(type(v) is int for v in doc['roi'])
                and doc['roi'] == list(roi)):
            values['roi'] = 'provided_unverified'
        identity = doc.get('identity')
        if (evidence(identity) and type(identity.get('session_token')) is str
                and re.fullmatch('[0-9a-f]{32}', identity['session_token'])
                and type(identity.get('map_id')) is str and re.fullmatch('[A-Za-z0-9_]{1,64}', identity['map_id'])
                and identity.get('perspective') == 'player'
                and len(tokens) == len(sources)
                and all(token == identity['session_token'] for token in tokens)):
            values['identity'] = 'provided_unverified'
        landmarks = doc.get('landmarks')
        if evidence(landmarks) and landmarks.get('coordinate_system') == 'roi_pixels':
            points = landmarks.get('points')
            if (type(points) is list and 2 <= len(points) <= 16
                    and all(type(p) is list and len(p) == 2
                        and all(_number(v) for v in p) and p[0] < roi[2] and p[1] < roi[3] for p in points)
                    and len({tuple(p) for p in points}) == len(points)):
                values['landmarks'] = 'provided_unverified'
        window = doc.get('stable_window')
        if type(window) is dict:
            a, b, margin = (window.get(k) for k in ('started_s', 'finished_s', 'margin_s'))
            if (all(_number(v) for v in (a, b, margin)) and a < b and 2*margin < b-a
                    and window.get('stationary_attested') is True
                    and all(s['timing']['state'] == 'recorded_ordered'
                        and a + margin <= s['timing']['started_s']
                        and s['timing']['finished_s'] <= b - margin for s in sources)):
                values['stable_window'] = 'provided_unverified'
        clock = doc.get('clock')
        if (evidence(clock) and clock.get('basis') == 'host_monotonic'
                and all(s.get('clock_basis') == 'host_monotonic' for s in sources)):
            values['clock'] = 'provided_unverified'
        for key, kind in (('provenance', 'independent_manual'), ('comparison_method', 'manual_spatial')):
            value = doc.get(key)
            if evidence(value) and value.get('kind') == kind:
                values[key] = 'provided_unverified'
        result['state'] = ('provided_unverified' if all(v == 'provided_unverified' for v in values.values())
                           else 'incomplete_or_invalid')
    except (OSError, ValueError, TypeError, RecursionError):
        result['state'] = 'invalid'
    return result


def diagnose(inputs, *, roi, manual_reference=None, max_frames=32, min_frames=3,
             black_level=8, black_fraction=.15, rectangle_fraction=.08,
             max_gap_s=.25, min_roi_pixels=256):
    # Limits can only be reduced or changed inside explicit hard caps.
    if (type(inputs) not in (list, tuple) or not 1 <= len(inputs) <= 8
            or type(max_frames) is not int or not 1 <= max_frames <= 128
            or type(min_frames) is not int or not 1 <= min_frames <= 128
            or type(min_roi_pixels) is not int or not 1 <= min_roi_pixels <= 1920*1080
            or type(black_level) is not int or not 0 <= black_level <= 255
            or any(not _number(v) or not 0 < v <= 1 for v in (black_fraction, rectangle_fraction))
            or not _number(max_gap_s) or not 0 < max_gap_s <= 10
            or type(roi) not in (tuple, list) or len(roi) != 4 or any(type(v) is not int for v in roi)):
        raise ValueError('invalid_limits_or_roi')
    thresholds = dict(black_level=black_level, black_fraction=black_fraction,
                      rectangle_fraction=rectangle_fraction, max_frames=max_frames,
                      min_frames=min_frames, max_gap_s=max_gap_s, min_roi_pixels=min_roi_pixels)
    frames, reasons, invalid, sources, declared = [], [], False, [], 0
    tokens, previous_end, seen_paths = [], None, set()
    def inspect(data, digest, input_number):
        frames.append(dict(_image(data, roi, black_level, black_fraction, rectangle_fraction),
                           sha256=digest, input=input_number))
    for input_number, path in enumerate(inputs):
        source = {'input': input_number, 'sha256': None, 'state': 'refused', 'reasons': [], 'clock_basis': 'unknown',
                  'declared_frames': None, 'timing': {'state': 'missing', 'max_gap_s': None}}
        sources.append(source)
        try:
            resolved = Path(path).resolve()
            if resolved in seen_paths:
                raise ValueError('input_duplicate')
            seen_paths.add(resolved)
            data = _read(path, 17 * 2**20)
            source['sha256'] = hashlib.sha256(data).hexdigest()
            if data[:2] == b'BM':
                tokens.append(None)
                declared += 1
                source['declared_frames'] = 1
                if len(frames) < max_frames:
                    inspect(data, source['sha256'], input_number)
            else:
                archive, index = _archive(data)
                with archive:
                    source['declared_frames'] = len(index['frames'])
                    declared += len(index['frames'])
                    for entry in index['frames']:
                        if len(frames) >= max_frames:
                            break
                        inspect(archive.read(entry['member']), entry['sha256'], input_number)
                source['timing'] = _timing(index['frames'], max_gap_s)
                token = index.get('session_token')
                tokens.append(token if type(token) is str and re.fullmatch('[0-9a-f]{32}', token) else None)
                source['clock_basis'] = 'host_monotonic' if index.get('clock_basis') == 'host_monotonic' else 'unknown'
                if index.get('complete') is not True:
                    raise ValueError('partial_reference')
            if Path(path).name.endswith('.partial'):
                raise ValueError('partial_reference')
            source['state'] = 'integrity_checked'
            timing = source['timing']
            if timing['state'] == 'recorded_ordered':
                if previous_end is not None:
                    if timing['started_s'] < previous_end:
                        raise ValueError('segment_time_order')
                    if timing['started_s'] - previous_end > max_gap_s:
                        reasons.append('segment_time_discontinuous')
                previous_end = timing['finished_s']
            else:
                previous_end = None
        except OSError:
            source['state'] = 'refused'
            source['reasons'].append('input_unavailable')
            reasons.append('input_unavailable')
            invalid = True
        except (ValueError, KeyError, TypeError, RecursionError, struct.error, zipfile.BadZipFile) as exc:
            code = str(exc) if type(exc) is ValueError and re.fullmatch('[a-z_]+', str(exc)) else 'input_invalid'
            source['state'] = 'refused'
            source['reasons'].append(code)
            reasons.append(code)
            invalid = True
    if len({(f['width'], f['height']) for f in frames}) > 1:
        reasons.append('dimensions_changed')
        invalid = True
    suspect = sum(f['state'] == 'black_or_mask_suspected' for f in frames)
    sufficient = sum(f['state'] == 'pixels_clear_not_attested' and f['roi_pixels'] >= min_roi_pixels for f in frames)
    if suspect:
        reasons.append('black_or_mask_suspected')
    if sufficient < min_frames:
        reasons.append('frames_insufficient')
    if declared > len(frames):
        reasons.append('sample_incomplete')
    for source in sources:
        if source['timing']['state'] != 'recorded_ordered':
            reasons.append('timing_' + source['timing']['state'])
        if source['clock_basis'] == 'unknown':
            reasons.append('clock_basis_unknown')
    manual = _manual(manual_reference, roi, sources, tokens)
    if manual['state'] != 'provided_unverified':
        reasons.append('manual_reference_missing' if manual['state'] == 'missing' else 'manual_reference_incomplete_or_invalid')
    return {'schema_version': 1, 'event': 'capture_quality', 'basis': 'historical_pixels_only',
            'current_permission': False, 'hud_validated': False, 'comparable': False,
            'counts': {'decoded': len(frames),
                       'declared': declared if all(s['declared_frames'] is not None for s in sources) else None,
                       'uninspected': declared-len(frames) if all(s['declared_frames'] is not None for s in sources) else None,
                       'suspect': suspect, 'sufficient': sufficient}, 'inputs': sources, 'thresholds': thresholds,
            'spatial_comparisons': 0, 'status': 'refused' if invalid else 'unknown' if reasons else 'diagnostic_only',
            'roi': list(roi), 'manual_reference': manual, 'frames': frames, 'reasons': sorted(set(reasons))}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, action='append', required=True,
                        help='BMP ou ZIP fermé explicite, répétable (8 maximum), aucun parcours dossier')
    parser.add_argument('--roi', type=int, nargs=4, required=True, metavar=('X', 'Y', 'W', 'H'),
                        help='pixels de l image, origine en haut à gauche ; aucune UV déduite')
    parser.add_argument('--manual-reference', type=Path, help='contrat indépendant JSON privé, jamais journal natif')
    parser.add_argument('--report-json', type=Path, required=True, help='NOUVEAU fichier absolu, hors répertoires sources')
    parser.add_argument('--max-frames', type=int, default=32)
    parser.add_argument('--min-frames', type=int, default=3)
    parser.add_argument('--min-roi-pixels', type=int, default=256)
    parser.add_argument('--black-level', type=int, default=8)
    parser.add_argument('--black-fraction', type=float, default=.15)
    parser.add_argument('--rectangle-fraction', type=float, default=.08)
    parser.add_argument('--max-gap-s', type=float, default=.25)
    args = parser.parse_args(argv)
    try:
        paths = args.input + ([args.manual_reference] if args.manual_reference else [])
        output = args.report_json.resolve()
        if (not args.report_json.is_absolute() or args.report_json.exists()
                or any(output.is_relative_to(p.resolve().parent) for p in paths)):
            raise ValueError('output_refused')
        result = diagnose(args.input, roi=args.roi, manual_reference=args.manual_reference,
                          **{key: getattr(args, key) for key in ('max_frames', 'min_frames', 'min_roi_pixels',
                             'black_level', 'black_fraction', 'rectangle_fraction', 'max_gap_s')})
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result, stream, ensure_ascii=True, allow_nan=False, indent=2)
            stream.write('\n')
    except (OSError, ValueError, TypeError, RecursionError):
        print(json.dumps({'event': 'capture_quality_error', 'code': 'input_or_output_refused',
                          'current_permission': False, 'comparable': False, 'hud_validated': False}))
        return 1
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return 0 if result['status'] == 'diagnostic_only' else 1


if __name__ == '__main__':
    raise SystemExit(main())
