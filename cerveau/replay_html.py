"""HTML local de replay_debrief.build, sans parseur ni observation supplémentaires."""
from contextlib import ExitStack
from html import escape
import json


def render(report):
    """Consomme uniquement le rapport minimisé déjà construit, jamais le replay brut."""
    def text(value):
        return escape('inconnu' if value is None else str(value), quote=True)

    state = report['state']
    provenance = report['provenance']
    coverage = report['coverage']
    rows = []
    for hero in state['heroes']:
        life = {True: 'vivant', False: 'mort', None: 'inconnu'}[hero['alive']]
        rows.append('<tr>' + ''.join('<td>' + text(value) + '</td>' for value in
                    (hero['team'], hero['hero'], hero['level'], life)) + '</tr>')
    announcements = []
    for event in state['events']:
        if event.get('name') not in (None, 'LevelUp'):
            announcements.append('<li>' + text(event['t']) + ' s · ' + text(event['name'])
                                 + ' · équipe ' + text(event.get('team')) + '</li>')
    shim = ('SHIM accepté explicitement : observations indicatives, décodage NON certifié.'
            if provenance['protocol_shim'] else
            'Protocole installé pour le build ; aucune validation indépendante native/HUD.')
    summary = '<br>'.join(text(line) for line in report['debrief_fr'].splitlines()[:3])
    return '''<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Débrief replay historique</title>
<style>
:root{color-scheme:dark}body{background:#11151d;color:#e6ebf4;font:17px/1.65 system-ui,sans-serif;max-width:960px;margin:2em auto;padding:0 1em}
h1,h2{line-height:1.3}section{margin:2em 0}p,td,li{overflow-wrap:anywhere}
.notice{border-left:4px solid #f4c673;background:#202733;padding:1em}table{border-collapse:collapse;width:100%}
th,td{padding:.6em;text-align:left;border-bottom:1px solid #465268}small{color:#bdc9db}
</style></head><body>
<h1>Débrief replay historique</h1>
<p class="notice">Lecture hors ligne uniquement. Ni état live, ni preuve native/HUD/CURRENT,
ni conseil tactique. La perspective d’équipe est hypothétique, pas une identité locale vérifiée.</p>
<section><h2>Résumé</h2><p>''' + summary + '''</p>
<p>Instant demandé : ''' + text(state['meta']['t_s']) + ''' s de mission (préparation incluse, pas chrono HUD).
Équipe replay : ''' + text(state['ally_team']) + ''' · perspective : player-team.</p></section>
<section><h2>Faits autorisés à cet instant</h2><p>Alliés reconnus : ''' + text(', '.join(state['composition']['allies']) or None) + '''.<br>
Adversaires reconnus : ''' + text(', '.join(state['composition']['enemies']) or None) + '''.</p>
<table><caption>Derniers événements reconnus, pas mesures continues</caption>
<thead><tr><th>Équipe</th><th>Héros</th><th>Niveau observé</th><th>Vie observée</th></tr></thead>
<tbody>''' + ''.join(rows) + '''</tbody></table>
<h3>Annonces publiques passées</h3><ul>''' + (''.join(announcements) or '<li>Aucune annonce autorisée dans la fenêtre projetée.</li>') + '''</ul></section>
<section><h2>Inconnues et refus</h2><p>Composition : ''' + text(coverage['recognized_heroes']) + ' héros reconnus sur ' + text(coverage['roster_slots']) + ''' emplacements.
Une composition partielle n’est pas complétée. Niveau/vie inconnus ne signifient pas zéro/vivant.</p>
<p>État de l’objectif inconnu, même après une annonce. PV, ressources, talents, cooldowns et charges
ne sont pas restitués par ce débrief. Une entrée refusée par le CLI ne produit aucun rapport.</p></section>
<section><h2>Rappel documentaire statique</h2><p>''' + text(report['knowledge']['objective']) + '''</p>
<p>Ce rappel KB n’est ni une observation ni un prochain objectif prédit.</p></section>
<section><h2>Protocole et limites</h2><p class="notice">''' + text(shim) + '''</p>
<p>Build : ''' + text(provenance['build']) + ' · protocole : ' + text(provenance['protocol']) + '''.</p>
<p>Au plus 24 derniers événements projetés, tous antérieurs ou égaux à l’instant demandé.
Pas d’historique exhaustif, d’interpolation, de score final, de futur, de coordonnées ou d’identité personnelle.
Héros/cartes inconnus restent omis/inconnus selon les catalogues existants.</p>
<p>Un code 0 signifie seulement que ce débrief historique a été produit, éventuellement partiel ou indicatif.
Il ne qualifie aucune lecture native, aucun HUD, aucune fraîcheur CURRENT ni permission live.</p>
<small>Projection existante cerveau.replay.project · débrief cerveau.replay_debrief ·
Sans script, réseau, ressource externe, API, audio ni ouverture automatique de navigateur.</small></section>
</body></html>
'''


def publish(report, destination):
    """Réserve une sortie neuve sous ancêtres Windows locaux protégés sans liens.

    Pas de remplacement/nettoyage : un échec peut laisser une sortie partielle,
    qui reste refusée à la prochaine invocation. Pas de publication atomique globale.
    """
    from .session_catalog import _absolute, _ancestors, _pin, _write
    html = render(report)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    destination = _absolute(destination)
    with ExitStack() as guards:
        _ancestors(guards, destination.parent)
        destination.mkdir()  # exclusif, y compris liens/junctions pendants
        guards.enter_context(_pin(destination, directory=True))
        _write(destination / 'report.json', payload)
        _write(destination / 'REPORT.html', html)
