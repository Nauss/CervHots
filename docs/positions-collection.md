# Positions alliées — collecte et journal durable

La sélection `--collection positions` collecte **cœur + positions**, sans lire
les autres familles optionnelles. `--collection all` tente aussi les positions.
La CLI passive garde `core` par défaut ; `cerveau.playtest` sélectionne déjà
`positions` par défaut. Aucun mode ni lecteur live n'est activé par ce guide.

## Portée native multi-cartes

**Héros principaux alliés vivants, joueur local inclus, build 98348.**
Pas de positions ennemies, de clones ou de dernière position connue d'un mort.
L'acquisition accepte les **19 identifiants** de `hotstate/position_maps.py`,
vérifiés dans les scripts installés, en lisant les bornes de la simulation
active. Cela inclut DragonShire, BraxisHoldout, les autres cartes du catalogue
et l'identifiant exact `Warhead Junction` (avec espace).

La qualification est explicite : `map_validation=player_recipe` pour Volskaya,
`native_bounds_only` ailleurs. Cette deuxième valeur signifie que les gardes
natives ont réussi, **pas** qu'une recette joueur/calibration HUD a été effectuée
sur cette carte. Sources, liste exacte et preuves :
[POSITIONS-MULTICARTES.md](../etudes/rea/POSITIONS-MULTICARTES.md).
Une carte inconnue reste refusée (`carte_positions_non_prise_en_charge`) ; des
bornes incohérentes refusent `bornes_positions_incoherentes`, sans liste vide fictive.

Les contrôles de perspective, identité de partie, reçu in-process, âge et budget
WHOLE restent en place. Un paquet omettant un allié vivant est rejeté au
normaliseur, pas envoyé comme une couverture complète au Coach. Les modes
`core` et `talents` n'entrent pas dans le projecteur des positions.

## Utilisation

Préflight sans mémoire, réseau ou son :

```text
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --preflight --collection positions
```

Pour une session live **autorisée séparément**, ajouter `--collection positions`
au lancement de [collecte passive](passive-session.md#préparation-et-lancement).
Conserver les trois chemins absolus : identité privée existante, sortie neuve et
STOP neuf. La collecte passive n'appelle ni Coach/API, ni TTS/Mumble.
Ne pas redémarrer une session avant la fermeture vérifiée du lecteur précédent.
Le playtest affiche `positions_maps` et `positions_player_recipe_maps` séparément.
Son mode macro reste borné à Volskaya ; ce changement concerne l'acquisition,
pas l'extension des règles macro ou des autres familles.
Le nouveau mode `reactive`, décrit dans [playtest.md](playtest.md), peut annoncer
une infériorité numérique sans utiliser de coordonnées : ce contrat non spatial
ne qualifie pas les positions des autres cartes et n'affaiblit pas le mode libre.

## Données enregistrées

Chaque événement `observation` de `events.jsonl` inclut maintenant `positions`,
même sans appel du Coach. L'export de `cerveau.positions_journal` est partagé
avec `coach_input.coverage` : mêmes coordonnées, couverture et refus, sans
recopier un paquet mémoire brut.

| Champ sous `observation.positions` | Sens |
|---|---|
| `status` / `reason` | Normalisé, refusé, rejeté, non sélectionné ou inconnu ; code de refus fermé quand disponible. |
| `source` | `native_player` pour une source live au contexte natif reconnu ; ce label historique n'est pas une permission. |
| `source_mission_t_s` | Temps mission de l'échantillon, **pas** le chrono HUD. |
| `age_s` / `read_window_s` | Âge original à la normalisation et durée de lecture, non renouvelés à l'écriture. |
| `map_validation` | `player_recipe` ou `native_bounds_only` ; `null` si non disponible. |
| `allies_expected` / `allies_alive` | Couverture de l'équipe locale complète ; `null` si non établie. |
| `positions_acquired` | Nombre de coordonnées validées ; `null` si indisponibles. Zéro n'est valide que si tous les alliés sont morts. |
| `value` | `map_id`, `t`, `team`, `bounds`, `map_validation`, `heroes` ; `null` si indisponible. |
| `value.bounds` | Rectangle natif `[xmin,ymin,xmax,ymax]` relu dans l'acquisition, sans substitution des bornes Volskaya. |
| `value.heroes[]` | `slot`, `team`, `x`, `y`, `u`, `v` uniquement. |

`x/y` sont les coordonnées natives dans les bornes jouables observées. `u/v`
sont normalisées entre 0 et 1, avec `v=0` en haut. Elles doivent correspondre
aux mêmes `x/y` et aux bornes de la carte. Une équipe partielle, un doublon,
un ennemi, un mort, un âge invalide ou des coordonnées incohérentes n'est pas
exporté comme un échantillon valide. Aucun pseudo, identifiant de compte,
seed, pointeur, reçu ou secret n'est copié dans ce bloc.

Un refus n'hérite jamais des coordonnées du cycle précédent. Les coordonnées
stockées ne sont pas un paquet natif authentifié : les réinjecter ne leur donne
pas le statut CURRENT. Les rapports historiques existants n'affichent pas encore
ces coordonnées ; elles sont conservées dans le JSONL.

## Vérification hors ligne

```text
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_positions_journal.py -v
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_positions_multimap.py -v
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m unittest discover -s tests
```

Les tests exercent `NativeSource` → acquisition → normalisation → boucle passive
→ fichier JSONL avec un backend mémoire **SYNTHETIC**, sans ouvrir le jeu, appeler
une API externe ou diffuser du son. Ils couvrent les alliés morts, les valeurs
malformées, les refus, la sélection avant projection et la non-réutilisabilité
des données persistées. Ils ne constituent pas une nouvelle validation live.
