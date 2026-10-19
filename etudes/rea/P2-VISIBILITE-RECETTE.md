# Reprise visibilité — identité active vérifiée, cycles brouillard non prouvés

> Historique de préparation. Les deux cycles sont désormais documentés dans
> `P2-VISIBILITE-VALIDATION.md` (19octobre, Volskaya uniquement). Les anciennes
> limites budgétaires ci-dessous ne remplacent pas le mandat nocturne amendé.

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
171 tests sur les deux Python. La revue indépendante isolée
`20261018_205828_1e2cbe` a approuvé le diff exact de préparation ensuite committé
`08eed35aeada66699b15bdab824b51514b8539ae`, sans défaut security/logic identifié,
mais explicitement sans approbation live. Le snapshot approuvé a été relu avant
commit. La première revue de reprise (`deleg_7648e464`) couvre b2d8cb5/100b71b.

## Seconde recette réellement exécutée, budget épuisé

La seconde et dernière tentative autorisée a duré240s :307 frames,614 tentatives
et307 PNG acceptés, aucun saut hors premier plan. Le rejeu exact du code gelé
08eed35 consomme614/614 read-sets/horloges :557 diagnostics acceptés,57 refus de
déchirure.660 états héroïques inconnus restent inconnus (554 mort hors périmètre,
106 callback de révélation non traduit), et ne sont pas des frames/refus globaux.
Acquisition maximale16ms, image encadrée maximale422ms ; horloge Windows
quantifiée, jamais une garantie d'atomicité ni de coût nul.

Le hash natif initial seed/cache est identique dans toutes les acquisitions
acceptées. Sa comparaison au hash dérivé indépendamment du replay sauvegardé
est exacte, après sortie normale du jeu. Le replay build98348 reste décodé avec
le shim déclaré91756 ; il n'a jamais servi de producteur live. Les deux séries
principales cumulent477 frames,954 tentatives exactement rejouées (860 acceptées,
94 refus) et427 PNG vérifiés, hors pré-échantillons. Le code gelé16 fichiers de
la première série a aussi été rechargé depuis sa copie durable pour la rejouer
indépendamment du nouveau code18 fichiers.

La comparaison des trois captures par partie aux replays observateurs historiques
retrouve aussi exactement les deux identités distinctes Volskaya et Braxis ;
l'ancien Dragon donne une troisième identité concordante. Ces sept dumps sont
des corroborations STRUCTURELLES de la source initiale, pas des validations de
visibilité joueur, d'atomicité, ou une extension Dragon/Braxis.

Le chemin public `read(context)` a été réellement exercé en rejeu sur les614
tentatives v2 :557 résultats/57 refus concordants.557 contrôles du normaliseur
sur enveloppe SYNTHÉTIQUE vérifient l'absence de XY/vitaux/ressources/cooldowns
ennemis malgré le booléen. L'allowlist n'a été patchée que dans ce processus
d'audit historique ; elle reste VIDE dans le produit. Ces enveloppes ne sont
pas une capture complète P0/P1/initData et ne prouvent pas une acquisition live
fraîche du chemin complet ; aucune valeur replay ne remplit le live.

Roster effectif v2, confirmé par le replay : Diablo local ; Abathur, Auriel,
Lunara, Kerrigan alliés ; Asmodan, Uther, Kramer, Ragnaros, Chen ennemis. L'UI
avait accepté quatre choix Abathur en lobby mais les a réassignés : ne pas
utiliser le roster prévu comme preuve de vision absente. Toujours neuf IA,
zéro observateur actif et aucun humain externe. Le jeu a été fermé normalement
et les états audio initiaux restaurés/relus par l'opérateur, pas par Cody.

## Critère encore manquant — ne pas livrer partiellement

Les annotations indépendantes ne prouvent pas deux cycles du même ennemi
visible→brouillard→revisible. Première série : six observations positives
étiquetées, dont trois seulement encadrées par deux lectures acceptées ; aucune
comparaison négative certaine de brouillard. Seconde série : Asmodan est nommé,
avec modèle/barre rouge à la frame102/HUD09:33 ; la frame143/HUD10:06 montre une
caméra plus au nord sur le pointB vide, sans prouver qu'Asmodan y est encore.
Les disparitions pendant apparition/embarquement du protecteur, une mort ou
un simple départ hors cadre ne sont PAS des transitions de brouillard validées.
Une inspection complémentaire de six frames régulièrement espacées et des
frames102/143 confirme cette ambiguïté, pas un deuxième cycle inventé.

L'opérateur a épuisé les deux tentatives autorisées et a explicitement interdit
une troisième sous le mandat courant. Aucune nouvelle partie n'est lancée pour
ce lot. Le besoin de reprise est un scénario instrumenté permettant d'identifier
et de garder la même région ennemie avant/après pertes de vision, sans vision
partagée persistante ni embarquement/transformation ; il appartient à la
coordination opérateur et à une décision de budget, pas au propriétaire de jouer.
Tant que ce critère manque : carte NON LIVRÉE, allowlist vide, aucun descendant
libéré, aucune intégration/push main. Sources, traces, captures, replays, revues
et audits sont conservés dans le handoff privé durable, jamais des dumps en Git.

La revue finale RO indépendante `20261018_213201_f1fd6e` a réellement relancé
171 tests sur chacun des deux Python, rejoué les340 acquisitions avec le code
gelé v1 et les614 avec le code v2, vérifié les427 PNG et les16/18 sources gelées.
Verdict : `code_review_passed=true`, zéro défaut security/logic identifié,
`release_approved=false`. Outre les deux cycles non attestés, elle exige avant
une future livraison la trace du chemin LIVE COMPLET réel
initData/P0P1→NativeReader.read_state→normaliseur→clé antipéremption, en un même
processus avec fraîcheur non simulée. Les557 enveloppes synthétiques de rejeu
public-core ne remplissent pas ce critère. Préparer ce collecteur/tests hors
ligne avant toute éventuelle nouvelle recette décidée par la coordination ;
ne pas simplement rejouer une troisième fenêtre du diagnostic existant.

## Outil de preuve pipeline préparé hors ligne, sans troisième capture

`etudes/rea/scripts/capture_visibility_pipeline.py` prépare maintenant ce chemin
réel : buffer initData lu à chaque prélèvement → vrai ContextProbe →
reader.snapshot/NativeReader.read_state → normaliseur → tactical_key, dans un
même processus. Aucun roster, niveau ou paquet P0/P1 n'est fabriqué par ce
collecteur. La région ciblée est celle d'initData : aucun compteur gt_* du tas
entier n'est revendiqué. Une seconde lecture des octets initData détecte leur
modification pendant l'acquisition ; le hash initial natif doit aussi concorder.

La découverte RO est séparée et bornée (256MiB demandés,20s,16384 requêtes de
régions, lectures de1MiB avec recouvrement64KiB). Elle ne donne qu'une adresse
privée candidate, pas une permission de réutiliser le contexte. Chaque tentative
redécode et revérifie le buffer et la perspective active. Un label joueur est
fourni dans un petit fichier UTF8 privé sous out/, jamais une credential ni une
valeur imprimée. Le collecteur peut aussi utiliser une adresse déjà identifiée,
mais ne remplace pas une découverte manquante par une adresse supposée.

Pour évaluer le booléen encore non livré, le processus DIAGNOSTIC privé active
explicitement sa seule allowlist candidate, avec le flag obligatoire
`--candidate-visibility`, puis la restaure même en erreur. Le produit reste
fermé ; aucun paquet ne va à une API/coach/audio. L'horloge live est transmise à
la vraie monotonic, en enregistrant ses valeurs, jamais gelée. Sont tracés les
octets demandés/échecs, horloges, paquets réellement lus, sortie normalisée,
âges des reçus, clé antipéremption et refus optionnels. Le rejeu est étiqueté
historique, génère ses propres reçus éphémères et consomme les lectures/horloges
dans l'ordre ; il ne revendique pas la fraîcheur live de l'ancien JSON.

Les tests hermétiques supplémentaires exercent ce vrai code de chaîne sur
mémoire et initData SYNTHÉTIQUES, y compris une horloge réellement transmise,
rejeu exact, refus observateur/match périmé/initData déchiré/dump roulant,
expiration murale malgré mission en pause, transition encadrant l'image,
confidentialité ennemie, sélection native du candidat et budget discovery.
185 tests passent sur chacun des deux Python à ce stade. Cela prépare l'outil ;
cela ne fournit NI deux cycles réels NI une nouvelle capture du pipeline live.
Aucune troisième partie n'est lancée. La commande future reste conditionnée à
l'arbitrage explicite du budget/scénario par la coordination opérateur.
