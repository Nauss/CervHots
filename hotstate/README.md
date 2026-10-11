# hotstate — la couche stats de CervHots

**Mission :** fournir à l'agent de décision (le cerveau du coach) **toutes les
stats de la partie en cours**, quel que soit le moyen de les obtenir. Une seule
sortie, un seul contrat : `schema/game_state.schema.json`. La source (replay,
mémoire, vision) est un détail d'implémentation derrière ce contrat.

**État (10/10/2026) :** extracteur **validé sur 2 parties réelles** (replays du
compte). Source live : la piste « replay en cours de partie » est **morte**
(vérifiée — voir plus bas) ; il reste la vision, et la mémoire en plan B.

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

## Notes techniques (pièges connus)

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
