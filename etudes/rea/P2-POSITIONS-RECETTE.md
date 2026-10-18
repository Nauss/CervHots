# P2 — recette et livraison des positions alliées Volskaya

## Portée

Le lecteur build98348 publie les positions des héros principaux ALLIÉS vivants
sur Volskaya uniquement. Il exige un vrai joueur local et une équipe confirmés
dans les objets natifs actifs, concordants avec le contexte initData. Observateur,
replay, contexte absent, lecture ambiguë/déchirée/périmée => champ absent, pas zéro.
Aucun ennemi ni unité additionnelle énumérée par propriété (illusion/compagnon).
Dragon et Braxis restent fermées. Aucun replay futur ne remplit le live.
Base parent : main `3361e4efcf8ad8eb1ba8ac8b5fb1dc46196d86a7`.

Cette note remplace le statut préparatoire de `P2-POSITIONS.md`, qui conserve les
sources natives, instructions suivies, gardes d'identité et protocole d'acquisition.
`VALIDATED_MAPS` contient seulement `Volskaya`, vérifié aussi par le normaliseur.
Le code ne produit PAS des pixels d'écran : XY natifs fixed signés/4096, puis :

    u = (x - 4) / 240
    v = 1 - (y - 4) / 192

Région native active `[4,4,244,196]`, +X droite, +Y haut. Aucun rectangle HUD,
résolution ou marge constant n'est ajouté au produit. Le getter commun et les
observations visuelles étayent ce repère, pas toutes les formes de tous les héros.

Modèle : `positions: {t,map_id,heroes:[{id,hero,team,x,y,u,v}]}` seulement.
Ni noms, comptes, tags, pointeurs, reçu HMAC ni racines. Surcharge d'équipe adverse
ou carte différente => omission, jamais ennemis réétiquetés. Roster/héros/vie et
bornes sont contrôlés une seconde fois au normaliseur ; extras retirés.

## Fraîcheur et cohérence

`LocalPlayer` actif -> racine client -> CPlayer, équipe `+0x1c`, type `+0x1d` :
slot local humain1, IA2, équipes natives0/1 et5v5. Modes observateur/replay refusés,
branches de spectateur jamais utilisées. Empreintes PE/code strictes, RVA/ASLR,
profil98348 et encodage14 seulement. `CPlayer+0x58` sélectionne le héros principal ;
tag complet/génération/index/propriétaire et flags de vie vérifiés avant tout XY.

Relecture exacte des racines, code, clés, CPlayer, tags, owner, flags, bornes et XY.
Budget monotone ET mission125ms ; aucun cache/retry/extrapolation. Détecteur
conservateur, PAS verrou atomique : ABA entre prélèvements non exclu. La fenêtre
P0/P1 globale1s reste indépendante. `native_session` empreinte les objets de cette
acquisition, pas une identité persistante garantie à travers réutilisation d'adresse.
Le hash initData reste un label, pas l'autorité de perspective native.

Reçu HMAC éphémère couvrant le paquet complet et son début monotone ; âge0..1s
exigé même en pause mission. Falsification, autre processus, paquet expiré => omission.
Chemin supporté : direct `cerveau --live --player NOM` dans le même processus.
`--state` interprocessus perd volontairement les positions. Clé jamais persistée.
Changement de coordonnées/disponibilité annule le conseil ; nouvel horodatage seul
d'une position identique ne l'annule pas. Seuil0,75, silence et opt-ins inchangés.
Aucun appel coach/API/TTS/Mumble exécuté pour ce lot.

## Recette réelle du 18/10/2026

Une partie PRIVÉE Volskaya, Diablo local contrôlé par l'opérateur assistant et neuf
IA ; aucun observateur actif, aucun humain externe/PvP. Déplacements deux axes,
points stables, mort/respawn. Client fermé normalement et deux endpoints audio
restaurés/read-back par l'opérateur. Replay final : corroboration seulement de la
carte/composition/perspective, fallback91756 pour build98348 explicite, jamais source live.

Collecteur gelé `3f10bac24e0d0177534f4ae505756189a77d055d`, trois séries sans overlap :

| Série | Trames/PNG | Tentatives | Acceptées | Déchirures refusées | Local mort omis |
|---|---:|---:|---:|---:|---:|
| 001 | 119 | 238 | 227 | 11 | 0 |
| 002 | 159 | 318 | 302 | 16 | 21 |
| 003 | 158 | 316 | 298 | 18 | 22 |
| Total | 436 | 872 | 827 | 45 | 43 |

Rejeu intégral exécuté : ordre/adresse/taille/bytes ET horloges monotones exacts,
872 résultats diagnostiques reproduits et436 SHA256 PNG vérifiés. Acceptation94,839%,
maximum noyau accepté5,419ms, aucune garde assouplie.394 paires PNG doublement
acceptées ; fenêtre extérieure maximale349,679ms. PNG non synchrone au micro-instant
XY : héros stable avant/après exigé pour calibration. Endpoints identiques ne
prouvent pas à eux seuls l'absence d'un aller-retour entre prélèvements.

Le même trace exerce aussi `AlliedPositions.read` avec la liste réelle ouverte,
sans mock de permission :872 tentatives, mêmes827 réussites/45 refus. Cette
vérification historique emploie les identités natives et un label de match
synthétique ; ce n'est PAS la capture du paquet initData/P0P1 complet ni une
acquisition live fraîche. Chaîne normaliseur complète/falsifications : tests hermétiques.

Mort locale : première omission acceptée série002/trame148, mission266,25s ;
retour série003/trame12/après,285,125s. Flags4 puis0, MÊME tag/objet à travers respawn.
Ce n'est donc PAS un remplacement de référence. Luisaile/Jaina ont aussi des
omissions réelles flags4 puis retour. Aucun remplacement volontaire/forme spéciale
réalisable exercé dans ce match ; changement slot/génération/propriétaire et
compagnon restent des tests synthétiques, pas une validation terrain universelle.
Les trois en-têtes prouvent le refus public à contexte local absent.

## Comparaison aux pixels : portée et exclusions

Cinq centres verts Diablo annotés indépendamment par l'opérateur, relus sur PNG
par l'implémenteur et une revue séparée ; curseurs verts voisins exclus. Trois
points d'ajustement, deux réservés, incertitude estimée±1px/axe. Ajustement recalculé :

    px = 1327,537409 + 495,632594 * u
    py =  979,693492 + 392,712386 * v

Points réservés : erreur max1,344px/RMS1,029px, relative aux annotations entières,
pas à une vérité subpixel. Rectangle EXTRAPOLÉ, pas quatre bords observés ; une
résolution1865×1399, aucune projection universelle revendiquée.

Contrôles supplémentaires sans réajuster : huit centres de portraits alliés bleus,
identifiés contre le HUD puis annotés AVANT comparaison aux XY, stables avant/après.
Luisaile3, Jaina2, Dehaka1, Medivh2 : max2,458px/RMS1,571px, incertitude estimée±2px/axe,
brackets extérieurs249..272ms environ. Une neuvième annotation Dehaka mobile et
mal transcrite est conservée EXCLUE, non corrigée après comparaison pour fabriquer
une réussite. Superpositions et formes corbeau non identifiables exclues de la
référence. Dehaka n'a qu'un point séparé stable ; pas de couverture des bords extrêmes.

Tolérance comparative5px radiaux choisie rétrospectivement : pas un test statistique
préenregistré. Ces résidus ne sont PAS une borne d'erreur de toute la carte/alliés.
Aucun paramètre de cette projection écran ne remplace les coordonnées natives.

## Outils, tests et conservation

`capture_positions.py` : collecteur privé RO borné, deux tentatives autour d'un PNG
opt-in ; durée<=120s, intervalle>=0,25s, au plus8192reads/1Mio par tentative, aucun
scan tas par image. Pillow importé seulement avec PNG ; sources/commit gelés,
création exclusive. HWND jeu au premier plan avant ET après, GetWindowRect
multiscreen : surface compositée, PAS texture DirectX isolée ; overlays/DPI possibles.
Écarter toute image contaminée. Ce worker ne prend pas la GUI ni le PID.

`replay_positions.py INPUT.jsonl --public --out AUDIT.json` vérifie exactement
noyaux diagnostic/public, refus/horloges et SHA256 PNG. Sans jeu, Pillow, API ou son.
Ne pas exposer ses acquisitions historiques comme état live frais.

Tests hermétiques : mouvement/axes/fixed signé/table non uniforme/ASLR/bornes,
génération/propriétaire/remplacement, mort/respawn, identité absente/observer/IA,
racine changée avec dict inchangé, déchirures/budget, falsification/expiration en
mission figée, confidentialité, annulation tactique, corruption ordre/horloge/trace.
Aucune dépendance à la KB ignorée ou aux fichiers privés.

Preuves HORS Git et hors worktree jetable :
`out/player-position-recipe/2026-10-18/run292-volskaya/` (captures/sources gelées) et
`out/p2-handoff/2026-10-18/positions-implementation/` (audits/revue de livraison).
SHA256 JSONL001/002/003 :

- `c2921fada79f9042de8cde8a1dbd8f3a786b3a2111d520174f1268296f8bf29d`
- `bfa8aadc8cc1d31f3f098c21292c761ef3499e2f9d7db443441080a88091c23a`
- `81e460732a943a26380e2e1aeaa2d5ac8d648bbdee2d9e34a11914d891eca5bb`

Anciennes captures observateur/roulantes : structure seulement, pas recette joueur.
Dragon : signatures concordantes mais bornes différentes `[8,24,240,182]` et aucun
PNG applicable => aucune ouverture. Braxis ne remplace pas Dragon. Objectifs,
camps/structures, visibilité ennemie, talents/cooldowns restent hors lot.
