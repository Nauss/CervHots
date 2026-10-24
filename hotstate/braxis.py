"""Bounded Braxis publication diagnostics, never an objective producer."""
from pathlib import Path
import hashlib
import json
import struct
import time

from . import braxis_decoders as decoders
from .native import NativeUnavailable

Refused = decoders.Refused
PROFILE = Path(__file__).parent / 'profiles/98348-braxis.json'
FUNCTIONS = (
    (6003, 'libSCHO_gf_MMHOInitializeHiveControlCapturePoints'),
    (6007, 'libSCHO_gf_MMHOGetHiveControlBeaconOwners'),
    (6122, 'libSCHO_gt_MMHOHiveControlBeaconMonitor_Func'),
)


class WholeTx:
    """Shared WHOLE budget, no caching/dedup; attempted short reads cost too."""
    def __init__(self, memory, *, clock=time.perf_counter):
        self.memory = memory
        self.module_base = self.base = memory.module_base
        self.module_size = getattr(memory, 'module_size', None)
        self.recorded_non_atomic = getattr(memory, 'recorded_non_atomic', False)
        self.clock = clock
        self.start = clock()
        self.reads = []
        self.bytes = 0
        self.limit_s, self.limit_reads, self.limit_bytes = .125, 8192, 1048576

    def blocked(self):
        return (self.clock() - self.start >= self.limit_s
                or len(self.reads) >= self.limit_reads or self.bytes >= self.limit_bytes)

    def read(self, address, size):
        if (type(address) is not int or type(size) is not int
                or not 0 < size <= 65536 or not 0x10000 <= address < address + size < 0x800000000000):
            raise Refused('address_or_size')
        if self.blocked() or self.bytes + size > self.limit_bytes:
            raise Refused('whole_budget')
        self.bytes += size
        row = {'address': address, 'size': size, 'hex': None}
        self.reads.append(row)
        try:
            data = self.memory.read_memory(address, size)
        except OSError:
            row['transport_error'] = True
            raise Refused('transport_error') from None
        finally:
            row['elapsed_s'] = self.clock() - self.start
        row['hex'] = None if data is None else data.hex()
        if row['elapsed_s'] >= self.limit_s:
            raise Refused('whole_time')
        if data is None or len(data) != size:
            raise Refused('short_read')
        return data

    read_memory = read

    def u(self, address, fmt='Q'):
        return struct.unpack('<' + fmt, self.read(address, struct.calcsize('<' + fmt)))[0]


def run_channel(tx, decode):
    start, before, at = len(tx.reads), tx.bytes, tx.clock()
    if tx.blocked():
        return {'status': 'not_attempted', 'reason': 'whole_budget', 'requests': 0,
                'read_start': start, 'read_end': start, 'bytes_requested': 0, 'elapsed_s': 0.0}
    try:
        value = decode(tx)
        if tx.clock() - tx.start >= tx.limit_s:
            raise Refused('whole_time')
        result = {'status': 'observed', 'result': value}
    except (Refused, NativeUnavailable, UnicodeError, struct.error) as exc:
        status = 'not_attempted' if str(exc) == 'whole_budget' and len(tx.reads) == start else 'refused'
        result = {'status': status, 'reason': str(exc)}
    except (OSError, ImportError):
        result = {'status': 'refused', 'reason': 'diagnostic_dependency_unavailable'}
    return {**result, 'read_start': start, 'read_end': len(tx.reads),
            'requests': len(tx.reads) - start, 'bytes_requested': tx.bytes - before,
            'elapsed_s': tx.clock() - at}


def frame(tx, index, name):
    """Independently named slot with publication/record stability rechecks."""
    table = tx.u(tx.base + 0x3b8c5c8)
    if not table:
        raise Refused('function_table_null')
    pointer = tx.u(table + index * 8)
    if not pointer:
        raise Refused('function_slot_null')
    record = tx.read(pointer, 0x70)
    length = struct.unpack_from('<I', record, 0x58)[0] >> 2
    flags = struct.unpack_from('<I', record, 0x5c)[0]
    if length != len(name):
        raise Refused('frame_function_name_length')
    name_pointer = struct.unpack_from('<Q', record, 0x60)[0] if flags & 2 else pointer + 0x60
    if tx.read(name_pointer, length) != name.encode():
        raise Refused('frame_wrong_function')
    if (tx.u(tx.base + 0x3b8c5c8) != table or tx.u(table + index * 8) != pointer
            or tx.read(pointer, 0x70) != record):
        raise Refused('frame_publication_changed')
    return {'index': index, 'name': name, 'address': pointer, 'record_hex': record.hex(),
            'frame_zero_dwords': struct.unpack_from('<I', record, 0)[0],
            'frame_bound_operand': struct.unpack_from('<I', record, 4)[0],
            'code_offset': struct.unpack_from('<I', record, 8)[0],
            'cleanup_bytes': struct.unpack_from('<I', record, 12)[0]}


def diagnose(tx):
    """No type/compiler outcome gates another independently rooted channel."""
    channels = {name: run_channel(tx, decode) for name, decode in
                (('compiler', decoders.compiler_global), ('type', decoders.named_type))}
    for index, name in FUNCTIONS:
        channels[f'frames.{index}'] = run_channel(tx, lambda t: frame(t, index, name))
    return channels



def verify_build(tx):
    pins = json.loads(PROFILE.read_text(encoding='utf-8'))
    for pin in pins['code']:
        if hashlib.sha256(tx.read(tx.base + pin['rva'], pin['size'])).hexdigest() != pin['sha256']:
            raise Refused('diagnostic_code_pin')
    if tx.module_size != pins['image_size']:
        raise Refused('module_size')
    return {'build': 98348}


def read_clock(tx):
    from .native import NativeReader
    return NativeReader(tx).read_clock()


def read_context(tx, player_label):
    from .native_context import NativeContextProbe
    if tx.recorded_non_atomic:
        raise Refused('contexte_natif_capture_non_atomique')
    if not player_label:
        raise Refused('private_player_label_missing')
    probe = NativeContextProbe(player_label)
    probe.observe_native(tx)
    tx.context_probe = probe
    # Retain only map and opaque match identity privately; no players/label.
    return {'meta': probe.finish().get('meta', {}), 'perspective': 'not_validated'}


def recheck_context(tx):
    probe = getattr(tx, 'context_probe', None)
    if probe is None:
        raise Refused('context_initial_unavailable')
    probe.recheck(tx)
    return {'stable': True}


def collect(memory, *, player_label=None, clock=time.perf_counter, experiment='publication'):
    """One attempt, guarded, bounded and never normalized or sealed for Coach."""
    if experiment not in ('publication', 'runtime-roots'):
        raise ValueError('diagnostic_experiment')
    from . import braxis_roots
    metadata = (('compiler', 'type', *(f'frames.{index}' for index, _ in FUNCTIONS))
                if experiment == 'publication' else tuple(f'roots.{name}' for name in braxis_roots.DECODERS))
    tx = WholeTx(memory, clock=clock)
    names = ('clock_before', 'context', *metadata, 'context_after', 'clock_after')
    channels = {name: {'status': 'not_attempted', 'reason': 'build_guard', 'requests': 0,
                       'bytes_requested': 0, 'elapsed_s': 0.0} for name in names}
    build = run_channel(tx, verify_build)
    if build['status'] == 'observed':
        channels['clock_before'] = run_channel(tx, read_clock)
        channels['context'] = run_channel(tx, lambda t: read_context(t, player_label))
        channels.update(diagnose(tx) if experiment == 'publication' else braxis_roots.diagnose(tx))
        channels['context_after'] = run_channel(tx, recheck_context)
        channels['clock_after'] = run_channel(tx, read_clock)
    clocks = [channels[key] for key in ('clock_before', 'clock_after')]
    interval = None
    if all(row['status'] == 'observed' for row in clocks):
        values = [row['result'] for row in clocks]
        if 0 <= values[1] - values[0] <= .125:
            interval = values
    context = channels['context'].get('result', {}).get('meta', {})
    context_bracketed = (channels['context_after']['status'] == 'observed' and interval is not None)
    return {'schema': ('braxis-causal-v1' if experiment == 'publication' else 'braxis-runtime-roots-v1'),
            'experiment': experiment, 'qualification': 'private_diagnostic_not_atomic',
            'module_base': tx.base, 'module_size': tx.module_size,
            'build': build, 'channels': channels, 'measurement': measure(channels),
            'mission_clock': interval, 'perspective': 'not_validated',
            'target_map': ('unknown' if not context_bracketed else
                           'holdout_recorded' if context.get('map_id') == 'BraxisHoldout'
                           else 'wrong_map' if context.get('map_id') else 'unknown'),
            'reads': tx.reads, 'physical_requests': len(tx.reads), 'bytes_requested': tx.bytes,
            'elapsed_s': tx.clock() - tx.start, 'normalized_acquisitions': 0,
            'objective': None, 'coach': False}


def measure(channels):
    """Separate a scoped lookup miss from a channel never physically attempted."""
    absent = {'compiler_root_null', 'global_table_absent',
              'named_global_not_yet_published', 'named_type_absent',
              'function_table_null', 'function_slot_null', 'selector_table_null',
              'selector_slot_null', 'descriptor_arena_null', 'simulation_root_null',
              'simulation_database_null'}
    return {
        'scoped_absences': [name for name, row in channels.items()
                            if row['status'] == 'refused' and row.get('reason') in absent
                            and row.get('requests', 0) > 0],
        'unattempted': [name for name, row in channels.items() if row['status'] == 'not_attempted'],
        'observed_metadata': [name for name, row in channels.items() if row['status'] == 'observed'],
        'global_absence_proven': False, 'objective': None, 'coach': False,
        'gates': {key: 'unproven' for key in ('B1', 'B2', 'B3')},
    }
