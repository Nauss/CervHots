#!/usr/bin/env python
"""Private UNRELEASED full native pipeline instrumentation; no coach/audio/GUI.

Live clocks are recorded by forwarding the real monotonic clock, never frozen.
Only this diagnostic process temporarily enables the candidate boolean path;
product VALIDATED_MAPS stays empty. No output is sent to a model or speaker.
A real initData buffer is reread/decoded/rechecked for EVERY sample. Discovery
is separately bounded and never grants cached context permissions.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hotstate.context import ContextProbe
from hotstate.match import ActiveMatch
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.positions import AlliedPositions, _RecordedMemory
from hotstate.reader import ProcessBackend, snapshot as read_snapshot
from hotstate.visibility import CurrentVisibility
from cerveau.state import snapshot as normalize
from cerveau.runner import tactical_key
from etudes.rea.scripts.capture_positions import (
    TraceMemory, ReplayTrace, GameWindowState, capture_game_image, frozen_sources, utc,
)

REAL_CLOCK = time.monotonic
PIPELINE_KIND = 'unreleased_full_native_visibility_pipeline'


class RecordedClock:
    def __init__(self, clock):
        self.clock, self.values = clock, []
    def __call__(self):
        value = self.clock()
        self.values.append(value)
        return value


class PipelineMemory(ProcessBackend):
    """RO process proxy so reader.snapshot keeps its normal live source path.

    No OpenProcess here: CLI owns the already verified ProcessBackend. Tests and
    historical replays use explicitly labelled fixtures, never live claims.
    """
    def __init__(self, backend, address, size, *, native_context=False):
        if type(size) is not int or not 16 <= size <= 65536:
            raise NativeUnavailable('taille_initdata_pipeline_invalide')
        if not (native_context and address is None) and (type(address) is not int or not 0x10000 <= address < 0x800000000000 - size):
            raise NativeUnavailable('adresse_initdata_pipeline_invalide')
        self.trace = TraceMemory(backend)
        self.module_base = backend.module_base
        self.recorded_non_atomic = getattr(backend, 'recorded_non_atomic', False)
        self.address, self.size, self.context_bytes = address, size, None
    def read_memory(self, address, size):
        return self.trace.read_memory(address, size)
    def positions_clock(self):
        return self.trace.positions_clock()
    def regions_bytes(self):
        data = self.read_memory(self.address, self.size)
        if data is None or len(data) != self.size:
            raise NativeUnavailable('initdata_pipeline_incomplet')
        self.context_bytes = data
        yield self.address, data
    def recheck_context(self):
        if self.context_bytes is None or self.read_memory(self.address, self.size) != self.context_bytes:
            raise NativeUnavailable('initdata_pipeline_dechire')


def take_sample(backend, probe, address, size=65536, *, native_profile=None, clock=None):
    """Actual reader.snapshot -> read_state -> normalizer -> key, same process.

    No fabricated roster/envelope and no replay input in the live CLI. Raw reads
    may include private user bytes: they stay ONLY in ignored private traces.
    """
    from hotstate.native_context import NativeContextProbe
    native_context = isinstance(probe, NativeContextProbe)
    memory = PipelineMemory(backend, address, size, native_context=native_context)
    recorded = RecordedClock(REAL_CLOCK if clock is None else clock)
    row = {'wall_before': utc(), 'monotonic_before': REAL_CLOCK(),
           'status': 'rejected', 'mode': 'unreleased_pipeline_diagnostic',
           'recorded_non_atomic': memory.recorded_non_atomic,
           'execution_kind': ('fixture_or_recorded_clock_NOT_LIVE'
                              if native_profile is not None or clock is not None
                              else 'acquisition_real_monotonic_record_only')}
    optional_errors = []
    real_read = CurrentVisibility.read
    def observed_read(reader, context, **kwargs):
        try:
            return real_read(reader, context, **kwargs)
        except NativeUnavailable as exc:
            optional_errors.append(str(exc))
            raise
    try:
        with contextlib.ExitStack() as stack:
            # Record-only live forwarding. Replay tests explicitly supply a
            # historical clock sequence; they are NOT a fresh live acquisition.
            stack.enter_context(patch('time.monotonic', recorded))
            stack.enter_context(patch('hotstate.visibility.VALIDATED_MAPS', ('Volskaya',)))
            stack.enter_context(patch.object(CurrentVisibility, 'read', observed_read))
            if memory.recorded_non_atomic:
                raise NativeUnavailable('capture_pipeline_non_atomique')
            whole_started = time.monotonic()
            pre = NativeReader(memory, profile=native_profile)
            initial = ActiveMatch().observe(pre)
            # No trigger counter claim from the targeted initData-only region.
            raw = read_snapshot(memory, {'triggers': {}}, context=probe, native_profile=native_profile)
            row['raw'] = raw
            row['context_status'] = probe.reason
            row['map_metadata_observed'] = {k: raw['meta'][k] for k in ('map_id', 'map') if k in raw['meta']}
            if raw['meta'].get('native_status') != 'valide':
                raise NativeUnavailable(raw['meta'].get('native_status', 'coeur_pipeline_absent'))
            if native_context:
                probe.recheck(memory)
            else:
                memory.recheck_context()
            row['native_match_equals_context'] = raw['meta'].get('match_id') == initial['match_id']
            if not row['native_match_equals_context']:
                raise NativeUnavailable('contexte_pipeline_partie_native_incoherente')
            clean = normalize(raw)
            row['normalized'] = clean
            row['tactical_key'] = tactical_key(clean)
            row['receipt_ages_s'] = {key: time.monotonic() - packet['acquisition']['monotonic_s']
                for key in ('perspective', 'positions', 'visibility')
                if isinstance((packet := raw.get(key)), dict) and 'acquisition' in packet}
            if 'visibility' not in clean:
                raise NativeUnavailable('visibilite_pipeline_absente')
            if any(h['team'] != clean['ally_team'] and any(k in h for k in
                   ('health', 'health_max', 'resource', 'resource_max', 'x', 'y', 'cooldowns', 'talents'))
                   for h in clean['heroes']):
                raise AssertionError('enemy tactical leak in diagnostic normalizer')
            row['whole_snapshot_window_s'] = time.monotonic()-whole_started
            if not 0 <= row['whole_snapshot_window_s'] <= 0.125:
                raise NativeUnavailable('fenetre_pipeline_globale_depassee')
            row['status'] = 'accepted'
    except (NativeUnavailable, ValueError) as exc:
        row['rejected'] = str(exc)
    row.update(wall_after=utc(), monotonic_after=REAL_CLOCK(), reads=memory.trace.reads,
               bytes_requested=memory.trace.bytes_requested, wall_clock_calls=recorded.values,
               optional_visibility_refusals=optional_errors)
    return row


def replay_sample(row, module_base, probe, address, size=65536, *, native_profile=None):
    """Exact historical audit only; no original receipt is trusted or imported."""
    replay = ReplayTrace(module_base, row['reads'])
    # Global recorded clock covers ALL native/optional/freshness calls. Do not
    # also consume ReplayTrace.positions_clock's separate legacy stream.
    shadow = SimpleNamespace(module_base=module_base, read_memory=replay.read_memory,
                             recorded_non_atomic=row.get('recorded_non_atomic', False))
    times = iter(row['wall_clock_calls'])
    # Map cache is an external immutable-handle input, not live memory. Replay
    # the metadata actually observed in this row, never a future replay value.
    with patch.object(probe, 'map_resolver', lambda handles: dict(row.get('map_metadata_observed', {}))), \
            patch.object(probe, 'map_cache', {}):
        repeated = take_sample(shadow, probe, address, size, native_profile=native_profile,
                               clock=lambda: next(times))
    replay.finish()
    sentinel = object()
    if next(times, sentinel) is not sentinel:
        raise AssertionError('unconsumed full-pipeline clock')
    if repeated.get('rejected') != row.get('rejected') or repeated['status'] != row['status']:
        raise AssertionError('pipeline refusal differs')
    if repeated.get('normalized') != row.get('normalized') or repeated.get('tactical_key') != row.get('tactical_key'):
        raise AssertionError('pipeline boundary/key differs')
    if repeated.get('whole_snapshot_window_s') != row.get('whole_snapshot_window_s'):
        raise AssertionError('whole pipeline clock differs')
    repeated['execution_kind'] = 'historical_exact_replay_NOT_LIVE'
    return repeated


def capture_frame(backend, probe, address, size=65536, *, screenshot=None, **options):
    row = {'wall_before': utc(), 'monotonic_before': REAL_CLOCK(),
           'before': take_sample(backend, probe, address, size, **options)}
    if screenshot is not None:
        image = {'wall_before': utc(), 'monotonic_before': REAL_CLOCK()}
        image.update(screenshot())
        image.update(wall_after=utc(), monotonic_after=REAL_CLOCK())
        row['image'] = image
    row['after'] = take_sample(backend, probe, address, size, **options)
    row.update(wall_after=utc(), monotonic_after=REAL_CLOCK())
    return row


def bounded_regions(backend, *, max_bytes=256 * 1024 ** 2, max_seconds=20, diagnostics=None):
    """Finite RO discovery; ≤1MiB request, overlap for a ≤64KiB initData buffer."""
    class MBI(ctypes.Structure):
        _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
            ('AllocationProtect', wt.DWORD), ('__align', wt.DWORD), ('RegionSize', ctypes.c_size_t),
            ('State', wt.DWORD), ('Protect', wt.DWORD), ('Type', wt.DWORD)]
    if not 0 < max_bytes <= 256 * 1024 ** 2 or not 0 < max_seconds <= 20:
        raise ValueError('discovery limits invalid')
    address, requested, queries = 0, 0, 0
    chunks = read_bytes = failures = readable = 0
    deadline = REAL_CLOCK() + max_seconds
    reason = 'consumer_stopped'
    try:
        while address < 0x800000000000 and requested < max_bytes and queries < 16384 and REAL_CLOCK() < deadline:
            mbi = MBI(); queries += 1
            if not backend.k32.VirtualQueryEx(backend.handle, ctypes.c_void_p(address),
                                             ctypes.byref(mbi), ctypes.sizeof(mbi)):
                reason = 'query_failed'
                break
            base, size = mbi.BaseAddress or 0, mbi.RegionSize or 0x1000
            if base + size <= address:
                reason = 'invalid_region_progress'
                break
            if (mbi.State == 0x1000 and mbi.Type == 0x20000
                    and not mbi.Protect & 0x100 and mbi.Protect & 0xff != 1):
                readable += 1
                cursor = base
                while cursor < base + size and requested < max_bytes and REAL_CLOCK() < deadline:
                    count = min(1024 ** 2, base + size - cursor, max_bytes - requested)
                    requested += count; chunks += 1
                    data = backend.read_memory(cursor, count)
                    if data:
                        read_bytes += len(data)
                        yield cursor, data
                    else:
                        failures += 1
                    cursor += max(1, count - 65536) if count > 65536 else count
            address = base + size
    finally:
        if diagnostics is not None:
            now = REAL_CLOCK()
            if reason == 'consumer_stopped':
                if requested >= max_bytes: reason = 'byte_limit'
                elif queries >= 16384: reason = 'query_limit'
                elif now >= deadline: reason = 'time_limit'
                elif address >= 0x800000000000: reason = 'address_space_end'
            diagnostics.update(query_count=queries, readable_regions=readable,
                read_requests=chunks, bytes_requested=requested, bytes_read=read_bytes,
                read_failures=failures, elapsed_s=max(0, now - (deadline - max_seconds)),
                stop_reason=reason, max_bytes=max_bytes, max_seconds=max_seconds,
                max_queries=16384, max_request_bytes=1024 ** 2)


def discover_context(backend, probe, *, regions=None, native_profile=None, diagnostics=None):
    """Select a private address by native initial identity, NOT by uniqueness alone."""
    acquired = REAL_CLOCK(); recorded = _RecordedMemory(backend)
    n = NativeReader(recorded, profile=native_profile)
    active = ActiveMatch().observe(n)
    AlliedPositions(n)._identity(n, json.loads((ROOT / 'hotstate/hero_ids.json').read_text()))
    for address, data in recorded.read_set:
        if backend.read_memory(address, len(data)) != data:
            raise NativeUnavailable('identite_discovery_dechiree')
    if not 0 <= REAL_CLOCK() - acquired <= 0.125:
        raise NativeUnavailable('identite_discovery_perimee')
    probe.begin(); total = anchors = 0
    scan = {}
    iterator = iter(bounded_regions(backend, diagnostics=scan) if regions is None else regions)
    reason = 'no_matching_context'
    try:
        for base, data in iterator:
            total += len(data)
            anchors += data.count(probe.anchor)
            probe.feed(base, data)
            if probe.reason == 'contexte_ambigu' or probe.attempts >= 128:
                reason = 'decoder_limit_or_ambiguous_context'
                raise NativeUnavailable('contexte_discovery_ambigu')
            for key, context in probe.contexts.items():
                digest = hashlib.sha256(key[0].to_bytes(4, 'little') + b''.join(key[1])).hexdigest()
                if digest == active['match_id']:
                    handles = tuple(context['_cache_handles'])
                    metadata = probe.map_resolver(handles)
                    if metadata.get('map_id') != 'Volskaya':
                        reason = 'unknown_map'
                        raise NativeUnavailable('carte_discovery_inconnue')
                    probe.map_cache[handles] = metadata
                    reason = 'selected'
                    return {'address': probe.candidate_addresses[key][0], 'size': 65536,
                            'native_match_id': digest, 'bytes_scanned': total,
                            'map_metadata': metadata, 'permission': 'NONE_redecode_and_check_each_sample'}
        raise NativeUnavailable('initdata_actif_non_trouve_budget_borne')
    finally:
        if hasattr(iterator, 'close'):
            iterator.close()
        if diagnostics is not None:
            hashes = sorted(hashlib.sha256(key[0].to_bytes(4, 'little') + b''.join(key[1])).hexdigest()
                            for key in probe.contexts)
            diagnostics.update(active_match_id=active['match_id'], context_match_hashes=hashes,
                matching_contexts=sum(h == active['match_id'] for h in hashes),
                decoded_contexts=len(hashes), decoder_attempts=probe.attempts,
                decoder_rejections=probe.rejected, probe_reason=probe.reason,
                anchor_occurrences=anchors, bytes_fed=total, scan=scan,
                stop_reason=reason, elapsed_s=max(0, REAL_CLOCK() - acquired),
                mode='private_discovery_diagnostics_NO_raw_seed_cache_label_or_payload')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--preflight', action='store_true')
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--player-file', type=Path, help='private UTF8 game label, not a credential')
    context = parser.add_mutually_exclusive_group()
    context.add_argument('--context-address', type=lambda s: int(s, 0))
    context.add_argument('--discover-context', action='store_true')
    context.add_argument('--native-context', action='store_true', help='read proven CURRENT native InitData fields; no heap scan')
    parser.add_argument('--context-bytes', type=int, default=65536)
    parser.add_argument('--candidate-visibility', action='store_true')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--duration', type=float, default=240)
    parser.add_argument('--interval', type=float, default=0.5)
    parser.add_argument('--png', action='store_true')
    args = parser.parse_args(argv)
    extras = tuple(ROOT / p for p in ('etudes/rea/scripts/capture_visibility_pipeline.py',
                     'cerveau/state.py', 'cerveau/runner.py', 'cerveau/brain.py', 'kb/data/map_timings.json'))
    commit, manifest = frozen_sources(args.expected_commit, extra_paths=extras)
    if args.preflight:
        from PIL import ImageGrab
        from hotstate.protocols import load_protocol
        protocol = load_protocol()
        print(f'OFFLINE_PIPELINE_PREFLIGHT_OK {commit} {len(manifest)} files; {protocol.__name__}; no process opened')
        return 0
    if (not args.candidate_visibility or args.player_file is None or args.out is None
            or not (args.native_context or args.discover_context or args.context_address is not None)
            or not 0 < args.duration <= 300 or not 0.5 <= args.interval <= 10
            or not 16 <= args.context_bytes <= 65536
            or (args.context_address is not None and not 0x10000 <= args.context_address < 0x800000000000 - args.context_bytes)):
        parser.error('explicit candidate/player/out/context consent and bounded parameters required')
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / 'out') or out.suffix != '.jsonl':
        parser.error('output must be a new private worktree out/ JSONL')
    common = Path(subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=ROOT,text=True).strip())
    if not common.is_absolute(): common = (ROOT / common).resolve()
    player_file = args.player_file.resolve()
    if not any(player_file.is_relative_to(p) for p in (ROOT/'out', common.parent/'out')) or player_file.stat().st_size > 256:
        parser.error('player-file must be a short private out/ file, never a config/credential file')
    player = player_file.read_text(encoding='utf-8').strip()
    if '\n' in player or '\r' in player or not 2 <= len(player) <= 64:
        parser.error('invalid private game label')
    probe = ContextProbe(player)
    if args.native_context:
        from hotstate.native_context import NativeContextProbe
        probe = NativeContextProbe(player)
    from hotstate.protocols import load_protocol
    protocol = load_protocol()
    grab = None
    if args.png:
        from PIL import ImageGrab
        grab = ImageGrab.grab
    out.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive output is acquired BEFORE opening a process; no evidence overwrite.
    with out.open('x', encoding='utf-8') as stream, contextlib.ExitStack() as files:
        # Reserve a separate private report before OpenProcess. Even a bounded
        # discovery refusal must leave diagnostics, not just an empty JSONL.
        report_stream = (files.enter_context(out.with_suffix('.discovery.json').open('x', encoding='utf-8'))
                         if args.discover_context else None)
        backend = ProcessBackend(args.pid)
        try:
            diagnostics = {}
            report = {'kind': 'private_bounded_discovery_diagnostics', 'commit': commit,
                      'status': 'rejected', 'wall_before': utc(), 'diagnostics': diagnostics,
                      'sources_sha256': manifest, 'publication': 'NONE'}
            try:
                discovery = (discover_context(backend, probe, diagnostics=diagnostics)
                             if args.discover_context else None)
                report['status'] = 'selected'
            except Exception as exc:
                # Never serialize arbitrary decoder/IO exceptions containing
                # private bytes. Known native refusal strings contain no data.
                report['rejected'] = str(exc) if isinstance(exc, NativeUnavailable) else type(exc).__name__
                raise
            finally:
                if report_stream is not None:
                    report['wall_after'] = utc()
                    json.dump(report, report_stream, indent=2, allow_nan=False)
                    report_stream.flush()
            address = discovery['address'] if discovery else args.context_address
            window = GameWindowState(backend.pid) if grab else None
            stream.write(json.dumps({'kind':PIPELINE_KIND,
                'commit':commit,'sources_sha256':manifest,'module_base':backend.module_base,
                'context_address':address,'context_size':args.context_bytes,'discovery':discovery,
                'context_mode':'initdata_native_fields' if args.native_context else 'serialized_initdata_memory',
                'wire_decoder_used_for_context':not args.native_context,
                'protocol':protocol.__name__,'png':args.png,'coach_or_audio':False,
                'clock':'record_only_REAL_monotonic_live; historical replay separately labelled',
                'publication':'candidate gate in THIS private diagnostic process only; product gate unchanged',
                'trigger_counters':'not claimed; targeted initData region only'})+'\n');stream.flush()
            deadline, sequence = REAL_CLOCK()+args.duration, 0
            while REAL_CLOCK() < deadline:
                png = out.with_name(f'{out.stem}-{sequence:05d}.png')
                row = capture_frame(backend, probe, address, args.context_bytes,
                    screenshot=(lambda: capture_game_image(png, window, grab)) if grab else None)
                row['sequence'] = sequence
                stream.write(json.dumps(row,allow_nan=False)+'\n');stream.flush();sequence += 1
                delay = min(args.interval,deadline-REAL_CLOCK())
                if delay > 0: time.sleep(delay)
        finally:
            backend.close()
    print(f'Private unreleased pipeline trace saved: {out}; no coach/audio/publication.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
