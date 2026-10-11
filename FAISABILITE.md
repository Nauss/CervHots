# CervHots — Coach IA temps réel pour Heroes of the Storm

**Étude de faisabilité et plan — 10/10/2026**

Projet : un coach IA qui observe une partie de HotS en cours via capture d'écran
(minimap + bandeau des héros), analyse la situation, génère un texte de coaching,
le fait prononcer en TTS et le diffuse dans un canal Mumble.

---

## 0. Verdict

**Faisable.** Tous les briques existent, matures et gratuites. Aucune n'est
bloquante techniquement. Le seul vrai risque est la **qualité de lecture de la
minimap par le modèle de vision** — c'est là que doit porter le POC et
l'investissement (prompting, découpe des crops, évaluation sur replays).
Aucune donnée de jeu live n'est lisible autrement que par les pixels :
les replays HotS ne sont écrits qu'à la fin de partie, donc la capture d'écran est
bien la seule source d'information en direct (confirmé par Blizzard : « Replay
files aren't created until after the match has finished »).

Budget de latence réaliste : **~5 à 12 s** entre une situation sur l'écran et le
coach qui parle. C'est compatible avec du coaching (pas du micro-management
action par action), à condition d'un texte court et d'une cadence espacée.

---

## 1. Architecture générale

```
HotS (plein écran)
   │
   ▼
[1] CAPTURE ── dxcam (Desktop Duplication) ── crops : minimap, bandeau haut, timer
   │           1–2 Hz + détection de changement (hash/diff)
   ▼
[2] PERCEPTION ── OCR (timer, niveaux, PV) + VLM (API du pote, format OpenAI)
   │              → état de partie structuré (JSON)
   ▼
[3] CERVEAU ─── mémoire de partie + heuristiques + prompt coach
   │              → 1–2 phrases prioritaires, non répétitives
   ▼
[4] TTS ──────── Piper (fr_FR-siwis) ou Kokoro (ff_siwis), local, gratuit
   │              → PCM 48 kHz mono
   ▼
[5] MUMBLE ───── bot pymumble → canal de l'équipe (respect des tours de parole)
```

Pipeline asynchrone avec file de messages : si une analyse est déjà en cours,
la suivante **remplace** l'ancienne (on ne joue pas un conseil périmé).
Principe : « le coach ne parle que de l'état le plus frais ».

---

## 2. Axe 1 — Module de capture

**Techno : dxcam ou BetterCam** (API Desktop Duplication, Windows uniquement).
Sur petite région : ~387 FPS pour dxcam vs ~57 pour mss (benchmarks kylefu.me /
rapidshot). mss reste un fallback simple. On capture à 1–2 Hz, la perf n'est
donc pas un sujet — le choix se joue sur la précision des coordonnées.

**Zones à capturer (résolution fixée une fois pour toutes) :**

| Zone | Contenu utile | Position typique |
|---|---|---|
| Minimap | positions héros, brouillard, objectifs, camps | bas-droite (fixe, non déplaçable dans HotS) |
| Bandeau haut | niveaux d'équipe, portraits PV/mana, ults prêts, timers de mort | haut écran |
| Timer de partie | horloge centrale | haut-centre |

**Points d'attention :**
- HotS n'a **aucun réglage de taille/position de HUD** (contrairement à LoL) →
  les coordonnées de crops sont stables pour une résolution donnée. Bonne
  nouvelle pour le hard-coding.
- Piège Windows : **mise à l'échelle DPI** — il faut capturer en coordonnées
  physiques ou désactiver le scaling pour la résolution de jeu. POC obligatoire.
- Fenêtrage : figer « plein écran fenêtré » pour éviter les décalages.
- **Outil de calibration** indispensable (Phase 1) : affiche un aperçu avec les
  rectangles de crops superposés, permet de les ajuster, sauvegarde un profil
  `resolution → rectangles`.

---

## 3. Axe 2 — Perception (analyse des images)

Deux voies complémentaires, dans cet ordre de coût :

### a. OCR local (gratuit, ~10 ms) — chiffres fiables
Timer de partie, niveaux d'équipe, PV/mana, timers de mort : gros caractères,
OCR trivial (Windows.Media.Ocr comme HeroesReplay, ou PaddleOCR/tesseract).
On extrait du **fait vérifiable** sans LLM.

### b. VLM via l'API OpenAI-compatible du pote — sémantique
Format standard, éprouvé :
```json
{ "model": "<modèle vision>", "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "<prompt structuré>"},
      {"type": "image_url", "image_url": {"url": "data:image/png;base64,<...>"}}
    ]}]}
```
- Minimap + bandeau = 2 images par requête (≤ 4 recommandé).
- **Upscaler les crops** avant envoi : les pastilles de héros font ~10 px,
  le détail fin compte. Recommandation générique : ~1280 px max sur le grand
  côté pour du détail ; tokens ~ (h×w)/784.
- Sortie demandée en **JSON strict** : positions estimées par zone, danger,
  objectifs actifs, lecture du brouillard, avec un niveau de confiance.
- Prompt avec **légende du HUD** (que signifie chaque pastille/couleur) +
  exemples few-shot (captures annotées).

### c. Option « modèle de décision typé » (type JEV)
`autotrust/JEV-27B-VL` (HF) : base Qwen3.8-27B + tête de décision « System 1 »,
servable en vLLM (API OpenAI-compatible). Au lieu d'une description libre, on
pose des **questions typées** (noul/choice/score : yes/no, choix parmi 2–16
options, note 0–5) ; les réponses + **probas calibrées** constituent le JSON de
perception — JSON garanti par construction, garde-fou de confiance mesurable,
une passe, rapide. Nuance : JEV **évalue** une image contre un jeu de questions
prédéfini, il n'extrait pas en ouvert → le travail se déplace vers la conception
des questions, et les faits bruts restent à l'OCR/CV. Variante sobre : VLM
classique + `response_format: json_schema` (décodage contraint outlines/xgrammar).
Attention : `typesafe/jev` hébergé (Cloudflare) = state texte/JSON **sans images**.
Contrainte : 27B multimodal à servir chez le pote (pas sur le PC qui joue) ; à
évaluer sur les crops HotS (aucun de ces modèles ne connaît le jeu).

### d. Option de robustesse : CV classique en amont (optionnel, phase 5)
La littérature traite la lecture de minimap MOBA par détection d'objets
(YOLO sur icônes de joueurs — Dota2-Vis 2026, détection LoL AAAI 2023,
latence ~6 ms). Si le VLM lit mal, un petit détecteur de pastilles de
couleurs (règles + template matching) peut fournir des positions exactes au
LLM qui ne fait plus que raisonner. Pas nécessaire au MVP.

### Validation sans jouer
**Corpus de test à partir de replays** : lancer des .StormReplay en mode
observateur (projets HeroesReplay le font déjà automatiquement), capturer les
crops, et comparer la lecture du VLM à la **vérité terrain heroprotocol**
(positions, niveaux, événements — lib officielle Blizzard qui décode les replays).
C'est LE moyen de mesurer la qualité de perception sans stress de partie live.

---

## 4. Axe 3 — Cerveau (génération du coaching)

- **Mémoire de partie** : journal tournant (résumés des N derniers cycles,
  conseils déjà donnés) envoyé en contexte — anti-répétition obligatoire
  (le coach qui se répète est la première cause d'abandon).
- **Principes de prompt** : ne commenter que ce qui est visible (anti-
  hallucination), phrases courtes (≤ 25 mots ≈ 8–10 s de parole), ton
  « aventurier » (pas « conteur » 😉), une seule priorité par intervention,
  ignorer les situations banales (silence > bruit).
- **Personnalité du coach** (exigence produit) : utile d'abord, **fun, fin et
  piquant** quand ça aide (« Ils sont trois à manquer à l'appel. Devine lesquels. »),
  jamais toxique. Doser la répartie : la remarque utile, la pique, ou le silence.
  Le charme se règle dans les prompts de la phase 3.
- **Déclencheurs** : timer d'objectif proche, ennemis disparus de la minimap,
  déséquilibre de lane, mort récente, talent/ult qui devient disponible.
  Le cerveau choisit LE moment de parler et LE sujet.
- Tout passe par l'API du pote (vision + texte). Réponse en JSON :
  `{parler: bool, priorite: 1-3, texte: "..."}`.
- Garde-fous : pas de conseil si confiance < seuil ; cooldown mini entre deux
  prises de parole (ex. 15 s) ; file « latest wins ».

---

## 5. Axe 4 — TTS

Gratuit et local (contrainte prix) — deux candidats sérieux, français natif :

| | Piper (fr_FR-siwis) | Kokoro (ff_siwis) |
|---|---|---|
| Latence 1er audio | ~390 ms (CPU) | ~900–1300 ms (CPU) |
| Vitesse synthèse | très au-dessus du temps réel | ~5–10× temps réel |
| Qualité | correcte, un peu robotique | bonne, naturelle |
| Mémoire | ~300 MB | ~900 MB |

Recommandation : **Kokoro** si la qualité de voix compte (le rendu visuel/sonore
soigné est une exigence connue), **Piper** si la latence prime. Les deux tournent
en local pendant que HotS tourne (82M/20M paramètres, CPU largement suffisant).
Sortie : PCM 48 kHz mono pour Mumble. Streaming phrase par phrase possible
(découpe aux frontières de phrases) pour réduire la latence perçue.

---

## 6. Axe 5 — Diffusion Mumble

**pymumble** (client Mumble en Python) — le pattern exact existe :
texte → TTS wav → ffmpeg → PCM → `mumble.sound_output.add_sound(pcm)`.
- Format audio : PCM signé 48 kHz mono (16 bits selon API.md ; l'exemple
  officiel pousse du s32le — à trancher au POC, conversion ffmpeg en une ligne).
- Dépendance système : **libopus**.
- Limites connues d'azlux/pymumble (1.6.1, 2021) : audio en **TCP tunneling**
  uniquement (pas d'UDP média) — parfaitement suffisant pour un bot qui parle.
  Compatible serveurs récents via le fork maintenu `~oopsbagel/pymumble` 2.0
  (UDP chiffré AES-OCB2, version string à jour). Prévoir le fork si échec.
- Bot rejoint le canal de l'équipe avec un compte « Coach », et **cède la
  parole** : les callbacks d'état de parole (usertalking) permettent d'attendre
  un silence ou de baisser la priorité si quelqu'un parle (anti-chevauchement).
- Murmur auto-hébergé possible si besoin (gratuit), sinon le serveur existant
  de la bande.

---

## 7. Axe 6 — Orchestration temps réel

Boucle asynchrone unique (asyncio) :

1. Capture à 1 Hz ; si pas de changement notable (hash perceptuel) → skip.
2. Cycle d'analyse lancé au max toutes les 15–30 s, ou sur déclencheur.
3. Perception (OCR + VLM) → état JSON → cerveau → réplique.
4. TTS → file Mumble ; si la file contient déjà un conseil, le plus frais gagne.

Budget typique : VLM 2–6 s + texte 2–4 s + TTS 0,5–2 s ≈ **5–12 s** bout en bout.
Acceptable : le coach parle d'une situation qui vient d'arriver, pas d'une
frame. Les phases où l'API du pote est lente se dégradent proprement
(enchaînements de conseils plutôt que temps réel serré).

---

## 8. Risques et mitigations

| Risque | Gravité | Mitigation |
|---|---|---|
| Le VLM lit mal la minimap (petites icônes, brouillard) | **Élevée** | crops upscalés + few-shot + JSON avec confiance + corpus replay pour mesurer ; fallback CV classique |
| Latence API (le pote) | Moyenne | cadence 20–30 s, latest-wins, streaming TTS |
| Conseils répétitifs / hors-sujet | Moyenne | mémoire de partie, garde-fous de prompt, cooldown |
| pymumble vieux vs serveurs récents | Moyenne | fork oopsbagel ; POC audio dès la phase 0 |
| DPI / résolution qui bouge | Faible | profil de calibration, résolution figée |
| ToS / anti-triche | Faible | pixels uniquement (comme OBS) — aucun accès mémoire |
| Voix FR trop synthétique | Faible | Kokoro (qualité) vs Piper (latence), à écouter au POC |

---

## 9. Plan de développement

**Phase 0 — POC parole (½–1 j)** : bot pymumble qui lit un texte fixe via TTS
dans le canal. Valide libopus, format audio, fork si besoin. Zéro dépendance
au jeu.

**Phase 1 — Capture + calibration (2–3 j)** : dxcam, outil de calibration
(aperçu + rectangles), profil résolution, export PNG des crops.

**Phase 2 — Perception (3–5 j)** : appel API vision, prompt structuré + JSON,
OCR du bandeau. Évaluation sur captures fixes et replays (vérité terrain
heroprotocol). C'est la phase à fort potentiel d'itération.

**Phase 3 — Cerveau (2–3 j)** : prompt coach, mémoire de partie, déclencheurs,
anti-répétition, sortie `{parler, texte}`.

**Phase 4 — Intégration live (1–2 j)** : boucle asyncio, file latest-wins,
TTS → Mumble, tests en vraie partie, réglage cadence/cooldowns.

**Phase 5 (optionnel)** : dataset replay annoté, détection d'événements par CV,
supervision (petite UI/console affichant l'état et ce que le coach voit).

Stack : Python (venv via uv, **Python 3.12** recommandé — les wheels dxcam/
numpy peuvent manquer sur 3.14), dxcam, openai (client), piper-tts ou kokoro,
pymumble, Pillow/opencv pour crops et upscale.

---

## 10. Questions à trancher avec le pote (API)

- Quel(s) modèle(s) vision disponible(s) ? Latence typique ? Taille d'image max ?
- Quotas / rate limits ?
- L'API expose-t-elle aussi `/v1/audio/speech` (TTS) ? (Sinon TTS local.)
- Disponibilité pendant les parties (il joue aussi ?).

## Sources clés

- Capture : kylefu.me « Python - Fast Screen Capture » (bench dxcam/mss/PIL),
  PyPI dxcam / BetterCam / rapidshot (benchmarks).
- Mumble : github.com/azlux/pymumble (+ API.md, example `talking_bot.py`),
  fork ~oopsbagel/pymumble (UDP chiffré, serveurs récents).
- TTS : benchmarks on-device (picovoice.ai, contracollective.com, micdrop.dev),
  rhasspy/piper#821 (comparaison FR Piper vs Kokoro), Kokoro voices (ff_siwis).
- Vision : format OpenAI-compatible (docs vLLM/mycellm/abliteration —
  `image_url` base64, tokens = h×w/784, ≤4 images/req).
- Données de jeu : github.com/Blizzard/heroprotocol, ebshimizu/hots-parser,
  HeroesReplay/HeroesReplay (spectate automatisé + capture écran),
  forum Blizzard (replay écrits seulement en fin de partie).
- Minimap par CV : arXiv 2606.26970 (Dota2-Vis), AAAI 2023 (LoL minimap
  detection, 6.4 ms/inférence).
