# P2 — positions des héros principaux : implémentation partielle, recette manquante

Statut : NON LIVRÉ. Aucun ajout à la liste `VALIDATED_MAPS` ; aucune position live
n'est actuellement publiée, même si un JSON entrant prétend être validé.
La poursuite de P2 est autorisée ; le besoin restant concerne une recette réelle
coordonnée, pas une nouvelle approbation générale d'implémentation.
Base vérifiée : main `3361e4efcf8ad8eb1ba8ac8b5fb1dc46196d86a7` (chrono livré).

## Code réellement exécuté

- `hotstate/positions.py` : lecteur borné, lecture seule, aucun appel du client.
- `hotstate/profiles/98348-positions.json` : empreintes et bornes structurelles.
- `hotstate/native.py` : lecture optionnelle ; refus => champ absent, jamais zéro.
- `cerveau/state.py` : seconde barrière typée et liste de publication indépendante
  des assertions du JSON ; rejet ennemi/mort/ambigu/périmé et nettoyage des extras.
- `cerveau/runner.py` : déplacement/disparition de positions annulent une consigne ;
  le seul changement d'horodatage d'un relevé identique ne l'annule pas.
- `etudes/rea/scripts/audit_positions.py` : audit exclusivement hors ligne, utilisé
  sur les trois captures Volskaya ; ses dix unités diagnostiques ne vont PAS au
  modèle. Aucun replay ne remplit l'observation native.

Les cas acceptés de la suite utilisent explicitement une liste de publication
ouverte par mock et de la mémoire SYNTHÉTIQUE. Ils ne constituent pas une recette
joueur. La liste réelle reste vide côté producteur ET consommateur.

## Source native établie pour le build 98348

Projet Ghidra existant ouvert seul avec `-readOnly -noanalysis`. Aucun changement
au client, injection ou invocation de native. Les adresses ci-dessous sont celles
de l'image de recherche ; la production utilise des RVA relatives à l'ASLR.

1. Déclaration Galaxy `UnitGetPosition`, index de dispatch 1477, cas RVA
   `0x2005065` : appel `7ff62dd503b0`.
2. Le getter appelle `7ff62c34bad0`, résolveur de tag d'unité déjà utilisé en P1.
   Source retenue : tag du héros principal `CPlayer+0x58`, PAS une énumération des
   unités possédées. Contrôle tag complet/génération et propriétaire `unit+0x44`.
3. Encodage global 14 obligatoire. Le getter lit le vecteur encodé à `unit+0x60`
   avec `7ff62c015500`. Il copie ce vecteur dans le point Galaxy retourné via
   `7ff62c0179a0`. Pas de nouveau « composant position » supposé : le chemin
   démontré est directement le vecteur du CUnit résolu.
4. Le décodeur emploie la table image RVA `0x32c1c90` (4096 DWORD), la clé pointée
   par RVA `0x3388ae0`, deux indices masqués 4095 et l'échange `0x55555555`.
   Les DWORD décodés sont interprétés comme fixed signés /4096.
5. `PointGetX` (1149 -> `7ff62dd645d0`) retourne le DWORD bas du vecteur du point ;
   `PointGetY` (1150 -> `7ff62dd64900`) le DWORD haut. Les usages installés dans
   NativeLib traitent ces résultats en fixed. Aucune coordonnée Z publiée ; le
   champ copié par le getter à +0x1c n'est pas ici revendiqué comme position Z.
6. `RegionPlayableMap` (1216 -> `7ff62ddd1000`) appelle
   `7ff62c67ac00(0x10)` : racine simulation décodée, région `(16+31)*16 = 0x2f0`.
   `7ff62dc1e290` convertit les quatre entiers en fixed par décalage de 12 bits.
   La racine est la même famille active que l'horloge mission, pas un scan de tas.

Les empreintes couvrent les plages .pdata des getters et du décodeur ; les deux
petits helpers sans entrée .pdata sont décodés jusqu'au RET. Ces mêmes empreintes
passent sur les trois images Volskaya et sur l'ancienne image Dragon, autre ASLR.
Les autres branches d'encodage ne sont ni implémentées ni acceptées.

## Repère et comparaison hors ligne : portée exacte

Trois dumps Volskaya : trente héros principaux lus, trente couples XY dans le
rectangle natif `[4,4,244,196]`. Deux groupes près des bases deviennent des groupes
centraux haut/milieu/bas. Les PNG effectivement ouverts `00069`, `00137`, `00202`
montrent qualitativement cette répartition. X croît vers la droite et Y vers le
haut dans ce rapprochement. La normalisation candidate du rectangle jouable est :

    u = (x - xmin) / (xmax - xmin)
    v = 1 - (y - ymin) / (ymax - ymin)

Ce n'est PAS encore une calibration du rectangle de rendu de la minicarte : le
fond décoratif, le masque et les marges ne prouvent pas la transformation UI.
Aucun écart pixel maximal ou moyen ne peut être honnêtement annoncé. Aucun seuil
d'erreur de recette n'est réputé satisfait ; normalisation écran non validée.

| Capture | Mission image | Fenêtre roulante murale | PNG chevauchant cette fenêtre |
|---|---:|---:|---|
| Volskaya 008 | 8.375 s | 2.533 s | 66 à 72 |
| Volskaya 037 | 37.375 s | 2.590 s | 135 à 140 |
| Volskaya 065 | 65.6875 s | 2.889 s | 199 à 205 |

L'horloge de l'image ne date pas les CUnit lus plus tard dans le tas. Une image
chevauchant la fenêtre ne rend PAS le dump synchrone. Les premières images de la
session étaient du chargement. Les autres PNG ouverts (`00134`, `00198`) servent
seulement au contexte qualitatif et ne sont pas des paires de validation.

Toutes ces captures sont observateur omniscient, `local_player=null`. Aucun bot
n'est renommé joueur humain. Elles ne peuvent justifier de publication alliée
pour une perspective locale. Les trois captures ont tous leurs héros vivants :
mort/réapparition, remplacement et propriétaire sont testés synthétiquement,
PAS recoupés en réel pour ce lot.

Dragon : les empreintes passent dans `live-a`, mission 1163.5625 s ; la région
structurelle vaut `[8,24,240,182]`, différente de Volskaya. Aucun PNG synchrone
applicable : Dragon n'est pas ajouté au profil de carte ni déclaré validé.
Braxis ne remplace pas Dragon ; un essai structurel préliminaire y a refusé un tag
invalide au chargement. Aucun support Braxis n'a été ajouté.

## Contrat et refus

Le paquet interne envisagé contient status, map_id, bornes, mission_t_s,
read_window_s, identité anonyme de partie/local/équipe et heroes (id, slug, x,y,u,v).
Le modèle ne reçoit que t, map_id et les coordonnées typées des héros alliés
vivants. Aucun nom, tag, pointeur, compte, équipe forcée ou position ennemie.
Les diagnostics `offline_non_atomic` sont toujours omis par le normaliseur.

Lecture réordonnée/répétée exactement : racines, profil/code, clés, CPlayer,
tag/génération, propriétaire, vie, vecteur et bornes. Changement => refus sans
retry ni ancienne position de secours. Budget mur et mission 125 ms ; aucune
extrapolation. Cette double lecture est conservatrice, PAS un verrou atomique ;
un aller-retour ABA entre deux prélèvements n'est pas exclu. Pas de preuve de
capacité/débit réel avant la recette ciblée. Un timer mort/position inconnu ne
devient jamais zéro. La fenêtre globale P0/P1 reste indépendante (1 s).

Les tests couvrent mouvement, axes, normalisation, signed fixed, table de clés
non uniforme, ASLR, bornes/profil/carte inconnus, mort/réapparition synthétique,
remplacement de génération et de slot, compagnon non sélectionné, propriétaire,
identité absente/ambiguë, lecture déchirée, fenêtre, confidentialité et fraîcheur.
Le chrono déjà livré, mission/replay, seuil 0.75, silence et opt-ins sont conservés.
Aucun appel coach/TTS/Mumble, nouvelle partie ou prise de premier plan dans ce run.

## Recette ciblée indispensable avant intégration/livraison

Coordonner une partie privée Volskaya avec un VRAI joueur local, identité et équipe
résolues par le contexte existant ; PNG minicarte + lectures natives brèves bornées
avant/après chaque image. Déplacer le héros dans deux directions indépendantes
et repérer plusieurs positions stables pour mesurer axes, limites, marges et
l'erreur de projection ; capturer mort/réapparition et changement effectif de
référence principale si disponible. Garder les lectures déchirées/ambiguës refusées.
Un contrôle à identité locale absente doit laisser toutes les positions absentes.
Une recette observateur ne remplace pas cette perspective.

Revue indépendante du WIP fermé (`deleg_637bcf90`) : aucun défaut bloquant dans
le chemin actuellement activé, 120 tests exécutés sur chacun des deux Python.
Ce verdict n'est PAS une revue de livraison ni une autorisation d'ouvrir la liste.
Après ajout du test de mutation du contexte fourni : 121 tests passent sur
Python système et Python du coach ; `git diff --check` passe.
Trois obligations supplémentaires à vérifier avant cette ouverture :

- Le contrôle final de `_context` compare le dictionnaire Python fourni ; il
  détecte sa mutation, PAS une nouvelle identité native active. Établir la liaison
  au contexte actif et tester le changement partie/local/équipe pendant la lecture
  (ne pas présenter le seul hash initData comme une racine native démontrée).
- La fraîcheur du normaliseur est relative à la mission dans le même paquet ;
  une pause ou un paquet réutilisé n'établit pas une fraîcheur murale. Vérifier la
  provenance/acquisition et le contrôle d'âge de la chaîne réelle, sans prétendre
  qu'un horodatage mission seul valide des données rejouées.
- La relecture exacte inclut l'horloge initiale : un tick peut refuser un relevé
  de moins de 125 ms. Mesurer le taux réel d'acceptation ; ne pas masquer les refus
  ou affaiblir les gardes uniquement pour réussir la recette.

Après cette preuve : ajuster si nécessaire la normalisation, compléter les
empreintes/fixtures et l'audit temporel, revue indépendante finale, ouvrir seulement
la carte réellement validée, tests des deux Python, commit/intégration/push main
et vérification du hash distant. Ne pas clore cette carte sur ce travail partiel
et ne pas débloquer le lot visibilité suivant avant livraison effective.
