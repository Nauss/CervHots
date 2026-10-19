# hotstate — la couche stats de CervHots

**Mission :** fournir à l'agent de décision (le cerveau du coach) **toutes les
stats de la partie en cours**, quel que soit le moyen de les obtenir. Une seule
sortie, un seul contrat : `schema/game_state.schema.json`. La source (replay,
mémoire, vision) est un détail d'implémentation derrière ce contrat.

**État (17/10/2026) :** lecture mémoire des trois compteurs validée en partie
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
Le reste de cette note conserve l'historique initial du 10 octobre.

Lot visibilité : `visibility.py` est un lecteur conservateur, activé uniquement
pour le booléen courant Volskaya après deux cycles joueur recoupés. Positions,
PV/ressources, talents et cooldowns ennemis restent fermés.
`etudes/rea/P2-VISIBILITE.md` décrit les sources, limites et le collecteur
borné. Le durcissement associé exige désormais une perspective native humaine
courante et un reçu du même processus âgé au plus1s pour transmettre PV/ressources
alliés au modèle ; un JSON externe ou dump historique ne les autorise plus.
La lecture native est aussi soumise à une relecture intégrale et125ms murales.

---

## Ce que HotS nous donne déjà (validé sur pièces)

Un `.StormReplay` contient un flux d'événements bien plus riche que le HUD.
Inventaire réellement observé sur les replays testés :

| Famille | Événements | Ce que ça donne au coach |
|---|---|---|
| Héros | `spawn`, `death`, `respawn` (+ position, tueur) | qui est vivant, où, qui vient de mourir |
| Progression | `LevelUp`, `TalentChosen`, `SUpgradeEvent` | niveaux d'équipe, talents choisis (dont les ults) |
| Économie | `PeriodicXPBreakdown` (fenêtres de 60 s) | XP par équipe, d'où vient l'avantage |
| Objectifs | `TributeCollected`, `RavenCurseActivated`… (par map) | phase d'objectif en cours |
| Carte | `JungleCampCapture`, `TownStructureDeath`, `RegenGlobePickedUp` | camps, structures, pression de lane |
| Positions | `SUnitPositionsEvent` (~toutes les 15 s) | positions des héros régulièrement |
| Communication | pings, chat | ce que l'équipe demande |
| Fin de partie | `SScoreResultEvent`, `EndOfGame*` | dégâts, soins, temps mort, score final |

Pas besoin de lire la mémoire du jeu pour tout ça **si le fichier est lisible
pendant la partie** — c'est exactement ce que teste `live_probe.py`.

## Utilisation

```bash
cd hotstate
uv venv .venv
uv pip install --python .venv/Scripts/python.exe heroprotocol

# Extraction d'un replay -> game_state.json (contrat hotstate)
.venv/Scripts/python.exe extract.py "chemin/vers/partie.StormReplay" --summary
```

Sortie : JSON conforme à `schema/game_state.schema.json`
(`meta`, `players`, `timeline`, `position_snapshots`, `final_score`, `available`).

## Les chemins vers le « en direct » — dans l'ordre

**Vérifié (10/10/2026) : le `.StormReplay` n'existe qu'après la partie.** Il
n'arrive dans `Documents\...\Replays\` qu'une fois l'écran MVP passé ; pendant
la partie, les données vivent dans des fichiers temporaires de reconnexion
(`%LOCALAPPDATA%\Temp\Heroes of the Storm\TempWriteReplayP1\`), au format blob
non documenté, effacés à la fermeture du jeu. Le forum Blizzard est explicite :
*« Replay files aren't created until after the match has finished, so there
isn't a way to get replay data during a live match without breaking the EULA. »*
→ la piste « parser le replay en cours de partie » est **abandonnée**.

1. **Vision (plan A).** Capture de la minimap + du bandeau, analysée par le
   modèle vision. Légal, testable tout de suite. Les replays deviennent alors
   **vérité terrain** : `extract.py` produit l'état réel d'une partie passée,
   pour mesurer ce que la vision en lit vraiment (phase 2 de la roadmap).
2. **Mémoire (plan B).** REA + Ghidra pour localiser l'état dans le binaire,
   puis petit lecteur. Décision **ToS/Warden** requise avant toute lecture live.
3. **Bonus gratuit, en direct** : pendant la partie, `replay.server.battlelobby`
   (fichier temporaire, parsable — cf. Heroes.StormReplayParser) donne map,
   compositions et identités de joueurs. C'est ce que lit HotsStats. Utile pour
   le contexte du coach (qui joue quoi, sur quelle map), pas pour les stats de
   match.

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

## Prochaines étapes

1. **Corpus d'évaluation de la vision** : sur N replays, capturer les crops du
   HUD (rejoués dans le client) et comparer ce que le modèle vision en lit à
   l'état réel d'`extract.py` — LA mesure de la phase 2.
2. Brancher le format `game_state` sur l'agent de décision (côté vision) +
   exploiter `replay.server.battlelobby` pour le contexte (comps, map).
3. Si la vision ne suffit pas : plan B mémoire (REA + Ghidra, `etudes/rea/`),
   décision ToS/Warden au préalable.
