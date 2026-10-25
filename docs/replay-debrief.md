# Débrief replay local, sans service ni audio

Depuis la racine du dépôt, Python 3.12 ou 3.14 avec `hotstate/requirements.txt`
installé (`heroprotocol`, qui apporte `mpyq`). L'exécution ne télécharge rien,
ne charge pas `.env`, ne construit ni Coach ni client API, n'importe aucun
backend mémoire/audio et n'ouvre aucun client GUI. Ni `kb.db` ni modèle requis.

```bash
python -B -m cerveau.replay_debrief \
  --replay "C:/archives/partie.StormReplay" \
  --team 0 --perspective player-team --at 60
```

**Entrée unique explicite**, fichier local stable de 32 MiB maximum. Aucun scan
du dossier personnel. `--team` vaut l'indice replay **0 ou 1**, pas une couleur
HUD ; `player-team` choisit une perspective d'équipe **hypothétique**, pas un
joueur local authentifié. Pas de mode observateur/omniscient, de détection de
joueur, de remplacement de carte ou de composition. `--at` est le temps de
**mission**, préparation incluse, pas le chrono HUD. Temps fini et positif ou nul,
limité à la durée décodée et à 21600 s ; durée inconnue = refus.

## Sorties

- Par défaut : un seul JSON minimisé sur stdout, contenant `debrief_fr` lisible,
  `state` (projection existante sans aucune coordonnée), `provenance`, `coverage`,
  `map` et `knowledge` (rappel statique du briefing KB, pas observation).
- `--format text` : uniquement le même débrief français, sans JSON.
- Aucune écriture par la commande. Pour conserver les deux, rediriger le JSON
  vers un **nouveau fichier distinct du replay**, puis lire `debrief_fr` dans le
  JSON, ou exécuter à nouveau avec `--format text`. Ne jamais rediriger sur la
  source : le shell la tronquerait avant le démarrage de Python.
- Codes : **0** débrief produit (éventuellement partiel/non certifié) ; **1**
  fichier/décodage/projection/fidélité refusés, motif fermé JSON sur stderr,
  stdout vide ; **2** arguments absents/invalides (aide argparse). Les erreurs
  de décodeur ne recopient ni chemin privé, ni pseudo, ni exception brute.

Composition et faits connus restent utiles même avec des inconnues : listes de
héros reconnus par équipe, dernier niveau et dernier état de vie reconnus,
annonces publiques passées autorisées. Ce n'est ni un dump du diagnostic
`--diagnose` ni un second projecteur : la commande appelle
`hotstate.extract.extract` puis `cerveau.replay.project`. Le briefing réutilise
`kb.briefing.public_facts`, sans SQLite ni conseil généré.

## Protocole exact ou shim : choix explicite

Par défaut, **refus** si `hotstate.extract` a dû utiliser un protocole de repli.
Pour une inspection historique **indicative, non certifiée**, ajouter :

```bash
python -B -m cerveau.replay_debrief \
  --replay "C:/archives/partie.StormReplay" \
  --team 0 --perspective player-team --at 60 --allow-protocol-shim
```

Le JSON expose le build, le protocole effectivement chargé, `protocol_shim` et
`fidelity=unverified_protocol_shim` ; le texte porte l'avertissement SHIM. Cette
option n'invente aucun champ et ne valide pas le schéma du build. **Si la fidélité
exacte est nécessaire, ne pas utiliser cette option** : le refus est le résultat
correct. Un protocole installé ne prouve pas non plus l'exactitude du replay
ni l'état natif/HUD. Le SHA256 avant/après détecte une modification visible de
l'entrée ; il n'est pas un verrou atomique contre une substitution concurrente.
Conserver l'entrée stable durant la commande.

## Limites de perspective et d'inconnues

- Aucun nom, compte, chat, résultat final, métrique finale, événement futur ou
  XY (même allié) exporté. Seuls les événements projetés à `t <= --at` restent.
- Les héros et cartes passent les **catalogues existants**, non élargis ici.
  Une carte inconnue reste `map=null`, sans rappel KB ; un héros non reconnu
  est omis et la composition est explicitement **incomplète**. La taille du
  roster et le nombre de héros reconnus sont exposés, pas les identités omises.
- Niveau/vie sont les derniers événements reconnus, pas une mesure continue
  ni des PV ; `null` veut dire inconnu, jamais zéro/vivant par défaut. Un cycle
  de vie incomplet/ambigu reste inconnu selon les refus du projecteur existant.
- Au plus les **24 derniers événements projetés** : les annonces publiques ne
  forment ni un historique exhaustif ni un état actuel de l'objectif.
  `coverage.objective_state=null`, même si une annonce passée existe.
- Le rappel KB décrit la mécanique statique d'une carte reconnue. Pas de prochain
  objectif extrapolé, compte à rebours, conseil tactique inventé ou nouvelle
  allowlist. Une carte reconnue dans le replay n'autorise aucun lecteur natif.
- Replay historique uniquement : aucune preuve live, HUD, BraxisHoldout natif,
  CURRENT, partie privée/neuf IA, ni lien avec les captures004/006 du lot14.

## Recette exercée (corpus déjà autorisé, lecture seule)

Depuis la racine du dépôt, chemins Bash Windows natifs :

```bash
python -B -m cerveau.replay_debrief \
  --replay "C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot2/operator/PRIVATE/causal-001.StormReplay" \
  --team 0 --perspective player-team --at 60 --allow-protocol-shim --format text
```

Sur ce corpus, build98348/protocol91756 SHIM, 5 héros reconnus sur10 ; Jaina,
Ana, Yrel côté0, Genji et Medivh côté1, derniers niveaux observés1, vies inconnues.
Le rappel KB des balises reste **statique**, l'objectif observé inconnu. Sur
`lot1/operator-recovery/PRIVATE/recipe-001.StormReplay`, 8 héros reconnus sur10,
carte inconnue (`Garden of Terror Classic` n'est pas ajoutée au catalogue).
Ces sorties partielles sont des débriefs historiques, pas une recette native.

## Tests sans audio ni réseau

```bash
python -B -m unittest tests.test_replay_debrief -v
# Prérequis de deux tests historiques de découverte : répertoire out/ existant.
mkdir -p out
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -v
# Même entrée réelle, accès réseau/Coach/API/audio/mémoire et scan personnel interdits :
python -B tests/helpers/replay_debrief_offline.py \
  --replay "C:/archives/partie.StormReplay" \
  --team 0 --perspective player-team --at 60 --allow-protocol-shim
```

Le helper exécute le vrai module et le vrai décodeur ; seules les opérations
interdites sont remplacées par des exceptions. Les fixtures unitaires sont
explicitement synthétiques. Les tests existants de voix utilisent des doubles,
pas un périphérique audio. Logs RED/GREEN, exécutions réelles 3.12/3.14 et hashes
sont conservés dans `out/weekend/2026-10-24/lot15/` ; intégration main et revue
indépendante restent des étapes séparées de l'implémentation.
