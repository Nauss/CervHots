"""DIAGNOSTIC current LOCAL costs, native classes6/7 command0 only.

Reads current active data roots and the explicit owning player's overlay. No
client call, base-loadout fallback, event countdown, HUD-slot or castability
claim. Other native classes/locations/commands remain explicitly unqualified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .local_experiments import pointer, text
from .native import NativeUnavailable

PROFILE = json.loads((Path(__file__).parent/'profiles/98348-cooldown-costs.json').read_text(encoding='utf-8'))


def verify(n):
    if n.profile.get('build') != 98348 or PROFILE.get('build') != 98348 or len(PROFILE.get('signatures', ())) != 11:
        raise NativeUnavailable('cooldown_cost_profile_unsupported')
    for s in PROFILE['signatures']:
        if hashlib.sha256(n.read(n.base+s['rva'], s['size'])).hexdigest() != s['sha256']:
            raise NativeUnavailable('cooldown_cost_signature_mismatch')


def _owner(value):
    if type(value) is not int or not 1 <= value <= 10:
        raise NativeUnavailable('cost_local_owner_invalid')
    return value


def _link(n, value):
    if not value:
        return None
    pointer(value)
    # An actual empty native string is not a missing memory read or ready CD.
    if n.value(value+0x18) >> 2 == 0:
        return None
    return text(n, value)


def applicability(n, native_owner, flag, mode, value):
    """Reproduce c7acd30's condition and player opt-out, not cast legality."""
    _owner(native_owner)
    if not flag:
        if mode == 2:
            eligible = ((value-65536) & 0xffffffff) > 15
        elif mode == 3:
            eligible = value < 0x7fffffff
        elif mode == 4:
            eligible = value > 0
        elif mode == 5:
            eligible = True
        elif mode == 6:
            eligible = False
        else:
            eligible = value != 0
        if not eligible:
            return False
    index = n.value(n.base+PROFILE['cooldown_condition_index_rva'])
    if index != 0xffffffff:
        if index >= 65536:
            raise NativeUnavailable('cost_condition_index_unqualified')
        bits = n.value(n.base+PROFILE['condition_bits_rva']+(index >> 3), 'B')
        if not bits & (1 << (index & 7)):
            return True
    mask = n.value(n.base+PROFILE['condition_player_mask_rva'])
    return not bool((mask >> native_owner) & 1)


def current_cost(n, instance, native_owner):
    """Source-only cost metadata. Caller owns identity, budgets and rechecks."""
    _owner(native_owner)
    reference = n.value(pointer(instance)+0x28, 'Q')
    instance_root = reference & ~31
    pointer(instance_root)
    index = n.value(instance_root+2, 'H')
    root = pointer(n.value(n.base+0x3388b18, 'Q'))
    database = pointer(n.value(root+8, 'Q'))
    name_count = n.value(database+0x90)
    if not 0 < name_count <= 65536 or index >= name_count:
        raise NativeUnavailable('cost_name_index_invalid')
    descriptor = pointer(n.value(pointer(n.value(database+0xa0, 'Q'))+index*8, 'Q'))
    link_index = n.value(descriptor+0x40, 'H')
    data_count = n.value(database+0x38)
    if not 0 < data_count <= 65536 or link_index >= data_count:
        raise NativeUnavailable('cost_data_index_invalid')
    source = n.value(pointer(n.value(database+0x48, 'Q'))+link_index*8, 'Q')
    if source & 1:
        raise NativeUnavailable('cost_lazy_resolution_requires_native_call_FORBIDDEN')
    pointer(source)
    if n.value(source, 'B') & 1 or source != instance_root:
        raise NativeUnavailable('cost_instance_root_not_current')
    classdesc = pointer(n.value(source+0x60, 'Q'))
    class_id = n.value(classdesc+0x24)
    if class_id not in (6, 7):
        return {'status': 'unknown', 'native_class': class_id, 'reason': 'cost_native_class_unqualified'}
    membership = pointer(n.value(classdesc+0x100, 'Q'))
    if not n.value(membership+(class_id >> 3), 'B') & (1 << (class_id & 7)):
        raise NativeUnavailable('cost_native_class_membership_invalid')
    flags = n.value(n.base+PROFILE['registry_flags_rva']+(class_id >> 3), 'B')
    registry = n.base+PROFILE['registry_rva']+class_id*0x2a48
    callback = next(s['rva'] for s in PROFILE['signatures'] if s['name'] == f'CostClass{class_id}')
    if (not flags & (1 << (class_id & 7)) or not 1 <= n.value(registry) <= 64
            or not n.value(registry+8, 'B') or n.value(registry+0x60, 'Q') != n.base+callback):
        raise NativeUnavailable('cost_callback_registry_mismatch')
    table = pointer(n.value(source+0x70, 'Q'))
    # dd1d410 explicitly overlays owner low5bits. Never choose default player16.
    overlay = pointer(n.value(table+native_owner*8, 'Q'))
    cost = overlay+8  # classes6/7 command0, not command1's separate +90 block
    maximum = n.value(cost+0x20, 'i')
    if not 0 <= maximum <= 1024*4096:
        raise NativeUnavailable('cost_charge_max_invalid')
    location, charge_location = n.value(cost+0x50), n.value(cost+0x38)
    cd_link, charge_link = _link(n, n.value(cost+0x48, 'Q')), _link(n, n.value(cost+0x30, 'Q'))
    condition = [n.value(cost+0x54), n.value(cost+0x58), n.value(cost+0x5c, 'i')]
    storage = {1: 'unit', 2: 'player'}
    applies = (applicability(n, native_owner, *condition)
               if location in storage and cd_link and len(cd_link) >= 4 else None)
    return {'status': 'diagnostic_current_cost', 'native_class': class_id, 'command': 0,
            'cooldown_storage': storage.get(location, 'unqualified'), 'cooldown_link': cd_link,
            'charge_storage': storage.get(charge_location, 'unqualified'), 'charge_link': charge_link,
            'charges_max': maximum/4096, 'cooldown_condition': condition,
            'cooldown_applies': applies, 'source_scope': 'current_local_player_overlay_NOT_BASE'}


def diagnostic_abilities(instances, unit_links, sources):
    """Diagnostic join ONLY with actual current cost link+storage, never name.

    Missing source/link stays unknown. Ready below means cooldown complete,
    NOT castability nor even charge availability. No fresh receipt is issued.
    """
    rows = []
    for instance in instances:
        row = {'ability': instance['ability'], 'cooldown_status': 'unknown',
               'charges_status': 'unknown', 'cast_legality': 'unknown'}
        cost = instance.get('current_cost', {})
        if cost.get('status') != 'diagnostic_current_cost':
            rows.append(row)
            continue
        link, storage = cost.get('cooldown_link'), cost.get('cooldown_storage')
        remaining = None
        if cost.get('cooldown_applies') is True:
            if storage == 'unit':
                remaining = unit_links.get(link)
            elif storage == 'player':
                sample = sources.get('player_cooldowns', {})
                if sample.get('status') == 'diagnostic_observed':
                    remaining = sample['value'].get(link, {}).get('remaining_s')
        if remaining is not None:
            row.update(cooldown_status='diagnostic_observed', remaining_s=remaining,
                       cooldown_ready=remaining == 0, cooldown_link=link, cooldown_storage=storage)
        maximum, charge_storage = cost.get('charges_max'), cost.get('charge_storage')
        if maximum == 0:
            row['charges_status'] = 'not_applicable_current_max_zero'
        elif maximum is not None and maximum > 0 and charge_storage in ('unit', 'player'):
            sample = sources.get(charge_storage+'_charges', {})
            value = sample.get('value', {}).get(cost.get('charge_link')) if sample.get('status') == 'diagnostic_observed' else None
            if value is not None:
                row.update(charges_status='diagnostic_observed', charges_max=maximum,
                           charges_used=value['charges_used'], charges_available=max(0, maximum-value['charges_used']),
                           charge_regen_s=value['regen_s'])
        rows.append(row)
    return rows
