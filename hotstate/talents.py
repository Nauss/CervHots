"""Build98348 selected talent tree research (NOT yet a coach producer).

Persistent native selection is distinct from PlayerHasTalent membership and
from the offered Hero catalog. No calls into the client, writes or GUI.
"""
from __future__ import annotations

import struct
import hashlib
import copy
import json
import time
from pathlib import Path

from .native import NativeReader, NativeUnavailable
from .native_context import NativeContextProbe
from .positions import AlliedPositions, _RecordedMemory
from .match import ActiveMatch
from .local_experiments import pointer, text, _BudgetMemory, _clock

PROFILE = json.loads((Path(__file__).parent/'profiles/98348-talents.json').read_text())
VALIDATED_SCOPES = ()  # full recipe gate closed until this exact path is exercised


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


def read_tree(n, player, native_id, *, include_levels=False):
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
    result = {'selected': resolve_selections(indices, offered), 'offered': offered,
            'unselected_tiers': sorted({r['tier'] for r in offered}
                - {tier for tier, index in enumerate(indices) if index != 0xffffffff}),
            'level_requirement': 'unknown_NOT_YET_QUALIFIED'}
    if include_levels:
        result['tier_levels'] = read_tier_levels(n, data)
        result.pop('level_requirement')
        if any(row['tier'] not in result['tier_levels'] for row in offered):
            raise NativeUnavailable('talent_tier_level_unknown')
    return result


def read_tier_levels(n, data):
    """Hero.TalentTierArray: native selection level gate, not a fixed schedule."""
    count = n.value(data+0x518)
    if not 0 < count <= 31:
        raise NativeUnavailable('talent_tier_levels_absent_or_invalid')
    table = pointer(n.value(data+0x528, 'Q'))
    result = {}
    for i in range(count):
        tier, level, _ = struct.unpack('<III', n.read(table+i*12, 12))
        if not 1 <= tier <= 31 or not 1 <= level <= 30 or tier in result:
            raise NativeUnavailable('talent_tier_level_unknown')
        result[tier] = level
    return result


class NativeTalentChoices:
    """Current local/allied selections; never read enemy talent fields."""
    def __init__(self, native):
        self.native = native

    def read(self, context, *, hero_ids=None):
        from .acquisition import issue
        expected = copy.deepcopy(context)
        map_id, match_id, local, team, _ = AlliedPositions._context(expected)
        ids = json.loads((Path(__file__).parent/'hero_ids.json').read_text()) if hero_ids is None else hero_ids
        hero = ids.get(expected['local_player']['hero'], expected['local_player']['hero'])
        if not any(scope_map == map_id for scope_map, _ in VALIDATED_SCOPES):
            raise NativeUnavailable('talent_recipe_scope_unqualified')
        budget = _BudgetMemory(self.native.memory, clock=time.monotonic)
        recorded = _RecordedMemory(budget)
        if budget.recorded_non_atomic:
            raise NativeUnavailable('talent_non_atomic_dump')
        n = NativeReader(recorded, profile=self.native.profile)
        if PROFILE['build'] != n.profile['build'] or not PROFILE.get('signatures'):
            raise NativeUnavailable('talent_profile_unsupported')
        for s in PROFILE['signatures']:
            if hashlib.sha256(n.read(n.base+s['rva'], s['size'])).hexdigest() != s['sha256']:
                raise NativeUnavailable('talent_signature_mismatch')
        if ActiveMatch().observe(n)['match_id'] != match_id:
            raise NativeUnavailable('talent_match_mismatch')
        first = _clock(n, recorded)
        actual = AlliedPositions(n)._identity(n, ids)
        if actual[:3] != (local, team, hero):
            raise NativeUnavailable('talent_local_identity_mismatch')
        players = []
        for member in actual[3]:
            # Permission is decided BEFORE touching a player's talent table or Hero data.
            if member['team'] != team:
                continue
            ident = member['id']
            player = pointer(n.player_pointer(ident+1))
            member_hero = n.hero_id(player, ids)
            tag = n.value(player+0x58)
            sample = {'id': ident, 'hero': member_hero, 'generation': tag & 0x3fffff,
                      'status': 'unknown', 'tiers': None, 'reason': 'unqualified_scope'}
            if (map_id, member_hero) in VALIDATED_SCOPES:
                try:
                    unit = n.unit_pointer(tag, ident+1)
                    level = n.unit_level(unit)
                    tree = read_tree(n, player, ident+1, include_levels=True)
                    tiers = selection_tiers(tree, level)
                    sample.update(status='observed', tiers=tiers)
                    sample.pop('reason')
                except NativeUnavailable as exc:
                    sample['reason'] = str(exc)
            players.append(sample)
        if not any(p['status'] == 'observed' for p in players):
            raise NativeUnavailable('talent_no_qualified_player')
        local_sample = next(p for p in players if p['id'] == local)
        for address, data in recorded.coherence_reads('talent_torn'):
            if budget.read_memory(address, len(data)) != data:
                raise NativeUnavailable('talent_torn')
        last = _clock(n, recorded)
        elapsed = time.monotonic()-budget.started
        if context != expected or not 0 <= elapsed <= 0.125 or not 0 <= last-first <= 0.125:
            raise NativeUnavailable('talent_stale_or_context_changed')
        return issue({'status': 'validated', 'map_id': map_id, 'match_id': match_id,
            'local_id': local, 'team': team, 'local_hero': hero, 'generation': local_sample['generation'],
            'native_session': actual[4], 'mission_t_s': last, 'read_window_s': elapsed,
            'tiers': local_sample['tiers'], 'players': players, 'scope': 'allied_selected_talents'}, budget.started)


def selection_tiers(tree, level):
    selected = {row['tier']: row for row in tree['selected']}
    offered_tiers = {row['tier'] for row in tree['offered']}
    tiers = []
    for tier, required in sorted(tree['tier_levels'].items()):
        choice = selected.get(tier)
        if choice is not None and required > level:
            raise NativeUnavailable('talent_choice_above_current_level')
        tiers.append({'tier': tier, 'required_level': required,
            'status': 'selected' if choice else 'unselected' if tier in offered_tiers else 'unknown',
            'slot': choice['slot'] if choice else None,
            'catalog_id': choice['catalog_id'] if choice else None})
    return tiers


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
        if PROFILE['build'] != n.profile['build'] or not PROFILE.get('signatures'):
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
