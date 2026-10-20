"""Native instance/Unit/Player/charge diagnostic sources, build98348 only.

No catalogue base loadout is used: UnitAbilityGet's active bitmap and instance
resolver are followed on every acquisition. Slots are NOT HUD button bindings.
Current costs/type/max charges are NOT yet decoded. No effective ability state
or castability may be inferred by joining these separate diagnostic tables.
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from .local_experiments import pointer, text, cooldown_value, follow_link
from .native import NativeUnavailable

PROFILE = json.loads((Path(__file__).parent/'profiles/98348-cooldown-sources.json').read_text(encoding='utf-8'))


def verify(n):
    if n.profile.get('build') != 98348 or PROFILE.get('build') != 98348 or len(PROFILE.get('signatures', ())) != 12:
        raise NativeUnavailable('cooldown_sources_profile_unsupported')
    for s in PROFILE['signatures']:
        if hashlib.sha256(n.read(n.base+s['rva'], s['size'])).hexdigest() != s['sha256']:
            raise NativeUnavailable('cooldown_sources_signature_mismatch')


def active_instances(n, unit, *, native_owner=None):
    """Native UnitAbilityCount/Get active ordinals; names resolved via instances.

    A missing instance/descriptor is unknown/refused, NOT absent or ready.
    Unit generation, owner and all traversed fields require caller rechecks.
    """
    root = n.value(pointer(unit)+0x140, 'Q') & ~3
    if not root:
        raise NativeUnavailable('ability_instance_root_absent')
    pointer(root)
    bitmap = struct.unpack('<Q', n.read(root+0x40, 8))[0]
    extent = n.value(root+0x62, 'B')
    if not 0 <= extent <= 64 or bitmap >> extent:
        raise NativeUnavailable('ability_instance_bitmap_invalid')
    if not bitmap:
        return []
    catalogue_root = pointer(n.value(n.base+0x3388B18, 'Q'))
    database = pointer(n.value(catalogue_root+8, 'Q'))
    count = n.value(database+0x90)
    if not 0 < count <= 65536:
        raise NativeUnavailable('ability_catalogue_count_invalid')
    table = pointer(n.value(database+0xa0, 'Q'))
    rows, seen = [], set()
    for slot in range(extent):
        if not bitmap & (1 << slot):
            continue
        instance = pointer(n.value(root+0x68+slot*8, 'Q'))
        if instance in seen:
            raise NativeUnavailable('ability_duplicate_instance')
        seen.add(instance)
        reference = n.value(instance+0x28, 'Q') & ~31
        if not reference:
            raise NativeUnavailable('ability_descriptor_reference_absent')
        pointer(reference)
        index = n.value(reference+2, 'H')
        if index >= count:
            raise NativeUnavailable('ability_catalogue_index_invalid')
        descriptor = pointer(n.value(table+index*8, 'Q'))
        name = text(n, pointer(n.value(descriptor+0x30, 'Q')))
        row = {'ordinal': len(rows)+1, 'instance_slot': slot,
                     'ability': name, 'slot_kind': 'native_instance_NOT_HUD_button',
                     'cost_binding': 'unproven', 'ability_type': 'unqualified'}
        if native_owner is not None:
            from .cooldown_costs import current_cost
            try:
                row['current_cost'] = current_cost(n, instance, native_owner)
            except NativeUnavailable as exc:
                if str(exc) in ('prototype_window_expired', 'prototype_budget_exceeded'):
                    raise
                row['current_cost'] = {'status': 'unknown', 'reason': str(exc)}
        rows.append(row)
    return rows


def stored_links(n, owner, *, storage, charges=False):
    """Local diagnostic store, not a claim that a named ability uses it.

    Owner MUST be the identity-validated local CPlayer/CUnit, never arbitrary
    roster entries. Unit/Player storage roots differ, charge units differ too.
    """
    if storage not in ('unit', 'player') or type(charges) is not bool:
        raise ValueError('unsupported cooldown storage')
    pointer(owner)
    if storage == 'player':
        node = n.value(owner+(0x1e8 if charges else 0x1f8), 'Q')
    else:
        state = pointer(n.value(owner+8, 'Q'))
        head = n.value(state+(0 if charges else 8), 'Q')
        if not head:
            raise NativeUnavailable('charge_root_absent' if charges else 'cooldown_root_absent')
        node = n.value(pointer(head)+8, 'Q')
    node = follow_link(node, lambda a: n.value(a, 'Q'))
    seen, result = set(), {}
    while node:
        if node in seen or len(seen) >= 128:
            raise NativeUnavailable('cooldown_storage_cycle_or_limit')
        seen.add(node)
        name = text(n, pointer(n.value(node+0x10, 'Q')))
        if name in result:
            raise NativeUnavailable('cooldown_storage_duplicate_link')
        remaining = cooldown_value(n.value(node+0x18, 'i'))
        if charges:
            used = n.value(node+0x1c, 'i')
            if not 0 <= used <= 1024*4096:
                raise NativeUnavailable('charge_used_invalid')
            a, b = struct.unpack('<ii', n.read(node+0x20, 8))
            full = max(0, a+b)
            result[name] = {'regen_s': remaining, 'charges_used': used/4096,
                            'regen_full_s': cooldown_value(full),
                            'charges_max': 'unknown', 'ability_binding': 'unproven'}
        else:
            result[name] = {'remaining_s': remaining, 'ability_binding': 'unproven'}
        node = follow_link(n.value(node+8, 'Q'), lambda a: n.value(a, 'Q'))
    return result
