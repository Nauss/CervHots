"""Independent native root diagnostics, NOT a SCHO global/objective decoder.

Offsets derive from pinned complete historical functions; no native calls,
heap scan, unit names, owners, positions, vitals or fallback data reads.
"""
import hashlib
import json
import struct
from pathlib import Path
from .braxis_decoders import Refused

PROFILE = Path(__file__).parent / 'profiles/98348-braxis-roots.json'


def decode_channel(tx, name):
    """Code/size gate belongs to each independent channel and its WHOLE slice."""
    profile = json.loads(PROFILE.read_text(encoding='utf-8'))
    if tx.module_size is not None and tx.module_size != profile['image_size']:
        raise Refused('module_size')
    for pin in profile['channels'][name]:
        if hashlib.sha256(tx.read(tx.base + pin['rva'], pin['size'])).hexdigest() != pin['sha256']:
            raise Refused('runtime_code_pin')
    return DECODERS[name](tx)


def diagnose(tx):
    from .braxis import run_channel
    return {f'roots.{name}': run_channel(tx, lambda t, n=name: decode_channel(t, n))
            for name in DECODERS}


def unit_pages(tx):
    """Bounded native registry alternative; full tags only, no unit payload.

    Publication and slot/tag coherence are observations, not proof of allocator
    success, active/free list membership, SCHO origin or continuous lifetime.
    """
    address = tx.base + 0x34f02c0
    header = tx.read(address, 8)
    limit = struct.unpack_from('<I', header, 4)[0]
    if not 1 <= limit <= 1024:
        raise Refused('unit_pool_bound')
    low = tx.u(tx.base + 0x32c38b4, 'I')
    high = tx.u(tx.base + 0x32c55d0, 'I')
    pages, tags, references, nulls = [], [], [], []
    for ordinal in range((limit + 15) // 16):
        slot = address + 8 + ordinal * 8
        encoded = tx.read(slot, 8)
        lo, hi = struct.unpack('<II', encoded)
        page = (((hi + high) & 0xffffffff) << 32) | (lo ^ low)
        pages.append([slot, encoded, page])
        if not page:
            nulls.append(ordinal)
            continue
        pointer(page, 'unit_page_null')
        for index in range(ordinal * 16, min(limit, (ordinal + 1) * 16)):
            tag_address = page + (index & 15) * 0x2f0 + 0x10
            tag = tx.u(tag_address, 'I')
            tags.append([tag_address, tag])
            if (tag + 1) & 0xfffffffe and tag >> 22 == index:
                references.append([index, tag])
    # All consumed fields are physically re-read; equality cannot exclude ABA.
    if (tx.read(address, 8) != header
            or tx.u(tx.base + 0x32c38b4, 'I') != low
            or tx.u(tx.base + 0x32c55d0, 'I') != high):
        raise Refused('unit_pool_changed')
    for slot, encoded, _ in pages:
        if tx.read(slot, 8) != encoded:
            raise Refused('unit_page_changed')
    for tag_address, tag in tags:
        if tx.u(tag_address, 'I') != tag:
            raise Refused('unit_reference_changed')
    return {'limit': limit, 'pages': [[i, p] for i, (_, _, p) in enumerate(pages)],
            'references': references, 'null_pages': nulls,
            'scho_allocation_proven': False, 'lifetime_proven': False}


def simulation_root(tx):
    """Physical reset-path roots, NOT evidence of SCHO VM membership."""
    root = pointer(tx.u(tx.base + 0x3388b18), 'simulation_root_null')
    database = pointer(tx.u(root + 0x2a0), 'simulation_database_null')
    bound = tx.u(database + 0x38, 'H')
    if (tx.u(tx.base + 0x3388b18) != root
            or tx.u(root + 0x2a0) != database
            or tx.u(database + 0x38, 'H') != bound):
        raise Refused('simulation_root_changed')
    return {'root': root, 'database': database, 'reset_bound_raw': bound,
            'scho_membership_proven': False}


def descriptor_arena(tx):
    """Inspect the type-descriptor allocator header, never SCHO global bytes."""
    address = tx.base + 0x2fa7300
    raw = tx.read(address, 48)
    _, alignment, block, end, start, cursor = struct.unpack('<6Q', raw)
    pointer(block, 'descriptor_arena_null')
    if not (0x10000 <= start <= cursor <= end < 0x800000000000
            and block + 16 <= start and alignment <= 4095
            and (alignment & (alignment + 1)) == 0):
        raise Refused('descriptor_arena_bounds')
    header = tx.read(block, 16)
    if struct.unpack_from('<Q', header)[0] != end:
        raise Refused('descriptor_arena_header')
    if tx.read(address, 48) != raw or tx.read(block, 16) != header:
        raise Refused('descriptor_arena_changed')
    return {'block': block, 'end': end, 'start': start, 'cursor': cursor,
            'header_consistent': True, 'scho_allocation_proven': False}


def context_selector(tx):
    """Sample execution-stack selection; empty stack never becomes active VM."""
    count = tx.u(tx.base + 0x2f71528, 'I')
    if count == 0:
        if tx.u(tx.base + 0x2f71528, 'I') != count:
            raise Refused('selector_changed')
        return {'selection': 'fallback_only', 'selected': None,
                'active_vm_proven': False}
    # Diagnostic cap, not an inferred native stack capacity.
    if count > 4096:
        raise Refused('selector_bound')
    table = pointer(tx.u(tx.base + 0x2f71538), 'selector_table_null')
    selected = pointer(tx.u(table + (count - 1) * 8), 'selector_slot_null')
    if (tx.u(tx.base + 0x2f71528, 'I') != count
            or tx.u(tx.base + 0x2f71538) != table
            or tx.u(table + (count - 1) * 8) != selected):
        raise Refused('selector_changed')
    return {'selection': 'stack_selected', 'selected': selected,
            'count': count, 'table': table, 'active_vm_proven': False}


def pointer(value, null_reason):
    if value == 0:
        raise Refused(null_reason)
    if not 0x10000 <= value < 0x800000000000:
        raise Refused('root_pointer_invalid')
    return value


DECODERS = {'selector': context_selector, 'descriptor_arena': descriptor_arena,
            'simulation_root': simulation_root, 'unit_pages': unit_pages}


def sample_transitions(previous, current):
    """Equality/change between adjacent qualified samples, never lifetime/ABA.

    A missing/refused sample breaks comparison. No bridge across match changes,
    absent context, Outpost, backward clocks or a mission gap over ten seconds.
    """
    def identity(raw):
        if (not raw or raw.get('experiment') != 'runtime-roots'
                or raw.get('target_map') != 'holdout_recorded'
                or raw.get('build', {}).get('status') != 'observed'
                or not 0 <= raw.get('elapsed_s', 1) < .125
                or raw['channels'].get('context_after', {}).get('status') != 'observed'):
            return None
        mission = raw.get('mission_clock')
        if not mission or not 0 <= mission[1] - mission[0] <= .125:
            return None
        context = raw['channels'].get('context', {})
        if context.get('status') != 'observed':
            return None
        return context.get('result', {}).get('meta', {}).get('match_id')

    current_id, previous_id = identity(current), identity(previous)
    comparable = (current_id and previous_id == current_id
                  and 0 <= current['mission_clock'][0] - previous['mission_clock'][1] <= 10)
    states = {}
    for name in DECODERS:
        key = f'roots.{name}'
        row = current['channels'].get(key, {})
        old = previous['channels'].get(key, {}) if previous else {}
        state = 'not_comparable'
        if current_id and row.get('status') == 'observed':
            if previous is None:
                state = 'first_sample'
            elif comparable and old.get('status') == 'observed':
                state = 'sample_equal' if old['result'] == row['result'] else 'sample_changed'
        states[key] = state
    return states


def measure(raw):
    """Closed non-tactical report; private roots/tags/hashes never escape."""
    selector = raw['channels'].get('roots.selector', {})
    selection = selector.get('result', {}).get('selection') if selector.get('status') == 'observed' else None
    selection = selection if selection in ('fallback_only', 'stack_selected') else 'not_observed'
    missing = ['compiled_global_to_vm_binding', 'scho_global_allocation_and_generation',
               'active_free_retired_membership', 'perspective_binding']
    if selection != 'stack_selected':
        missing.append('executing_context_not_sampled')
    return {'selector_selection': selection, 'missing_links': missing,
            'unit_pool_is_scho_allocator': False, 'continuous_lifetime_proven': False,
            'sampled_equality_excludes_aba': False, 'objective': None, 'coach': False}
