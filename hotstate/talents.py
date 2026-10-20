"""Build98348 selected talent tree research (NOT yet a coach producer).

Persistent native selection is distinct from PlayerHasTalent membership and
from the offered Hero catalog. No calls into the client, writes or GUI.
"""
from __future__ import annotations

import struct
import hashlib
import json
import time
from pathlib import Path

from .native import NativeReader, NativeUnavailable
from .native_context import NativeContextProbe
from .positions import AlliedPositions, _RecordedMemory
from .match import ActiveMatch
from .local_experiments import pointer, text, _BudgetMemory, _clock

PROFILE = json.loads((Path(__file__).parent/'profiles/98348-talents.json').read_text())


def resolve_selections(indices, offered):
    """Resolve the current tree without requiring a previous observation."""
    if len(indices) != 32:
        raise NativeUnavailable('talent_selection_incomplete')
    by_index = {row['index']: row for row in offered}
    if len(by_index) != len(offered):
        raise NativeUnavailable('talent_catalog_ambiguous')
    result = []
    for tier, index in enumerate(indices):
        if type(index) is not int or not 0 <= index <= 0xffffffff:
            raise NativeUnavailable('talent_selection_invalid')
        if index == 0xffffffff:
            continue
        row = by_index.get(index)
        if row is None or row['tier'] != tier:
            raise NativeUnavailable('talent_selected_id_or_tier_unresolved')
        result.append(dict(row))
    return result


def read_tree(n, player, native_id):
    """Private diagnostic: persisted indices plus the matching current Hero tree.

    Caller MUST bind player/hero/match/generation, fingerprint, budget and
    recheck all reads. This low-level helper does not issue a receipt.
    """
    if type(native_id) is not int or not 1 <= native_id <= 10:
        raise NativeUnavailable('talent_native_player_invalid')
    hero = pointer(n.value(player+0x50, 'Q'))
    hero_index = n.value(hero+0x40, 'H')
    root = pointer(n.value(n.base+0x3388b18, 'Q'))
    database = pointer(n.value(root+0x148, 'Q'))
    count = n.value(database+0x38)
    if not 0 < count <= 65536 or hero_index >= count:
        raise NativeUnavailable('talent_hero_catalog_invalid')
    table = pointer(n.value(database+0x48, 'Q'))
    data = n.value(table+hero_index*8, 'Q')
    # Tagged/lazy descriptors require a native mutation to resolve. Never do it.
    pointer(data)
    if n.value(data, 'B') & 1:
        raise NativeUnavailable('talent_hero_catalog_lazy')
    count = n.value(data+0x500)
    if not 0 < count <= 128:
        raise NativeUnavailable('talent_tree_count_invalid')
    entries = pointer(n.value(data+0x510, 'Q'))
    offered = []
    slots = set()
    for index in range(count):
        entry = entries+index*0x40
        desc = pointer(n.value(entry, 'Q'))
        tier, slot = struct.unpack('<II', n.read(entry+8, 8))
        if not 0 < tier < 32 or not 0 < slot <= 32 or (tier, slot) in slots:
            raise NativeUnavailable('talent_tree_tier_or_slot_invalid')
        slots.add((tier, slot))
        offered.append({'index': index, 'tier': tier, 'slot': slot,
                        'catalog_id': text(n, pointer(n.value(desc+0x30, 'Q')))})
    indices = struct.unpack('<32I', n.read(n.base+0x3677a30+native_id*128, 128))
    return {'selected': resolve_selections(indices, offered), 'offered': offered,
            'unselected_tiers': sorted({r['tier'] for r in offered}
                - {tier for tier, index in enumerate(indices) if index != 0xffffffff}),
            'level_requirement': 'unknown_NOT_YET_QUALIFIED'}


def diagnose(backend, probe, *, clock=None, native_profile=None):
    """WHOLE bounded private diagnostic, no receipt/publication or history cache.

    Generic source candidate only: actual hero/map coverage is NOT granted by
    this research entrypoint. No enemy talent fields are read; local only.
    """
    row = {'status': 'rejected', 'source': 'native_selected_talents_diagnostic_NOT_PRODUCT'}
    if not isinstance(probe, NativeContextProbe):
        return dict(row, reason='talent_context_source_unsupported')
    clock = time.monotonic if clock is None else clock
    budget = _BudgetMemory(backend, clock=clock)
    recorded = _RecordedMemory(budget)
    try:
        if budget.recorded_non_atomic:
            raise NativeUnavailable('talent_non_atomic_dump')
        n = NativeReader(recorded, profile=native_profile)
        if PROFILE['build'] != n.profile['build'] or len(PROFILE['signatures']) != 6:
            raise NativeUnavailable('talent_profile_unsupported')
        for signature in PROFILE['signatures']:
            code = n.read(n.base+signature['rva'], signature['size'])
            if hashlib.sha256(code).hexdigest() != signature['sha256']:
                raise NativeUnavailable('talent_signature_mismatch')
        initial = ActiveMatch().observe(n)
        first = _clock(n, recorded)
        probe.begin()
        probe.observe_native(budget, native_profile=native_profile, clock=clock)
        context = probe.finish()
        map_id, match_id, local, team, _ = AlliedPositions._context(context)
        ids = json.loads((Path(__file__).parent/'hero_ids.json').read_text())
        actual = AlliedPositions(n)._identity(n, ids)
        if (context['meta'].get('context_source') != 'initdata_native_fields'
                or match_id != initial['match_id'] or actual[:2] != (local, team)
                or ids.get(context['local_player']['hero'], context['local_player']['hero']) != actual[2]):
            raise NativeUnavailable('talent_local_identity_mismatch')
        player = pointer(n.player_pointer(local+1))
        tag = n.value(player+0x58)
        unit = n.unit_pointer(tag, local+1)
        level = n.unit_level(unit)
        tree = read_tree(n, player, local+1)
        for address, data in recorded.coherence_reads('talent_torn'):
            if budget.read_memory(address, len(data)) != data:
                raise NativeUnavailable('talent_torn')
        probe.recheck(budget)
        last = _clock(n, recorded)
        elapsed = clock()-budget.started
        if not 0 <= last-first <= 0.125 or not 0 <= elapsed <= 0.125:
            raise NativeUnavailable('talent_window_expired')
        row.update(status='accepted_diagnostic_NOT_PRODUCT', hero=actual[2],
            map_id=map_id, local_id=local, team=team, match_id=match_id,
            generation=tag & 0x3fffff, level=level, tree=tree,
            mission_interval_s=[first, last], elapsed_s=elapsed,
            coverage='unqualified hero/map candidate; local only; no coach publication')
    except NativeUnavailable as exc:
        row['reason'] = str(exc)
    row.update(read_count=budget.read_count, bytes_requested=budget.bytes_requested)
    return row
