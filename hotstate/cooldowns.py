"""Bounded LOCAL unit cooldown-link diagnostic, not an ability producer.

Only names and current native values are read; no catalogue/event countdown.
A link does NOT prove an effective ability, slot, charges or cast legality.
No ally/enemy cooldown enumeration. The game backend is owned by the operator.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .local_experiments import _BudgetMemory, _clock, cooldown_value, follow_link, pointer, text
from .native import NativeReader, NativeUnavailable
from .native_context import NativeContextProbe
from .match import ActiveMatch
from .positions import AlliedPositions, _RecordedMemory

# The source signatures are the three cooldown helpers exercised by game18.
# Reusing signatures does NOT extend the historical qualification to Dragon.
_EXPERIMENT = json.loads((Path(__file__).parent/'profiles/98348-local-experiments.json').read_text(encoding='utf-8'))
SIGNATURES = tuple(s for s in _EXPERIMENT['signatures']
                   if s['name'] in ('UnitGetCooldown', 'UnitCooldownList', 'TaggedNext'))


def read_unit_links(n, unit):
    """Private diagnostic links only; absent node is never an implicit zero."""
    state = pointer(n.value(pointer(unit)+8, 'Q'))
    head = n.value(state+8, 'Q')
    if not head:
        raise NativeUnavailable('cooldown_root_absent')
    pointer(head)
    node = follow_link(n.value(head+8, 'Q'), lambda a: n.value(a, 'Q'))
    result, seen = {}, set()
    while node:
        if node in seen or len(seen) >= 128:
            raise NativeUnavailable('cooldown_list_cycle_or_limit')
        seen.add(node)
        name = text(n, pointer(n.value(node+0x10, 'Q')))
        if name in result:
            raise NativeUnavailable('cooldown_duplicate_link')
        result[name] = cooldown_value(n.value(node+0x18, 'i'))
        node = follow_link(n.value(node+8, 'Q'), lambda a: n.value(a, 'Q'))
    return result


def select_link(links, name):
    result = {'cooldown_link': name, 'storage': 'unit',
              'ability_binding': 'unproven', 'cast_legality': 'unknown'}
    if name not in links:
        return dict(result, status='unknown', reason='cooldown_link_not_observed')
    remaining = links[name]
    return dict(result, status='observed', remaining_s=remaining,
                cooldown_ready=remaining == 0)


def observe(backend, probe, *, clock=None):
    """One diagnostic acquisition, WHOLE context/identity/rechecks included.

    Raw readsets are owned by the caller, never emitted here. No receipt for
    the coach is issued. Volskaya/Stitches has a historical link-only proof;
    DragonShire is a NEW diagnostic scope, NOT a product validation allowlist.
    """
    clock = time.monotonic if clock is None else clock
    row = {'status': 'rejected', 'kind': 'local_unit_cooldown_diagnostic_NOT_PRODUCT'}
    if not isinstance(probe, NativeContextProbe):
        return dict(row, reason='cooldown_native_probe_required')
    budget = _BudgetMemory(backend, clock=clock)
    recorded = _RecordedMemory(budget)
    try:
        if budget.recorded_non_atomic:
            raise NativeUnavailable('cooldown_non_atomic_dump')
        n = NativeReader(recorded)
        if n.profile.get('build') != 98348 or len(SIGNATURES) != 3:
            raise NativeUnavailable('cooldown_profile_unsupported')
        for signature in SIGNATURES:
            if hashlib.sha256(n.read(n.base+signature['rva'], signature['size'])).hexdigest() != signature['sha256']:
                raise NativeUnavailable('cooldown_signature_mismatch')
        initial = ActiveMatch().observe(n)
        first = _clock(n, recorded)
        probe.begin()
        probe.observe_native(budget, clock=clock)
        context = probe.finish()
        map_id, match_id, local, team, _ = AlliedPositions._context(context)
        ids = json.loads((Path(__file__).parent/'hero_ids.json').read_text(encoding='utf-8'))
        actual = AlliedPositions(n)._identity(n, ids)
        if (map_id not in ('Volskaya', 'DragonShire')
                or context.get('meta', {}).get('context_source') != 'initdata_native_fields'
                or initial['match_id'] != match_id or actual[:2] != (local, team)
                or ids.get(context['local_player']['hero'], context['local_player']['hero']) != actual[2]
                or any(p['team'] != next(m['team'] for m in actual[3] if m['id'] == p['id'])
                       for p in context['players'])):
            raise NativeUnavailable('cooldown_identity_or_scope')
        player = pointer(n.player_pointer(local+1))
        tag = n.value(player+0x58)
        unit = pointer(n.unit_pointer(tag, local+1))
        alive = n.value(unit+0x39, 'B') & 6 == 0
        # Dead/corpse list is not a live ability source. Still recheck identity.
        links = read_unit_links(n, unit) if alive else None
        for address, data in recorded.coherence_reads('cooldown_torn'):
            if budget.read_memory(address, len(data)) != data:
                raise NativeUnavailable('cooldown_torn')
        probe.recheck(budget)
        last = _clock(n, recorded)
        elapsed = clock()-budget.started
        if not 0 <= last-first <= 0.125 or not 0 <= elapsed <= 0.125:
            raise NativeUnavailable('cooldown_window_expired')
        row.update(status='diagnostic_observed', map_id=map_id, match_id=match_id,
                   local_id=local, team=team, hero=actual[2], alive=alive,
                   unit_tag=tag, generation=tag & 0x3FFFFF,
                   mission_interval_s=[first, last], elapsed_s=elapsed,
                   ability_binding='unproven', player_storage='unqualified',
                   charges='unqualified', cast_legality='unknown')
        if alive:
            row['links'] = links
        else:
            row['reason'] = 'local_dead_no_ability_observation'
    except NativeUnavailable as exc:
        row = dict(status='rejected', kind=row['kind'], reason=str(exc))
    row.update(read_count=budget.read_count, bytes_requested=budget.bytes_requested)
    return row
