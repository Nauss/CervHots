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

## Résultat réel R3 et correctif R4 strictement hors ligne

Les diagnostics R3 sous 30ca38c ont été rejoués avec leurs sources historiques
préservées, et non avec R4 : 402 tentatives, 201 PNG hachées, 304 acceptations de
SECTIONS natives privées. Le Full court a donné zéro acceptation sur dix : cinq
budgets 8192, quatre cohérences natives, un battlefield absent après refus de
cohérence. Un exit 0 du collecteur ne signifie pas un succès du pipeline.
Les acceptations de sections ne prouvent ni normalisation Full ni livraison 5.

La visite du camp 1 a montré les deux défenseurs et le libellé de fortification ;
la visibilité des membres a évolué False/False, True/True, puis False/False après
retrait. L'ancre Unknown n'est pas False et ne doit pas être renommée ainsi.
Capture, réapparition, remplacement et matrice complète restent à qualifier.

Sur le core sélectionné, la capture réelle affiche 26400/17600 tandis que les
lectures conditionnelles +0x220 et +0x22C valent respectivement 72089600 et zéro :
elles produisent le composant 17600 et son ratio 100%. Ce n'est PAS une égalité
avec les PV totaux du panneau. Aucun clamp de 150 à 100, bouclier ou bonus n'est
présumé comme explication validée. Le getter compilé contient d'autres branches
de propriétés ; les composants supplémentaires du core R3 n'ont pas été lus.
La sémantique des PV doit être réconciliée sur une prochaine recette autorisée.

Après libération explicite du gel R3 et fin des recettes, R4 réduit les I/O du
recensement avec un bloc privé de 56 octets. La trace conserve tout le bloc, mais
le read-set de cohérence sélectionne uniquement le tag, les flags, le lien
catalogue de la bonne branche et le propriétaire effectivement consommés.
Les octets inutilisés +0x14/+0x42 ne sont donc toujours pas des sources vérifiées.
Une variation d'un champ consommé, une contradiction répétée ou un bloc tronqué
refuse ; les XY/vitales de héros ne sont jamais lus par ce recensement.

Le chemin candidat produit désormais les deux familles depuis UNE acquisition
combinée bornée à 125ms : une vérification de profil/identité/visibilité, puis
recheck de TOUS les champs consommés des deux familles, sans cache inter-frame.
Les deux reçus restent distincts et identifiés par leur section, mais partagent
la même fenêtre réelle et le même instant d'acquisition. Pas de prétention à
l'atomicité du moteur ni d'augmentation du budget de 8192 lectures.

Le benchmark R4 sur anciens octets non atomiques avec identité MOCKÉE mesure
6765 lectures (6782 avec constructeur), contre 7913 hors constructeur dans le
benchmark R3. Il ne comprend pas le vrai contexte/core/identité du pipeline et
ne prouve PAS que le Full réel entre dans le budget. La preuve Full R3 reste un
échec, les traces R3 ne doivent pas être rejouées en prétendant utiliser R4.

VALIDATED_MAPS reste vide. Aucun nouveau live, partie 13, activation, push main
ou livraison/déblocage 6 n'est autorisé par ces correctifs hors ligne. Une future
fenêtre de recette explicite est nécessaire après correction et revue ; la fin
de la fenêtre nocturne n'est pas un besoin de propriétaire comme pilote.
