# CervHots

Le coach IA qui regarde une partie de Heroes of the Storm en cours et te parle
dans Mumble : capture d'écran (minimap + bandeau des héros), analyse par IA,
texte de coaching, TTS, diffusion vocale.

## Ce repo

Monorepo : il accueille tous les briques du projet, chacune dans son
répertoire (capture, perception, cerveau, TTS, bot Mumble, outils…).
Chaque brique a son propre projet, ses propres dépendances.

## Pour démarrer

- `FAISABILITE.md` — l'étude complète : architecture, options techniques,
  risques, roadmap. **À lire en premier.**
- `IDEA.md` — l'idée de départ, en une ligne.
- `CervHots-Presentation.html` / `.pdf` — la présentation pour Groco
  (API OpenAI-compatible) : 10 planches, navigation clavier.
- `etudes/` — les petites études techniques, une par sous-répertoire.
  En cours : `etudes/rea/` — utiliser REA (reverse engineering) pour accéder
  aux infos de jeu en direct plutôt qu'aux seuls pixels.
  `etudes/api/` — accès à l'API de Groco (gateway compatible OpenAI).
  `etudes/kb/` — base de connaissances du coach (cartes, timings, builds,
  synergies, counters) : architecture retenue, sources de données.
- `grocoapi/` — client minimal (zéro dépendance) de l'API de Groco : config
  centralisée dans `.env` (racine, jamais versionné), chat, comptes, jobs
  async. Test : `python grocoapi/smoke.py`.
- `hotstate/` — **la couche stats** : tout ce qui sort de HotS (niveaux, talents,
  morts, XP, objectifs, positions) normalisé pour l'agent de décision.
  Extracteur de replays validé (vérité terrain) ; lecteur live **validé
  hors-ligne** (`reader.py`, 9/9 valeurs exactes vs replay) qui lit les
  triggers de jeu en mémoire vive. La vision n'est plus nécessaire : les
  infos viennent de la mémoire, en valeurs exactes.
- `kb/` — **la couche savoir** : ce qui interprète l'état de jeu (cartes,
  timings, talents, synergies, counters). Base SQLite de faits (gamedata
  gratuite, commit épinglé) + 106 fiches curatées (16 cartes + 90 héros,
  rédaction LLM puis relecture). `briefing.py` compile le briefing court du
  coach (3-4 points) ; timings validés sur 76 replays. Étude : `etudes/kb/`.
  **Relecture web effectuée le 12/10/2026** (agent délégué) : 106 fiches
  vérifiées contre wiki/icy-veins/etc., 61 corrigées, 44 OK, 1 incertaine —
  rapports sourcés dans `kb/notes/_relecture/`.

## État

Étude de faisabilité validée (oct. 2026). POC parole (bot Mumble + TTS) à
venir. Couches stats (`hotstate/`) et savoir (`kb/`) en place ; reste la
couche stats empiriques (v3, agrégée depuis nos replays) et le cerveau.
