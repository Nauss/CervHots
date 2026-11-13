# hotstate — la couche stats de CervHots

**Mission :** normaliser les seuls champs établis, avec leurs inconnus, refus et
provenance. Le [schéma historique](schema/game_state.schema.json) ne rend pas les
sources interchangeables : replay historique, référence visuelle et acquisition
native actuelle n'ont ni la même perspective ni les mêmes permissions.

## État courant vérifié — 26/10/2026

Base MAIN locale vérifiée : `09bf4cdc03272001e605fb70d94ec402d2664472`, lot38
intégré ; preuve durable locale :
`C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot38/integration/verification.json`
(PASS, revue indépendante ROGER SAME-CARD run745, recettes depuis MAIN).
Ce hash désigne la base vérifiée, pas le futur commit documentaire. Le dossier
lot39 est une préparation mutable hors ligne, pas une livraison produit ni un gel.
Les preuves `out/` sont ignorées par Git et ne sont pas distribuées avec ce guide.

Parcours livré sans Coach/API/audio : [guide de démarrage](../docs/start-here.md),
démo SYNTHETIC, débrief replay JSON/texte/HTML, inspection historique des journaux
et préflight core sans backend. Collecte passive durable intégrée, **core par
défaut CLI**, optionnels sur opt-in : [contrat core](../docs/core-collection.md).
La [matrice actuelle et ses limites](../docs/start-here.md#familles--ce-que-les-preuves-permettent-réellement-de-dire)
fait la distinction avec les résultats anciens ci-dessous : objectif Dragon
exporté/rejoué avec limites, Volskaya objectif qualification seulement, Braxis
non débloqué. Aucun nouveau gain live/native/HUD déduit du lot38 ou de ce guide.

## Priorité actuelle et limites du direct

1. **Voies natives ciblées prioritaires**, sans élargir les allowlists ni affaiblir
   build, contexte, perspective, fraîcheur, WHOLE ou contrôles de cohérence.
2. **Vision seulement en recours explicitement autorisé.** Les captures sont
   des références indépendantes à qualifier (identité, temps, qualité, perspective),
   pas un nouveau producteur de statistiques. Aucun OCR/modèle vision implicite.
3. **Replay historique distinct.** Un fichier peut être un **préfixe partiel**,
   sans score final : ne pas déclarer qu'un replay est forcément final. Cela ne
   qualifie ni un fichier temporaire ni le replay comme source live. Les événements
   absents restent inconnus ; données omniscientes et données joueur ne se confondent pas.

Le débrief livré refuse par défaut un protocole exact indisponible. Sur les corpus
98348 exercés avec protocole91756, `--allow-protocol-shim` est un opt-in **SHIM non
certifié** ; reconnaissance historique de 10/10 héros ≠ fidélité du protocole.
La perspective `player-team` est **hypothétique**, pas une identité locale prouvée.
Voir le [contrat replay](../docs/replay-debrief.md) et les argv réellement exercés
dans le guide, sans réutiliser leurs sorties existantes.

**Ce guide ne confère jamais CURRENT et n'annule aucun STOP.** La mention STOP
dans le texte ne prouve pas l'existence d'un STOP week-end ; l'absence d'un marqueur
ne donne aucune permission. Préflight technique, statut disque historique et
code0 ne prouvent ni contexte privé actuel ni fin d'un ancien lecteur. Démarrage,
arrêt et reprise restent une [procédure soumise à autorisation distincte](../docs/passive-quickstart.md),
avec parent/sortie/STOP neufs et anciens claims/STOP conservés.

**Aucune garantie juridique, EULA/ToS, anti-cheat ou de sécurité du compte**, même
en privé/IA. Lecture seule et absence d'injection ne suppriment pas ces risques.

## Historique conservé — 17 au 19/10/2026, pas l'état courant de MAIN

Les validations ci-dessous sont bornées à leurs captures/build/cartes. Le mot
CURRENT y décrit un contrôle de l'époque, pas une permission actuelle. Les
commandes anciennes sont des modèles non exécutés lot40, pas le quickstart livré.

**Positions multi-cartes actuelles :** `--collection positions` lit les bornes
de la simulation active sur les 19 identifiants de `position_maps.py` et conserve
la qualification : `player_recipe` pour Volskaya, `native_bounds_only` ailleurs.
Générations, identité, fraîcheur et budget inchangés ; aucune coordonnée ennemie.
Voir `docs/positions-collection.md` et `etudes/rea/POSITIONS-MULTICARTES.md` depuis
la racine. Les limites par carte des autres familles restent indépendantes.

**État historique (17/10/2026) :** lecture mémoire des trois compteurs validée en partie
IA jusqu'à Groco et Mumble. Le lecteur natif de simulation fournit maintenant
le chronomètre, les dix héros (IA comprises), leurs niveaux et états de vie,
ainsi que les PV/ressources alliés. Les dix choix, équipes, niveaux et états
de vie concordent avec le replay de la capture à **1163,5625 secondes**.
Deux timers non nuls ont aussi été validés dans une nouvelle partie IA sur
Volskaya puis exactement contre son tracker. Ajout du18/10 : positions des héros
principaux alliés vivants sur Volskaya, avec perspective native locale prouvée,
relecture exacte et reçu d'acquisition âgé au plus1s. Dragon/Braxis, positions
ennemies, objectifs/camps/structures et capacités restent exclus. Depuis le19/10,
la visibilité CURRENT est validée uniquement sur Volskaya build98348, sans
ouvrir d'autre champ ennemi ; voir `etudes/rea/P2-VISIBILITE-VALIDATION.md`.
Recette et limites pixels : `etudes/rea/P2-POSITIONS-RECETTE.md` depuis la racine.
Les positions nécessitent lecteur et normaliseur dans le même processus live ;
un JSON `--state` interprocessus ou un dump historique ne les autorise pas.
Les sections techniques suivantes conservent aussi des éléments du 10 octobre ;
elles ne remplacent pas les priorités et limites actuelles ci-dessus.

Lot visibilité : `visibility.py` est un lecteur conservateur, activé uniquement
pour le booléen courant Volskaya après deux cycles joueur recoupés. Positions,
PV/ressources, talents et cooldowns ennemis restent fermés.
`etudes/rea/P2-VISIBILITE.md` décrit les sources, limites et le collecteur
borné. Le durcissement associé exige désormais une perspective native humaine
courante et un reçu du même processus âgé au plus1s pour transmettre PV/ressources
alliés au modèle ; un JSON externe ou dump historique ne les autorise plus.
La lecture native est aussi soumise à une relecture intégrale et125ms murales.

---

## Inventaire historique des replays testés (10/10/2026)

Un `.StormReplay` contient un flux d'événements bien plus riche que le HUD.
Inventaire réellement observé sur les replays testés :

| Famille | Événements | Contenu historique observé, pas des champs live autorisés |
|---|---|---|
| Héros | `spawn`, `death`, `respawn` (+ position, tueur) | qui est vivant, où, qui vient de mourir |
| Progression | `LevelUp`, `TalentChosen`, `SUpgradeEvent` | niveaux d'équipe, talents choisis (dont les ults) |
| Économie | `PeriodicXPBreakdown` (fenêtres de 60 s) | XP par équipe, d'où vient l'avantage |
| Objectifs | `TributeCollected`, `RavenCurseActivated`… (par map) | phase d'objectif en cours |
| Carte | `JungleCampCapture`, `TownStructureDeath`, `RegenGlobePickedUp` | camps, structures, pression de lane |
| Positions | `SUnitPositionsEvent` (~toutes les 15 s) | positions des héros régulièrement |
| Communication | pings, chat | ce que l'équipe demande |
| Fin de partie | `SScoreResultEvent`, `EndOfGame*` | dégâts, soins, temps mort, score final |

Cet inventaire ne prouve ni disponibilité pendant une partie ni adéquation à la
perspective du joueur. `live_probe.py` est une sonde historique, pas une source
live qualifiée ni le parcours de collecte recommandé.

## Ancien exemple d'extraction — modèle non exécuté lot40

```bash
cd hotstate
uv venv .venv
uv pip install --python .venv/Scripts/python.exe heroprotocol

# Extraction d'un replay -> game_state.json (contrat hotstate)
.venv/Scripts/python.exe extract.py "chemin/vers/partie.StormReplay" --summary
```

Sortie : JSON conforme à `schema/game_state.schema.json`
(`meta`, `players`, `timeline`, `position_snapshots`, `final_score`, `available`).

## Ancienne piste replay en direct — constat borné du 10/10/2026

L'observation ancienne portait sur la publication d'un replay final dans le
répertoire utilisateur après l'écran MVP, et sur des fichiers temporaires de
reconnexion. Elle ne démontre pas l'impossibilité générale d'un préfixe partiel.
Aucun de ces temporaires n'est qualifié ici comme source actuelle de statistiques.
Un contexte de lobby ne prouve ni valeurs tactiques, ni fraîcheur, ni perspective
active. L'ancien ordre vision d'abord/mémoire ensuite est remplacé par la
[priorité native actuelle](#priorité-actuelle-et-limites-du-direct), sans garantie
juridique ou compte tirée d'un forum ou d'une technique de capture.

## Lecteur natif de simulation

`native.py` lit les structures utilisées par les natives Galaxy du moteur,
sans appeler ces fonctions et sans écrire dans le processus. Les RVA du profil
`profiles/98348.json` sont protégées par l'empreinte PE et **onze empreintes de
code**, identiques dans deux instances ASLR. Un autre build, une signature
modifiée, un pointeur invalide ou une association joueur/unité incohérente
fait refuser l'enrichissement, pas fabriquer une observation.

- `meta.t_s` / `clock_kind=mission` : `GameGetMissionTime`, fixed-point natif
  /4096 ; préparation incluse, comme les boucles du replay. Ce n'est ni
  l'horloge du PC ni le chrono HUD après ouverture des portes. Aucun décalage
  constant supposé n'est soustrait et ce temps ne pilote pas les timings HUD de la KB.
- `players` / `local_player` : IDs et équipes initData, dix héros dans `CPlayer` ;
  les IDs internes sont rapprochés des 90 slugs KB par `hero_ids.json`, extrait
  des `cHeroId` du cache heroes-talents. Aucun pseudo n'est exporté.
- `heroes` : état vivant/mort, premier composant XP actif (comme `UnitLevel`),
  `respawn_s` seulement si le héros est mort et son timer est lisible.
- PV et ressources : équipe locale uniquement. Les PV ennemis ne sont pas
  exposés en l'absence d'une validation de leur visibilité.
- Une observation native prend au plus une seconde de simulation entre ses
  lectures d'horloge de début et de fin, sinon elle est rejetée.
- Les triggers expérimentaux restent accessibles avec `--debug`, pas dans
  les statistiques publiées. Trois compteurs seulement sont validés.

Depuis la racine, après autorisation de lecture mémoire pour une partie IA :

```bash
# Un relevé en lecture seule, sans API et sans son
tts/.venv/Scripts/python.exe -m hotstate.reader --live --player NOM --out out/test-live/native-state.json

# Même lecteur sur une capture privée : module ET tas de la même session
tts/.venv/Scripts/python.exe -m hotstate.reader --dump out/recon-live/live-a.heap.bin out/recon-live/live-a.heap.json --image out/recon-live/live-a.bin --player NOM --out out/test-live/native-state.json
```

`meta.native_status=valide` signifie que l'enrichissement a passé ses contrôles.
Sans contexte local ou avec un profil incompatible, seuls les anciens champs
prouvés restent disponibles. Les fichiers du tas sont mappés en lecture seule
pour éviter de charger plusieurs Go en RAM. Une ancienne image prise au menu
ne remplace pas l'image de la partie : les globals du module évoluent aussi.

`etudes/rea/scripts/validate_native.py --image MODULE --heap TAS --manifest JSON
--replay REPLAY --player NOM --out SORTIE [--api]` vérifie l'identité de partie
et les dix héros/équipes/niveaux/états de vie. Les noms français de référence
sont rapprochés des identifiants de créations d'unités du replay, indépendamment
du lecteur natif. Le replay n'est jamais fusionné dans l'état envoyé à Groco.
Rapport réel : `out/rea-collection/validation/report.json` ; aucune lecture audio.
Rapport live : `out/rea-collection/live-validation/report.json` : dix héros,
niveaux et états concordants ; Li-Ming à 15,3125 s et Qhira à 3,5625 s de leur
réapparition, exactement comme les boucles tracker, sans arrondi décimal.
Le mapping `Volskaya` → `Volskaya Foundry` et la reprise d'un cache temporairement
incomplet sont testés. Au tout début, un buffer initData absent reste inconnu :
les cycles suivants recherchent à nouveau le contexte, sans en inventer un.

## Notes techniques (pièges connus)

- **Contexte mémoire opt-in.** `cerveau --live --player NOM` ou
  `cerveau.diagnostic --live --player NOM` active `context.ContextProbe`.
  Le scan des compteurs est réutilisé : pas de second parcours du tas.
  Le buffer `replay.initData` en mémoire est décodé avec le protocole Blizzard
  installé, sans offsets absolus. Carte : archive `.s2ma` désignée dans ce
  buffer, champ MapScript `mAPMapStringID`, rapprochement non ambigu avec la KB.
  Aucun nom de compte ou toon handle n'est transmis au cerveau.
- **Limites du contexte.** Sonde validée lorsque le nom recherché est le premier
  utilisateur initData (cas de cette partie IA à un humain). Dix slots actifs,
  équipes 5v5 et joueur unique sont requis. Plusieurs parties candidates ou
  trop de candidats => contexte absent, jamais réutilisation du précédent.
  En live, l'absence de fichier de lobby actif supprime aussi le contexte.
  Les choix IA peuvent être vides dans initData : le lecteur natif les enrichit
  ensuite. Sans cet enrichissement, `hero=null` et `composition_complete=false`
  restent explicites ; aucune complétion depuis le replay.
- **Identité de partie.** Un hash de seed+cache distingue deux parties et entre
  dans le contrôle de fraîcheur ; ce n'est ni une horloge ni une observation
  tactique. Les niveaux de compte/maîtrise du lobby ne sont pas des niveaux de
  partie et ne sont jamais exportés comme tels.
- **Python 3.12+.** Le chargeur amont `heroprotocol.versions` importe `imp`,
  retiré de Python. `protocols.py` utilise importlib pour charger les modules
  officiels installés, sans modifier le package ni simuler `imp`.
  Installer les dépendances dans l'environnement qui exécute le coach :
  `uv pip install --python tts/.venv/Scripts/python.exe -r hotstate/requirements.txt`.
- **Chat absent en partie IA.** Le bloc `replay.message.events` peut être
  absent ou vide : il est désormais ignoré, pas décodé comme `None`.

### Validation reproductible du contexte (sans jeu ni son)

`etudes/rea/scripts/validate_context.py` relit un dump avec mmap, récupère le
contexte avec le lecteur livré, puis compare identité de partie, héros local
et dix équipes au replay correspondant. `--api` ajoute un vrai appel Groco
contenant **uniquement l'observation capturée**, pas les données du replay.
Le rapport distingue le contexte vérifié des champs tactiques encore inconnus.
Les captures brutes restent privées sous `out/`, ignoré par Git.

- **Shim de protocole.** heroprotocol ne liste pas les builds récents
  (97xxx/98xxx) : `extract.py` les décode avec le dernier protocole connu.
  Vérifié fonctionnel sur le build 97771 (`meta.protocol_shim: true` le signale).
- **Temps.** `t` = secondes de jeu = `_gameloop / 16`.
- **Identités.** `PlayerID` (stat events) = `m_controlPlayerId` (tracker) =
  `m_workingSetSlotId + 1` (details) — vérifié sur les replays testés.
- **Coordonnées.** `SUnitBornEvent.m_x/m_y` (grille) et `SUnitPositionsEvent`
  (×4, cf. README heroprotocol) ne sont pas à la même échelle : à normaliser
  si l'agent compare les deux. Les positions sont en repère de map, pas écran.
- **fixed-point.** Les `data` de type `m_fixedData` (GameTime…) sont brutes ;
  l'échelle exacte varie selon l'événement, ne pas en dériver de temps —
  `_gameloop` fait foi.

## Roadmap historique remplacée — aucune activation par cette note

La roadmap initiale d'évaluation vision puis mémoire ne fixe plus l'ordre de
travail. Revenir au [guide livré](../docs/start-here.md) et à sa matrice bornée :
natif ciblé prioritaire, vision seulement recours autorisé, références non
productrices. Aucun nouveau match, scan, téléchargement ou appel API n'est
nécessaire pour lire les preuves hors ligne conservées.
