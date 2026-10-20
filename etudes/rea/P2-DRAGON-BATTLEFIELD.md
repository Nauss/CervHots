# Dragon Shire — camps et structures natifs qualifiés, proposition de branche

## Périmètre et frontière de livraison — 20 octobre 2026

Build98348/DragonShire exclusivement. Le vrai chemin est désormais
`NativeContextProbe → read_current → NativeReader → DragonBattlefield.read →
cerveau.state.snapshot → cerveau.battlefield.project → tactical_key`.
Une acceptation Full exige l'objectif Dragon typé, cinq camps et 90structures,
dans le même budget WHOLE. Un diagnostic seul, une famille absente ou une clé
calculée après expiration du budget ne sont jamais des acceptations Full.

La proposition autorise uniquement DragonShire dans le scope de cette famille.
Le catalogue ne donne aucune permission par lui-même ; une allowlist vide ferme
toujours le lecteur et le normaliseur. Aucun scope Volskaya n'est élargi.
La proposition doit être revue exactement puis commitée avant le préflight et
la courte recette finale `--qualified-battlefield`, sans override de permission.
Ni cette branche ni ses preuves ne valent intégration/push ou livraison produit.

Le collecteur `etudes/rea/scripts/capture_dragon_battlefield_pipeline.py` distingue
explicitement `--candidate-battlefield` (permission locale forcée, NOT_RELEASE)
et `--qualified-battlefield` (deux portes réellement ouvertes, aucun override,
NOT_RELEASE également). Le mode qualifié n'override pas non plus l'objectif
dans le sampler partagé. Préflight sans processus ; live exige opt-in, HEAD
propre exact, sources gelées, nouvelle sortie privée et ACK de l'opérateur.
Fenêtres habituelles12s/0.25s, maximum30s. Aucun coach/audio/GUI/PNG/OCR ni heap
scan dans le collecteur. Libellé privé en environnement enfant uniquement ;
readsets/pointeurs/identité/replays demeurent dans `out/` privé, hors Git/prompts.

## Implémentation exercée

- Profil séparé : 15 fonctions ACTIVE VM et signatures natives vérifiées ;
  initialisation de carte Dragon et données SiegeGiants/Knights fingerprintées.
  Les fonctions communes ont été comparées sur le dump Dragon conservé, et non
  simplement supposées compatibles depuis Volskaya.
- Cinq camps d'indices1–5 : SiegeGiants, Knights, SiegeGiants, Knights, Knights.
  Ancres fixes natives : (101,76.5), (100,110), (147,76.5), (148,110), (124,32.5).
  Deux défenseurs Giants ; trois MeleeKnight et un RangedMage pour Knights.
- Résolveur génération/type/propriétaire, groupes typés/génération et distinction
  des mercenaires partis en lane ; pas de disponibilité déduite d'un laner.
- Vérification du décodeur XY avant toute utilisation d'ancres/visibilité.
- Visibilité CURRENT avant les composantes vie/bouclier d'une structure.
  Le pourcentage mesure la vie de composant, pas le numérateur HUD combiné.
- Contexte natif, identité seed/cache, héros/équipe/roster et carte recoupés ;
  budget physique8192lectures/1MiB/125ms, rechecks des champs consommés, bits de
  visibilité, contexte et racines de l'horloge finale.
- La porte `TownGateL3VerticalRightVisionBlocked` est désormais reconnue comme
  type exact. Cela n'ajoute aucune entrée au catalogue public Volskaya.

## Catalogue et recette réelle du consommateur

Le diagnostic initial neuf `01` comporte40tentatives/30acceptations, PAS30Full.
Il établit90structures fixes natives cohérentes sur30observations. Le même replay
NORMAL recoupe90/90types/équipes/floorXY, dont48XY exacts et42comparaisons au
floor uniquement ; les coordonnées fractionnelles proviennent du natif, jamais
d'un floor inventé. Les90indices/générations concordent aussi avec le tracker.
L'ancien dump tardif/nonatomique (85entrées/58corps présents) demeure historique,
pas une preuve fraîche ni un substitut au catalogue initial de cette recette.

Le profil `98348-dragon-structures.json` contient uniquement les90repères Dragon.
Son SHA géométrique canonique est conservé, comme le SHA de la capture initiale.
Les IDs `dragon-NNN` sont liés explicitement au rang trié XY/type ; permuter deux
IDs ne passe plus sous le seul digest géométrique. Build/version exigent de vrais
entiers, pas bool/float. Cette qualification géométrique ne qualifie pas à elle
seule les transitions, l'identité native, les reçus ou le budget d'une lecture.

Le consommateur candidat `0d17a08` a réellement produit250Full sur863tentatives
dans22fenêtres de quatre matchs privés Sonya locale+9IA/0observateur. Les863
tentatives, y compris613refus, ont été rejouées strictement sur Python3.12 et3.14
(ordre/tailles/octets des reads, horloges, statut, normalisation et clé).
Maximum observé7015lectures/211557octets ; WHOLE accepté maximum94ms.
Ce sont les nouvelles preuves camps/structures, pas l'ancienne recette objectifs.

## Captures, disponibilité et structures : contrôles indépendants

Chaque contrôle utilise le replay NORMAL du MÊME match, seed+cache identiques.
Le protocole91756 est un repli explicitement déclaré pour98348, pas un schéma
exact98348 garanti. Le tracker n'est jamais un producteur live ni une permission
de rafraîchir une archive. Les preuves des classes sont séparées par match ;
aucun intervalle/cycle n'est construit en fusionnant deux matchs.

- Day002 : captures Siege1 à218.875 et Knights2 à358.125, owner0, recoupées tracker.
  Quatre destructions au TAG ENTIER/génération dont deux morphs de tours, une
  porte et un fort ;16IDs avec dégâts.3675observations CURRENT compatibles avec
  le tracker (3561alive/114destroyed), une observation ambiguë125ms écartée,
  zéro conflit. Absence, fog, unknown et remplacement ne valent pas destruction.
- Day003/Knights2 : capture tracker364.625owner0 ; quatre défenseurs initiaux et
  quatre retournés, types et DEUX hashes de groupes complets concordants natif/
  tracker. Dernier nonavailable[377.75,377.75], premier available[659.375,659.375].
  Borne[377.75,659.375], largeur281.625s, volontairement large. Naissance601.75
  du groupe retourné : PAS un instant de disponibilité.
- Day004/Siege1 : première observation CURRENT à123.0 déjà fighting, pas Idle.
  Capture tracker133.4375owner0 ; deux défenseurs dans chacun des groupes initiaux
  et retournés, types et DEUX hashes complets concordants. Dernier captured
  [312.375,312.4375], premier available[326.5,326.5] : borne[312.375,326.5],
  largeur14.125s. La naissance310.5625 n'est PAS la disponibilité. L'Idle initial
  de cette instance n'a pas été observé dans ce match et n'est jamais inventé.

Les bornes utilisent les DEUX vraies horloges `_observe`, pas seulement le temps
core ou la fin de paquet. La signature `cycle` décrit les défenseurs vivants
CURRENT et peut changer quand un membre meurt ; son changement seul ne prouve
donc jamais un respawn. Le retour exige captured puis réellement available,
nouvelle signature visible, et groupes complets recoupés indépendamment.
Préchargement, hibernation code4, timer0 ou nouvelle signature unavailable ne
sont PAS ready. Fraction native/paused=false ont été observés ; paused=true
n'a pas été provoqué par la recette live. Une échéance ne sert qu'à viser une
fenêtre, jamais à fabriquer un instant exact ou la disponibilité.

## Vérifications

Suites hermétiques Python3.12.12 et3.14.7 sans `.env` ni KB ignorée : contexte,
carte/match/héros/équipe/roster, budgets physiques/WHOLE, sources et racines
mutées, fog, génération/type/owner incohérents, laners, reçus absents/forgés ou
périmés, couverture normaliseur/clé, refusPNG/préflight sans processus et
absence d'override des DEUX portes dans le mode qualifié. Les fixtures servent
aux régressions, jamais au comptage Full ou à une preuve de coût live.

Les références privées immuables, logs et revue exacte doivent être consolidés
dans `out/day-fleet/2026-10-20/handoffs/t_de084111/ready-for-integration.json`
SEULEMENT après PASS et recette finale sans override. La composition avec
talents/CD doit ensuite revalider WHOLE, confidentialité et revue sur le delta
composé avant main/push. La clôture de cette phase n'est pas la livraison maître.
