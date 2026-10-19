# P2 — camps et structures Volskaya : diagnostic non livré

Ce document ne déclare PAS le lot 5 validé ni publié. Le producteur public reste
fermé, `VALIDATED_MAPS=()`. Le branchement cerveau candidat ne peut donc pas
émettre ces données hors du collecteur de diagnostic explicitement opt-in.

## Source native et périmètre réel

Build strict 98348 uniquement. Profil `98348-battlefield.json` : empreintes du
résolveur natif, type d'unité/catalogue, VM et quinze fonctions Galaxy actives.
Racine des globaux VM `module+0x3D0C920`, contrôles du tableau actif et des noms,
indices, bornes et bytecodes. Aucune recherche d'occurrence de nom dans le tas.
Les opérandes indexées du VM utilisent un stride ushort à +3, un offset 24-bit
à +5 : 780 octets par camp, 1065 par ville ; pas des offsets HUD constants.

Camps : cinq entrées, types défenseur/mercenaire 5,5,6,6,10 ; balises typées et
résolues par tag entier, propriétaire courant et génération. Naissance et
respawn sont des timers distincts avec registre, type19, génération, propriétaire
et contrôle des champs. Le nom officiel et les défenseurs du type6 restent à
recouper dans les sources de configuration installées. Les trois anciens dumps
ne prouvent aucune transition live ni simultanéité module/tas.

Structures : douze villes, tous les éléments enregistrés sont parcourus ;
recensement complémentaire borné du tableau actif d'unités pour cores, tours
isolées et murs non enregistrés. Le type vient du CDataUnit actif puis de son
index dans le catalogue, jamais d'une constante d'index ou d'une étiquette replay.
Les catégories reconnues explicitement sont core, fort, keep, fontaine, tour,
ruine de tour, porte et variantes de murs. Les références absentes/recyclées
restent inconnues ; `TownCannonTowerDead` est une transformation de type distincte
de la disparition ultérieure du corps. Les états sont encore des diagnostics
privés, PAS des données publiques au coach, même pour une structure ennemie.
Le catalogue exhaustif de la carte n'est pas encore déclaré couvert.

## Confidentialité et sémantique

Les scripts GameLib/MapMechanicsLib montrent une diffusion UI de minuterie et
capture passée ; cela ne prouve pas que Idle/Busy, les défenseurs ou les PV sont
visibles sous brouillard. `lv_capturingPlayer` désigne un participant crédité de
la capture passée, pas un ennemi actuellement en train de combattre.
Dead=2 inclut le préspawn. Paused=3 peut signifier défenseurs vaincus/balise ouverte
avant récompense, pas pause de la partie. HibernatingReadyToRespawn n'est pas prêt.
Ces codes restent privés en attendant une politique prouvée par recette.
Aucun XY, ressource, talent ou cooldown ennemi n'est ajouté au payload. Le
candidat PV ne concerne que des structures du catalogue statique confirmé,
CURRENT réellement vrai et unité vivante ; les octets PV ne sont pas lus quand
la visibilité est fausse/inconnue. Cela ne donne aucune permission aux héros.

## Collecteur de recherche

`etudes/rea/scripts/capture_battlefield.py` : préflight sans processus, commande
live réservée à l'opérateur assistant autorisé, durée <=300s, intervalle >=0.25s,
fichier neuf sous out/ ignoré, zéro GUI/pilotage/API/son. Capture avant/PNG/après,
traces ordonnées exactes et rejeu strict. Gel du commit et empreintes de toutes
les sources natives/profils plus collecteur. Le tableau des unités est borné à
1024 slots ; seules les lectures ciblées tag/type/flags/propriétaire sont faites,
sans XY/vitales/composants, et seuls les types de structures retenus sont
retournés. Budget trace inchangé : 8192
lectures, 1Mio par tentative, toute saturation est un refus.

L'égalité du read-set garde racines et champs métier. Le compteur mission est
bracketté séparément (0<=delta<=125ms), pas exigé égal ; sa racine encodée est
recontrôlée. Fraîcheur monotone indépendante <=125ms. Les timers et les en-têtes
qui changent entre les lectures produisent un refus conservateur ; la capture
n'est pas un verrou atomique et n'exclut pas ABA.

## Vérifications avant recette

TDD : tests initiaux échouaient faute de module ; après implémentation, tests
synthétiques de générations, corruption, type, registre, fermeture publication,
minuterie inconnue et préspawn, capture/rejeu/refus/bornes. Test de charge census
1024 slots sans XY/PV et test d'un tick autorisé conservant la racine.
Exécution hors ligne des trois dumps Volskaya : cinq camps et 83 entrées
structurelles dans les villes ; le recensement complémentaire de mission065
retourne 90 structures et zéro slot de type non résolu. Ceci est un résultat de
lecture non atomique, pas une population simultanée certifiée.

Restent obligatoires : recette réelle joueur+9IA, références carte/catalogue
indépendantes, capture/respawn/destruction/remplacement et brouillard, politique
publique, normaliseur et vrai pipeline, revue finale indépendante et livraison
main/remote. Un inventaire ou ce diagnostic ne les remplace pas.

## Diagnostic joueur 12, révision 1 et correctif borné

La courte capture réelle du candidat a1e5aee a produit 5 images/10 tentatives,
4 acceptées et 6 refusées pour lecture déchirée. Les 76 tentatives des deux
fenêtres ont été rejouées sous cette révision historique ; la fenêtre suivante
interrompue tôt a donné 33 images/66 refus (35 budget, 31 cohérence), sans succès.
Les 38 PNG et les sources historiques sont préservées en privé ; aucune recette
capture/respawn/destruction/brouillard n'est encore déclarée acquise.

Le read-set a localisé les déchirures principales sur des octets CUnit inutilisés
(+0x14, +0x42) inclus dans les anciens blocs de 56 octets. Le correctif lit
uniquement tag+0x10, flags+0x39, lien catalogue+0x18 ou +0x20, et propriétaire+0x44.
Toutes ces données consommées et les racines restent vérifiées. La relecture de
cohérence coalesce seulement les répétitions identiques adresse/taille/octets ;
une répétition contradictoire refuse la capture, les tailles différentes restent
séparées. Les lectures initiales et le rejeu ordonné ne sont pas coalescés.
Ce changement n'augmente ni 8192 lectures ni 125ms et n'ouvre aucun champ public.
Le booléen brut `spawned` n'est pas une preuve d'apparition : sa déclaration est
présente dans les scripts conservés, mais aucune affectation n'y a été trouvée.
