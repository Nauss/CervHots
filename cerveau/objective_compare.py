"""Compare manually transcribed public Dragon evidence; never issue live permission."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import io
import zipfile
from pathlib import Path

from .objective_journal import objective_summary

FIELDS = ('phase', 'sun.owner', 'moon.owner', 'statue.state', 'dragon.state')
MODE = 'historical_not_current'


def _closed(obj, keys):
    return type(obj) is dict and set(obj) == set(keys.split())


def _hex(value, length):
    return type(value) is str and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def _valid_value(field, value):
    if value is None:
        return True
    if field in ('sun.owner', 'moon.owner'):
        return type(value) is int and value in (0, 1) or type(value) is str and value == 'neutral'
    choices = {'phase': ('waiting', 'warning', 'shrines', 'dragon', 'unknown'),
               'statue.state': ('capturable', 'inactive', 'unknown'),
               'dragon.state': ('inactive', 'active', 'ended', 'unknown')}
    return type(value) is str and value in choices[field]


def _validate_reference(r):
    valid = _closed(r, 'schema_version dataset journal_sha256 binding provenance clock samples')
    if valid:
        b, p, c = r['binding'], r['provenance'], r['clock']
        valid = (type(r['schema_version']) is int and r['schema_version'] == 1
                 and type(r['dataset']) is str and r['dataset'] in ('operator', 'synthetic')
                 and _hex(r['journal_sha256'], 64)
                 and _closed(b, 'session_token map_id perspective')
                 and _hex(b['session_token'], 32)
                 and (b['map_id'] is None or b['map_id'] == 'DragonShire')
                 and type(b['perspective']) is str and b['perspective'] in ('native_player', 'observer', 'unknown')
                 and _closed(p, 'kind transcription same_match same_player_perspective evidence_sha256 match_link_sha256 clock_evidence_sha256')
                 and type(p['kind']) is str and p['kind'] in ('hud_video', 'replay_video', 'journal_replay')
                 and type(p['transcription']) is str and p['transcription'] in ('manual', 'ocr')
                 and type(p['same_match']) is bool and type(p['same_player_perspective']) is bool
                 and all(_hex(p[k], 64) for k in ('evidence_sha256', 'match_link_sha256', 'clock_evidence_sha256'))
                 and _closed(c, 'basis uncertainty_s')
                 and type(c['basis']) is str and c['basis'] in ('host_monotonic', 'replay', 'utc')
                 and (c['uncertainty_s'] is None or _number(c['uncertainty_s']))
                 and type(r['samples']) is list and len(r['samples']) <= 128)
    if valid:
        for s in r['samples']:
            if not (_closed(s, 'cycle field value stable_from_s stable_to_s boundary_uncertainty_s')
                    and type(s['cycle']) is int and 1 <= s['cycle'] <= 10000
                    and type(s['field']) is str and s['field'] in FIELDS
                    and _valid_value(s['field'], s['value'])
                    and all(s[k] is None or _number(s[k]) for k in (
                        'stable_from_s', 'stable_to_s', 'boundary_uncertainty_s'))):
                valid = False
                break
    if not valid:
        raise ValueError('invalid_reference')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_json_key')
        result[key] = value
    return result


def _load(data):
    return json.loads(data, object_pairs_hook=_pairs)


def _read(path, limit, code):
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(code)
    return data


def _number(value, high=1e10):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= high


def _digest(path):
    if path is None:
        return None
    total, digest = 0, hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(65536):
            total += len(chunk)
            if total > 64 * 2**20:
                raise ValueError('evidence_limit')
            digest.update(chunk)
    return digest.hexdigest()


def _global_reason(reference, data, artifacts):
    if reference['journal_sha256'] != hashlib.sha256(data).hexdigest():
        return 'journal_digest_mismatch'
    p = reference['provenance']
    if p['evidence_sha256'] == reference['journal_sha256']:
        return 'self_reference'
    if (p['kind'] != 'hud_video' or p['transcription'] != 'manual'
            or p['same_match'] is not True or p['same_player_perspective'] is not True):
        return 'provenance_unqualified'
    for name, path in artifacts.items():
        if path is None or _digest(path) != p[name + '_sha256']:
            return 'evidence_unverified'
    c = reference['clock']
    if c['basis'] != 'host_monotonic' or not _number(c['uncertainty_s'], .25):
        return 'clock_unqualified'
    if reference['binding']['map_id'] != 'DragonShire' or reference['binding']['perspective'] != 'native_player':
        return 'binding_mismatch'
    return None


def _verified_clip(reference, evidence, clock_evidence):
    """Hash and inspect the SAME bounded bytes; never decode/OCR or extract."""
    try:
        data = _read(evidence, 17 * 2**20, 'clip_limit')
        clock_data = _read(clock_evidence, 128 * 1024, 'clip_index_limit')
        p = reference['provenance']
        if (hashlib.sha256(data).hexdigest() != p['evidence_sha256']
                or hashlib.sha256(clock_data).hexdigest() != p['clock_evidence_sha256']):
            return 'evidence_unverified', None
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if (not 3 <= len(members) <= 401 or len({m.filename for m in members}) != len(members)
                    or any(m.compress_type != zipfile.ZIP_STORED or m.file_size > 512 * 1024 for m in members)):
                return 'evidence_unverified', None
            index_data = archive.read('index.json')
            if len(index_data) > 128 * 1024 or index_data != clock_data:
                return 'evidence_unverified', None
            index = _load(index_data)
            if not (_closed(index, 'schema_version session_token clock_basis transcription frames max_gap_s max_capture_s complete')
                    and type(index['schema_version']) is int and index['schema_version'] == 1
                    and index['complete'] is True
                    and index['clock_basis'] == 'host_monotonic'
                    and index['transcription'] == 'manual_required'
                    and type(index['frames']) is list and 2 <= len(index['frames']) <= 400):
                return 'evidence_unverified', None
            if index['session_token'] != reference['binding']['session_token']:
                return 'clip_binding_mismatch', None
            previous, gap, window, total = None, 0, 0, 0
            names = {'index.json'}
            for i, f in enumerate(index['frames']):
                name = f'frame-{i:04d}.bmp'
                if not (_closed(f, 'member started_s finished_s sha256') and f['member'] == name
                        and _number(f['started_s']) and _number(f['finished_s'])
                        and f['started_s'] <= f['finished_s'] and _hex(f['sha256'], 64)):
                    return 'evidence_unverified', None
                if previous is not None:
                    if previous > f['started_s']:
                        return 'evidence_unverified', None
                    gap = max(gap, f['started_s'] - previous)
                previous = f['finished_s']
                window = max(window, f['finished_s'] - f['started_s'])
                frame_data = archive.read(name)
                total += len(frame_data)
                if total > 16 * 2**20 or hashlib.sha256(frame_data).hexdigest() != f['sha256']:
                    return 'evidence_unverified', None
                names.add(name)
            if names != {m.filename for m in members}:
                return 'evidence_unverified', None
            if (not _number(index['max_gap_s']) or not _number(index['max_capture_s'])
                    or abs(index['max_gap_s'] - gap) > 1e-9 or abs(index['max_capture_s'] - window) > 1e-9):
                return 'evidence_unverified', None
            if reference['clock']['uncertainty_s'] + 1e-9 < window:
                return 'clock_unqualified', None
            return None, {'from_s': index['frames'][0]['finished_s'],
                          'to_s': index['frames'][-1]['started_s'], 'resolution_s': gap + window}
    except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile):
        return 'evidence_unverified', None


def _match_link_reason(reference, path):
    try:
        data = _read(path, 65536, 'match_link_limit')
        if hashlib.sha256(data).hexdigest() != reference['provenance']['match_link_sha256']:
            return 'evidence_unverified'
        w = _load(data)
        if not (_closed(w, 'schema_version dataset session_token map_id perspective scenario same_uninterrupted_match identity_verified_privately journal_sha256 evidence_sha256')
                and type(w['schema_version']) is int and w['schema_version'] == 1
                and w['dataset'] == reference['dataset']
                and all(w[k] == reference['binding'][k] for k in ('session_token', 'map_id', 'perspective'))
                and w['map_id'] == 'DragonShire' and w['perspective'] == 'native_player'
                and w['scenario'] == 'private_local_9bots' and w['same_uninterrupted_match'] is True
                and w['identity_verified_privately'] is True
                and w['journal_sha256'] == reference['journal_sha256']
                and w['evidence_sha256'] == reference['provenance']['evidence_sha256']):
            return 'match_link_unqualified'
    except (OSError, ValueError, TypeError, KeyError):
        return 'match_link_unqualified'
    return None


def _sample_reason(reference, matches, clean, samples, clip):
    if not matches:
        return 'observation_missing', None
    if len(matches) != 1:
        return 'observation_ambiguous', None
    row = matches[0]
    c = row.get('comparison')
    if type(c) is not dict:
        return 'binding_missing', None
    b = reference['binding']
    if (b['map_id'] != 'DragonShire' or b['perspective'] != 'native_player'
            or any(c.get(k) != b[k] for k in ('session_token', 'map_id', 'perspective'))):
        return 'binding_mismatch', None
    if clean['value_status'] != 'exported':
        return 'objective_unavailable', None
    start, end = c.get('read_started_s'), c.get('read_finished_s')
    if (c.get('clock_basis') != 'host_monotonic' or not _number(start) or not _number(end)
            or start > end):
        return 'native_time_unknown', None
    # Normalization took place somewhere in the measured read call. Enlarge its
    # bracket by ORIGINAL receipt age and read window; never renew the receipt.
    earliest = start - clean['age_s'] - clean['read_window_s']
    interval = [earliest, end]
    if earliest < 0 or end - earliest > .5:
        return 'native_uncertainty', interval
    if not samples:
        return 'reference_missing', interval
    if len(samples) != 1:
        return 'reference_ambiguous', interval
    s = samples[0]
    if not all(_number(s[k]) for k in ('stable_from_s', 'stable_to_s', 'boundary_uncertainty_s')):
        return 'time_unknown', interval
    if s['boundary_uncertainty_s'] + 1e-9 < clip['resolution_s']:
        return 'reference_resolution_unqualified', interval
    margin = reference['clock']['uncertainty_s'] + s['boundary_uncertainty_s']
    if (s['boundary_uncertainty_s'] > .25 or s['stable_to_s'] - s['stable_from_s'] > 30
            or not clip['from_s'] <= s['stable_from_s'] + margin <= earliest <= end <= s['stable_to_s'] - margin <= clip['to_s']):
        return 'time_not_contained', interval
    return None, interval


def _native_value(value, field):
    if field == 'phase':
        return value['phase']
    if field in ('sun.owner', 'moon.owner'):
        return value['shrines'][0 if field == 'sun.owner' else 1]['owner']
    family, key = field.split('.')
    return value[family][key]


def compare(journal, references, *, evidence=None, match_link=None, clock_evidence=None):
    reference = _load(_read(references, 65536, 'reference_limit'))
    _validate_reference(reference)
    data = _read(journal, 4 * 2**20, 'journal_limit')
    lines = data.splitlines()
    if len(lines) > 10000 or any(len(line) > 65536 for line in lines):
        raise ValueError('journal_limit')
    rows = [_load(line) for line in lines]
    if any(type(row) is not dict for row in rows):
        raise ValueError('invalid_journal')
    global_reason = _global_reason(reference, data, {'evidence': evidence, 'match_link': match_link,
                                                    'clock_evidence': clock_evidence})
    clip = None
    if global_reason is None:
        global_reason, clip = _verified_clip(reference, evidence, clock_evidence)
    observations = [r for r in rows if r.get('event') == 'observation']
    # Imported files are not trusted to preserve the collector's single-context
    # boundary. Refuse merged streams, even when a selected cycle looks valid.
    contexts = {json.dumps([r.get('session'), r.get('comparison', {}).get('session_token')], sort_keys=True)
                for r in observations if type(r.get('comparison')) is dict}
    if global_reason is None and len(contexts) > 1:
        global_reason = 'journal_context_ambiguous'
    if global_reason is None:
        global_reason = _match_link_reason(reference, match_link)
    cycles = sorted({r['cycle'] for r in reference['samples']}) or [None]
    fields = []
    for cycle in cycles:
        matches = [r for r in observations if r.get('cycle') == cycle]
        row = matches[0] if len(matches) == 1 else {}
        stored = row.get('objective', {})
        stored = stored if type(stored) is dict else {}
        state = {'objective_qualification': stored}
        if stored.get('family') == 'dragon' and type(stored.get('value')) is dict:
            state['objective'] = dict(stored['value'], map_id='DragonShire',
                                      t=stored.get('source_mission_t_s'))
        clean = objective_summary(state)
        for field in FIELDS:
            samples = [r for r in reference['samples'] if r['cycle'] == cycle and r['field'] == field]
            status, reason, native, expected = 'non_comparable', 'reference_missing', None, None
            reason, interval = ((global_reason, None) if global_reason else
                                _sample_reason(reference, matches, clean, samples, clip))
            if reason is None:
                native = _native_value(clean['value'], field)
                expected = samples[0]['value']
                if native in (None, 'unknown') or expected in (None, 'unknown'):
                    reason = 'value_unknown'
                elif field in ('sun.owner', 'moon.owner') and (type(native) is int or type(expected) is int):
                    # HUD blue/red is player-relative, not proof of native team
                    # index. Neutral has no such ambiguity; no guessed mapping.
                    reason = 'team_mapping_unqualified'
                else:
                    status = 'compared' if native == expected else 'divergent'
                    reason = 'exact_value' if status == 'compared' else 'value_mismatch'
            fields.append({'cycle': cycle, 'field': field, 'status': status,
                           'reason': reason, 'native': native, 'reference': expected,
                           'source_monotonic_interval_s': interval})
    return {'event': 'objective_comparison', 'mode': MODE, 'current_permission': False,
            'dataset': reference['dataset'], 'provenance': 'operator_attested',
            'fields': fields, 'counts': {s: sum(r['status'] == s for r in fields)
                                       for s in ('compared', 'divergent', 'non_comparable')}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', required=True, type=Path, help='closed historical events.jsonl')
    parser.add_argument('--references', required=True, type=Path, help='manual closed-schema JSON; not OCR')
    parser.add_argument('--evidence', type=Path, help='independent HUD video; hash checked, content operator-attested')
    parser.add_argument('--match-link', type=Path, help='same private match/player perspective witness')
    parser.add_argument('--clock-evidence', type=Path, help='measured host-monotonic video calibration witness')
    args = parser.parse_args(argv)
    try:
        result = compare(**vars(args))
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({'event': 'objective_comparison_error', 'mode': MODE,
                          'current_permission': False, 'code': 'invalid_or_unavailable_comparison'}))
        return 1
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
