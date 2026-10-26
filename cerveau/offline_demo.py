"""Démonstration SYNTHETIC hors ligne et silencieuse ; jamais une partie réelle."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # Ne pas réémettre d'argv arbitraire (identité ou chemin privé).
        raise ValueError('invalid_arguments')


def main(argv=None):
    parser = _Parser(description=__doc__, allow_abbrev=False)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--destination', type=Path,
        help='répertoire local absolu NEUF, parent existant (Windows)')
    mode.add_argument('--verify', type=Path,
        help='vérifier en lecture seule une démonstration complète (Windows)')
    try:
        args = parser.parse_args(argv)
    except ValueError:
        print('Arguments invalides ; utiliser --help.', file=sys.stderr)
        return 2
    if args.verify is not None:
        from .demo_integrity import run
        return run(args.verify)
    try:
        result = demonstrate(args.destination)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print('Démonstration refusée ou interrompue ; conserver toute sortie partielle et choisir une destination neuve.', file=sys.stderr)
        return 1
    print(_dump(result), end='')
    return 0


def _dump(value):
    import json
    return json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2)+'\n'


def _records(case):
    # Petit journal documentaire inventé, sans acquisition ni émission de reçu.
    # Les formes/valeurs sont ensuite vérifiées par les composants produit.
    players = [dict(slot=i, hero=hero, level=1, status='unknown', tiers=None)
        for i, hero in enumerate(('sonya', 'ltmorales', 'mei', 'kaelthas', 'murky'))]
    players[0].update(status='observed', tiers=[])
    acquisition = dict(schema_version=1, sequence=1, cycle=1, event='acquisition',
        outcome='accepted', collection='all', data_kind='SYNTHETIC')
    observation = dict(schema_version=1, sequence=2, cycle=1, event='observation',
        data_kind='SYNTHETIC', session='session_'+'a'*12, map='map_'+'b'*12,
        mission_t_s=41., elapsed_s=1., timestamp_utc='2026-01-01T00:00:01+00:00',
        available_fields=['heroes', 'talents', 'local_cooldowns'],
        comparison=dict(session_token='a'*32, map_id='DragonShire', perspective='native_player',
            clock_basis='host_monotonic', read_started_s=101., read_finished_s=101.02),
        heroes=[dict(slot=i, team=int(i>=5), level=1, alive=True,
            hero='hero_'+'c'*12) for i in range(10)],
        talents=dict(status='normalized', source='native_player', source_mission_t_s=41.,
            age_s=.01, read_window_s=.005,
            value=dict(build=98348, map_id='DragonShire', team=0, local_slot=0, players=players)),
        local_cooldowns=dict(status='normalized', source='native_player', reason=None,
            source_mission_t_s=41., age_s=.025, read_window_s=.01,
            value=dict(build=98348, map_id='DragonShire', hero='sonya', local_slot=0, team=0,
                actor_scope='current_native_main_hero', ui_control_body='unknown', alive=True,
                abilities=[dict(ability='BarbarianAncientSpear', instance_slot=22,
                    slot_kind='native_instance_NOT_HUD_button', cast_legality='unknown',
                    cooldown_status='observed', remaining_s=0., cooldown_ready=True,
                    charges_status='unknown')])))
    if case == 'unknown':
        acquisition.pop('collection')  # Sélection absente != sélection de toutes les familles.
    if case == 'refused':
        observation.pop('comparison')  # Aucun sauvetage d'une identité historique incomplète.
    return [acquisition, observation, dict(schema_version=1, sequence=3, cycle=1,
        event='boundary', reason='session_limit', data_kind='SYNTHETIC')]


def demonstrate(destination):
    """Composer exclusivement les API historiques ; conserver un échec partiel."""
    from contextlib import ExitStack, redirect_stdout, redirect_stderr
    import io
    import json
    import os
    from types import SimpleNamespace
    from . import session_catalog as catalog
    from . import catalog_integrity, session_diagnosis, native_history, session_html

    target = catalog._absolute(destination)
    commands = []
    with ExitStack() as guards:
        catalog._ancestors(guards, target.parent)
        if os.path.lexists(target):
            raise ValueError('output_exists')
        # mkdir exclusif, aucune suppression, réutilisation ou rollback trompeur.
        catalog._reserve(target)
        guards.enter_context(catalog._pin(target, directory=True))
        catalog._write(target/'SYNTHETIC.txt', NOTICE)
        sources, reports = target/'synthetic-sessions', target/'reports'
        for folder in (sources, reports):
            folder.mkdir()
            guards.enter_context(catalog._pin(folder, directory=True))

        def exercise(mode, function, args, expected, case=None):
            # Les données imprimées par les CLI sont déjà écrites dans leurs
            # rapports ; ne pas les réexporter en double sur le terminal.
            with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
                code = function(args)
            if len(out.getvalue()) + len(err.getvalue()) > 256*1024:
                raise ValueError('unexpected_output_limit')
            commands.append(dict(mode=mode, case=case, exit_code=code, expected_code=expected))
            if code != expected:
                raise ValueError('unexpected_component_code')
            return json.loads(out.getvalue())

        for case in ('absent', 'refused', 'unknown', 'zero'):
            source, report = sources/case, reports/case
            for folder in (source, report):
                folder.mkdir()
                guards.enter_context(catalog._pin(folder, directory=True))
            catalog._write(source/'SYNTHETIC.txt', NOTICE)
            if case == 'absent':
                catalog._write(source/'status.json', _dump(dict(data_kind='SYNTHETIC',
                    event='initializing', current_permission=False)))
            else:
                catalog._write(source/'events.jsonl', ''.join(_dump(r).replace('\n', '')+'\n'
                    for r in _records(case)))
            args = SimpleNamespace(journal=source/'events.jsonl', visual_reference=[])
            args.report_dir = report/'diagnosis'
            exercise('--diagnose', session_diagnosis.run, args, 1 if case == 'absent' else 0, case)
            expected = 1 if case in ('absent', 'refused') else 0
            args.report_dir = report/'summary'
            exercise('--summarize', native_history.run, args, expected, case)
            args.report_dir = report/'html'
            # Le publieur atomique HTML renomme un dossier : incompatible avec
            # les parents Windows ici épinglés sans partage d'écriture/suppression.
            # Composer les mêmes build/render, publier exclusivement sous garde.
            html_result = session_html.build(args.journal)
            args.report_dir.mkdir()
            guards.enter_context(catalog._pin(args.report_dir, directory=True))
            catalog._write(args.report_dir/'report.json', _dump(html_result))
            catalog._write(args.report_dir/'REPORT.html', session_html.render(html_result, synthetic=True))
            code = 0 if html_result['history']['state'] == 'recorded_observation' else 1
            commands.append(dict(mode='--report-html', case=case, exit_code=code,
                expected_code=expected, api='session_html.build/render'))
            if code != expected:
                raise ValueError('unexpected_html_state')
        args = SimpleNamespace(sessions_root=sources, report_dir=target/'catalog')
        exercise('--catalog', lambda a: catalog.run(a, synthetic=True), args, 1)
        # Absence et refus sont voulus. Presentation context is explicit, not
        # inferred from directory names, journal data_kind or generic schemas.
        verification = exercise('--verify-catalog', catalog_integrity.run, args, 0)
        result = dict(event='offline_demo', schema_version=1, data_kind='SYNTHETIC',
            basis='synthetic_historical_not_current', current_permission=False,
            authenticated=False, hud_validated=False, commands=commands, verification=verification)
        catalog._write(target/'demo.json', _dump(result))
        from .demo_integrity import publish
        publish(target)
    # Toutes les références/handles sont libérés ici. Aucun backend n'a été ouvert.
    return result


NOTICE = '''SYNTHETIC — données entièrement inventées, aucun match ni source privée.
Les états et horloges documentaires ne sont ni authentifiés ni actuels.
Zéro de recharge synthétique != sort lançable ; charges inconnues.
Braxis non qualifié ; contexte hérité inconnu. Aucune permission CURRENT.
Ne démontre ni lecture native réelle, STOP réel, HUD, carte/build réels ou coût réel.
Aucun navigateur, Coach, API, réseau ou audio ; aucun conseil de jeu.
La fermeture session_limit du journal est fictive, pas un arrêt de processus réel.
Un HTML ou catalog/COMPLETE.json seul ne prouve PAS la complétude de cette démo.
Exiger DEMO_COMPLETE.json et python -B -m cerveau.offline_demo --verify DESTINATION.
Sans vérification code 0 : sortie ancienne, partielle, altérée ou refusée ; ne pas reprendre ici.
'''


if __name__ == '__main__':
    raise SystemExit(main())
