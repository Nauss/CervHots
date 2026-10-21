# Frontière replay → coach joueur (F01 / E1)

## Portée

`snapshot()` conserve le contrat normalisé du coach, mais délègue exclusivement
les entrées replay (source replay OU présence de timeline) à `cerveau/replay.py`.
Il n'existe aucun drapeau omniscient sur cette projection. Le chemin mémoire/live,
ses receipts, sa fraîcheur, ses budgets et ses allowlists ne sont pas modifiés.
`hotstate/extract.py`, son JSON rétrospectif, son résumé diagnostic et les oracles
existants restent inchangés : extraction omnisciente et projection joueur sont
bien deux usages distincts. Ne pas envoyer directement le JSON d'extraction à
`Coach.decide()` : le point d'entrée produit est `snapshot()` / `make_source()`.

Les trois négatifs Astra sont des fixtures synthétiques, pas une fuite native
observée. Ces tests ne sont ni une preuve universelle de non-fuite ni une
qualification de l'utilité du coach.

## Perspective et temps

- Un replay exige `--at SECONDES` et `--team 0|1`, sauf identité locale structurée
  liée sans ambiguïté à un slot du roster (id/équipe/héros). Identité d'observateur
  non liée, équipe absente ou contradictoire : refus explicite. Une sélection
  explicite d'équipe est une perspective hypothétique horsligne, pas une preuve
  de l'identité humaine historique ou de ses permissions de visibilité.
- Le repli historique implicite sur l'équipe 0 n'est plus applicable aux replays,
  même si l'aide CLI partagée le mentionne encore pour les sources sans contexte.
  Aucun changement de cette aide partagée pendant le lot macro parallèle.
- `at` reste en secondes de mission, inclut la préparation ; aucune conversion
  vers le chrono HUD, aucun décalage universel. Valeur finie, non booléenne,
  0..21600 s, sans dépasser une durée valide fournie. Cette borne d'ingénierie
  reprend celle du consommateur natif, pas une durée maximale garantie de HotS.
- Événements triés AVANT application de la vie et des niveaux, jamais après `at`.
  Les 24 derniers faits admissibles sont transmis ; le compteur de morts porte
  sur tout le préfixe admissible, non sur ces seuls 24 faits.
- S01 : une ligne future dont le temps est valide dans 0..21600 est ignorée avant
  validation de son type/identité. Elle ne change pas le préfixe projeté à `at`.
  Une ligne non datée ou au temps invalide ne peut pas être classée future et
  continue d'invalider conservativement sa famille. Le candidat initial avait
  une dépendance conservative au futur, pas une fuite future démontrée.

## Coordonnées

L'extracteur actuel ne produit AUCUNE preuve historique de visibilité joueur.
Donc aucune XY ennemie n'est admissible, même si le tracker la fournit ou si une
clé JSON prétend qu'elle est visible. Pas d'inférence géométrique de visibilité.
Toutes les `event.pos` sont omises (y compris spawns, morts et structures) : elles
n'ont pas cette preuve, ni la sémantique d'une position actuelle.

Seul le dernier `position_snapshots` daté peut produire des positions alliées :

- Nom utilisé seulement comme clé interne de jointure unique, jamais en sortie.
- Héros/équipe du roster connus ; état vivant établi par spawn/respawn antérieur.
- Aucune mort ni nouvelle transition de vie entre le sample et `at`.
- Âge conservé par son vrai `t`, entre 0 et 1 s inclus ; pas d'interpolation ni de
  maintien sur le trou d'environ 15 s du tracker (cadence décrite dans le schéma).
- Coordonnées x/y scalaires finies non booléennes, 0..2048 bruts, divisées par 4
  conformément à `extract.decode_positions()`. L'enveloppe conservatrice 0..512
  rejoint la borne externe existante de `state._native_positions()` ; ce n'est
  PAS une qualification des bornes jouables de toutes les cartes. Hors enveloppe
  signifie inconnu, pas clamp ni zéro. Ce contrôle ne donne aucune permission.
- Sample malformé/non daté, dernier sample ambigu au même instant, champ absent,
  mort ou vie inconnue : pas de fallback vers une ancienne position. Une famille
  de cycle de vie malformée rend la vie actuelle inconnue. Des transitions de vie
  contradictoires au même instant rendent cet état inconnu.
- B01 : toute transition spawn/death/respawn du préfixe sans jointure unique
  par player, ou avec héros contradictoire/composite, invalide la famille de vie
  entière pour ce snapshot : aucun alive, aucune XY, aucun deaths_total. Même
  une transition valide ultérieure ne rétablit pas cette famille dans ce préfixe.
  Les transitions ambiguës ne sont pas émises comme faits de vie. Les autres
  faits publics indépendants restent admissibles. Ce choix sacrifie la
  disponibilité plutôt que de rattacher naïvement par héros (doublons possibles).
  Un nom dupliqué reste ambigu même si une des lignes du roster est invalide.

La famille positions est absente si aucun allié ne satisfait ces conditions.
Cette politique réduit volontairement sa disponibilité dans un replay clairsemé.

## Typage fermé et minimisation récursive

Aucune valeur composite du replay n'est copiée en sortie. Chaque structure est
reconstruite : nombres bornés, booléens calculés, listes/dictionnaires de champs
connus, chaînes issues d'un vocabulaire public versionné dans Git. Une simple
regex alphanumérique n'est PAS une preuve de caractère public.

- Héros : clés/valeurs de `hotstate/hero_ids.json`, reconnaissance insensible à
  la casse et sortie canonique issue du catalogue. Identifiant inconnu omis,
  même s'il ressemble à un nom de héros valide. Certaines dénominations locales
  non inventoriées seront donc inconnues ; pas de catalogue externe ajouté.
- Cartes : noms/slugs/alias français de `kb/data/map_timings.json` ; sortie canonique.
- Les overrides carte/compositions passent par les mêmes vocabulaires ; au plus
  cinq héros par liste d'override. Roster d'entrée limité à dix participants.
- Vie : types spawn/death/respawn connus. Aucun player/killer, compte, chat, nom
  libre, résultat final, unité, pointeur ou donnée privée imbriquée transmis.
- Niveaux : événement `LevelUp`, entier strict 1..30 ; seul `data.Level` ressort.
- Objectifs publics : vocabulaire explicite de noms d'annonces globales présents
  dans `kb/tools/events_par_carte.json` (pas cet inventaire entier). Seule une
  équipe `TeamID` entière 4096/8192 est projetée ; aucune autre donnée libre.
  Ces événements sont des faits historiques, pas une phase d'objectif actuelle
  reconstruite ni une permission de consulter des structures/camps cachés.
- Upgrades : aucun catalogue de tracker qualifié par cette source. Toute la
  famille upgrade est omise, pas de chaîne libre ni de faux talent de remplacement.
- Structures, camps et événements inconnus : omis faute de projection qualifiée.
- Champs absents/invalides restent absents : pas de niveaux/vie/XY par défaut.
  Le compteur zéro est permis uniquement avec une liste hero_events structurée
  et datée valide, éventuellement réellement vide ; famille absente/invalide
  n'est pas un zéro observé.

Les vocabulaires statiques bornent les chaînes ; ils n'attestent pas l'authenticité
d'un JSON hostile qui pourrait fabriquer des faits en utilisant ces mêmes noms.
La frontière minimise les données et les permissions, elle n'est pas un dispositif
d'attestation cryptographique du replay.

## Compatibilité et tests

Les anciennes assertions qui exigeaient `SyntheticTalent` et une XY après mort
ont été remplacées par leurs négatifs. Les contrôles publics utiles restent :
composition, niveaux, vie, objectifs, chronologie/borne 24, échelle /4 positive
après respawn. Les anciennes fixtures replay spécifient maintenant l'équipe.
`test_cli` fournit explicitement une famille de morts observée vide pour conserver
son test de politique d'âge sans assimiler l'absence à zéro ; `test_gameplay_contract`
spécifie l'équipe pour continuer à vérifier l'absence de chrono HUD en replay.
Ces deux ajustements de tests, hors du fichier ciblé principal, sont nécessaires
au changement volontaire du contrat replay, sans modification de CLI/brain/runner.
La révision B01 donne aussi une jointure player cohérente aux fixtures historiques
de coupure temporelle/borne 24 ; leurs assertions de chronologie et de taille
restent inchangées. Les nouvelles régressions vérifient séparément le refus des
transitions sans jointure, au normaliseur et dans le prompt factice.

Commande ciblée : `python -m unittest discover -s tests -p test_replay_coach_boundary.py -v`.
Les fixtures incluent un vrai prompt préparé par `Coach` via un client FAUX,
sans réseau, API réelle, voix ni backend live. Les régressions complètes sont
exécutées séquentiellement sur Python 3.12 et 3.14, avec vérification des chemins
d'import du worktree. Preuves et manifeste exact sous
`out/post-audit/2026-10-21/replay/` du dépôt principal (hors Git).

Cette phase fournit un candidat local gelé pour revue indépendante, ni publication
main/push, ni activation live. Pas besoin d'un nouveau jeu pour cette correction
replay horsligne ; la composition native 980dd24 reste gelée et distincte.
