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

`hotstate/reader.py` conserve trois compteurs globaux validés. Avec `--player NOM`,
le contexte initData et le lecteur natif build 98348 ajoutent l'horloge observée,
les dix héros, niveaux et états de vie, ainsi que PV/ressources alliés.
`respawn_s` est présent pour un héros mort si son timer natif est lisible ;
Li-Ming et Qhira ont été vérifiées en partie, puis exactement contre le tracker.
Les positions/visibilité, objectifs,
camps, structures et capacités restent inconnus en live.

L'état natif a été vérifié contre le replay de sa propre capture : dix choix,
équipes, niveaux et états de vie concordants à 1163,5625 secondes. Un vrai appel
Groco a reçu ces champs anonymisés. Sa phrase a été rejetée par le seuil inchangé
de 0,75 (confiance renvoyée : 0,55) : transfert réussi ne veut pas dire parole forcée.
Rapports : `out/rea-collection/validation/report.json` et
`out/rea-collection/live-validation/report.json` ; aucun son joué.
La CLI finale sur capture a aussi obtenu un conseil accepté à 0,85 avec le
seuil par défaut 0,75, sans `--wav` ni `--mumble`.
`clock_kind=mission` inclut la préparation : le cerveau et la KB ne l'assimilent
pas au chrono HUD ni à un état d'objectif observé.

Sans profil/contexte valide, le repli ne crée ni niveaux ni état de vie : les
anciens compteurs seuls ne suffisent généralement pas à un conseil tactique.
Les variations continues de PV/ressources et de countdown n'affament pas le coach :
la fraîcheur suit leurs bandes tactiques, mais annule toujours sur changement de
niveau, de vie/mort, d'identité de partie ou de bande de santé critique.

### Contexte mémoire et enrichissement natif

Ajouter `--player NOM` à `--live` ou `--dump` active la recherche initData.
L'équipe locale détectée remplace alors le défaut 0 ; `--team 0/1` reste une
surcharge explicite. `local_player` ne contient que slot, équipe et héros,
jamais le pseudo. `composition_complete=false` signifie que les listes de
compositions sont partielles, pas que les autres joueurs sont absents/morts.
La carte est récupérée dans le cache de map correspondant. Le contexte est
recherché dans le même scan mémoire que les compteurs ; il n'ajoute ni chrono
supposé, ni niveau de maîtrise recyclé, ni état de vie inventé.

Validé sur la capture IA : Dragon Shire, Ragnaros, équipe 1. Les neuf héros IA
absents d'initData sont récupérés ensuite dans les objets natifs `CPlayer`,
jamais depuis le replay. `composition_complete=true` indique les dix choix connus.
Voir `hotstate/README.md` pour les limites de la sonde et du profil.

`--dump HEAP_BIN HEAP_JSON --image MODULE_BIN --player NOM` rejoue le même
lecteur sur une capture privée. Le module et le tas doivent venir de la même
session. En live la base du module vient de PSAPI, jamais de l'ImageBase préféré.

## Test live diagnostic (distinct du coach tactique)

Après accord explicite pour la lecture mémoire et déclenchement manuel de la
voix, une partie **contre des IA chargée sur la carte** peut servir à vérifier :

```bash
tts/.venv/Scripts/python -m cerveau.diagnostic --live --mumble --cycles 6 --interval 30
```

Le serveur de test par défaut est `127.0.0.1:64739`, canal `Root`, bot
`Coach-Live-Test`. Le client humain doit être dans ce canal et non assourdi.
Ce parcours n'est **pas une stratégie dégradée** : il transmet uniquement les
trois compteurs validés présents, puis demande à Groco de sélectionner l'une
de deux formulations factuelles autorisées. Une réponse différente est rejetée.
Un compteur absent reste inconnu, pas zéro. Aucun seuil du coach n'est abaissé.

La session est bornée (6 cycles par défaut, 12 maximum), sans accès mémoire à
l'import ni avec `--help`. Les relevés périmés, une erreur API ou une demande
d'arrêt n'envoient pas de son. La lecture n'est pas relancée pour fabriquer une
horloge de jeu ; la phrase précise qu'il s'agit des totaux globaux **au relevé**.
Le TTS est effectué une seule fois et son PCM passe par l'adaptateur Mumble
existant, avec attente de silence, contrôle de fraîcheur et borne de diffusion.

Journaux sans clés/headers dans `out/test-live/session-*/events.jsonl` :
`observation`, `api_requete` (messages effectivement passés au client),
`api_reponse`, `phrase_validee`, `tts_termine`, `mumble_envoye` ou raison d'échec.
`out/test-live/current.json` référence la session et son résultat. Une seule
session simultanée est permise (`RUNNING`). Pour arrêter : Ctrl+C ou création
du fichier `out/test-live/STOP`. L'arrêt attend la fin du scan/appel déjà en
cours ; aucun nouveau PCM n'est envoyé ensuite (un audio déjà en vol peut finir).
Retirer un ancien `STOP` avant un nouvel essai, seulement après vérification
qu'aucune session n'est active. Les handles et le bot sont libérés à la sortie.

Sans `--mumble`, le diagnostic reste silencieux ; `--wav-dir chemin` permet
une synthèse fichier uniquement. La confirmation de l'envoi Mumble et la
confirmation humaine d'écoute sont deux validations distinctes.

## Vérifier sans produire de son

```bash
python -m unittest discover -s tests -v
uvx ruff check cerveau tests grocoapi hotstate/reader.py
```

Les tests utilisent des données synthétiques explicitement identifiées et un
serveur HTTP local ; ils n'appellent pas Groco et ne lisent pas le jeu. Le chemin
réel replay → API Groco → WAV a aussi été exécuté : voir
`etudes/cerveau/ETUDE.md`. Le 17/10/2026, le cycle replay → Groco → Piper →
Mumble a été exécuté et l'écoute complète confirmée par le propriétaire.
Le mode diagnostic a aussi passé un appel Groco réel et une synthèse WAV,
sans son, sur un relevé historique explicitement identifié comme replay.
Trois séries live de six cycles ont ensuite atteint l'envoi Mumble sans erreur.
Cela valide le circuit technique des compteurs, pas un coaching tactique complet.
L'enrichissement de contexte a été validé séparément sur la capture mémoire
prise pendant cette partie, recoupée avec son replay ; la capture n'est jamais
présentée comme une observation live actuelle.
