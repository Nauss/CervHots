# Disponibilité core hors ligne — sans permission implicite

Avant de collecter, depuis **le checkout exact à contrôler** et avec le runtime
qui servira réellement à la collecte :

```bash
cd C:/root/dev/AI/CervHots
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --check-ready --collection core --player-file C:/CervHots-private/player.txt --output-dir C:/root/dev/AI/CervHots/out/core-run-001/session --stop-file C:/root/dev/AI/CervHots/out/core-run-001.STOP
```

Les chemins sont des **exemples à préparer**, pas un ordre d'exécution live.
L'identité n'est jamais passée en argv : seul son fichier privé absolu est lu
avec le lecteur borné existant (261 octets maximum). Aucun contenu, chemin,
pseudo, environnement ou détail d'exception n'est publié par ce contrôle.

## Contrat et codes

Une ligne JSON stable sur **stdout**, un résumé français bref sur **stderr**.
Le schéma `schema_version=1`, l'ordre des clés et les codes sont déterministes
pour les mêmes entrées inspectées :

- **0** : `technical_ready=true`, contrôles techniques passés ;
- **1** : indisponibilité technique/IO : STOP déjà présent, sortie existante,
  parent déjà revendiqué, identité absente/invalide/vide, runtime/dépendance
  requise ou données produit indisponibles ;
- **2** : arguments/chemins invalides ou absents, sélection autre que `core`,
  mélange avec un mode live/historique. Les erreurs d'arguments sont anonymisées.

`current_permission=false`, `current_context="unattested"` et
`reader_active=null` restent **inconditionnels**, même avec code 0. Aucun fichier
historique, ancien PID ou préflight vert ne prouve le contexte privé ACTUEL,
l'absence d'un lecteur, la santé du jeu ou la permission de lancer.

[Exemple JSON effectivement généré](examples/core-readiness.json) : CLI réelle,
fixtures disque **SYNTHETIC**, mêmes octets sous Python 3.12 et 3.14. Ce n'est
pas une preuve live, une référence HUD ou une identité réelle.

## Ce qui est vérifié — et ce qui ne l'est pas

Le mode réutilise `passive_session.preflight(core=True)` ; il n'y a pas de second
préflight. Le préflight core est également sélectionné par
`--preflight --collection core` et avant une collecte explicitement core :

- Windows, Python >= 3.12, pointeurs 64 bits ; découverte des modules requis
  (`ctypes`, modules produit, `grocoapi` déjà importé par le paquet historique) ;
- parsing JSON des profils existants, présence des trois profils natifs requis
  et dictionnaire d'identifiants de héros non vide ;
- découverte séparée de `mpyq`/`heroprotocol`, **optionnels pour core** : leur
  absence/indisponibilité de découverte ne bloque pas ce mode. Le préflight par
  défaut `all` conserve ses vérifications replay historiques.

La découverte de module n'exécute **pas** le backend ni toutes ses branches et
ne garantit pas qu'une installation corrompue fonctionnera. Le parsing des
profils n'atteste ni build actif ni validité sémantique native. Aucun import des
modules backend live/reader/native_context/garde, aucun handle mémoire, recherche
processus, mutex, réseau/API, GUI, audio ou Coach construit par le contrôle.
Le chargement historique du paquet `cerveau` importe ses classes Coach/Decision,
sans les construire ni appeler un service.

Les chemins locaux absolus sont inspectés sans création, suppression, renommage
ni **write probe**. UNC/réseau, périphériques réservés, ADS, caractères invalides,
traversées et liens/jonctions existants sont refusés. Les futurs parents peuvent
être absents : le contrôle remonte leurs ancêtres existants sans les créer.
Un ancien `passive-session.lock` est conservé et refuse la réutilisation du parent.
STOP présent, même répertoire, refuse. Les collisions entre chemins sont refusées.

**Limites honnêtes :** pas de test d'écriture, donc aucune promesse d'ACL, espace
libre, disque futur ou exclusivité. L'inspection n'est ni atomique ni une
réservation ; les chemins et droits peuvent changer immédiatement. Les gardes
live, STOP et mutex doivent encore être appliquées lors d'une collecte autorisée.
Aucun STOP global n'est découvert implicitement : fournir le STOP de la session
préparée et respecter séparément tout arrêt de campagne applicable.

## Étape indépendante avant lancement

Après contrôle technique seulement : confirmer indépendamment la fin des anciens
collecteurs et le contexte/permission joueur privé **ACTUELS**. Si inconnus, ne
pas lancer. Après intégration locale revue et ces confirmations explicites,
utiliser [la commande core, l'arrêt ciblé et la reprise neuve](core-collection.md#exemple-de-lancement-stop-et-reprise).
Ne jamais enlever un STOP ou claim pour obtenir un vert ; choisir un parent,
une sortie et un STOP neufs après les confirmations indépendantes.

## Vérification réexécutable sans jeu

```bash
# Depuis le checkout examiné, dépendances locales déjà disponibles :
uv run --offline --no-project --python 3.12 --with mpyq --with heroprotocol python -B -m unittest discover -s tests -p test_session_readiness.py -v
uv run --offline --no-project --python 3.14 --with mpyq --with heroprotocol python -B -m unittest discover -s tests -p test_session_readiness.py -v
```

Les enfants `tests/helpers/readiness_guard.py` exercent la vraie CLI, interdisent
les imports effectifs des backends, les constructeurs OS/Coach/API et les IO
réseau/écritures. Ils injectent séparément l'absence d'une dépendance, sans mode
simulé dans le produit. Ces tests ne lancent ni ne ferment le jeu.
