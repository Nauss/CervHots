# hotstate — la couche stats de CervHots

**Mission :** fournir à l'agent de décision (le cerveau du coach) **toutes les
stats de la partie en cours**, quel que soit le moyen de les obtenir. Une seule
sortie, un seul contrat : `schema/game_state.schema.json`. La source (replay,
mémoire, vision) est un détail d'implémentation derrière ce contrat.

**État (10/10/2026) :** extracteur **validé sur 2 parties réelles** (replays du
compte). La source live est en cours d'expérience (`live_probe.py`).

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

# Expérience LIVE : à lancer pendant une partie de HotS
.venv/Scripts/python.exe live_probe.py
```

Sortie : JSON conforme à `schema/game_state.schema.json`
(`meta`, `players`, `timeline`, `position_snapshots`, `final_score`, `available`).

## Les chemins vers le « en direct » — dans l'ordre

1. **Replay partiel (privilégié).** Le fichier `.StormReplay` est-il écrit
   pendant la partie et décodable au fil de l'eau ? `live_probe.py` le prouve
   (ou infirme) dès la prochaine partie : il suit le fichier en écriture et
   note ce qui se décode, quand. Si oui → stats complètes, légales, zéro risque
   de ban. Seul le score final n'arrive qu'en toute fin.
2. **Lecture mémoire** (plan B, étude `etudes/rea/`) — localiser l'état dans le
   binaire avec REA + Ghidra, puis petit lecteur. Coût : temps de reverse ;
   **risque : ToS + Warden, décision explicite du propriétaire du compte**.
3. **Vision** (plan C, plan initial) — capture de la minimap + bandeau. Ne
   sert plus qu'à la nuance sémantique (brouillard, « lecture de la map ») si
   les plans 1 ou 2 marchent.

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

1. Lancer `live_probe.py` pendant une vraie partie → trancher le chemin 1.
2. Si chemin 1 OK : `live_extract.py` (flux live → `game_state` toutes les N s)
   et branchement sur l'agent de décision.
3. Si non : passer au chemin 2 (REA + Ghidra, voir `etudes/rea/ETUDE.md`).
