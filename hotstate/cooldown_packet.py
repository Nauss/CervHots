"""Bounded main-local-hero cooldown packet, partial Spear CD scope only.

Only the actual whole-consumer/HUD-qualified current Spear binding is exposed.
Current native instances and player cost overlays are read, never a base loadout
or an event countdown. Only cooldown readiness; castability/HUD bindings unknown.
No process, GUI, coach or audio is opened here. Caller owns the live backend.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path

from .native import NativeReader, NativeUnavailable
from .positions import AlliedPositions, _RecordedMemory
from .local_experiments import _BudgetMemory, _clock, pointer
from .match import ActiveMatch
from .cooldowns import read_unit_links, SIGNATURES
from . import cooldown_sources, cooldown_costs
from .acquisition import issue
from .cooldown_qualification import QUALIFIED_BINDINGS, qualify

ROOT = Path(__file__).resolve().parents[1]
VALIDATED_SCOPES = (('DragonShire', 'sonya'),)


class LocalCooldowns:
    def __init__(self, native):
        self.native = native

    def read(self, context, *, hero_ids=None):
        ids = hero_ids if hero_ids is not None else json.loads((ROOT/'hotstate/hero_ids.json').read_text())
        map_id, match, local, team, _ = AlliedPositions._context(context)
        hero = ids.get(context['local_player']['hero'], context['local_player']['hero'])
        if (map_id, hero) not in VALIDATED_SCOPES:
            raise NativeUnavailable('recette_cooldowns_absente')
        row = self._observe(context, hero_ids=ids)
        acquired = row.pop('_acquired')
        row['status'] = 'validated'
        return issue(row, acquired)

    def diagnose(self, context, *, hero_ids=None):
        row = self._observe(context, hero_ids=hero_ids)
        row.pop('_acquired')
        row['status'] = 'diagnostic_NOT_PRODUCT'
        return row

    def _observe(self, context, *, hero_ids=None):
        expected = copy.deepcopy(context)
        map_id, match, local, team, _ = AlliedPositions._context(expected)
        if expected['meta'].get('context_source') != 'initdata_native_fields':
            raise NativeUnavailable('cooldown_current_native_context_required')
        if getattr(self.native.memory, 'recorded_non_atomic', False):
            raise NativeUnavailable('cooldown_non_atomic_dump')
        clock = time.monotonic
        budget = _BudgetMemory(self.native.memory, clock=clock)
        recorded = _RecordedMemory(budget, cache=True)
        n = NativeReader(recorded, profile=self.native.profile)
        if len(SIGNATURES) != 3:
            raise NativeUnavailable('cooldown_signature_profile_invalid')
        for s in SIGNATURES:
            if hashlib.sha256(n.read(n.base+s['rva'], s['size'])).hexdigest() != s['sha256']:
                raise NativeUnavailable('cooldown_signature_mismatch')
        cooldown_sources.verify(n)
        cooldown_costs.verify(n)
        initial = ActiveMatch().observe(n)
        if initial['match_id'] != match:
            raise NativeUnavailable('cooldown_active_match_mismatch')
        first = _clock(n, recorded)
        ids = hero_ids if hero_ids is not None else json.loads((ROOT/'hotstate/hero_ids.json').read_text())
        actual = AlliedPositions(n)._identity(n, ids)
        if (actual[:2] != (local, team)
                or actual[2] != ids.get(expected['local_player']['hero'], expected['local_player']['hero'])
                or any(p['team'] != next(m['team'] for m in actual[3] if m['id'] == p['id']) for p in expected['players'])):
            raise NativeUnavailable('cooldown_identity_or_scope')
        player = pointer(n.player_pointer(local+1))
        tag = n.value(player+0x58)
        unit = pointer(n.unit_pointer(tag, local+1))
        alive = n.value(unit+0x39, 'B') & 6 == 0
        abilities = []
        if alive:
            links = read_unit_links(n, unit)
            scope = (n.profile['build'], map_id, actual[2])
            bindings = QUALIFIED_BINDINGS.get(scope, {})
            instances = cooldown_sources.active_instances(n, unit, native_owner=local+1,
                                                          allowed_abilities=frozenset(bindings))
            # Permission selects acquisitions, not values. CURRENT instance
            # class/command/link/max still have to pass qualify() below.
            required_stores = set()
            for case in bindings.values():
                if case[1] == 'player':
                    required_stores.add('player_cooldowns')
                if case[5] > 0 and case[3] in ('unit', 'player'):
                    required_stores.add(case[3] + '_charges')
            stores = {}
            for name, owner, storage, charges in (
                    ('unit_charges', unit, 'unit', True),
                    ('player_cooldowns', player, 'player', False),
                    ('player_charges', player, 'player', True)):
                if name not in required_stores:
                    continue
                try:
                    stores[name] = {'status': 'diagnostic_observed',
                        'value': cooldown_sources.stored_links(n, owner, storage=storage, charges=charges)}
                except NativeUnavailable as exc:
                    if str(exc) in ('prototype_window_expired', 'prototype_budget_exceeded'):
                        raise
                    stores[name] = {'status': 'unknown', 'reason': str(exc)}
            rows = cooldown_costs.diagnostic_abilities(instances, links, stores)
            for instance, row in zip(instances, rows):
                row = qualify(scope, instance, row)
                if row is None:
                    continue  # An attached internal/peer ability is not a HUD grant.
                value = {k:v for k,v in row.items() if k in (
                    'ability', 'cooldown_status', 'remaining_s', 'cooldown_ready',
                    'charges_status', 'charges_max', 'charges_used', 'charges_available',
                    'charge_regen_s', 'cast_legality')}
                value.update(instance_slot=instance['instance_slot'], slot_kind=instance['slot_kind'])
                for field in ('cooldown_status', 'charges_status'):
                    if value[field] == 'diagnostic_observed':
                        value[field] = 'observed'
                abilities.append(value)
        for address, data in recorded.coherence_reads('cooldown_torn'):
            if budget.read_memory(address, len(data)) != data:
                raise NativeUnavailable('cooldown_torn')
        last = _clock(n, recorded)
        elapsed = clock()-budget.started
        if not 0 <= last-first <= 0.125 or not 0 <= elapsed <= 0.125 or context != expected:
            raise NativeUnavailable('cooldown_window_or_context_changed')
        return {'map_id': map_id, 'match_id': match, 'local_id': local, 'team': team,
                'local_hero': actual[2], 'alive': alive, 'mission_t_s': last,
                'actor_scope': 'current_native_main_hero', 'ui_control_body': 'unknown',
                'read_window_s': elapsed, 'abilities': abilities, '_acquired': budget.started,
                'read_count': budget.read_count, 'bytes_requested': budget.bytes_requested}
