"""Qualified CURRENT bindings, not a hero catalogue or base loadout.

Only Sonya's main-hero Spear Unit cooldown is qualified by the real whole
consumer/HUD cycle. BattleRage dynamic Full, other peers, modifiers and UI
control-body transformations remain unqualified. Upstream MUST verify actual
native instance/cost/storage/owner/root signatures before this narrowing step.
"""
from __future__ import annotations

import copy
from .native import NativeUnavailable

# (native class, CD storage/link, charge storage/link, qualified current max).
# max0 permits only explicit not-applicable from a CURRENT native zero, never
# a missing node. Other entries may be added only after their own qualification.
QUALIFIED_BINDINGS = {
    (98348, 'DragonShire', 'sonya'): {
        'BarbarianAncientSpear': (9, 'unit', 'Abil/BarbarianAncientSpear', None, None, 0),
    },
}
CD_FIELDS = ('remaining_s', 'cooldown_ready')
CHARGE_FIELDS = ('charges_max', 'charges_used', 'charges_available', 'charge_regen_s')


def binding(scope, ability):
    return QUALIFIED_BINDINGS.get(scope, {}).get(ability)


def qualify(scope, instance, row):
    """Narrow already-observed native values; never construct a missing ability."""
    ability = instance['ability']
    case = binding(scope, ability)
    if case is None:
        return None
    if row.get('ability') != ability or row.get('cast_legality') != 'unknown':
        raise NativeUnavailable('cooldown_binding_row_or_cast_scope_mismatch')
    result = copy.deepcopy(row)
    def unknown(kind, fields):
        result[kind] = 'unknown'
        for field in fields:
            result.pop(field, None)
    cost = instance.get('current_cost', {})
    bound = (isinstance(cost, dict) and cost.get('status') == 'diagnostic_current_cost'
             and cost.get('source_scope') == 'current_local_player_overlay_NOT_BASE'
             and type(cost.get('native_class')) is int and cost['native_class'] == case[0]
             and type(cost.get('command')) is int and cost['command'] == 0
             and cost.get('cooldown_storage') == case[1] and cost.get('cooldown_link') == case[2])
    if not bound:
        unknown('cooldown_status', CD_FIELDS)
        unknown('charges_status', CHARGE_FIELDS)
        return result
    if cost.get('cooldown_applies') is not True:
        unknown('cooldown_status', CD_FIELDS)
    maximum = cost.get('charges_max')
    numeric = type(maximum) in (int, float)
    if case[5] == 0:
        if (not numeric or maximum != 0
                or result.get('charges_status') != 'not_applicable_current_max_zero'):
            unknown('charges_status', CHARGE_FIELDS)
    elif (not numeric or maximum != case[5] or cost.get('charge_storage') != case[3]
            or cost.get('charge_link') != case[4]
            or (result.get('charges_status') == 'diagnostic_observed' and result.get('charges_max') != case[5])):
        unknown('charges_status', CHARGE_FIELDS)
    return result
