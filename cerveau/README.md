# cerveau — le coach relié à Groco

`hotstate → état observé → briefing kb → Groco → décision → Piper/Kokoro → Mumble`

Zéro dépendance supplémentaire pour le cerveau. Utiliser l'interpréteur de
`tts/.venv` pour générer un WAV ou diffuser dans Mumble. **Le mode par défaut
écrit du JSON dans la console : il ne charge ni TTS, ni Mumble, ni lecteur mémoire.**

## Configuration

Une seule source de clés : `.env` racine, ignoré par Git. Ne pas recopier le token
ailleurs. Arguments > variables d'environnement > `.env`.

- `GROCO_API_URL`, `GROCO_API_TOKEN` : configuration du client existant.
- `GROCO_MODEL` : identifiant exact renvoyé par `python -m cerveau --check`, au
  format `compte/modèle`. Configuration locale validée : `claude-azqc/sonnet`.
- `GROCO_REASONING_EFFORT` : optionnel ; aucun effort imposé par défaut.
- `MUMBLE_HOST`, `MUMBLE_PORT`, `MUMBLE_USER`, `MUMBLE_PASSWORD`, `MUMBLE_CHANNEL` :
  configuration existante, lue uniquement pour la diffusion demandée.

La gateway n'accepte ni `response_format`, ni `max_tokens`, ni contenu multimodal
dans son schéma actuel. Le format JSON est demandé au modèle puis **validé
localement**, il n'est pas garanti par l'API.

## Exécuter

Depuis la racine du dépôt :

```bash
# Découverte, sans chat ni son
python -m cerveau --check

# Replay réel déjà extrait par hotstate/extract.py ; aucune lecture du futur
python -m cerveau --state partie.hotstate.json --at 73.5 --team 0

# Même parcours avec synthèse locale, fichier seulement, AUCUNE lecture sonore
# Aucun fichier n'est écrit si le cerveau choisit le silence.
tts/.venv/Scripts/python -m cerveau --state partie.hotstate.json --at 73.5 --team 0 --wav out/coach.wav

# Lire un dump mémoire existant, sans toucher au processus du jeu
python -m cerveau --dump partie.heap.bin partie.heap.json --map cursed-hollow --allies Jaina,Muradin,Valla,Anduin,Sonya --enemies Diablo,Li-Ming,Raynor,Rehgar,Dehaka

# Consommer le JSON d'un producteur live qui le réactualise en continu
python -m cerveau --state hotstate-live.json --watch --map cursed-hollow
```

Un seul cycle par défaut ; `--watch` active la boucle toutes les 25 secondes.
`--team` désigne l'équipe alliée du replay (0 par défaut, 1 si nécessaire).
La carte et les compositions du replay sont récupérées automatiquement ; les
options `--map`, `--allies`, `--enemies` peuvent les préciser pour la mémoire.
`--at` est obligatoire pour les replays et interdit avec `--watch`.

### Diffusion sonore et lecture mémoire : deux activations distinctes

- `--mumble` **active réellement la voix dans le canal**. Ne l'utiliser qu'après
  l'accord de la personne qui écoute, sur son action manuelle ; jamais en test
  automatique. Ajouter ce drapeau à une commande avec l'interpréteur `tts/.venv`.
- `--live` remplace `--state`/`--dump` et ouvre le processus HotS en lecture seule
  (PID optionnel par `--pid`). Le risque ToS/Warden reste celui de la lecture
  mémoire : décision explicite du propriétaire requise avant de la lancer.
- Aucun de ces modes n'est activé implicitement par l'autre.
- Ctrl+C arrête la boucle et libère le bot et le handle du processus.

## Décision et garde-fous

Réponse console : `parler`, `priorite` (1–3), `texte`, `confiance`, `style`,
`sujet`, `raison`. Les erreurs API sont visibles (`erreur_api_404`, etc.).

- Une priorité, une phrase de **25 mots / 240 caractères maximum**.
- Seuil de confiance 0,75 ; il s'agit d'une **auto-évaluation du modèle**, pas
  d'une probabilité calibrée. Réglage explicite : `--min-confidence`.
- JSON invalide, texte trop long, faible confiance ou API en échec → silence.
- Historique borné à huit conseils réellement livrés ; blocage des répétitions.
- Cooldown 15 s après livraison, pas après simple génération.
- Un seul appel en vol, aucune file d'attente. Péremption 20 s ; l'état est relu
  après le LLM, après le TTS et avant l'envoi audio. Un changement tactique annule
  le conseil. L'horloge murale et les globes ne l'invalident pas à eux seuls.
- Si des humains parlent, attendre au plus 3 s puis abandonner ; diffusion
  surveillée et bornée, y compris en cas de déconnexion Mumble.
- Le replay est tronqué à `--at` : aucun score final, résultat de victoire,
  événement futur ou chat envoyé au modèle. Les pseudonymes sont remplacés par
  les héros ; les positions des snapshots sont ramenées à l'échelle de la grille.

## Limite de la source live actuelle

`hotstate/reader.py` fournit des **compteurs globaux**, pas encore les niveaux,
PV, positions et morts par joueur en direct. Seuls `deaths_total`,
`respawns_total` et `globes_total` sont retenus parmi les triggers validés.
L'horodatage système n'est jamais présenté comme temps de jeu. Les autres
triggers, encore expérimentaux, ne passent pas dans le prompt.

Ces données seules ne justifient pas un conseil tactique : le coach doit alors
se taire. Les replays, eux, apportent composition, niveaux et états de vie
observés, événements et positions. Le branchement ne crée pas les données que
le lecteur mémoire n'expose pas encore.

## Vérifier sans produire de son

```bash
python -m unittest discover -s tests -v
uvx ruff check cerveau tests grocoapi hotstate/reader.py
```

Les tests utilisent des données synthétiques explicitement identifiées et un
serveur HTTP local ; ils n'appellent pas Groco et ne lisent pas le jeu. Le chemin
réel replay → API Groco → WAV a aussi été exécuté : voir
`etudes/cerveau/ETUDE.md`. La diffusion Mumble de ce nouveau parcours reste à
valider après autorisation, les tests d'adaptateur étant faits sans connexion.
