"""Closed cooldown exports (lot8 schema), revalidated without issuing receipts.

Only existing qualified bindings are admissible. Independent historical samples
are not casts, reset evidence, HUD buttons or total castability.
"""
from __future__ import annotations

from .diagnostics import number

TIMING = ('source_mission_t_s', 'age_s', 'read_window_s')
VALUE_FIELDS = ('remaining_s', 'cooldown_ready', 'charges_max', 'charges_used',
                'charges_available', 'charge_regen_s')


def _value(packet):
    """Re-sanitize lot8's stored schema, never diagnostic tables or receipts."""
    from hotstate.cooldown_packet import VALIDATED_SCOPES
    from hotstate.cooldown_qualification import binding
    if (type(packet) is not dict or type(packet.get('build')) is not int or packet['build'] != 98348
            or type(packet.get('map_id')) is not str or type(packet.get('hero')) is not str
            or (packet['map_id'], packet['hero']) not in VALIDATED_SCOPES
            or type(packet.get('local_slot')) is not int or not 0 <= packet['local_slot'] < 10
            or type(packet.get('team')) is not int or packet['team'] not in (0, 1)
            or packet.get('actor_scope') != 'current_native_main_hero'
            or packet.get('ui_control_body') != 'unknown' or type(packet.get('alive')) is not bool
            or type(packet.get('abilities')) is not list or len(packet['abilities']) > 64
            or (not packet['alive'] and packet['abilities'])):
        raise ValueError('invalid_cooldowns_export')
    abilities, slots = [], set()
    for a in packet['abilities']:
        if (type(a) is not dict or type(a.get('ability')) is not str
                or type(a.get('instance_slot')) is not int or not 0 <= a['instance_slot'] < 64
                or a['instance_slot'] in slots or a.get('slot_kind') != 'native_instance_NOT_HUD_button'
                or a.get('cast_legality') != 'unknown'
                or a.get('cooldown_status') not in ('observed', 'unknown')
                or a.get('charges_status') not in ('observed', 'unknown', 'not_applicable_current_max_zero')):
            raise ValueError('invalid_cooldowns_export')
        case = binding((packet['build'], packet['map_id'], packet['hero']), a['ability'])
        if case is None:
            raise ValueError('invalid_cooldowns_export')
        slots.add(a['instance_slot'])
        row = {k: a[k] for k in ('ability', 'instance_slot', 'slot_kind', 'cast_legality',
                                 'cooldown_status', 'charges_status')}
        if a['cooldown_status'] == 'observed':
            if (not number(a.get('remaining_s'), 0, 3600) or type(a.get('cooldown_ready')) is not bool
                    or a['cooldown_ready'] != (a['remaining_s'] == 0)):
                raise ValueError('invalid_cooldowns_export')
            row.update(remaining_s=a['remaining_s'], cooldown_ready=a['cooldown_ready'])
        elif any(k in a for k in ('remaining_s', 'cooldown_ready')):
            raise ValueError('invalid_cooldowns_export')
        fields = VALUE_FIELDS[2:]
        if a['charges_status'] == 'observed':
            if (case[5] <= 0 or a.get('charges_max') != case[5]
                    or not all(number(a.get(k), 0, 3600 if k == 'charge_regen_s' else 1024) for k in fields)
                    or a['charges_available'] != max(0, a['charges_max'] - a['charges_used'])):
                raise ValueError('invalid_cooldowns_export')
            row.update({k: a[k] for k in fields})
        elif (any(k in a for k in fields)
              or (a['charges_status'] == 'not_applicable_current_max_zero' and case[5] != 0)):
            raise ValueError('invalid_cooldowns_export')
        abilities.append(row)
    return {**{k: packet[k] for k in ('build', 'map_id', 'hero', 'local_slot', 'team',
                                      'actor_scope', 'ui_control_body', 'alive')},
            'abilities': sorted(abilities, key=lambda a: a['instance_slot'])}


def cooldowns_summary(state):
    """Persist only the normalized product projection and its original age."""
    q = state.get('cooldowns_qualification')
    q = q if type(q) is dict else {}
    status = q.get('status')
    result = dict(status=status if type(status) is str and status in (
        'normalized', 'refused', 'rejected', 'not_attempted') else 'unknown',
        source='native_player' if q.get('source') == 'native_player' else 'unknown',
        source_mission_t_s=None, age_s=None, read_window_s=None, value=None)
    if result['status'] != 'normalized':
        return result
    result['status'] = 'rejected'
    try:
        meta, local, team = state['meta'], state['local_player'], state['ally_team']
        packet = state['local_cooldowns']
        if (result['source'] != 'native_player' or meta.get('source') != 'live'
                or meta.get('native_status') != 'valide'
                or meta.get('context_source') != 'initdata_native_fields'
                or type(local.get('id')) is not int or type(local.get('team')) is not int
                or type(team) is not int or local['team'] != team
                or packet['local_id'] != local['id'] or packet['hero'] != local['hero']
                or not number(q.get('source_mission_t_s'), 0, 21600)
                or not number(q.get('age_s'), 0, 1) or not number(q.get('read_window_s'), 0, .125)
                or not number(meta.get('t_s'), 0, 21600)
                or not 0 <= meta['t_s'] - q['source_mission_t_s'] <= 1
                or packet['t'] != q['source_mission_t_s']):
            return result
        owners = [h for h in state['heroes'] if h.get('id') == local['id']]
        if (len(owners) != 1 or type(owners[0].get('id')) is not int
                or type(owners[0].get('team')) is not int or owners[0]['team'] != team
                or owners[0].get('hero') != local['hero'] or owners[0].get('alive') is not packet['alive']):
            return result
        value = _value(dict(packet, build=meta['native_build'], team=team, local_slot=packet['local_id']))
        result.update(status='normalized', value=value, **{k:q[k] for k in TIMING})
    except (KeyError, TypeError, ValueError, AttributeError):
        pass
    return result


def consistent(observations):
    """Check local identity across the entire stream, including refused gaps."""
    identity = alias = None
    for row in observations:
        for family, slot_key in (('local_cooldowns', 'local_slot'), ('talents', 'local_slot')):
            packet = row.get(family)
            if type(packet) is not dict or packet.get('status') != 'normalized':
                continue
            value = packet.get('value')
            # Legacy invalid talent handling belongs to the existing validator.
            if family == 'talents' and identity is None:
                continue
            try:
                slot, team = value[slot_key], value['team']
                hero = value.get('hero') if family == 'local_cooldowns' else next(
                    p['hero'] for p in value['players'] if p['slot'] == slot)
                if (type(slot) is not int or not 0 <= slot < 10
                        or type(team) is not int or team not in (0, 1) or type(hero) is not str):
                    return False
                current = (slot, team, hero)
                if identity is not None and identity != current:
                    return False
                identity = current
            except (KeyError, TypeError, AttributeError, StopIteration):
                return False
    if identity is None:
        return True
    slot, team, hero = identity
    for row in observations:
        # Include talents preceding the first cooldown binding as well.
        t = row.get('talents')
        if type(t) is dict and t.get('status') == 'normalized':
            try:
                v = t['value']
                local = [p for p in v['players'] if p['slot'] == slot]
                if (v['local_slot'] != slot or v['team'] != team
                        or len(local) != 1 or local[0]['hero'] != hero):
                    return False
            except (KeyError, TypeError):
                return False
        heroes = row.get('heroes')
        if type(heroes) is list:
            local_rows = [h for h in heroes if type(h) is dict and h.get('slot') == slot]
            if len(local_rows) > 1:
                return False
            for owner in local_rows:
                if 'team' in owner and (type(owner['team']) is not int or owner['team'] != team):
                    return False
                if 'hero' in owner:
                    if alias is not None and owner['hero'] != alias:
                        return False
                    alias = owner['hero']
    return True


def historical(packet, row, journal_sha256):
    """One independently recorded observation; no fallback, clock or receipt."""
    from .native_history import _status, _provenance, _roster
    result = dict(status=_status(packet), value=None, source=None, source_mission_t_s=None,
                  original_age_s=None, read_window_s=None, provenance=None)
    if result['status'] != 'normalized':
        return result
    result['status'] = 'rejected'
    try:
        if not _provenance(packet, row):
            return result
        value = _value(packet.get('value'))
        roster = _roster(row)
        available = row.get('available_fields')
        if (roster is None or type(available) is not list or 'heroes' not in available
                or value['map_id'] != row['comparison']['map_id']):
            return result
        owner = roster[value['local_slot']]
        if (owner['team'] != value['team'] or type(owner.get('alive')) is not bool
                or owner['alive'] != value['alive']):
            return result
        # A same-event talent binding, when present, cannot disagree. It is not
        # required for cooldown-only collection and is never used to fill gaps.
        talents = row.get('talents')
        if type(talents) is dict and talents.get('status') == 'normalized':
            t = talents['value']
            actors = [p for p in t['players'] if p['slot'] == value['local_slot']]
            if (t['local_slot'] != value['local_slot'] or t['team'] != value['team']
                    or len(actors) != 1 or actors[0]['hero'] != value['hero']):
                return result
        for a in value['abilities']:
            for key in VALUE_FIELDS:
                a.setdefault(key, None)
        result.update(status='normalized', value=value, source='native_player',
            source_mission_t_s=packet['source_mission_t_s'], original_age_s=packet['age_s'],
            read_window_s=packet['read_window_s'], provenance=dict(
                journal_sha256=journal_sha256, sequence=row['sequence'],
                key='/local_cooldowns/value', basis='recorded_not_authenticated'))
    except (KeyError, TypeError, ValueError):
        pass
    return result


def readable(packet):
    lines = [f"Recharge locale : {packet['status']} ; âge original : {packet['original_age_s']} s (non renouvelé).",
             'cooldown_ready ne signifie pas lançable ; slot instance natif ≠ bouton HUD.']
    value = packet['value']
    if value is None:
        lines.append('Valeurs inconnues/non exportées ; absence ou refus ≠ zéro.')
    else:
        lines.append(f"Build {value['build']} ; {value['map_id']} ; héros {value['hero']} ; "
                     f"slot local {value['local_slot']} ; équipe {value['team']} ; vie : {value['alive']}.")
        if not value['abilities']:
            lines.append('Aucune aptitude exportée à cet instant ; aucun reset ou cast déduit.')
        for a in value['abilities']:
            lines.append(f"  {a['ability']} (instance native {a['instance_slot']}) : "
                         f"recharge {a['cooldown_status']} ; restant {a['remaining_s']} s ; "
                         f"cooldown_ready={a['cooldown_ready']} ; charges {a['charges_status']} ; "
                         f"disponibles={a['charges_available']} ; lançable : inconnu.")
    lines.append('Échantillon indépendant ; aucune interpolation, propagation, inférence de cast ou reset.')
    return '\n'.join(lines)
