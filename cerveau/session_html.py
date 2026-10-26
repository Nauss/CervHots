"""Static local view of the existing minimized historical engines. No acquisition."""
from __future__ import annotations

from html import escape
import json
import os
from pathlib import Path
import sys
import tempfile

from . import native_history, session_diagnosis


STATUS = {'normalized': 'Valeur présente (historique)', 'not_selected': 'Non sélectionné',
          'unknown': 'Inconnu', 'refused': 'Refusé', 'rejected': 'Rejeté',
          'not_attempted': 'Non tenté'}
FAMILIES = {'gameplay_clock': 'Horloge de mission', 'positions': 'Positions',
            'visibility': 'Visibilité', 'objective': 'Objectif', 'talents': 'Talents',
            'local_cooldowns': 'Temps de recharge locaux', 'battlefield': 'Champ de bataille'}


def build(path):
    # One bounded parser, two semantic projections of the SAME bytes.
    records, integrity = session_diagnosis._journal(path)
    history = native_history._summarize(records, integrity)
    diagnosis = session_diagnosis._diagnose(records, integrity)
    keys = ('counts_scope', 'total_acquisitions', 'counts', 'refusal_codes',
            'optional_refusals', 'normalized_fields', 'stop')
    return dict(event='session_html', schema_version=1, basis='historical_not_current',
                authenticated=False, current_permission=False, hud_validated=False,
                history=history, diagnosis={k: diagnosis[k] for k in keys})


def _text(value):
    return escape(str(value), quote=True)


def _objective_value(value):
    """Translate only the already exported public structure, preserving nulls."""
    labels = dict(phase='Phase', shrines='Sanctuaires', statue='Statue', dragon='Dragon',
                  start='Début', respawn='Réapparition', warning='Avertissement',
                  id='Sanctuaire', owner='Équipe propriétaire', state='État',
                  contested='Contesté', team='Équipe', channeling='Canalisation',
                  remaining_s='Temps restant (s)', paused='En pause')
    words = dict(sun='Soleil', moon='Lune', unknown='inconnu', waiting='attente',
                 warning='avertissement', shrines='sanctuaires', dragon='dragon',
                 neutral='neutre', controlled='contrôlé', inactive='inactif',
                 active='actif', alive='vivant', absent='absent')
    if type(value) is dict:
        return '<dl>'+''.join('<dt>'+_text(labels.get(k, k))+'</dt><dd>'+_objective_value(v)
                              +'</dd>' for k, v in value.items())+'</dl>'
    if type(value) is list:
        return '<ul>'+''.join('<li>'+_objective_value(v)+'</li>' for v in value)+'</ul>'
    if value is None:
        return 'inconnu'
    if type(value) is bool:
        return 'oui' if value else 'non'
    return _text(words.get(value, value))


def render(result, *, synthetic=False):
    from .report_context import synthetic_notice
    notice = synthetic_notice(synthetic)
    history, diagnosis = result['history'], result['diagnosis']
    # All dynamic values are text nodes, never attributes, CSS, URLs or markup.
    summary = _text(native_history.readable(history, include_timeline=False))
    from .cooldowns_journal import readable as cooldowns_readable
    cooldowns = history.get('local_cooldowns')
    cooldowns_text = _text(cooldowns_readable(cooldowns) if cooldowns else 'Valeurs refusées : aucune retenue.')
    timeline = history['core_timeline']
    timeline_summary = _text(native_history.timeline_summary(timeline))
    timeline_rows = ''.join('<tr>'+''.join('<td>'+_text(cell)+'</td>' for cell in cells)+'</tr>'
                            for cells in native_history.timeline_rows(timeline))
    families = history['families'] or {name: 'unknown' for name in FAMILIES}
    family_rows = ''.join('<tr><th>'+_text(label)+'</th><td>'+_text(STATUS.get(families[name], 'Inconnu'))
                          +'</td></tr>' for name, label in FAMILIES.items())
    counts = diagnosis['counts']
    count_rows = ''.join('<tr><th>'+label+'</th><td>'+_text(counts[key])+'</td></tr>' for key, label in (
        ('acquisitions', 'Acquisitions enregistrées'), ('observations', 'Observations enregistrées'),
        ('refused_cycles', 'Cycles avec refus'), ('errors', 'Erreurs enregistrées'),
        ('source_errors', 'Erreurs de source')))
    refusals = ''.join('<li>'+_text(code)+' : '+_text(count)+'</li>'
                       for code, count in diagnosis['refusal_codes'].items())
    optional = ''.join('<li>'+_text(FAMILIES[name])+' — '+_text(code)+' : '+_text(count)+'</li>'
                       for name, reasons in diagnosis['optional_refusals'].items()
                       for code, count in reasons.items())
    fields = ', '.join(diagnosis['normalized_fields']) or 'aucun champ exporté'
    objective = history.get('objective')
    objective_value = ('<p>Valeur inconnue ou non exportée ; absence/refus ≠ zéro.</p>'
                       if not objective or objective['value'] is None
                       else _objective_value(objective['value']))
    scope = ('Journal complet : décomptes des seuls événements enregistrés.'
             if diagnosis['counts_scope'] == 'recorded_events' else
             'Journal incomplet : préfixe valide seulement ; totaux de session inconnus.')
    later = {True: 'oui', False: 'non', None: 'inconnu'}[history['later_refusal_or_error']]
    timing_rows = ''
    for name in ('talents', 'objective', 'local_cooldowns'):
        packet = history.get(name) or {}
        values = [packet.get(key) for key in ('source_mission_t_s', 'original_age_s', 'read_window_s')]
        timing_rows += '<tr><th>'+_text(FAMILIES[name])+'</th>'+''.join(
            '<td>'+_text('inconnu' if value is None else value)+'</td>' for value in values)+'</tr>'
    return '''<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Session enregistrée — rapport local</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#11151d;color:#e6ebf4;font:16px/1.6 system-ui,sans-serif}
main{max-width:960px;margin:auto;padding:32px 20px 60px}h1{font-size:1.9rem;line-height:1.2}h2{font-size:1.15rem;color:#a9c9ff;margin:0 0 12px}
p{margin:10px 0;overflow-wrap:anywhere}.notice{border-left:4px solid #f4c673;padding:12px 18px;background:#252218}.muted{color:#bcc6d7}
section{background:#1b2230;border:1px solid #344055;border-radius:12px;padding:20px;margin:18px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;margin:0}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid #344055}th{font-weight:500}td{color:#d9e6ff}li{overflow-wrap:anywhere}
.table-scroll{max-width:100%;min-width:0;overflow-x:auto}
.table-scroll:focus-visible{outline:2px solid #a9c9ff;outline-offset:2px}
.table-scroll table{min-width:36rem}th,td{overflow-wrap:anywhere}
dl{display:grid;grid-template-columns:minmax(90px,1fr) 3fr;gap:4px 16px}dt{color:#bcc6d7}dd{margin:0;overflow-wrap:anywhere}dd dl{margin:0}
@media(max-width:600px){main{padding:20px 12px}section{padding:14px}th,td{padding:6px 3px}}
</style></head><body>'''+notice+'''<main>
<header><p class="muted">CervHots · Lecture locale pour l’aventurier</p><h1>Votre session enregistrée</h1>
<p class="notice">Historique NON authentifié. Jamais CURRENT, ni validation HUD, ni conseil.
Inconnue ≠ zéro. Aucun âge actuel calculé, aucun reçu recréé.</p></header>
<section><h2>Dernière observation et cœur enregistré</h2><pre>'''+summary+'''</pre>
<p>Refus ou erreur après cette observation : '''+_text(later)+'''.</p>
<p class="muted">Santé et ressource locales : uniquement les paires enregistrées et validées du même événement, avec liaison locale explicite. Type de ressource inconnu, pas nécessairement du mana. Aucun état natif supplémentaire n’est reconstitué.</p></section>
<section><h2>Chronologie historique bornée</h2><p>'''+timeline_summary+'''</p>
<p class="muted">Ordre ordinal des enregistrements (1 = première ligne du journal), aucune durée ni horloge de jeu déduite. Chaque ligne est indépendante : aucune interpolation ni continuité à travers une rupture, une valeur invalide ou une frontière. Âge du cœur inconnu ; ressource générique, type inconnu.</p>
<p class="muted">Tableaux larges : défilement horizontal au toucher ou au clavier après mise au point du tableau.</p>
<div class="table-scroll" role="region" tabindex="0" aria-label="Chronologie du cœur local — défilement horizontal"><table><caption>Chronologie du cœur local — historique non authentifié</caption>
<thead><tr><th scope="col">Ordre du journal</th><th scope="col">Observation ou rupture</th><th scope="col">PV / maximum</th><th scope="col">Ressource / maximum</th><th scope="col">Vie</th></tr></thead>
<tbody>'''+timeline_rows+'''</tbody></table></div></section>
<section><h2>Sélection et qualification des champs</h2><div class="table-scroll" role="region" tabindex="0" aria-label="Sélection des champs — défilement horizontal"><table>'''+family_rows+'''</table></div>
<p class="muted">Ces statuts ne promettent pas une valeur lisible : seuls talents, objectif et cooldowns locaux qualifiés sont exportés.
Non sélectionné ≠ inconnu ≠ refusé ≠ valeur présente. Une sélection absente ou invalide reste inconnue.</p></section>
<section><h2>Cooldowns et charges locaux enregistrés</h2><pre>'''+cooldowns_text+'''</pre><p class="muted">Valeurs de la même observation uniquement ; slot instance natif ≠ bouton HUD ; cooldown_ready ne signifie pas lançable. Charges inconnues/non applicables ≠ disponibles. Aucun cast, reset, continuité ou changement de corps contrôlé déduit.</p></section>
<section><h2>Objectif historique exporté</h2>'''+objective_value+'''</section>
<section><h2>Horloges originales des valeurs optionnelles</h2><div class="table-scroll" role="region" tabindex="0" aria-label="Horloges originales — défilement horizontal"><table><tr><th>Famille</th><th>Mission source (s)</th><th>Âge original (s)</th><th>Fenêtre de lecture originale (s)</th></tr>'''+timing_rows+'''</table></div>
<p class="muted">Ces durées ne sont ni un âge actuel ni une nouvelle permission ; inconnu n’est pas zéro.</p></section>
<section><h2>Collecte réellement enregistrée et refus</h2><p>'''+_text(scope)+'''</p><div class="table-scroll" role="region" tabindex="0" aria-label="Décomptes enregistrés — défilement horizontal"><table>'''+count_rows+'''</table></div>
<p>Champs normalisés enregistrés (pas une qualification HUD) : '''+_text(fields)+'''</p>
<h3>Refus du cœur</h3><ul>'''+(refusals or '<li>Aucun refus enregistré dans le périmètre lu ; pas une preuve d’absence ailleurs.</li>')+'''</ul>
<h3>Refus optionnels</h3><ul>'''+(optional or '<li>Aucun refus optionnel enregistré dans le périmètre lu.</li>')+'''</ul></section>
<section><h2>Clôture et limites</h2><p>Motif de clôture enregistré : '''+_text(history['closure']['recorded_reason'])+'''.</p>
<p>Activité actuelle inconnue. Aucune conclusion de disponibilité live, de propriété du lecteur ou d’autorisation de lecture.</p>
<p>La dernière observation n’est pas un état actuel ; un refus ultérieur ne la rafraîchit pas.
Les âges optionnels sont ceux enregistrés à la normalisation ; l’âge du cœur demeure inconnu.
Les horloges UTC, mission et monotone ont des bases distinctes. Aucun rapprochement HUD/replay indépendant n’est établi ici.</p></section>
<footer class="muted">Rapport statique autonome · sans réseau, image, script, audio ou navigateur automatique.</footer>
</main></body></html>
'''


def _rename_new(source, target):
    """Atomic directory publication WITHOUT replacing even an empty target.

    Windows rename already has no-replace semantics. Linux needs renameat2;
    ordinary POSIX rename could silently replace a competing empty directory.
    Refuse unsupported platforms/filesystems instead of weakening the guard.
    """
    if os.name == 'nt':
        os.rename(source, target)
    elif sys.platform.startswith('linux'):
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, 'renameat2', None)
        if rename is None:
            raise OSError('atomic_no_replace_unavailable')
        rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:
            raise OSError(ctypes.get_errno(), 'atomic_publication_refused')
    else:
        raise OSError('atomic_no_replace_unavailable')


def _publish(target, files):
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.cervhots-report-', dir=target.parent))
    try:
        for name, text in files.items():
            with (stage/name).open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
        _rename_new(stage, target)
    finally:
        # Only the private staging names are ours; never touch a competing target.
        for name in files:
            try:
                (stage/name).unlink()
            except FileNotFoundError:
                pass
        try:
            stage.rmdir()
        except FileNotFoundError:
            pass


def run(args):
    try:
        if args.report_dir.resolve().is_relative_to(args.journal.resolve().parent):
            raise ValueError('output_overlaps_input')
        if args.report_dir.exists() or args.report_dir.is_symlink():
            raise ValueError('output_exists')
        result = build(args.journal)
        html = render(result)
        data = json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2)+'\n'
        _publish(args.report_dir, {'report.json': data, 'REPORT.html': html})
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps(dict(event='session_html_error', code='output_or_input_refused',
                              current_permission=False, hud_validated=False)))
        return 1
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return 0 if result['history']['state'] == 'recorded_observation' else 1
