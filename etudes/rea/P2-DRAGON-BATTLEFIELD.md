# Dragon Shire — camps et structures, candidat natif NON livré

## Périmètre et fermeture

Build98348 exclusivement. `DragonBattlefield.read()` refuse inconditionnellement
avec `recette_champ_bataille_dragon_absente`. Aucun branchement à `read_current`,
au normaliseur, au coach ou à l'audio ; les allowlists publiques Volskaya ne
changent pas. Le succès d'un diagnostic ne qualifie pas le consommateur produit.

Le collecteur privé `etudes/rea/scripts/capture_dragon_battlefield.py` accepte
uniquement des fenêtres de 30s maximum, sans PNG/OCR ni pilotage GUI. Les données
brutes/readsets restent dans `out/`, jamais dans Git ni dans un prompt modèle.
Le libellé du joueur est fourni par variable locale privée, pas par argument.

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

## Preuve historique, PAS recette live

L'ancien ensemble privé `out/recon-live/live-a.{bin,heap.bin,heap.json}` a été
réexécuté avec le nouveau lecteur sans mock des getters : 5camps, 85entrées du
registre de villes et 58structures encore présentes. Le catalogue initial
indépendant du même replay contient90structures et5balises de camps : le dump
est tardif et nonatomique, il ne permet pas de reconstruire les coordonnées
fixes des structures absentes. Ne pas remplacer ces coordonnées par des floors
tracker, ni leur absence par une destruction.

Les58structures observées correspondent chacune à une naissance initiale unique
par type exact, équipe et floorXY dans le replay du même seed/cache. Le parcours
privé détaillé s'exécute également : 21structures CURRENT au snapshot, camp3
projeté available et les4autres unknown. Ces valeurs sont des références
historiques, jamais une nouvelle acquisition fraîche. Le décodeur replay utilise
le repli91756 signalé pour build98348, pas une garantie de schéma exact98348.

Les scripts/rapports d'exécution et données restent privés dans
`out/research/{inspect_dragon_battlefield.py,exercise_dragon_battlefield.py,
dragon-battlefield-offline-summary.json}` du worktree de la carte.

## Ce qui manque pour livrer le lot7

1. Catalogue initial90 avec coordonnées natives fixes, recoupé au replay du même
   match ; le recensement observé privé ne vaut jamais catalogue complet.
2. Capture et nouveau cycle/respawn des DEUX classes de camps Dragon, avec
   borne dernière lecture CURRENT nonavailable → première CURRENT available.
   Birth/preload, timer natif (fraction/pause) et disponibilité restent distincts.
3. DécroissancePV/destruction/morph/remplacement applicables Dragon, tag et
   génération recoupés au tracker ; la disparition d'un corps n'est pas sa mort
   tactique. La qualification Volskaya ne remplit pas ces critères.
4. Branche candidate du vrai consommateur, coût WHOLE réel, confidentialité,
   revue indépendante exacte puis intégration/push vérifiés seulement si PASS.

L'opérateurGUI exclusif désigné t_d6e15259 est clos ; son successeur opérationnel
Dragon t_7d4211b0 est également clos. Aucun auteur ne reprend la GUI, aucun match
ni nouvelle allocation n'est inventé. Le compteur transmis est22/24parties ; la
borne22:08:26Europe/Paris reste inchangée. Une affectation opérationnelle explicite
est nécessaire avant une nouvelle recette, sans demander au propriétaire de
jouer ni rouvrir les anciennes cartes. Aucun doublon de carte n'est créé ici.

Scénario ciblé proposé pour l'opérateur : une partie privée Dragon local+9IA,
fenêtre initiale12s avant toute destruction pour le catalogue ; fenêtres courtes
sur capture Giants puis Knights, autour du respawn calculé natif et sur une
structure attaquée. Préserver le même replay/seed-cache, terminer et restituer
menu/audio avant la borne. Ce scénario n'est pas une autorisation d'exécuter un
collecteur non revu ; le diagnostic doit d'abord mesurer son taux utile et coût.

## Vérifications

358tests PASS sur Python3.12 et3.14, dont16nouveaux tests synthétiques. Tests de
lecture/horloges strictement ordonnés, mutation d'une source consommée et des
racines finales, incohérences carte/match/héros/équipe/roster, budgets, groupes
recyclés, laners, données cachées, absence de reçu et refusPNG/préflight sans
processus. Les mocks d'orchestration ne sont pas une preuve de coût live.
