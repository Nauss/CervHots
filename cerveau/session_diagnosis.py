"""Read-only aggregation of the passive journal; no acquisition or comparison.

This is an inspection view of existing journal events, not another state pipeline.
All input claims are historical and unauthenticated. No receipts are created.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import io
import datetime as dt
import json
import math
import re
import stat
import struct
import sys
import zipfile

from .diagnostics import FIELDS
from .objective_compare import _load, _read, _number

STOP_REASONS = ('stop_file', 'session_limit', 'session_changed', 'interrupted',
                'failure_limit', 'software_error', 'source_close_failed', 'native_reader_unavailable')


FAMILIES = ('gameplay_clock', 'positions', 'visibility', 'objective', 'talents',
            'local_cooldowns', 'battlefield')
QUALIFICATIONS = ('normalized', 'refused', 'rejected', 'not_attempted', 'not_selected', 'unknown')


def _bounded(path, limit):
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('not_regular')
    return _read(path, limit, 'input_limit')


def _finite(value):
    if type(value) is int and value.bit_length() > 1023:
        raise ValueError('integer_limit')
    if type(value) is float and not math.isfinite(value):
        raise ValueError('nonfinite')
    if type(value) is dict:
        for item in value.values():
            _finite(item)
    elif type(value) is list:
        for item in value:
            _finite(item)


def _journal(path):
    rows, state, digest = [], 'complete', None
    try:
        data = _bounded(path, 4 * 2**20)
        digest = hashlib.sha256(data).hexdigest()
        seen, previous_cycle = set(), 0
        for sequence, line in enumerate(data.splitlines(keepends=True), 1):
            if len(line) > 65536 or sequence > 10000:
                state = 'limit_exceeded'
                break
            if not line.endswith(b'\n'):
                state = 'truncated'
                break
            row = _load(line)
            _finite(row)
            if (type(row) is not dict or type(row.get('schema_version')) is not int
                    or row['schema_version'] != 1 or type(row.get('sequence')) is not int
                    or row['sequence'] != sequence or type(row.get('cycle')) is not int
                    or not previous_cycle <= row['cycle'] <= 10000
                    or type(row.get('event')) is not str):
                raise ValueError('invalid_record')
            key = (row['event'], row['cycle'])
            if row['event'] in ('acquisition', 'observation', 'refusal'):
                if key in seen:
                    raise ValueError('duplicate_event')
                seen.add(key)
            previous_cycle = row['cycle']
            rows.append(row)
        if not data:
            state = 'empty'
    except OSError:
        state = 'unavailable'
    except ValueError as exc:
        state = 'limit_exceeded' if exc.args == ('input_limit',) else 'invalid'
    except (TypeError, RecursionError):
        state = 'invalid'
    return rows, {'state': state, 'sha256': digest,
                  'bytes_limit': 4 * 2**20, 'line_bytes_limit': 65536, 'records_limit': 10000}


def diagnose(journal):
    return _diagnose(*_journal(journal))


def _diagnose(rows, integrity):
    """Aggregate already bounded/parsed records without another disk read."""
    from .passive_session import measured_acquisition
    from hotstate.diagnostics import refusal
    acquisitions = [r for r in rows if r['event'] == 'acquisition']
    observations = [r for r in rows if r['event'] == 'observation']
    refusals = [r for r in rows if r['event'] == 'refusal']
    boundaries = [r for r in rows if r['event'] == 'boundary']
    measured = [measured_acquisition(dict(r, optional_refusals=(
        r['optional_refusals'] if type(r.get('optional_refusals')) is dict else {})))
        for r in acquisitions]
    codes = {r['cycle']: refusal(r.get('refusal', {}).get('code')
             if type(r.get('refusal')) is dict else None)['code']
             for r in acquisitions if r.get('outcome') == 'refused'}
    codes.update({r['cycle']: refusal(r.get('code'))['code'] for r in refusals})
    fields, unknown_fields = Counter(), 0
    families = {name: Counter() for name in FAMILIES}
    optional = {name: Counter() for name in FAMILIES}
    for row in measured:
        for name, detail in row['optional_refusals'].items():
            optional[name][detail['code']] += 1
    metadata = {name: Counter() for name in ('mission_clock', 'elapsed_clock', 'utc_clock',
                'host_read_bounds', 'identity_binding', 'native_player_origin')}
    provenance = {name: {key: Counter() for key in ('source', 'original_age_window', 'mission_clock')}
                  for name in FAMILIES}
    identities = set()
    for r in observations:
        comparison = r.get('comparison')
        comparison = comparison if type(comparison) is dict else {}
        bounds = (comparison.get('clock_basis') == 'host_monotonic'
                  and _number(comparison.get('read_started_s'))
                  and _number(comparison.get('read_finished_s'))
                  and comparison['read_started_s'] <= comparison['read_finished_s'])
        binding = all(type(r.get(k)) is str and re.fullmatch(k + '_[0-9a-f]{12}', r[k])
                      for k in ('session', 'map'))
        binding = bool(binding and type(comparison.get('session_token')) is str
                       and re.fullmatch('[0-9a-f]{32}', comparison['session_token'])
                       and type(comparison.get('map_id')) is str
                       and comparison['map_id'] in ('DragonShire', 'Volskaya')
                       and comparison.get('perspective') == 'native_player')
        if binding:
            identities.add((r['session'], r['map'], comparison['session_token'], comparison['map_id']))
        utc = False
        try:
            value = r.get('timestamp_utc')
            utc = (type(value) is str and len(value) <= 64
                   and dt.datetime.fromisoformat(value).utcoffset() == dt.timedelta(0))
        except ValueError:
            pass
        for key, valid in {'mission_clock': _number(r.get('mission_t_s'), 21600),
                           'elapsed_clock': _number(r.get('elapsed_s')),
                           'utc_clock': utc, 'host_read_bounds': bounds,
                           'identity_binding': binding,
                           'native_player_origin': comparison.get('perspective') == 'native_player'}.items():
            metadata[key]['available' if valid else 'missing_or_invalid'] += 1
        available = r.get('available_fields')
        for field in set(k for k in available if type(k) is str) if type(available) is list else ():
            if field in FIELDS:
                fields[field] += 1
            else:
                unknown_fields += 1
        for name in FAMILIES:
            packet = r.get(name)
            packet = packet if type(packet) is dict else {}
            status = packet.get('status') if type(packet) is dict else None
            families[name][status if type(status) is str and status in QUALIFICATIONS else 'unknown'] += 1
            for key, valid in {'source': packet.get('source') == 'native_player',
                               'original_age_window': (_number(packet.get('age_s'), 1)
                                   and _number(packet.get('read_window_s'), .125)),
                               'mission_clock': _number(packet.get('source_mission_t_s'), 21600)}.items():
                provenance[name][key]['available' if valid else 'missing_or_invalid'] += 1
    costs = {}
    for key in ('elapsed_ms', 'reads', 'bytes_requested'):
        values = [r[key] for r in measured if key in r]
        costs[key] = {'maximum': max(values) if values else None,
                      'missing': len(measured) - len(values)}
    reason = boundaries[-1].get('reason') if boundaries else None
    all_cycles = {r['cycle'] for r in rows if r['cycle'] > 0}
    measured_cycles = {r['cycle'] for r in acquisitions}
    complete = integrity['state'] == 'complete'
    return {'event': 'session_diagnosis', 'schema_version': 1,
            'basis': 'historical_not_current', 'current_permission': False,
            'hud_validated': False, 'spatial_comparisons': 0,
            'journal': integrity,
            'counts_scope': 'recorded_events' if complete else 'valid_prefix_only',
            'total_acquisitions': len(acquisitions) if complete else None,
            'counts': {'acquisitions': len(acquisitions), 'observations': len(observations),
                       'acquisition_outcomes': dict(sorted(Counter(r['outcome'] for r in measured).items())),
                       'refusal_events': len(refusals), 'refused_cycles': len(codes),
                       'boundaries': len(boundaries),
                       'source_errors': sum(r['event'] == 'source_error' for r in rows),
                       'errors': sum(r['event'] == 'error' for r in rows),
                       'unknown_events': sum(r['event'] not in ('acquisition', 'observation', 'refusal',
                            'boundary', 'source_error', 'error') for r in rows),
                       'unmeasured_cycles': len(all_cycles - measured_cycles)},
            'costs': costs, 'refusal_codes': dict(sorted(Counter(codes.values()).items())),
            'normalized_fields': dict(sorted(fields.items())), 'unknown_fields': unknown_fields,
            'families': {k: dict(sorted(v.items())) for k, v in families.items()},
            'optional_refusals': {k: dict(sorted(v.items())) for k, v in optional.items()},
            'metadata': {k: {'available': v['available'], 'missing_or_invalid': v['missing_or_invalid']}
                         for k, v in metadata.items()},
            'family_provenance': {name: {k: {'available': v['available'],
                                 'missing_or_invalid': v['missing_or_invalid']}
                                 for k, v in p.items()} for name, p in provenance.items()},
            'identity': {'state': ('single_recorded_binding' if len(identities) == 1
                        and metadata['identity_binding']['missing_or_invalid'] == 0
                        else 'incomplete_or_mixed'), 'distinct_recorded_bindings': len(identities),
                        'authenticated': False, 'build_identity': 'not_recorded'},
            'stop': {'recorded_reason': reason if type(reason) is str and reason in STOP_REASONS else 'unknown',
                     'reader_active': None},
            'evidence': {'status': 'non_comparable', 'visual_references': 'absent',
                         'missing_requirements': ['independent_visual_identity',
                            'calibrated_spatial_reference', 'independent_stable_time_interval']}}


def _pixels(data):
    """Narrow BMP diagnostic, not HUD recognition. Ignore alpha, never OCR."""
    if len(data) < 54 or len(data) > 512 * 1024 or data[:2] != b'BM':
        raise ValueError('bmp_format')
    size, offset = struct.unpack_from('<I4xI', data, 2)
    header, width, height, planes, bits, compression = struct.unpack_from('<IiiHHI', data, 14)
    if (header not in (40, 108, 124) or not 16 <= width <= 1920
            or not 16 <= abs(height) <= 1080 or planes != 1 or bits not in (24, 32)
            or compression != 0 or not 14 + header <= offset <= 4096):
        raise ValueError('bmp_format')
    height = abs(height)
    stride = ((width * bits + 31) // 32) * 4
    if size != len(data) or offset + stride * height != len(data):
        raise ValueError('bmp_incomplete')
    black = 0
    for ty in range(8):
        for tx in range(16):
            count = total = 0
            for y in range(ty * height // 8, (ty + 1) * height // 8):
                for x in range(tx * width // 16, (tx + 1) * width // 16):
                    start = offset + stride * y + x * (bits // 8)
                    count += max(data[start:start + 3]) <= 8
                    total += 1
            black += count >= .98 * total
    return {'width': width, 'height': height, 'near_black_tiles': black, 'tiles': 128}


def visual_reference(path):
    """Inspect only explicitly supplied bytes. ZIP closure/hash never attest pixels."""
    result = {'state': 'invalid_or_unsupported', 'sha256': None,
              'spatial_status': 'non_comparable', 'stable_time_reference': 'not_supplied',
              'independent_identity': 'unverified', 'calibration': 'not_supplied',
              'frame_time_bounds': 'missing_or_invalid', 'frames_inspected': None,
              'frames_black_or_masked_suspected': None, 'partial': None}
    try:
        data = _bounded(path, 17 * 2**20)
        result['sha256'] = hashlib.sha256(data).hexdigest()
        if data[:2] == b'BM':
            frames = [_pixels(data)]
            result['partial'] = path.name.endswith('.partial')
        else:
            # Bound central-directory allocation before ZipFile builds its list.
            end = data.rfind(b'PK\x05\x06', max(0, len(data) - 65557))
            if end < 0 or len(data) - end < 22:
                raise ValueError('archive_directory')
            _, disk, directory_disk, disk_count, count, size, offset, comment = struct.unpack_from('<4s4H2IH', data, end)
            if (disk or directory_disk or disk_count != count or not 2 <= count <= 401
                    or size > 65536 or offset + size != end or end + 22 + comment != len(data)):
                raise ValueError('archive_directory')
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = archive.infolist()
                if (not 2 <= len(members) <= 401 or len({m.filename for m in members}) != len(members)
                        or sum(m.file_size for m in members) > 17 * 2**20
                        or any(m.compress_type != zipfile.ZIP_STORED or m.file_size > 512 * 1024
                               or m.flag_bits & 1 or not re.fullmatch(
                                   r'index\.json|frame-[0-9]{4,8}\.bmp|segment-[0-9]{4,8}\.(?:jsonl|seal\.json)',
                                   m.filename) for m in members)):
                    raise ValueError('archive_limits')
                index_data = archive.read('index.json')
                if len(index_data) > 128 * 1024:
                    raise ValueError('index_limit')
                index = _load(index_data)
                _finite(index)
                if type(index) is not dict or type(index.get('frames')) is not list:
                    raise ValueError('invalid_index')
                entries = index['frames']
                if not 1 <= len(entries) <= 400:
                    raise ValueError('invalid_index')
                frames, names, timed, previous = [], set(), True, None
                for entry in entries:
                    if type(entry) is not dict or type(entry.get('member')) is not str:
                        raise ValueError('invalid_frame')
                    name = entry['member']
                    if not re.fullmatch(r'frame-[0-9]{4,8}\.bmp', name) or name in names:
                        raise ValueError('invalid_frame')
                    names.add(name)
                    frame = archive.read(name)
                    if hashlib.sha256(frame).hexdigest() != entry.get('sha256'):
                        raise ValueError('frame_hash')
                    frames.append(_pixels(frame))
                    start, end = entry.get('started_s'), entry.get('finished_s')
                    ordered = (_number(start) and _number(end) and start <= end
                               and (previous is None or previous <= start))
                    timed = timed and ordered
                    previous = end if ordered else None
                if names != {m.filename for m in members if m.filename.endswith('.bmp')}:
                    raise ValueError('unindexed_frame')
                # Read all small metadata too: catch CRC errors without extracting.
                for member in members:
                    if member.filename not in names and member.filename != 'index.json':
                        archive.read(member)
                result['partial'] = index.get('complete') is not True or path.name.endswith('.partial')
                result['frame_time_bounds'] = 'recorded_not_independent' if timed else 'missing_or_invalid'
        result['frames_inspected'] = len(frames)
        result['frames_black_or_masked_suspected'] = sum(f['near_black_tiles'] >= 4 for f in frames)
        result['state'] = ('partial_reference' if result['partial'] else
                           'black_or_masked_suspected' if result['frames_black_or_masked_suspected'] else
                           'pixels_decoded_not_attested')
    except OSError:
        result['state'] = 'unavailable'
    except (ValueError, TypeError, KeyError, RecursionError, struct.error, zipfile.BadZipFile):
        pass
    return result


def readable(result):
    c = result['counts']
    lines = ['Diagnostic historique — NON COMPARABLE / HUD non valide',
             f"Journal: {result['journal']['state']}; portee: {result['counts_scope']}",
             f"Acquisitions: {c['acquisitions']}; observations normalisees: {c['observations']}; "
             f"cycles refuses: {c['refused_cycles']}; evenements refus: {c['refusal_events']}; arrets: {c['boundaries']}",
             f"Arret enregistre: {result['stop']['recorded_reason']}; activite actuelle: inconnue",
             'Origine/horloges/bornes/identite (disponible; absent/invalide):']
    for key, value in result['metadata'].items():
        lines.append(f"  {key}: {value['available']}; {value['missing_or_invalid']}")
    lines.append('Familles (qualifications enregistrees, pas revalidees):')
    for name, statuses in result['families'].items():
        text = ', '.join(f'{k}={v}' for k, v in statuses.items()) or 'aucune observation'
        age = result['family_provenance'][name]['original_age_window']
        lines.append(f"  {name}: {text}; age/fenetre absents ou invalides={age['missing_or_invalid']}")
    lines.append('Preuves visuelles: ' + result['evidence']['status'])
    references = result['evidence'].get('references', [])
    if not references:
        lines.append('  Aucune reference explicitement fournie.')
    for i, reference in enumerate(references, 1):
        lines.append(f"  Reference {i}: {reference['state']}; frames decodees={reference['frames_inspected']}; "
                     f"noir/masquage suspect={reference['frames_black_or_masked_suspected']}; "
                     f"bornes frames={reference['frame_time_bounds']}; fenetre stable independante=non fournie")
    lines.extend(['Absence/refus/inconnu != zero; presence normalisee != comparaison.',
                  'Identite visuelle independante, calibration spatiale et fenetre stable non etablies.',
                  'Comparaisons spatiales: 0. Integrite disque != validation HUD.'])
    return '\n'.join(lines) + '\n'


def run(args):
    try:
        # Never add reports to the source session or overwrite old reports.
        if args.report_dir.resolve().is_relative_to(args.journal.resolve().parent):
            raise ValueError('output_overlaps_input')
        result = diagnose(args.journal)
        result['evidence']['references'] = [visual_reference(p) for p in args.visual_reference]
        result['evidence']['visual_references'] = 'supplied' if args.visual_reference else 'absent'
        text = readable(result)
        args.report_dir.mkdir(parents=True, exist_ok=False)
        with (args.report_dir / 'diagnosis.json').open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=True, allow_nan=False, indent=2)
        with (args.report_dir / 'SUMMARY.txt').open('x', encoding='utf-8') as stream:
            stream.write(text)
    except (OSError, ValueError, TypeError, RecursionError):
        print(json.dumps({'event': 'session_diagnosis_error', 'code': 'output_or_input_refused',
                          'current_permission': False, 'hud_validated': False}))
        return 1
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    print(text, file=sys.stderr, end='')
    return 0 if result['journal']['state'] == 'complete' else 1
