# Positions natives multi-cartes — build 98348

## Acquisition ouverte, qualification terrain distinguée

`hotstate.positions.AlliedPositions.read()` utilise maintenant la région jouable
**de la simulation active** sur les 19 identifiants publics de
`hotstate/position_maps.py`. Ce n'est pas l'ajout de bornes Volskaya aux autres
cartes : les quatre bornes sont lues dans la région native et incluses dans la
relecture de cohérence à chaque acquisition.

Deux niveaux sont transmis jusque dans le Coach et le journal :

- `player_recipe` : Volskaya, recette joueur historique de `P2-POSITIONS.md` ;
- `native_bounds_only` : les autres cartes, acquisition native contrôlée mais
  **sans nouvelle recette joueur ni calibration minimap indépendante**.

`VALIDATED_MAPS` reste limité à Volskaya. `SUPPORTED_MAPS` est le catalogue des
identifiants reconnus, pas une liste de recettes mesurées. Le statut producteur
`validated` atteste les gardes d'acquisition ; il ne doit pas effacer la nuance
`map_validation`. Les autres familles gardent leurs propres gardes par carte.
Le mode macro du playtest reste limité à Volskaya ; le mode libre existant peut
recevoir les positions et leur qualification, avec revalidation spatiale inchangée.

## Source et contrôles

La chaîne de décodage est celle déjà documentée : Galaxy `UnitGetPosition`,
`SUnit + 0x60`, décodeur 14, coordonnées fixes /4096 ; `RegionPlayableMap` fournit
la région rectangulaire native de la simulation. Aucune fonction du jeu n'est
appelée. Les empreintes PE/code du profil `98348-positions.json`, le CPlayer,
les handles/générations/propriétaires et l'identité locale restent vérifiés.

La région doit contenir quatre entiers avec `-256 <= xmin < xmax <= 512` et
`-256 <= ymin < ymax <= 512`. Volskaya conserve en plus sa comparaison exacte
aux bornes mesurées `[4,4,244,196]`. Aucune borne fixe non mesurée n'est inventée
pour une autre carte. Chaque coordonnée doit appartenir à la région observée.

Seuls les héros principaux alliés vivants sont lus ; les coordonnées ennemies
ne sont pas demandées. Équipe complète 5v5, perspective joueur humain, exclusion
des captures/replays comme source live, relecture exacte, reçus du même processus,
âge maximal 1 s et budget WHOLE 125 ms restent obligatoires. Une référence unité
invalide, un rectangle incohérent ou une lecture déchirée reste un refus.

Les paquets normalisés et le journal conservent désormais `bounds` et
`map_validation`. Le normaliseur et l'export contrôlent ces valeurs et la
correspondance x/y/u/v. Elles participent à la clé tactique : un changement de
région invalide aussi un conseil spatial préparé précédemment.

## Catalogue réellement identifié sur disque

[positions-map-sources.json](positions-map-sources.json) conserve les empreintes
SHA-256 des scripts, les noms de 22 archives de carte et leurs 19 identifiants
exacts. Inventaire : 67 archives `.s2ma` présentes, dont 4 illisibles ; l'absence
de script de carte dans une archive de dépendance n'est pas une carte manquante.
Tous les 22 scripts identifiés ont été résolus avec le vrai `map_from_cache()`.
Le catalogue de code correspond exactement à l'ensemble des identifiants trouvés.
Ces empreintes prouvent l'origine des identifiants, pas une validation de positions.

**Correction nécessaire du résolveur :** l'identifiant source de Menace nucléaire
est `Warhead Junction`, avec un espace. L'ancien motif `[A-Za-z0-9_]+` ne pouvait
pas le lire. Le nouveau motif accepte les espaces internes simples et préserve
le token exact ; il ne transforme pas cet identifiant en `WarheadJunction` et ne
corrige pas les espaces de début/fin, doubles espaces ou retours à la ligne.

## Preuves exercées et limites

### SYNTHETIC, pas du terrain

`tests/test_positions_multimap.py` exerce les 19 cartes sur le vrai
`read_current`/normaliseur/journal, avec rectangles **délibérément synthétiques**,
sans patch de l'allowlist des recettes. Contrôles : équipe alliée exacte, absence
de lecture x/y ennemie, autres familles non sélectionnées, budgets, âge, refus
sur rectangle incohérent, relecture déchirée, mauvais contexte et tentative de
promouvoir artificiellement une carte en `player_recipe`.

Un test passe aussi par le vrai `NativeSource`, la boucle passive et le JSONL,
puis les lecteurs historiques, sur `BraxisHoldout` synthétique. L'identifiant
est conservé jusqu'au rapport, sans inventer une validation HUD. Le préflight
énumère séparément les cartes d'acquisition et les recettes joueur. Les replays
exacts continuent de comparer toutes les lectures/horloges/coordonnées/refus ;
seule la nouvelle métadonnée de qualification est vérifiée séparément.

### Captures historiques réelles, pas du live actuel

Sept anciens couples module/tas ont été examinés en lecture seule. Leur carte
a été identifiée depuis les handles de cache de l'application capturée et le
script désigné, **pas depuis le nom du dossier** :

| Capture locale ignorée par Git | Résultat |
|---|---|
| `out/recon-live/live-a` | DragonShire, bornes `[8,24,240,182]`, 10 positions structurelles |
| `out/autonomous-ia/2026-10-18/volskaya/mission-008`, `037`, `065` | Volskaya, bornes `[4,4,244,196]`, 10 positions structurelles chacune |
| `out/autonomous-ia/2026-10-18/braxis/mission-037`, `065` | **BraxisOutpost**, bornes `[2,64,246,162]`, 10 positions structurelles chacune |
| `out/autonomous-ia/2026-10-18/braxis/mission-008` | Refus conservé : `reference_unite_native_invalide` |

Bilan : six lectures structurelles réussies, une refusée. Le contrôle exigeant
sept succès est donc resté en échec ; aucune garde n'a été levée pour le faire
passer. Le dossier nommé `braxis` ne prouve **pas** BraxisHoldout. Les lectures
structurelles inspectent les dix unités dans un dump privé ; cela n'ouvre pas
les positions ennemies dans le produit joueur. Aucun reçu CURRENT n'est émis.

Les dumps sont roulants et non atomiques. Cette vérification confirme la chaîne
native et plusieurs rectangles réels ; elle ne garantit ni le taux de refus,
ni la précision minimap, ni la pertinence des conseils sur les 19 cartes.
Aucun nouveau match, lecteur de processus, appel API externe ou son n'a été lancé.
