"""Player view of recorded native observations. No receipt or current permission.

The technical collection diagnosis remains in session_diagnosis. This view keeps
one recorded instant plus a bounded core timeline, never filling holes from
another observation or a replay.
"""
from __future__ import annotations

from collections import deque
import datetime as dt
import json
import re
import sys

from .session_diagnosis import _journal, FAMILIES, QUALIFICATIONS, STOP_REASONS
from .objective_compare import _number
from .objective_journal import objective_summary
from .talents_journal import _value


def _status(packet):
    value = packet.get('status')
    return value if type(value) is str and value in QUALIFICATIONS else 'unknown'


def _packet(row, name, not_selected):
    if not_selected is None:
        return {'status': 'unknown'}
    raw = row.get(name)
    packet = raw if type(raw) is dict else {}
    available = row.get('available_fields')
    if (name in not_selected or (_status(packet) == 'normalized'
            and (type(available) is not list or name not in available))):
        return {'status': 'not_selected'}
    return packet


def _provenance(packet, row):
    return (packet.get('source') == 'native_player'
            and _number(packet.get('age_s'), 1) and _number(packet.get('read_window_s'), .125)
            and _number(packet.get('source_mission_t_s'), 21600)
            and 0 <= row['mission_t_s'] - packet['source_mission_t_s'] <= 1)


def _roster(row):
    heroes = row.get('heroes')
    if type(heroes) is not list or len(heroes) != 10:
        return None
    roster = {}
    for h in heroes:
        if (type(h) is not dict or type(h.get('slot')) is not int or not 0 <= h['slot'] < 10
                or h['slot'] in roster or type(h.get('team')) is not int or h['team'] not in (0,1)):
            return None
        roster[h['slot']] = h
    if any(sum(h['team'] == team for h in roster.values()) != 5 for team in (0,1)):
        return None
    return roster


def _talents(packet, row):
    result = dict(status=_status(packet), source=None, source_mission_t_s=None,
                  original_age_s=None, read_window_s=None, local=None)
    if result['status'] != 'normalized':
        return result
    result['status'] = 'rejected'
    try:
        if not _provenance(packet, row):
            return result
        value = _value(packet.get('value'))
        roster = _roster(row)
        if (roster is None or value['map_id'] != row['comparison']['map_id']
                or any(roster[p['slot']]['team'] != value['team']
                       or type(roster[p['slot']].get('level')) is not int
                       or roster[p['slot']].get('level') != p['level'] for p in value['players'])):
            return result
        local = next(p for p in value['players'] if p['slot'] == value['local_slot'])
        if local['status'] != 'observed':
            return result
        # Catalog IDs are not qualified French labels, and need not leave disk.
        clean = dict(hero=local['hero'], level=local['level'],
            tiers=[{k:t[k] for k in ('tier','required_level','status','slot','label')}
                   for t in local['tiers']])
        result.update(status='normalized', source='native_player',
            source_mission_t_s=packet['source_mission_t_s'], original_age_s=packet['age_s'],
            read_window_s=packet['read_window_s'], local=clean)
    except (KeyError, ValueError, TypeError, StopIteration):
        pass
    return result


def _objective(packet, row):
    result = dict(status=_status(packet), value=None, original_age_s=None,
                  source=None, source_mission_t_s=None, read_window_s=None)
    if result['status'] != 'normalized':
        return result
    result['status'] = 'rejected'
    if not _provenance(packet, row):
        return result
    # Reuse exactly the existing public Dragon exporter, without any receipt.
    if (row['comparison']['map_id'] != 'DragonShire' or packet.get('family') != 'dragon'
            or packet.get('value_status') != 'exported' or type(packet.get('value')) is not dict):
        return result
    state = dict(objective_qualification=packet,
        objective=dict(packet['value'], map_id='DragonShire', t=packet['source_mission_t_s']))
    clean = objective_summary(state)
    if clean['status'] == 'normalized' and clean['value_status'] == 'exported':
        result.update(status='normalized', value=clean['value'], source='native_player',
                      source_mission_t_s=clean['source_mission_t_s'],
                      original_age_s=clean['age_s'], read_window_s=clean['read_window_s'])
    return result


def _empty_core(status):
    return dict(status=status, identity_basis=None, original_age_s=None,
                health=dict(status=status, value=None, maximum=None),
                resource=dict(status=status, value=None, maximum=None), alive=None)


def _core(row, talents):
    """Local binding from this SAME validated packet, never a first-ally guess.

    The journal records a generic resource, not its kind (mana/fury/etc.).
    No native receipt is issued and no current catalog is consulted.
    """
    result = _empty_core('unknown')
    if talents['status'] != 'normalized':
        return result
    roster = _roster(row)
    value = row['talents']['value']
    available = row.get('available_fields')
    if (roster is None or type(available) is not list or 'heroes' not in available):
        return _empty_core('invalid')
    local = roster[value['local_slot']]
    if (local['team'] != value['team'] or type(local.get('hero')) is not str
            or not re.fullmatch('hero_[0-9a-f]{12}', local['hero'])):
        return _empty_core('invalid')
    result.update(status='recorded', identity_basis='validated_recorded_local_talents')
    for field, maximum in (('health', 'health_max'), ('resource', 'resource_max')):
        pair = result[field]
        pair['status'] = 'absent'
        # A present but malformed member stays invalid even if its partner is absent.
        if any(k in local and not _number(local[k], 100000) for k in (field, maximum)):
            pair['status'] = 'invalid'
        elif field in local and maximum in local:
            if local[maximum] <= 0 or local[field] > local[maximum]:
                pair['status'] = 'invalid'
            else:
                pair.update(status='recorded', value=local[field], maximum=local[maximum])
    if type(local.get('alive')) is bool:
        result['alive'] = local['alive']
    return result


def _consistent(observations):
    """Check the WHOLE recorded stream, not just a conveniently bound last row.

    These are unauthenticated consistency checks, never active identity checks.
    Legacy missing comparison/age cannot be reconstructed from external verdicts.
    """
    identity = local_identity = previous = core_identity = None
    for row in observations:
        try:
            c = row['comparison']
            if type(c) is not dict:
                return False
            for key in ('session', 'map'):
                if type(row.get(key)) is not str or not re.fullmatch(key + '_[0-9a-f]{12}', row[key]):
                    return False
            if (type(c.get('session_token')) is not str
                    or not re.fullmatch('[0-9a-f]{32}', c['session_token'])
                    or type(c.get('map_id')) is not str or c['map_id'] not in ('DragonShire', 'Volskaya')
                    or c.get('perspective') != 'native_player' or c.get('clock_basis') != 'host_monotonic'
                    or not _number(c.get('read_started_s')) or not _number(c.get('read_finished_s'))
                    or c['read_started_s'] > c['read_finished_s']
                    or not _number(row.get('mission_t_s'), 21600)
                    or not _number(row.get('elapsed_s'))
                    or type(row.get('timestamp_utc')) is not str or len(row['timestamp_utc']) > 64):
                return False
            utc = dt.datetime.fromisoformat(row['timestamp_utc'])
            if utc.utcoffset() != dt.timedelta(0):
                return False
            current = (row['session'], row['map'], c['session_token'], c['map_id'], c['perspective'])
            if identity is not None and identity != current:
                return False
            identity = current
            times = (row['mission_t_s'], row['elapsed_s'], utc, c['read_started_s'], c['read_finished_s'])
            if previous is not None and (any(a > b for a,b in zip(previous, times))
                                         or previous[4] > times[3]):
                return False
            previous = times
            packet = row.get('talents')
            if type(packet) is dict and packet.get('status') == 'normalized':
                value = packet.get('value')
                if type(value) is not dict or value.get('map_id') != c['map_id']:
                    return False
                team, slot = value.get('team'), value.get('local_slot')
                if type(team) is not int or team not in (0,1) or type(slot) is not int or not 0 <= slot < 10:
                    return False
                players = value.get('players')
                if type(players) is not list:
                    return False
                local_rows = [p for p in players if type(p) is dict and p.get('slot') == slot]
                if len(local_rows) != 1 or type(local_rows[0].get('hero')) is not str:
                    return False
                this_local = (team, slot, local_rows[0]['hero'])
                if local_identity is not None and local_identity != this_local:
                    return False
                local_identity = this_local
                roster = _roster(row)
                alias = roster[slot].get('hero') if roster else None
                if type(alias) is str and re.fullmatch('hero_[0-9a-f]{12}', alias):
                    binding = (team, slot, alias)
                    if core_identity is not None and binding != core_identity:
                        return False
                    core_identity = binding
        except (KeyError, ValueError, TypeError, OverflowError):
            return False
    if core_identity is not None:
        team, slot, alias = core_identity
        for row in observations:
            roster = _roster(row)
            # A legacy omission cannot supply a binding, but a recorded change
            # must not be hidden by a refused/missing optional packet.
            if roster is not None:
                local = roster[slot]
                if local['team'] != team or ('hero' in local and local['hero'] != alias):
                    return False
            else:
                # A divergent recorded local row can itself invalidate roster
                # balance. Do not hide that contradiction behind roster=None.
                heroes = row.get('heroes')
                if type(heroes) is list:
                    for local in heroes:
                        if (type(local) is dict and type(local.get('slot')) is int
                                and local['slot'] == slot
                                and (('team' in local and (type(local['team']) is not int
                                      or local['team'] != team))
                                     or ('hero' in local and local['hero'] != alias))):
                            return False
    return True


TIMELINE_ENTRY_LIMIT = 128


def _empty_timeline():
    return dict(status='refused', order_basis='journal_ordinal_not_time',
                counts_complete=False, total_observations=None, total_points=None,
                entry_limit=TIMELINE_ENTRY_LIMIT, total_entries=None, displayed_points=0,
                omitted_entries=None, truncated=None, entries=[])


def _core_timeline(rows, acquisitions):
    """Reuse the same-event local binding and value guards after WHOLE validation."""
    from .passive_session import measured_acquisition
    result = _empty_timeline()
    result.update(status='recorded', counts_complete=True, total_observations=0,
                  total_points=0, total_entries=0)
    entries = deque(maxlen=TIMELINE_ENTRY_LIMIT)
    for ordinal, row in enumerate(rows, 1):
        if row['event'] == 'observation':
            result['total_observations'] += 1
            acquisition = acquisitions[row['cycle']]
            selection = measured_acquisition({'collection': acquisition.get('collection')}).get('not_selected')
            core = _core(row, _talents(_packet(row, 'talents', selection), row))
            if (core['health']['status'] == 'recorded'
                    or core['resource']['status'] == 'recorded' or core['alive'] is not None):
                result['total_points'] += 1
            entries.append(dict(journal_ordinal=ordinal, kind='observation', core=core))
            result['total_entries'] += 1
        elif row['event'] in ('refusal', 'error', 'source_error', 'boundary'):
            entries.append(dict(journal_ordinal=ordinal, kind=row['event'], core=None))
            result['total_entries'] += 1
        elif row['event'] == 'acquisition' and row.get('outcome') in ('refused', 'error'):
            entries.append(dict(journal_ordinal=ordinal, kind='acquisition_refused', core=None))
            result['total_entries'] += 1
    result['entries'] = list(entries)
    result['omitted_entries'] = result['total_entries'] - len(entries)
    result['truncated'] = result['omitted_entries'] > 0
    result['displayed_points'] = sum(
        e['core'] is not None and (e['core']['health']['status'] == 'recorded'
            or e['core']['resource']['status'] == 'recorded' or e['core']['alive'] is not None)
        for e in entries)
    return result


def summarize(path):
    rows, integrity = _journal(path)
    return _summarize(rows, integrity)


def _summarize(rows, integrity):
    """Project already bounded/parsed records; shared by the local HTML view."""
    observations = [r for r in rows if r['event'] == 'observation']
    result = dict(event='native_history', schema_version=1, basis='historical_not_current',
        authenticated=False, current_permission=False, hud_validated=False,
        current_age_s=None, journal=integrity, state='refused', reason='no_observation',
        map=None, instant=None, public_levels=None, talents=None, objective=None,
        local_core=_empty_core('refused'), core_timeline=_empty_timeline(),
        families=None, families_basis='recorded_status_only',
        closure=dict(recorded_reason='unknown', reader_active=None),
        identity='not_established', later_refusal_or_error=None,
        limitations=['unauthenticated_disk', 'not_current', 'not_hud_validated',
                     'no_new_receipt', 'core_age_not_recorded', 'no_advice'])
    if integrity['state'] != 'complete':
        result['reason'] = 'incomplete_journal'
        return result
    if not observations:
        return result
    boundaries = [r for r in rows if r['event'] == 'boundary']
    if (len(boundaries) != 1 or rows[-1]['event'] != 'boundary'
            or type(boundaries[0].get('reason')) is not str or boundaries[0]['reason'] not in STOP_REASONS):
        result['reason'] = 'session_closure_unknown'
        return result
    result['closure']['recorded_reason'] = boundaries[0]['reason']
    if not _consistent(observations):
        result['reason'] = 'identity_or_time_refused'
        return result
    acquisitions = {r['cycle']: r for r in rows if r['event'] == 'acquisition'}
    refused_cycles = {r['cycle'] for r in rows if r['event'] in ('refusal', 'error', 'source_error')}
    if any(r['cycle'] not in acquisitions or acquisitions[r['cycle']].get('outcome') != 'accepted'
           or acquisitions[r['cycle']]['sequence'] >= r['sequence'] or r['cycle'] in refused_cycles
           for r in observations):
        result['reason'] = 'acquisition_pair_refused'
        return result
    result['core_timeline'] = _core_timeline(rows, acquisitions)
    row = observations[-1]
    result['identity'] = 'consistent_recorded_binding_not_authenticated'
    result['later_refusal_or_error'] = any(r['sequence'] > row['sequence']
        and r['event'] in ('refusal','error','source_error') for r in rows)
    result.update(state='recorded_observation', reason=None, map=row['comparison']['map_id'],
        instant=dict(sequence=row['sequence'], cycle=row['cycle'], mission_t_s=row['mission_t_s'],
                     host_read_bounds=dict(clock_basis='host_monotonic',
                         started_s=row['comparison']['read_started_s'], finished_s=row['comparison']['read_finished_s']),
                     timestamp_utc=dt.datetime.fromisoformat(row['timestamp_utc']).isoformat(),
                     elapsed_s=row['elapsed_s']))
    roster = _roster(row)
    available = row.get('available_fields')
    levels = []
    for team in (0, 1):
        team_levels = [h.get('level') for h in roster.values() if h['team'] == team] if roster else []
        valid = (type(available) is list and 'heroes' in available and len(team_levels) == 5
                 and all(type(v) is int and 1 <= v <= 30 for v in team_levels)
                 and len(set(team_levels)) == 1)
        levels.append(team_levels[0] if valid else None)
    result['public_levels'] = dict(by_team=levels, original_age_s=None, source='recorded_public_levels')
    from .passive_session import measured_acquisition
    acquisition = next((r for r in rows if r['event'] == 'acquisition' and r['cycle'] == row['cycle']), {})
    not_selected = measured_acquisition({'collection': acquisition.get('collection')}).get('not_selected')
    if not_selected is None:
        result['limitations'].append('selection_metadata_unknown')
    packets = {name: _packet(row, name, not_selected) for name in FAMILIES}
    result['families'] = {name: _status(packet) for name,packet in packets.items()}
    result['talents'] = _talents(packets['talents'], row)
    talents = result['talents']
    talents['selected_details'] = None
    if talents['status'] == 'normalized':
        from .talent_labels import resolve_selected, source_bytes
        value = packets['talents']['value']
        # Inspect only this validated local actor, never offered options/allies.
        actor_index, actor = next((i, p) for i, p in enumerate(value['players'])
                                  if p['slot'] == value['local_slot'])
        data = source_bytes()
        talents['selected_details'] = [dict(
            tier=t['tier'], required_level=t['required_level'], slot=t['slot'], catalog_id=t['catalog_id'],
            selection_provenance=dict(journal_sha256=integrity.get('sha256'), sequence=row['sequence'],
                build=value['build'], hero=actor['hero'], basis='recorded_not_authenticated',
                key=f'/talents/value/players/{actor_index}/tiers/{i}'),
            resolution=resolve_selected(value['build'], actor['hero'], t, data))
            for i, t in enumerate(actor['tiers']) if t['status'] == 'selected']
    result['local_core'] = _core(row, result['talents'])
    result['limitations'].extend(['resource_kind_not_recorded', 'local_binding_requires_recorded_talents'])
    result['objective'] = _objective(packets['objective'], row)
    for name in ('talents', 'objective'):
        result['families'][name] = result[name]['status']
    return result


def timeline_summary(timeline):
    if timeline['status'] != 'recorded':
        return 'Chronologie refusée : aucune valeur retenue ; totaux admissibles inconnus.'
    return (f"Points admissibles sur le flux complet : {timeline['total_points']} ; "
            f"observations : {timeline['total_observations']}. "
            f"Points affichés : {timeline['displayed_points']} ; "
            f"plafond : {timeline['entry_limit']} entrées (ruptures comprises). "
            f"Entrées antérieures omises : {timeline['omitted_entries']}.")


def timeline_rows(timeline):
    """Plain text cells from the minimized projection, shared by text and HTML."""
    labels = dict(recorded='enregistré', absent='absent', invalid='invalide',
                  unknown='inconnu', refused='refusé')
    kinds = dict(observation='Observation', refusal='Refus — rupture',
                 error='Erreur — rupture', source_error='Erreur de source — rupture',
                 acquisition_refused='Acquisition refusée — rupture', boundary='Frontière de clôture')
    for entry in timeline['entries']:
        core = entry['core']
        cells = [str(entry['journal_ordinal']), kinds.get(entry['kind'], 'Rupture inconnue')]
        if core is None:
            yield cells + ['—', '—', '—']
            continue
        if core['status'] != 'recorded':
            cells[1] += ' — liaison locale inconnue/invalide (rupture)'
        elif any(core[k]['status'] != 'recorded' for k in ('health', 'resource')):
            cells[1] += ' — paire absente/invalide (pas de continuité supposée)'
        for key in ('health', 'resource'):
            pair = core[key]
            cells.append(f"{pair['value']:.15g} / {pair['maximum']:.15g}"
                         if pair['status'] == 'recorded' else labels.get(pair['status'], 'inconnu'))
        cells.append({True: 'vivant', False: 'mort', None: 'inconnu'}[core['alive']])
        yield cells


def readable(result, *, include_timeline=True):
    lines = ['Observations natives enregistrées — historique NON authentifié.',
             'Jamais CURRENT, ni validation HUD ; aucun conseil ni reçu recréé.',
             'Âge actuel inconnu ; âge du cœur non enregistré (pas zéro).',
             f"Journal : {result['journal']['state']} ; résultat : {result['state']}."]
    if result['state'] == 'refused':
        lines.append('Valeurs retenues : aucune ; motif : ' + result['reason'] + '.')
    else:
        instant = result['instant']
        lines.append(f"Dernière observation enregistrée : mission {instant['mission_t_s']:g} s, "
                     f"UTC {instant['timestamp_utc']} (séquence {instant['sequence']}).")
        lines.append('Carte enregistrée : ' + (result['map'] or 'inconnue') + '.')
        levels = result['public_levels']['by_team']
        lines.append('Niveaux publics enregistrés : ' + ', '.join(
            f"équipe {i} : {v if v is not None else 'inconnu'}" for i,v in enumerate(levels)) + '.')
        core = result['local_core']
        labels = dict(recorded='enregistré', absent='absent', invalid='invalide',
                      unknown='inconnu', refused='refusé')
        for key, label in (('health', 'Santé locale'), ('resource', 'Ressource locale')):
            pair = core[key]
            shown = (f"{pair['value']:.15g} / {pair['maximum']:.15g}"
                     if pair['status'] == 'recorded' else 'inconnue')
            lines.append(f"{label} : {shown} ; {labels[pair['status']]}.")
        life = {True: 'vivant', False: 'mort', None: 'inconnue'}[core['alive']]
        lines.append('Vie locale : ' + life + ' (enregistrement historique).')
        lines.append('Type de ressource non enregistré : mana non établi ; aucun âge du cœur enregistré.')
        lines.append('Liaison locale : ' + ('talents locaux validés du même événement.'
                     if core['identity_basis'] else 'inconnue ; aucune identité devinée.'))
        talents = result['talents']
        lines.append(f"Talents locaux : {talents['status']} ; âge original à la normalisation : "
                     f"{talents.get('original_age_s')} s (non renouvelé).")
        local = talents.get('local')
        if local:
            lines.append(f"Héros local : {local['hero']} ; niveau enregistré : {local['level']}.")
            for tier in local['tiers'] or []:
                choice = (f"choix natif {tier['slot']}" if tier['status'] == 'selected'
                          else 'non sélectionné' if tier['status'] == 'unselected' else 'inconnu')
                lines.append(f"  palier {tier['tier']} (niveau requis {tier['required_level']}) : "
                             f"{choice} ; libellé inconnu.")
        details = talents.get('selected_details')
        if details is not None:
            from .talent_labels import detail_text
            lines.append('Talents locaux choisis — traçabilité et limites :')
            if not details:
                lines.append('  Aucun choix enregistré à cet instant ; aucune option offerte utilisée.')
            for detail in details:
                lines.extend(detail_text(detail))
            lines.append('Une correspondance statique ne qualifie jamais la lecture native ni le HUD.')
        objective = result['objective']
        lines.append('Objectif : ' + objective['status'] + ' ; absence/refus ≠ zéro.')
        if objective['value'] is not None:
            phases = dict(waiting='attente', warning='avertissement', shrines='sanctuaires',
                          dragon='dragon', unknown='inconnue')
            lines.append('  Phase publique Dragon : ' + phases[objective['value']['phase']] + '.')
    if include_timeline:
        timeline = result['core_timeline']
        lines.extend(['Chronologie du cœur local — ordre ordinal du journal, aucune durée.',
                      timeline_summary(timeline)])
        lines.extend(' | '.join(cells) for cells in timeline_rows(timeline))
    return '\n'.join(lines) + '\n'


def run(args):
    try:
        if args.report_dir.resolve().is_relative_to(args.journal.resolve().parent):
            raise ValueError('output_overlaps_input')
        result = summarize(args.journal)
        text = readable(result)
        args.report_dir.mkdir(parents=True, exist_ok=False)
        with (args.report_dir/'history.json').open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=True, allow_nan=False, indent=2)
        with (args.report_dir/'SUMMARY.txt').open('x', encoding='utf-8') as stream:
            stream.write(text)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps(dict(event='native_history_error', code='output_or_input_refused',
                              current_permission=False, hud_validated=False)))
        return 1
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    print(text, file=sys.stderr, end='')
    return 0 if result['state'] == 'recorded_observation' else 1
