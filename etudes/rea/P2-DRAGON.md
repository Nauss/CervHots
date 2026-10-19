# P2 — sanctuaires et Chevalier Dragon, build98348

**Date :** 19 octobre 2026 · **Statut :** diagnostic natif implémenté,
publication fermée ; transitions Dragon et intégration consommateur non qualifiées.

## 1. Résultat exercé et limites

`hotstate/dragon.py` lit les globals de la VM ACTIVE et les unités effectives,
pas les compteurs d'invocation des triggers. `inspect_saved()` a été exécuté
sur le vrai module/tas Dragon `live-a`, capture roulante historique conservée
hors Git. Résultat : phase waiting, sanctuaires sun/moon de types respectifs
DragonShireShrineSun et DragonShireShrineMoon, neutres et désactivés,
respawn15.875s. Ce résultat n'est NI une acquisition atomique NI un nouvel
instant live. Les références statue/dragon de cette ancienne capture sont
recyclées ; aucune lecture des propriétaires/vitales du remplaçant n'est permise.

Les fixtures couvrent capture, neutralisation, perte, contestation, état
inconnu/désactivé, canalisation, véhicule actif et fin. Elles ne prouvent PAS
ces transitions en partie. L'ancienne capture isolée ne peut pas compléter
la recette. Aucun transfert de qualification Volskaya/Braxis.

`DragonObjective.read()` refuse systématiquement `recette_dragon_absente`.
Aucun reçu tactique n'est émis, aucune intégration au reader/normaliseur n'est
activée ; les allowlists produit restent inchangées. Une acceptation du
collecteur est explicitement `accepted_diagnostic_NOT_PRODUCT`, pas Full.

## 2. Source, identité et sémantique

Profil `98348-dragon.json` : build/PE et signatures natives,30fonctions Galaxy
par index/nom/bornes/SHA256. Ce profil a été construit depuis la VM Dragon
historique, pas depuis une recherche de noms de tas. Les fonctions communes
GameLib ont leurs propres empreintes ; les fonctions Volskaya ne sont pas
substituées à une mécanique Dragon.

MapMechanicsLib initialise les deux entrées dans l'ordre Sun puis Moon,
stride21, en les reliant à leur captureBeaconIndex. Dans l'ancienne capture,
ces indices sont6/7, PAS nécessairement1/2. Le lecteur relit la liaison,
l'absence de doublon, les globals Sun/Moon, le type natif du sanctuaire et
celui du beacon ; tag/génération/propriétaire sont résolus à chaque lecture.
Pas d'orientation haut/bas supposée ni de pourcentage commun inventé.

CapturePoint utilise stride132, compteur signé et but64 pour4s à16ticks/s.
États : contested0, paused1, neutral2, captured3, reverting4, capturing5.
Le propriétaire de l'unité sanctuaire est indépendant de cet état.
La politique est contested DoNotDecay2, empty Owner0. Une capture désactivée
peut retenir propriétaire/compteur/état antérieurs pendant3s ; ces valeurs
ne deviennent pas une contestation/progression courante. Une référence
recyclée donne owner=null/state=unknown, jamais neutral par défaut.

Phases MapMechanicsLib : Idle0, ObelisksWarning1, ObelisksAvailable2,
DragonRampaging3. Les timers start/respawn/warning restent distincts et
vérifient registre, type19, génération, propriétaire, vtable et bornes.
Aucune origine HUD ou échéance exacte n'est reconstruite depuis un replay.

La statue capturable doit être VehicleDragon, possédée par11/12, avec les
deux sanctuaires courants de la même équipe. Le marqueur fini
TransformHeroVehicleBeingCapturedBehavior est ajouté par InitialEffect de
UseVehiclePersistent et retiré par FinalEffect, succès ou interruption.
Sa durée catalogue5s n'est PAS le temps de canalisation3s configuré par
InitTowers ; seul un booléen diagnostique en est tiré. Il reste privé :
une future projection ne devra pas exposer une canalisation ennemie cachée
sans preuve de publicité ou visibilité courante qualifiée sur Dragon.

En phase DragonRampaging, le véhicule vient du global unité courant ; le
pilote doit être le propriétaire actuel1..10 et le global DragonPlayer,
avec CPlayer actuel d'équipe0/1 et rôle humain/IA. La durée vient du premier
composant actif VehicleDragonTimedLife, comme le getter natif commun.
Aucun PV ni position héroïque n'est lu. Durée absente/zéro ne devient pas
un chevalier actif/prêt. Référence recyclée => état unknown, pas destroyed.
Le bit mort courant donne ended ; hors phase active on n'invente aucune
cause de fin historique.

## 3. Acquisition et collecteur

`diagnose()` exige un NativeContextProbe observé/recontrôlé, identité active
seed/cache, carteDragonShire, vrai joueur local humain5v5, équipe/héros/roster
cohérents. Aucun choix de bot comme joueur humain. Pas de calibration XY
Volskaya étendue à Dragon : aucune position n'est publiée par ce lecteur.

Budget physique8192lectures/1MiB/125ms, compteur de refus verrouillé,
relecture de tous les champs consommés et de la config, horloges mission
avant/après et monotone indépendante de la pause. Ce détecteur ne constitue
pas un verrou moteur : ABA reste une limite. L'horloge optionnelle injectée
dans NativeContextProbe permet le rejeu des mêmes délais sans changer le
comportement par défaut de la production existante.

`etudes/rea/scripts/capture_dragon.py` est destiné uniquement à l'opérateur :
préflight sans ouvrir le jeu, commit gelé, fenêtres0<durée<=30s et
intervalle>=0.25s, sortieJSONL privée neuve sous out/ du worktree. Aucun
argumentPNG ; aucun importPIL, OCR, contrôleGUI, heap scan, coach ou audio.
Le libellé joueur reste dans une variable locale, pas dans les commandes
ou manifestes. Les readsets privés contiennent des données contexte et
ne doivent jamais être joints au prompt/Git. Rejeu adresse/taille/octets
ET horloges en ordre strict ; les fixtures d'identité mockée sont nommées
comme telles et ne valent ni coût physique live ni perspective qualifiée.

## 4. Critères encore ouverts pour livraison

1. Recette Dragon native ciblée, joueur local+9IA, captures/pertes des deux
   sanctuaires, contestation recoupable, vraie canalisation/interruption ou
   fin, apparition/durée/fin du même véhicule avec replay indépendant.
2. Mesure réelle des acquisitions et refus, conservation des readsets et
   du replay de la même partie. Une ancienne capture ou une naissance
   tracker seule ne prouve pas ces états live.
3. Décider/qualifier les seules données publiques ; notamment canalisation
   cachée, pas de nouveau champ ennemi implicite.
4. Brancher ensuite le vrai consommateur, normalisation typée et clé tactique,
   reçus/fraîcheur/confidentialité, coût WHOLE non mocké et recette exacte.
5. Revue indépendante finale, intégration/main/push et SHA distant relu.

L'opérateur désigné par la directive, t_d6e15259/default, a clos sa recette
Volskaya après19/24parties. Cette préparation n'autorise pas Cody à prendre
la GUI, ni à ressusciter ses anciennes cartes. Handoff ciblé et coordination
opérateur sont nécessaires sans demander au propriétaire de jouer et sans
fabriquer une livraison pour libérer la chaîne.

## Sources clés

MapMechanicsLib installé : InitTowers3493–3620, ownership3641–3675,
statue3692–3844, durée3847–3850, capture7339–7455,
channel7466–7572, fin7608–7642, UI7648–7744.
GameLib installé : CapturePointCreate1266–1296, Enable1299–1321,
Disable1337–1349, getters1377–1420 et CapturePointLogic13619+.
GameLib_h : enums12–20 et structure540–556.
CASC effectdata : UseVehicleCommandeerInitialSet4514–4518,
UseVehicleCommandeerFinalSet4519–4525, UseVehiclePersistent5711–5727 ;
behaviordata TransformHeroVehicleBeingCapturedBehavior10621–10627.
Empreintes et chemins logiques dans le profil ; sources extraites et
résultats privés dans out/dragon364, à préserver hors du worktree avant clôture.
