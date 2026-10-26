"""Débrief replay déterministe et local ; ni Coach, ni API, ni son, ni mémoire."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

from cerveau.replay import MAX_TIME_S, project
from kb.briefing import public_facts


def build(raw, *, at, team, perspective, allow_protocol_shim=False):
    """Ne publie que la projection joueur existante, sans aucune coordonnée."""
    if perspective != 'player-team' or type(team) is not int or team not in (0, 1):
        raise ValueError('perspective_ou_equipe_invalide')
    meta = raw.get('meta', {})
    duration = meta.get('duration_s')
    if (type(duration) not in (int, float) or not math.isfinite(duration)
            or not 0 <= duration <= MAX_TIME_S):
        raise ValueError('duree_replay_inconnue')
    if type(meta.get('protocol_shim')) is not bool:
        raise ValueError('protocole_inconnu')
    if meta['protocol_shim'] and allow_protocol_shim is not True:
        raise ValueError('protocole_exact_indisponible')
    state = project(raw, at=at, team=team)
    state.pop('positions', None)
    for hero in state['heroes']:
        hero.setdefault('alive', None)
        hero.setdefault('level', None)
    knowledge = public_facts(state['meta'].get('map'))
    coverage = {'roster_slots': len(raw.get('players', [])),
                'recognized_heroes': len(state['heroes']), 'objective_state': None}
    protocol = meta.get('protocol')
    provenance = {'extractor': 'hotstate.extract.extract', 'projection': 'cerveau.replay.project',
                  'build': meta.get('build') if type(meta.get('build')) is int
                  and 0 < meta['build'] < 10000000 else None,
                  'protocol': protocol if type(protocol) is str
                  and re.fullmatch(r'protocol[0-9]{1,8}', protocol) else None,
                  'protocol_shim': meta['protocol_shim'],
                  'fidelity': 'unverified_protocol_shim' if meta['protocol_shim']
                  else 'installed_build_protocol', 'native_or_hud_validation': False}
    lines = [f"Débrief historique à {at:g} s de mission — équipe {team}.",
             "Perspective d'équipe hypothétique, pas identité locale vérifiée.",
             'Carte : ' + state['meta'].get('map', 'inconnue') + '.']
    for side, title in (('allies', 'Alliés reconnus'), ('enemies', 'Adversaires reconnus')):
        lines.append(title + ' : ' + (', '.join(state['composition'][side]) or 'inconnus') + '.')
    for hero in state['heroes']:
        life = {True: 'vivant', False: 'mort'}.get(hero.get('alive'), 'inconnu')
        lines.append(f"Équipe {hero['team']} · {hero['hero']} : dernier niveau observé "
                     f"{hero.get('level') or 'inconnu'}, dernier état de vie {life}.")
    if coverage['recognized_heroes'] < coverage['roster_slots']:
        lines.append('Composition incomplète : certains héros ne sont pas reconnus par le catalogue existant.')
    if meta['protocol_shim']:
        lines.append('SHIM de protocole accepté explicitement : décodage non validé pour ce build ; '
                     'toutes les observations ci-dessus sont indicatives, non certifiées.')
    objectives = [event for event in state['events']
                  if event.get('name') not in (None, 'LevelUp')]
    for event in objectives:
        lines.append(f"Annonce publique passée à {event['t']:g} s : {event['name']} "
                     f"(équipe {event.get('team', 'inconnue')}).")
    lines.append("État actuel de l'objectif inconnu ; annonces limitées aux 24 derniers événements projetés.")
    lines.append('Niveau/vie : dernier événement reconnu, pas PV ni mesure continue. '
                 'Aucun résultat final, futur, position ou conseil tactique. Aucune preuve native/HUD/CURRENT.')
    if knowledge['objective'] is not None:
        lines.append('Rappel KB statique (pas état observé) : ' + knowledge['objective'])
    return {'schema': 'replay-debrief-v1', 'state': state, 'knowledge': knowledge,
            'map': state['meta'].get('map'), 'coverage': coverage, 'provenance': provenance,
            'debrief_fr': '\n'.join(lines)}


def mission_seconds(text):
    value = float(text)
    if not math.isfinite(value) or not 0 <= value <= MAX_TIME_S:
        raise argparse.ArgumentTypeError('instant de mission fini entre 0 et 21600 requis')
    return value


MAX_REPLAY_BYTES = 32 * 1024 * 1024


def source_hash(path):
    """Lecture bornée, jamais de recherche automatique ni écriture du replay."""
    if not path.is_file():
        raise ValueError('fichier_replay_invalide')
    with path.open('rb') as stream:
        payload = stream.read(MAX_REPLAY_BYTES + 1)
    if not payload or len(payload) > MAX_REPLAY_BYTES:
        raise ValueError('taille_replay_invalide')
    if not payload.startswith((b'MPQ\x1a', b'MPQ\x1b')):
        raise ValueError('fichier_replay_invalide')
    return hashlib.sha256(payload).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--replay', type=Path, required=True, help='fichier local explicite et stable')
    parser.add_argument('--team', type=int, choices=(0, 1), required=True)
    parser.add_argument('--perspective', choices=('player-team',), required=True,
                        help="côté joueur hypothétique ; jamais observateur omniscient")
    parser.add_argument('--at', type=mission_seconds, required=True,
                        help='secondes de mission, préparation incluse, pas chrono HUD')
    parser.add_argument('--allow-protocol-shim', action='store_true',
                        help='autoriser un décodage indicatif non certifié pour ce build')
    parser.add_argument('--format', choices=('json', 'text'), default='json')
    parser.add_argument('--report-dir', type=Path,
                        help='HTML + JSON locaux : dossier absolu neuf, parent existant (Windows)')
    args = parser.parse_args(argv)
    try:
        before = source_hash(args.replay)
        # Aucun appel à la CLI extract : elle écrirait des données privées.
        from hotstate.extract import extract
        raw = extract(args.replay)
        report = build(raw, at=args.at, team=args.team, perspective=args.perspective,
                       allow_protocol_shim=args.allow_protocol_shim)
        if source_hash(args.replay) != before:
            raise ValueError('replay_modifie_pendant_lecture')
        report['provenance']['replay_sha256'] = before
        if args.report_dir is not None:
            from cerveau.replay_html import publish
            try:
                publish(report, args.report_dir)
            except (OSError, ValueError):
                raise ValueError('sortie_rapport_refusee') from None
    except Exception as exc:
        # Les décodeurs peuvent inclure des données personnelles dans leurs
        # exceptions : ni message brut, traceback, chemin, ni nom de fichier.
        reason = str(exc) if isinstance(exc, ValueError) else ''
        if reason not in {'fichier_replay_invalide', 'taille_replay_invalide',
                          'protocole_exact_indisponible', 'duree_replay_inconnue',
                          'protocole_inconnu', 'replay_modifie_pendant_lecture',
                          'sortie_rapport_refusee'}:
            reason = 'lecture_ou_projection_refusee'
        print(json.dumps({'status': 'refused', 'reason': reason}), file=sys.stderr)
        return 1
    print(report['debrief_fr'] if args.format == 'text' else
          json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
