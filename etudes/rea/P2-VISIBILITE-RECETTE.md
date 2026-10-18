# Reprise visibilité — préparation de la seconde recette

État : travail de branche NON LIVRÉ ; allowlist visibilité vide. Ce document
remplace les demandes historiques de créneau humain dans P2-VISIBILITE.md :
l'opérateur assistant t_cc601651 possède seul la GUI et conduit les recettes.

## Diagnostic réel initial, pas une validation finale

Le collecteur b2d8cb5 a produit170 frames/340 tentatives,303 diagnostics acceptés
et37 refus de déchirure.120 PNG fenêtre jeu vérifiés ;50 captures hors premier
plan ont été sautées et ne sont pas des preuves visuelles. La perspective est
un vrai joueur local Diablo +9IA en partie privée Volskaya build98348. Le replay
postérieur sert seulement au recoupement de la même partie, jamais au live.
Les annotations positives de trois images ne démontrent pas deux cycles
visible→brouillard→revisible. L'absence d'un ennemi hors cadre est ambiguë.
Acquisition maximale16ms avec horloge Windows quantifiée ; ce n'est pas une
atomicité ni une mesure de coût nul. Aucun accès GUI/jeu/coach/audio par Cody.

## Origine native de l'identité initiale — source puis champ

Le nouveau `hotstate/match.py` ne cherche pas une occurrence du seed dans le tas.
Il lit l'interface courante utilisée par la native GameMapPath : global RVA
0x2f825f8 XOR0x50c23112, contrôle ses pointeurs/vtable et les getters effectifs.
Le getter vtable+0xe0, RVA0x1324b70, retourne this+0x83f78 ; celui à+0x358,
RVA0x1327c00, lit this+0x1d910. L'état4 est celui exigé par la branche de
sauvegarde qui consomme cette source ; la simulation active est aussi exigée
par NativeReader et la perspective humaine est validée séparément.

La continuation de la fonction RVA0x132b0f0 transmet this+0x83f78 à0xdb9a40,
puis la copie0xcf96b0 vers un temporaire. Le même temporaire devient le cinquième
argument de0x134fbf0, transmis à0x1350f80 pour produire replay.initData. Cette
circulation de pointeurs se vérifie au désassemblage ; certaines décompilations
sont tronquées par une annotation non-return incorrecte. La branche globale
alternative n'est pas substituée à cette source courante. Aucun appel client
n'est exécuté pour lire ces données.

Les descripteurs natifs, racine versionnée888→alias889→struct775, donnent les
champs syncLobbyState par tags -3/-2/-1 : users0, gameDescription0xc308,
lobbyState0xe198. Le struct684 a28 champs, le struct762 en a11 ; leur ordre et
leurs tags concordent avec les déclarations du protocole Blizzard utilisé
(explicitement fallback91756, pas un décodeur98348 inventé).

- lobbyState champ4/tag-7, type767→3:uint32, offset62096 : seed initial relatif
  à la config0x1d428. Ce n'est PAS le RNG mutable de GameSetSeed.
- gameDescription champ21/tag-7, type706→642 : liste ordonnée de cache handles,
  offset4472, soit config+0xd480. Le schéma limite à32 éléments, stride40 ; les
  getters natifs RVA0x13572a0/0x13572b0 lisent countQ et data+8. Chaque élément
  est un blob40 octets, alias643→400 ; contrôle s2ma et bornes avant lecture.
- Le chemin GameMapPath à config+0xc770 concorde avec le champ mapFileName à
  gameDescription+1112 puis buffer+16, sans être utilisé comme preuve de seed.

Le lecteur confronte SHA256(seedLE32 + handles ordonnés) au match déclaré pour
la visibilité contextualisée ; modification seed/cache, contexte, racine,
getter, état ou signature => refus. Toutes ces lectures sont dans le read-set
recontrôlé de la visibilité et le budget mural125ms, non dans un cache de lobby.
Les signatures build98348 et tables d'offsets numériques sont fingerprintées.
Sur l'ancien dump Dragon roulant, le lecteur réellement exécuté retrouve six
handles et exactement le hash du contexte/replay historique. Cela corrobore la
structure, PAS une validation temporelle live ni une livraison Dragon.

## Contrat préparé, encore fermé avant recette

`CurrentVisibility.read` est implémenté mais protégé par une allowlist vide. Il
utilise exactement le cœur de `diagnose`, avec comparaison native match/contexte,
puis reçu HMAC même processus frais0..1s. Un diagnostic n'a jamais ce reçu.
Le normaliseur préparé ne conserve que id/héros/booléen courant (ou null) après
contrôles de source/build/carte/match/perspective/fraîcheur et identité héroïque.
Aucune XY/vitale/ressource/talent/cooldown ennemie n'est débloquée. La clé
antipéremption annule un conseil sur changement true/false/null ou disparition
de visibilité, pas sur le seul nouveau timestamp. Le seuil0.75 et les opt-ins
sonores sont inchangés ; aucun appel de décision ou son n'est nécessaire.

Tests RED : module identité absent puis chemin de publication absent. GREEN :
171 tests sur les deux Python. La nouvelle revue indépendante et la seconde
recette réelle incluant identité native et deux cycles annotables restent
nécessaires avant ouverture, intégration et push. La première revue de reprise
(deleg_7648e464) couvre b2d8cb5/100b71b seulement, pas ces nouveaux changements.
