# CervHots

Le coach IA de Heroes of the Storm : état de jeu (mémoire ou replay), savoir
de la KB, décision via l'API Groco, TTS local et diffusion dans Mumble.

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
  `etudes/tts/` — synthèse vocale : choix des moteurs, contrat audio Mumble.
  `etudes/mumble/` — bot Mumble : client pymumble, format audio tranché, POC.
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
- `tts/` — **la voix** : phrase du coach + modèle + ton → PCM s16le 48 kHz
  mono prêt pour Mumble. Deux moteurs locaux gratuits derrière une seule API :
  Piper (défaut, acté à l'écoute) et Kokoro (qualité), presets de ton, CLI et
  smoke test. Étude : `etudes/tts/`.
- `mumblebot/` — **la diffusion** : bot pymumble (fork 2.0) qui consomme
  `tts.Speech` et parle dans un canal Mumble, avec respect basique des tours
  de parole. POC parole validé en conditions réelles (murmur 1.5.915).
  Étude : `etudes/mumble/`.
- `cerveau/` — **le cerveau et les liens entre les briques** : hotstate → KB →
  Groco → décision courte → TTS → Mumble. Silence par défaut, validation JSON,
  anti-répétition, cooldown et rejet des conseils périmés. Le parcours réel
  replay → Groco → WAV est validé sans lecture sonore. Usage :
  `python -m cerveau --check`, puis `python -m cerveau --state partie.hotstate.json --at 73.5`.
  Détails et activations explicites du live/de la voix : `cerveau/README.md`.
  Étude et mesures : `etudes/cerveau/ETUDE.md`.

## État

Au 15/10/2026 : couches stats (`hotstate/`), savoir (`kb/`), voix (`tts/`) et
diffusion (`mumblebot/`) reliées par `cerveau/`. L'API Groco est provisionnée et
le parcours réel jusqu'au WAV est vérifié. La diffusion de ce nouveau parcours
en partie reste à autoriser et valider ; le lecteur mémoire actuel ne fournit
que des compteurs globaux, pas encore les informations tactiques détaillées
des replays. La couche stats empiriques (v3) reste hors de ce branchement.
