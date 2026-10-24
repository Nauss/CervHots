"""Braxis diagnostic command. Offline/preflight never opens a process.

Live is an explicit, bounded operator-only private-game diagnostic, not Coach.
"""
from pathlib import Path
import datetime
import json
import math
import time

from . import braxis

# Closed public vocabulary. Unknown exceptions/decoder text stay private.
REASONS = frozenset('''whole_budget whole_time address_or_size transport_error short_read
build_guard diagnostic_code_pin diagnostic_dependency_unavailable module_size compiler_root_null global_table_absent
named_global_not_yet_published named_type_absent type_bucket_bound type_bucket_changed
compiler_changed not_global_kind108 function_table_null function_slot_null
frame_function_name_length frame_wrong_function frame_publication_changed
private_player_label_missing contexte_natif_capture_non_atomique
profil_natif_invalide build_natif_non_pris_en_charge signature_native_invalide
aucune_simulation_active memoire_native_incomplete horloge_native_invalide
contexte_natif_invalide_ou_ambigu contexte_natif_partie_changee contexte_natif_perime
contexte_natif_dechire context_initial_unavailable channel_bytes_not_recorded'''.split())


def public_attempt(raw):
    """Closed schema: no pointers, names, decoded structures, identity or clocks."""
    channels = {}
    allowed = {'clock_before', 'clock_after', 'context', 'context_after', 'compiler', 'type',
               *(f'frames.{index}' for index, _ in braxis.FUNCTIONS)}
    for name in sorted(allowed):
        if name not in raw['channels']:
            continue
        row = raw['channels'][name]
        channels[name] = {key: row[key] for key in
                          ('status', 'requests', 'bytes_requested', 'elapsed_s') if key in row}
        if 'reason' in row:
            reason = row['reason']
            channels[name]['reason'] = reason if reason in REASONS else 'diagnostic_refused'
    return {'schema': 'braxis-causal-summary-v1', 'channels': channels,
            'build_status': raw['build']['status'],
            'measurement': braxis.measure(channels), 'target_map': raw['target_map'],
            'physical_requests': raw['physical_requests'], 'bytes_requested': raw['bytes_requested'],
            'elapsed_s': raw['elapsed_s'], 'mission_interval_recorded': raw['mission_clock'] is not None,
            'perspective': 'not_validated', 'normalized_acquisitions': 0, 'objective': None, 'coach': False}


def run_session(out, stops, *, seconds, interval, max_attempts, player_label,
                backend_factory, clock=time.monotonic, sleep=time.sleep,
                collect_attempt=braxis.collect):
    """Exclusive one-game session, with cost records and cooperative STOP.

    Bytes acquired across STOP/deadline or identity change are discarded, not
    retrospectively emitted. OS reads are synchronous: STOP is cooperative.
    """
    if (type(seconds) not in (int, float) or not math.isfinite(seconds) or not 1 <= seconds <= 120
            or type(interval) not in (int, float) or not math.isfinite(interval) or not 1 <= interval <= 10
            or type(max_attempts) is not int or not 1 <= max_attempts <= 60):
        raise ValueError('session_bounds')
    out = Path(out)
    stops = [Path(stop) for stop in stops] + [out / 'STOP']
    summary = {'stop_reason': 'attempt_limit', 'attempts': 0, 'persisted': 0,
               'public_persisted': 0,
               'discarded': 0, 'physical_requests': 0, 'bytes_requested': 0,
               'objective': None, 'coach': False, 'normalized_acquisitions': 0}
    if any(stop.exists() for stop in stops):
        return {**summary, 'stop_reason': 'STOP'}
    out.mkdir(parents=True, exist_ok=False)
    (out / 'PRIVATE').mkdir(mode=0o700)
    started = clock()
    summary['started_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    deadline = started + seconds
    backend = None
    match = None

    def stopped():
        if any(stop.exists() for stop in stops):
            return 'STOP'
        if clock() >= deadline:
            return 'duration'
        return None

    try:
        with (out / 'PRIVATE/readsets.jsonl').open('x', encoding='utf-8') as private, \
                (out / 'attempts.jsonl').open('x', encoding='utf-8') as public:
            reason = stopped()
            if reason:
                summary['stop_reason'] = reason
            else:
                backend = backend_factory()
                for _ in range(max_attempts):
                    reason = stopped()
                    if reason:
                        summary['stop_reason'] = reason
                        break
                    raw = collect_attempt(backend, player_label=player_label)
                    summary['attempts'] += 1
                    raw['attempt_index'] = summary['attempts']
                    raw['recorded_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    summary['physical_requests'] += raw['physical_requests']
                    summary['bytes_requested'] += raw['bytes_requested']
                    reason = stopped()
                    identity = raw['channels'].get('context', {}).get('result', {}).get('meta', {}).get('match_id')
                    if match and identity and identity != match:
                        reason = reason or 'match_changed'
                    if match and not identity:
                        reason = reason or 'context_lost'
                    if reason:
                        summary['discarded'] += 1
                        summary['stop_reason'] = reason
                        break
                    match = match or identity
                    private.write(json.dumps(raw, allow_nan=False) + '\n')
                    private.flush()
                    summary['persisted'] += 1
                    # A slow private flush can cross STOP/deadline. No public
                    # emission or further read afterwards.
                    reason = stopped()
                    if reason:
                        summary['stop_reason'] = reason
                        break
                    public.write(json.dumps(public_attempt(raw), allow_nan=False) + '\n')
                    public.flush()
                    summary['public_persisted'] += 1
                    reason = stopped()
                    if reason:
                        summary['stop_reason'] = reason
                        break
                    if raw['build']['status'] != 'observed':
                        summary['stop_reason'] = 'build_refused'
                        break
                    if raw['target_map'] == 'wrong_map':
                        summary['stop_reason'] = 'wrong_map'
                        break
                    if summary['attempts'] >= max_attempts:
                        break
                    until = min(clock() + interval, deadline)
                    while clock() < until and not stopped():
                        sleep(min(.05, until - clock()))
    except KeyboardInterrupt:
        summary['stop_reason'] = 'interrupted'
    except (Exception, SystemExit):
        summary['stop_reason'] = 'diagnostic_error'
        raise
    finally:
        try:
            if backend is not None:
                backend.close()
        finally:
            summary['elapsed_s'] = clock() - started
            summary['finished_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


def preflight(player_file=None):
    """Local sources/profile and explicit identity input only; zero native IO."""
    import hashlib
    import importlib.util
    from cerveau.player_identity import read_player_label
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / 'hotstate').glob('*.py')) + sorted((root / 'hotstate/profiles').glob('*.json'))
    paths += [root / 'cerveau/player_identity.py', root / 'hotstate/BRAXIS_DIAGNOSTIC.md']
    source_hashes = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in paths if path.is_file()}
    pins = json.loads(braxis.PROFILE.read_text(encoding='utf-8'))
    if len(pins['code']) != 6 or pins['image_size'] != 73064448:
        raise ValueError('diagnostic_profile_invalid')
    if player_file:
        read_player_label(player_file)
    return {'schema': 'braxis-preflight-v1', 'backend_opened': False, 'live_authorized': False,
            'private_identity_loaded': player_file is not None,
            'limits': {'seconds': .125, 'reads': 8192, 'bytes': 1048576},
            'source_hashes': source_hashes, 'code_pins': len(pins['code']),
            'map_cache_dependency_available': importlib.util.find_spec('mpyq') is not None,
            'perspective': 'not_validated', 'coach': False, 'objective': None}


class ExactMemory:
    """Sequential byte-exact transport: never pads, maps or adds missing bytes."""
    def __init__(self, base, reads):
        self.module_base = base
        self.rows = iter(reads)
        self.count = 0

    def read_memory(self, address, size):
        try:
            row = next(self.rows)
        except StopIteration:
            raise ValueError('readset_exhausted') from None
        self.count += 1
        if (address, size) != (row['address'], row['size']):
            raise ValueError('replay_request_mismatch')
        return None if row['hex'] is None else bytes.fromhex(row['hex'])

    def finish(self):
        sentinel = object()
        if next(self.rows, sentinel) is not sentinel:
            raise ValueError('replay_unconsumed_reads')


def replay_channels(rows):
    """Only recorded metadata channels; never claims context/build/freshness."""
    decodes = {'compiler': braxis.decoders.compiler_global, 'type': braxis.decoders.named_type}
    for index, name in braxis.FUNCTIONS:
        decodes[f'frames.{index}'] = lambda tx, i=index, n=name: braxis.frame(tx, i, n)
    channels = {key: {'status': 'not_recorded', 'reason': 'channel_bytes_not_recorded', 'requests': 0}
                for key in (*decodes, 'context', 'clock_before', 'clock_after')}
    seen = set()
    for row in rows:
        kind = row['kind']
        if kind not in decodes or kind in seen:
            raise ValueError('replay_unknown_or_duplicate_channel')
        seen.add(kind)
        memory = ExactMemory(row['module_base'], row['reads'])
        # Decode exact historical bytes, not the elapsed time of today's disk IO.
        tx = braxis.WholeTx(memory, clock=lambda: 0.0)
        replay = braxis.run_channel(tx, decodes[kind])
        expected_reason = row.get('reason', row.get('result', {}).get('reason'))
        if (replay['status'] != row['status']
                or replay.get('reason') != expected_reason
                or (replay['status'] == 'observed' and replay['result'] != row['result'])):
            raise ValueError('replay_result_mismatch')
        memory.finish()
        channels[kind] = {key: replay[key] for key in ('status', 'requests', 'bytes_requested')}
        if 'reason' in replay:
            channels[kind]['reason'] = replay['reason'] if replay['reason'] in REASONS else 'diagnostic_refused'
    return {'channels': channels, 'measurement': braxis.measure(channels),
            'build_verified_by_replay': False, 'qualification': 'exact_recorded_channels_only',
            'perspective': 'not_recorded', 'mission_clock': None, 'objective': None, 'coach': False}


def replay_attempt(raw):
    """Replay product metadata slices; context/time/build are not requalified."""
    if raw.get('schema') != 'braxis-causal-v1' or len(raw['reads']) > 8192:
        raise ValueError('readset_schema_or_bound')
    if sum(row['size'] for row in raw['reads']) > 1048576:
        raise ValueError('readset_byte_bound')
    rows, excluded = [], {}
    for kind in ('compiler', 'type', *(f'frames.{index}' for index, _ in braxis.FUNCTIONS)):
        row = raw['channels'].get(kind)
        if row is None or row['status'] == 'not_attempted':
            continue
        if row.get('reason') in ('whole_budget', 'whole_time', 'transport_error'):
            excluded[kind] = {'status': 'not_replayed', 'reason': 'whole_boundary_or_transport'}
            continue
        start, end = row['read_start'], row['read_end']
        if not 0 <= start <= end <= len(raw['reads']) or end - start != row['requests']:
            raise ValueError('readset_channel_bounds')
        rows.append({**row, 'kind': kind, 'module_base': raw['module_base'],
                     'reads': raw['reads'][start:end]})
    result = replay_channels(rows)
    result['channels'].update(excluded)
    result['measurement'] = braxis.measure(result['channels'])
    return result


def main(argv=None, *, backend_factory=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight', action='store_true', help='disk-only: never opens game')
    modes.add_argument('--replay', type=Path, help='exact recorded per-channel JSONL only')
    modes.add_argument('--live', action='store_true', help='operator-only private game diagnostic')
    parser.add_argument('--operator-private-game', action='store_true')
    parser.add_argument('--player-file', type=Path, help='absolute bounded private UTF8 label file; never label in argv')
    parser.add_argument('--out', type=Path, help='new exclusive session directory')
    parser.add_argument('--stop', type=Path, action='append', default=[], help='absolute STOP file, repeatable')
    parser.add_argument('--seconds', type=int, default=90, choices=range(1, 121), metavar='1..120')
    parser.add_argument('--interval', type=int, default=3, choices=range(1, 11), metavar='1..10')
    parser.add_argument('--max-attempts', type=int, default=30, choices=range(1, 61), metavar='1..60')
    args = parser.parse_args(argv)
    try:
        if args.preflight:
            print(json.dumps(preflight(args.player_file), sort_keys=True))
            return 0
        if args.replay:
            with args.replay.open('rb') as stream:
                for index in range(61):
                    line = stream.readline(4 * 1048576 + 1)
                    if not line:
                        if index == 0:
                            raise ValueError('empty_readset')
                        break
                    if index == 60 or len(line) > 4 * 1048576:
                        raise ValueError('readset_bounds')
                    row = json.loads(line)
                    result = replay_attempt(row) if 'schema' in row else replay_channels([row])
                    print(json.dumps(result, sort_keys=True))
            return 0
        if (not args.operator_private_game or args.player_file is None or args.out is None
                or not args.stop or not args.out.is_absolute()
                or any(not path.is_absolute() for path in args.stop)):
            raise ValueError('operator_private_scope_required')
        from cerveau.player_identity import read_player_label
        player = read_player_label(args.player_file)
        if backend_factory is None:
            def backend_factory():
                # Check the map resolver dependency before any process handle.
                import mpyq  # noqa: F401
                from .reader import ProcessBackend
                return ProcessBackend()
        summary = run_session(args.out, args.stop, seconds=args.seconds, interval=args.interval,
                              max_attempts=args.max_attempts, player_label=player,
                              backend_factory=backend_factory)
        print(json.dumps(summary, sort_keys=True))
        return 0 if summary['stop_reason'] not in ('diagnostic_error', 'build_refused', 'wrong_map') else 2
    except (OSError, ValueError, ImportError, KeyError, TypeError, SystemExit):
        # No source paths, identity, decoder values or exception text on stdout.
        print(json.dumps({'status': 'refused', 'reason': 'diagnostic_unavailable', 'coach': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
