# Session de test manuelle : natif → Coach → Piper → Mumble

## Correctifs après les parties du 15 novembre 2026

- Mumble est connecté dès le démarrage explicite `--mumble`, avant la partie
  et la première synthèse (`mumble_connected`, `audio_sent=false`). Aucun son de
  bienvenue ni lecture locale. Les annonces du coach **n'attendent plus le
  silence** et peuvent parler par-dessus la conversation, à la demande du
  propriétaire. La fraîcheur et l'anti-répétition restent obligatoires.
- Avant la première liaison de partie, `aucune_simulation_active` est une attente
  de matchmaking, pas une erreur comptée dans `failure_limit`. La durée globale
  `--max-seconds` reste bornée à 1800 secondes, **attente incluse**. Après liaison,
  la disparition de la simulation ferme toujours la session ; pas de relance
  automatique pour une autre partie.
- L'identifiant natif de carte reconnu suffit aux alertes non spatiales :
  l'absence du nom d'affichage ne les désactive plus. Un identifiant inconnu,
  une perspective invalide ou un état de vie incomplet restent bloquants.
- Le mode réactif ajoute `level_disadvantage`, phrase codée sans KB/API lorsque
  les cinq niveaux de chaque équipe sont connus, cohérents entre eux et
  indiquent au moins deux niveaux de retard. Il ne prétend pas connaître les
  talents sélectionnés. L'alerte numérique reste prioritaire.
  Texte : « L'équipe adverse a au moins deux niveaux d'avance. Évitez les combats
  et récupérez de l'expérience. »
- Cette seconde alerte ne dépend pas des positions/PV/ressources. Avant envoi,
  l'identité, la composition, les états de vie et les niveaux restent identiques,
  le temps ne recule pas et le conseil reste frais. Elle a son propre épisode
  anti-répétition, marqué seulement après livraison et réarmé seulement après
  observation complète d'un écart inférieur à deux niveaux. Unknown ne réarme pas.
- Le texte libre du modèle garde sa clé tactique **exacte**. Ces correctifs ne
  rendent pas valides les conseils spatiaux générés sur des positions anciennes,
  ne baissent pas le seuil de confiance et n'autorisent aucune donnée ennemie
  cachée. Les tests hors ligne ne prouvent pas une réception audio humaine.

## Historique et périmètre initial

**Mise à jour du 11 novembre 2026 :** un essai réel de la chaîne en mode `free`
a livré une annonce Mumble, entendue et confirmée par le propriétaire, mais sans
positions disponibles. Voir [le relais positions](RELAIS-POSITIONS.md) pour les
compteurs, refus et priorités. Les mentions de recette auteur ci-dessous décrivent
la preuve SYNTHETIC initiale ; elles ne résument pas cet essai live ultérieur et
ne qualifient toujours pas une nouvelle carte pour les positions.

**Candidat de code, pas une partie live validée.** La recette auteur est
**SYNTHETIC** : mémoire simulée, vrai `NativeSource`/mutex/`read_current`/
normaliseur/Coach/Pipeline, HTTP de boucle locale, Piper et Mumble factices.
Aucun jeu, serveur externe, haut-parleur ou canal vocal n'a été utilisé par
l'auteur. L'intégration dans main et la recette en vraie partie restent à vérifier.
Ce guide ne lève aucun STOP et ne donne aucune permission CURRENT.

## Périmètre utile

- Build natif **98348**, acquisition des positions alliées sur les **19 cartes
  identifiées** de `hotstate/position_maps.py`, avec bornes natives actives.
  `player_recipe` reste Volskaya ; ailleurs `native_bounds_only`, pas de recette
  terrain prétendue. Voir [positions-collection.md](positions-collection.md).
  Aucune extension de visibilité ou de positions ennemies.
- `cerveau.playtest` sélectionne **core + positions** par défaut, **avant**
  acquisition des autres familles. `--collection all` est le vrai chemin composé
  existant : plus d'informations possibles, mais plus coûteux et toujours sujet
  aux refus WHOLE. Il ne qualifie pas les familles non couvertes sur une carte.
- La CLI passive conserve **core** par défaut et reste sans Coach/API/audio.
  Son opt-in `--collection positions` et son `--check-ready` connaissent ce choix.
- Coach **réactif** par défaut (`--coach-mode reactive`) : l'intention contrôlée
  `outnumbered` est produite **sans KB ni appel API** sur les 19 cartes reconnues.
  Le code exige les dix héros et états de vie connus, cinq par équipe, une
  identité/perspective native courante cohérente, et strictement plus d'ennemis
  vivants que d'alliés. Aucune carte inconnue ni vie supposée n'autorise cette voie.
  Hors de cette alerte, le Coach libre configuré reçoit l'état avec positions
  et conserve la clé tactique exacte. Le modèle ne peut pas s'attribuer une
  intention contrôlée pour contourner cette validation.
  Texte codé : « Nous sommes en infériorité numérique. Évitez le combat jusqu'au
  retour des alliés. » Aucun ordre spatial, distance ou regroupement observé.
- Pré-envoi : nouvelle acquisition WHOLE, identité/carte/composition identiques,
  vecteur exact de vie des dix slots inchangé, précondition toujours vraie,
  conseil âgé d'au plus **20 s**. Mouvement seul autorisé **uniquement** pour
  cette intention/phrase codée. Les positions restent collectées et journalisées,
  et sont transmises au modèle lors du repli libre seulement.
  **Exception explicite du contrôleur : les positions facultatives refusées ou
  absentes ne bloquent pas cette seule phrase non spatiale** si tous les faits
  requis du cœur frais restent valides. Couverture/refus restent explicites ;
  aucune position n'est inventée. Refus WHOLE/cœur, vie inconnue ou identité
  invalide annulent toujours. Cette exception n'affaiblit pas le mode libre.
- Anti-répétition **par épisode** : aucune deuxième annonce pendant le même
  désavantage ; réarmement seulement après une observation courante complète
  sans désavantage. Unknown/refus ne réarme jamais.
- `--coach-mode macro` conserve le mode historique, borné à Volskaya : le modèle
  choisit cette même intention ou le silence, le code rend la phrase. Le mode
  réactif n'ajoute aucune qualification native, de positions ou HUD ; il utilise
  les faits de vie déjà contrôlés, indépendants de la géométrie de carte.
- Historique et cooldown de 15 s après livraison inchangés. Le repli libre
  peut toujours choisir le silence. Le score 1 de l'alerte codée représente la
  satisfaction de sa règle, pas une probabilité de victoire.
- `--coach-mode free` garde le Coach historique et `tactical_key` globale exacte.
  **Tout mouvement allié pendant la latence LLM peut annuler le conseil**. Ce
  mode n'est pas une solution au silence spatial ; voir `freshness.changed_fields`.

## Préparation hors ligne, sans secret dans les commandes

Depuis le checkout intégré (les exemples `--live` ci-dessous sont des modèles
**non exécutés** par l'auteur), utiliser le Python produit installé. Sous Bash :

```bash
cd C:/root/dev/AI/CervHots
export CERVHOTS_SCRATCH='C:/CHEMIN/DU/PROFIL/OPERATEUR/cache/scratch'
test -d "$CERVHOTS_SCRATCH" || exit 2
export TMPDIR="$CERVHOTS_SCRATCH"
export TEMP="$TMPDIR" TMP="$TMPDIR"
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.playtest
```

Remplacer le chemin scratch par le répertoire Hermes **existant du profil opérateur**,
pas celui d'un autre agent ; aucun repli vers le temp système. Les variables sont
locales au terminal. Le lanceur valide un chemin absolu existant ; l'opérateur
reste responsable du choix du profil et des droits d'écriture.

Le préflight par défaut ne construit ni source mémoire, ni client API, ni audio ;
il ne lit aucune configuration secrète. `ready` est **technique natif seulement**,
`kb_present` est un contrôle d'existence, pas de validité ni de configuration du
Coach. `coach_configuration=unchecked`, `current_permission=false` restent explicites.
La KB installée `kb/data/kb.db` est nécessaire au mode réel ; ne pas copier de
`.env` ou de secret dans un worktree/rapport. Au besoin fournir le **chemin** d'une
configuration centrale privée existante avec `--coach-env-file`.

Préparer un petit fichier UTF-8 privé contenant uniquement l'identité du joueur
(contrat existant `player_identity`), puis un parent de session **neuf**, une
sortie neuve et un STOP neuf. Ne jamais mettre le pseudo dans argv.
Contrôle de ces chemins sans mémoire/réseau/audio ni écriture :

```bash
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --check-ready --collection positions --player-file C:/PRIVATE/player.txt --output-dir C:/PRIVATE/playtest-new/session --stop-file C:/PRIVATE/playtest-new/STOP
```

Remplacer `C:/PRIVATE` localement ; ces chemins sont des exemples, pas des fichiers
livrés. Contrôle technique ≠ autorisation de lire le jeu.

## Démarrer et arrêter — action manuelle

Après autorisation distincte et préparation du match/perspective supportés :

```bash
# Silencieux : API autorisée explicitement, aucun import TTS/Mumble ni lecture sonore.
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.playtest --live --player-file C:/PRIVATE/player.txt --output-dir C:/PRIVATE/playtest-new/session --stop-file C:/PRIVATE/playtest-new/STOP --max-seconds 300
```

- Ajouter **manuellement** `--mumble` pour autoriser Piper puis diffusion Mumble.
  Connexion Mumble paresseuse, après une proposition fraîche ; un essai de handshake
  borné à 3 s, puis contrôle frais avant mise en file. Pas de phrase d'accueil.
- Ou ajouter `--wav` : fichiers `advice-0001.wav` dans la sortie neuve, **sans lecture**.
  `--wav` et `--mumble` sont exclusifs. Ni l'un ni l'autre n'est activé par défaut.
- Ajouter `--collection all` pour tenter toutes les familles existantes, pas pour
  contourner un refus ; si WHOLE refuse, le cycle n'alimente pas le Coach.
- API via le `configured_coach`/client Groco et la configuration centrale existants
  (`GROCO_*`), Mumble via la même configuration (`MUMBLE_*`). Aucune clé à imprimer.
- Durée 1–1800 s, intervalle 15–300 s, défaut 300/30. Un appel synchrone à la fois,
  jamais de rattrapage en rafale. L'intervalle est désormais **début-à-début** :
  un traitement de 8 s avec `--interval 15` laisse 7 s d'attente, pas 15 s.
  Un dépassement ne programme pas plusieurs cycles de rattrapage.
  Le mode réel réutilise la KB et Piper existants.

Arrêt depuis un autre terminal, **sur les chemins exacts enregistrés** :

```bash
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --request-stop --output-dir C:/PRIVATE/playtest-new/session --stop-file C:/PRIVATE/playtest-new/STOP
```

Ou Ctrl+C dans le terminal propriétaire. Le STOP est coopératif : pendant HTTP,
attendre le retour de l'appel borné (timeout = minimum du délai configuré, du
budget de fraîcheur **restant après préparation/journal** et du temps de session
restant), puis fermeture ; un son déjà mis en file ne peut être rétracté par ce
contrôle. STOP revérifié après lectures/persistances et avant LLM/envoi. Attendre
le **retour du terminal propriétaire**, pas seulement le succès du signal STOP.
`reader_active=null` signifie fermeture incertaine, pas un lecteur arrêté.

Une source native unique, mutex existant, enfin fermeture sur toutes les sorties.
Changement/perte d'identité de match/perspective/carte/composition ou recul du temps
arrête la session : **aucun rebind automatique**. Après fermeture confirmée :
nouvelle invocation, parent/sortie/STOP neufs ; conserver anciens claims et STOP.

### Petit lanceur Windows, pas de serveur ni GUI obligatoire

**Parcours à boutons recommandé après intégration : double-clic
`tools/playtest-panel.cmd`.** Tk stdlib seulement, aucun lancement mémoire/API/son
au chargement. Choisir le fichier identité privé existant (pas de saisie de pseudo),
puis **Vérifier**, **Démarrer silencieux** ou **Démarrer voix Mumble**.
Le dernier demande une confirmation Oui/Non. **Arrêter** utilise le contrôle STOP
existant, y compris si son enregistrement est encore en cours ; aucune terminaison
forcée. La fenêtre attend le retour du sous-processus avant fermeture ou redémarrage.
Les sessions/STOP neufs sont générés sous `out/playtest-ui/run-<aléatoire>/`, avec
`console.jsonl`, `session/events.jsonl` et `session/summary.json` pour les motifs.
Le panneau lance explicitement **30 minutes maximum** (`--max-seconds 1800`),
affichées avant démarrage ; STOP peut arrêter plus tôt. La CLI conserve 5 min par défaut.
Le panneau ne lit ni ne saisit de secret, et garde la configuration centrale existante.

Aucune variable à régler pour le panneau dans main : Python produit sous `tts/.venv`,
scratch dédié utilisateur `%LOCALAPPDATA%\hermes\operator-playtest\cache\scratch`
(créé au premier clic, pas le temp système ni le profil d'un autre agent).
Les overrides explicites `CERVHOTS_PYTHON`/`CERVHOTS_SCRATCH` restent disponibles
pour un opérateur sur worktree isolé. Le lecteur tourne dans le sous-processus,
jamais dans un thread Tk. Le panneau ne lance aucun serveur/bot à l'ouverture.

**Prérequis voix manuel :** serveur Mumble disponible/démarré par l'opérateur,
et configuration centrale correspondante. Au contrôle parent, `cervhots-murmur`
était arrêté (TCP refusé) ; aucune autorisation de le redémarrer n'a été reçue.
Client installé : `C:/Program Files/Mumble/client/mumble.exe` (information parent,
pas lancement auteur). Ne pas cliquer voix en prétendant que ce prérequis est validé.
Ni le panneau ni ses tests ne constituent une validation vocale réelle.

Depuis CMD, après intégration dans main :

```bat
set "CERVHOTS_SCRATCH=C:\CHEMIN\DU\PROFIL\OPERATEUR\cache\scratch"
tools\playtest.cmd preflight
tools\playtest.cmd silent C:\PRIVATE\player.txt C:\PRIVATE\playtest-new\session C:\PRIVATE\playtest-new\STOP
tools\playtest.cmd voice C:\PRIVATE\player.txt C:\PRIVATE\playtest-new\session C:\PRIVATE\playtest-new\STOP
tools\playtest.cmd stop C:\PRIVATE\playtest-new\session C:\PRIVATE\playtest-new\STOP
```

**Choisir une seule commande de démarrage**, avec chemins neufs. `voice` demande
une confirmation O/N avant `--mumble`. Un cinquième argument peut désigner le
fichier de configuration privé. Sans action : usage seulement, aucun démarrage.
`CERVHOTS_SCRATCH` est obligatoire et doit être absolu/existant, sinon code 2
avant démarrage. `CERVHOTS_PYTHON` peut désigner explicitement le Python produit
installé si ce checkout n'a pas `tts\.venv\Scripts\python.exe` (par exemple un
worktree isolé) ; aucun interpréteur global n'est choisi implicitement.
Ce lanceur CLI reste disponible ; le panneau Tk est seulement son alternative manuelle.

## Lire la recette et comprendre le silence

Console JSONL + `events.jsonl` + `summary.json`. Les journaux sont minimisés,
historiques et privés : aucun pseudo/compte, seed, pointeur, lecture brute, reçu
ou clé exportés. Les fichiers de contrôle restent locaux et ne sont pas des
permissions réutilisables. Les positions normalisées consignées sont des valeurs
historiques ; elles ne peuvent servir d'entrée CURRENT au lecteur.

- `acquisition` : sélection, refus fermés, lectures/octets/coût réellement tentés.
- `observation.positions` : coordonnées alliées conservées dès l'observation,
  même sans appel du Coach, avec temps mission/âge/couverture/refus. Schéma :
  [positions-collection.md](positions-collection.md). `bounds` conserve le rectangle
  actif ; `map_validation` distingue recette joueur et contrôles natifs seuls.
- `coach_input.coverage` : **entrée normalisée effectivement proposée au Coach**,
  alliés attendus/vivants/positions acquises (null si inconnues, pas zéro fictif),
  carte supportée, familles non sélectionnées/inconnues et refus positions.
  `positions` contient carte/temps mission/équipe et slots + x/y/u/v anonymisés.
  L'E2E compare ces valeurs au corps réellement reçu par HTTP local.
- `source_age_s`/`read_window_s` : âge **original à la normalisation** et fenêtre
  source des positions, pas latence LLM et pas âge renouvelé au flush.
  `coach_input.cycle_age_s` : temps depuis début du cycle au bord Coach.
  `coach_response.latency_s` : latence de `decide` (peut être locale, sans HTTP,
  en cas de répétition macro). `freshness.age_s` : âge total au recheck.
- Macro : `facts` au bord Coach, `macro_proposal.intent`, `macro_revalidation`
  et `macro_episode_rearmed`. `freshness` continue d'exposer la dérive globale,
  même quand la phrase macro non spatiale reste admissible.
- Réactif : `fact_decision` distingue une décision codée, sans appel API ;
  `intent_revalidation.accepted` est le verdict de son contrat. Une dérive
  globale dans `freshness` n'est pas à elle seule un rejet de cette phrase.
  Le repli libre reste strict, même s'il renvoie un champ JSON `intent`.
- `stage_timing` sépare `knowledge`, `synthesis`, `delivery_complete` ; ce dernier
  inclut la durée de lecture audio et n'est pas le début du son. Les temps API
  restent dans `coach_response`. `erreur_api_0` préserve le refus réseau/délai,
  sans conserver le message distant ni ses données privées.
- Silence volontaire, confiance insuffisante, réponse invalide, intention
  non autorisée, répétition, cooldown, `périmé`, `non_diffusé` restent distincts.
  `input_expired` évite un LLM après préparation trop lente.
- Compteurs : lectures acceptées/refusées, lectures avec positions, tentatives
  **Coach** (pas nécessairement HTTP dans le mode macro historique),
  `fact_decisions` séparées, propositions acceptées/refusées,
  périmés/non-envois, synthèses, WAV sauvegardés et envois Mumble terminés.
  `mumble_sent` vient du retour du transport après vidage de sa file, **pas**
  d'une preuve qu'un humain a entendu. Un opt-in ne vaut jamais un envoi.
  Le silence ne mémorise rien ; `remember` seulement après livraison réussie.

## Recette automatique sans jeu, API externe ni son

Depuis le checkout candidat, avec `TMPDIR/TEMP/TMP` Hermes ci-dessus :

```bash
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m unittest discover -s tests -p 'test_playtest*.py' -v
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_positions_collection.py -v
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_reactive_coach.py -v
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_coach_timing.py -v
```

Option de preuve test-only : `CERVHOTS_SYNTHETIC_LOG_DIR` vers un répertoire neuf
pour conserver les événements SYNTHETIC, jamais un mode de source produit.
Les mocks portent sur le transport mémoire, les profils/horloges de fixture,
la KB de test et les sorties audio ; pas sur le normaliseur, Coach, Pipeline
ou la réception HTTP. Les fixtures ne qualifient ni débit live, ni HUD, ni voix
réelle. Manquent encore : intégration/revue indépendantes, recette native
Volskaya autorisée et retour utilisateur sur la pertinence/voix manuelle.
