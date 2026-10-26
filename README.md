# CervHots

Outils Heroes of the Storm : démonstration hors ligne, débrief replay et
inspection de journaux natifs, **sans Coach/API/audio par défaut**. Le pipeline
historique de coach (KB → API Groco → TTS → Mumble) reste une voie distincte,
à activation explicite, pas le parcours de démarrage recommandé.

## Ce repo

Monorepo : il accueille tous les briques du projet, chacune dans son
répertoire (capture, perception, cerveau, TTS, bot Mumble, outils…).
Chaque brique a son propre projet, ses propres dépendances.

## Pour démarrer en cinq minutes

**[Choisir son parcours : `docs/start-here.md`](docs/start-here.md)** — commandes
Windows absolues de la recette hors ligne, sorties neuves et limites :

1. [Démo SYNTHETIC silencieuse](docs/start-here.md#1-démo-silencieuse-sans-jeu-ni-replay-recommandé) : aucune donnée personnelle ni jeu requis.
2. [Débrief d'un vrai replay historique](docs/start-here.md#2-vrai-replay-conservé-à-60-secondes) : SHIM non certifié sur opt-in explicite ; 10/10 héros reconnus sur les deux corpus historiques exercés, aucun gain live/HUD.
3. [Inspection d'un journal natif conservé](docs/start-here.md#3-journal-natif-existant--distinguer-état-et-contenu) : statut/diagnostic/HTML, jamais CURRENT.
4. [Préflight core sans backend](docs/start-here.md#4-préflight-sans-backend--live-uniquement-sur-autorisation-distincte) : préparation technique, pas autorisation live.

**STOP week-end maintenu : aucune activation par cette documentation.**
Arrêt/reprise native : signal ciblé ≠ lecteur arrêté ; confirmer le retour du
terminal propriétaire, puis parent/sortie/STOP neufs, anciens claims/STOP conservés.
La [matrice honnête des familles](docs/start-here.md#familles--ce-que-les-preuves-permettent-réellement-de-dire)
ne généralise aucune qualification carte × famille ; Braxis reste non débloqué.

### Références détaillées et anciens exemples

Les commandes abrégées et chemins entre chevrons ci-dessous sont des **modèles
non exécutés pour lot33**, pas des lanceurs prêts à copier. Utiliser le parcours
consolidé ci-dessus pour les recettes réellement exercées ; les voies API/voix
historiques ne font pas partie de son smoke silencieux.

- **Débrief replay local déterministe, sans Coach/API/audio** :
  `python -B -m cerveau.replay_debrief --replay <fichier.StormReplay> --team 0 --perspective player-team --at 60`.
  JSON minimisé avec résumé français ; ajouter `--report-dir C:/rapports/debrief-neuf`
  (Windows, parent existant) pour obtenir `REPORT.html` autonome sombre et `report.json`,
  puis ouvrir manuellement le HTML hors ligne. Refus du shim par défaut, opt-in indicatif
  explicite, inconnues préservées et aucune position exportée :
  [`docs/replay-debrief.md`](docs/replay-debrief.md).

- **Collecte native passive sans Coach/API/audio** : `python -m cerveau.passive_session`
  (préflight local, aucune mémoire ouverte). Lancement live explicite, identité
  privée par fichier, arrêt STOP et nouvelle commande par partie :
  [`docs/passive-quickstart.md`](docs/passive-quickstart.md) : parcours court avec
  chemins absolus, préflight, `--status` historique sans backend, `--request-stop`
  ciblé lié au contrôle des nouvelles sessions (signal ≠ preuve d'arrêt),
  reprise neuve (parent, sortie et STOP neufs ; ancien claim conservé) et codes
  de sortie. Vérifier la fin de l'ancien collecteur avant reprise. Contrat détaillé :
  [`docs/passive-session.md`](docs/passive-session.md).
  **Cœur natif seul par défaut CLI** : `--collection core` (ou omission), sélection avant toute
  lecture optionnelle, normalisation et journal sans optionnels :
  [`docs/core-collection.md`](docs/core-collection.md). Migration `all` → `core` :
  `--collection all` et `--collection talents` restent des opt-in explicites.
  Diagnostic **hors ligne** d'un journal explicite, JSON + résumé lisible,
  acquisitions/observations/refus/arrêt et preuves non comparables :
  `python -m cerveau.passive_session --diagnose --journal <absolu-events.jsonl> --report-dir <absolu-neuf>`,
  [`docs/session-diagnosis.md`](docs/session-diagnosis.md). Ni intégrité ZIP/hash,
  ni pixels non noirs ne valent validation HUD ; aucune collecte live nécessaire.
  **Résumé joueur des observations natives déjà enregistrées** :
  `python -B -m cerveau.passive_session --summarize --journal <absolu-events.jsonl> --report-dir <absolu-neuf>`,
  [`docs/native-history.md`](docs/native-history.md) : dernier instant cohérent,
  niveaux publics, talents locaux qualifiés et objectif public disponible ;
  inconnus/refus explicites, sans conseil, identité authentifiée ni CURRENT.
  **Préflight de qualité visuelle avant recette** :
  `python -B -m cerveau.capture_quality --help`,
  [`docs/capture-quality.md`](docs/capture-quality.md) : ROI explicite,
  intégrité BMP/ZIP et temporalité bornées, noir/masquage quantifié,
  contrat manuel indépendant. Unknown/refus bloque l'usage de la référence ;
  aucun verdict ne qualifie automatiquement HUD, calibration ou comparaison.
  Talents réellement choisis : journal allié durable, âge original, libellés
  inconnus sans provenance et inspection historique sans permission live :
  `python -m cerveau.talents_journal --help`,
  [`docs/talents-collection.md`](docs/talents-collection.md).
  Objectif Dragon : qualification explicite, valeurs publiques durables, âge
  source conservé et rejeu sans permission live :
  [`docs/objective-collection.md`](docs/objective-collection.md).
  Comparaison indépendante bornée à une référence HUD manuelle liée à la partie :
  `python -m cerveau.objective_compare --help`,
  [`docs/objective-comparison.md`](docs/objective-comparison.md).

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
  Extracteur de replays (vérité terrain), trois compteurs mémoire validés,
  contexte initData et lecteur natif (`native.py`, profil build 98348) :
  horloge, dix héros, niveaux, état de vie, PV/ressources alliés. Les dix héros,
  équipes, niveaux et états de vie sont recoupés avec le replay de la capture.
  Timers de mort validés en partie puis contre le tracker ; positions natives
  alliées vivantes sur Volskaya (build98348, joueur local prouvé, fraîcheur1s).
  Recette/limites : `etudes/rea/P2-POSITIONS-RECETTE.md`. Objectifs, camps,
  structures, visibilité/positions ennemies restent hors collecte live.
  Talents natifs choisis : sélection persistée, pas possessions/options offertes.
  Portée build98348/DragonShire : Sonya locale ; alliés Arthas, Dehaka,
  LtMorales et Tassadar. Autres héros/rôles/cartes inconnus, aucune généralisation.
  Contrat, recettes et limites : `etudes/rea/P2-TALENTS.md`.
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

## État au 26/10/2026 — base de recette locale lots33–36 intégrés

Base MAIN locale vérifiée à `0573b30fdb213ad449eb9172a35ea3093769c05d` : collecte
passive durable et opérations ciblées, défaut CLI core, préflight/readiness hors
ligne, diagnostic et restitution HTML de journaux, chronologie/trace des talents,
cooldowns historiques, catalogue/complétude et démonstration SYNTHETIC intégrés.
Le débrief replay JSON/texte/HTML est intégré aussi, sans Coach/API/audio.
Cela ne transforme pas leurs tests hors ligne en qualification native indépendante.
Le guide de démarrage et les alias replay historiques sont intégrés. Les deux
corpus exercent désormais 10/10 héros reconnus, sous SHIM indicatif non certifié ;
la vie n'est affichée que lorsqu'un événement reconnu l'établit. Carte inconnue
et objectif inconnu restent inconnus ; aucune nouvelle qualification native/live/HUD.

Objectif Dragon : exports/rejeu acquis avec limites ; Volskaya objectif reste
qualification seulement ; Braxis toujours fermé. Cooldown zéro historique ne
prouve ni cycle actif ni reset, charges inconnues ; noms choisis de talents non
qualifiés, camps/structures/visibilité ennemie non ouverts. Voir la
[matrice et ses preuves](docs/start-here.md#familles--ce-que-les-preuves-permettent-réellement-de-dire).
Les recettes opérateurs lot19/lot28 ont refusé le live (contexte privé actuel
inconnu) : aucun gain core/all réel ni STOP produit live n'en est déduit.
Les compteurs ambigus ne sont pas convertis en total de matchs.

### Historique conservé — état au 17/10 et ajout du 18/10

Le paragraphe suivant conserve l'état ancien, **pas la description actuelle de
MAIN** ; notamment « objectifs hors collecte » est daté et doit être lu avec la
matrice actuelle ci-dessus.

Au 17/10/2026 : couches stats (`hotstate/`), savoir (`kb/`), voix (`tts/`) et
diffusion (`mumblebot/`) reliées par `cerveau/`. L'API Groco est provisionnée et
le parcours réel replay → Groco → Piper → Mumble a été vérifié, écoute humaine
confirmée. Le lecteur natif fournit maintenant composition, niveaux, états de
vie, timers de mort et PV/ressources alliés. Une partie IA sur Volskaya a vérifié
dix héros/équipes/niveaux/états et deux timers non nuls, exacts au tracker.
L'horloge suit le temps de mission du replay, préparation incluse ; elle n'est
pas confondue avec le chrono HUD. Ajout du18/10 : positions alliées Volskaya
seulement ; Dragon/Braxis non ouvertes, aucune position ennemie. Objectifs,
camps/structures, visibilité et capacités restent hors collecte live ; les
statistiques empiriques (v3) aussi.
