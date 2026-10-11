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

## État

Étude de faisabilité validée (oct. 2026). Prochaine étape : le POC parole
(bot Mumble + TTS).
