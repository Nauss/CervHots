# P2 — sanctuaires et Chevalier Dragon, build98348

**Date :** 19 octobre 2026 · **Statut :** champs natifs qualifiés par20/22,
activation strictement DragonShire/build98348 proposée en revue finale.
Intégration/main/distant restent à vérifier avant de déclarer la livraison.

## 1. Résultat exercé et limites

`hotstate/dragon.py` lit les globals de la VM ACTIVE et les unités effectives,
pas les compteurs d'invocation des triggers. `inspect_saved()` a été exécuté
sur le vrai module/tas Dragon `live-a`, capture roulante historique conservée
hors Git. Résultat : phase waiting, sanctuaires sun/moon de types respectifs
DragonShireShrineSun et DragonShireShrineMoon, neutres et désactivés,
respawn15.875s. Ce résultat n'est NI une acquisition atomique NI un nouvel
instant live. Les références statue/dragon de cette ancienne capture sont
recyclées ; aucune lecture des propriétaires/vitales du remplaçant n'est permise.

Recette20 native, sansPNG :405acquisitions dont347diagnostics acceptés,
56déchirures refusées et2refus de cohérence, aucun dépassement de budget.
Sun et Moon ont captures/pertes/contestations/reversions effectivement observées,
694observations de propriétaire recoupées au tracker indépendant du même match,
identité seed/cache et un humainStitches local+9IA sans observateur confirmés.
Premier marqueur canalisation vrai observé168.625–171.375s ; activation tracker
171.625s, chevalier natif actif ensuite, contrôle joueurIA5 ; décès tracker202.75s
dans la borne native conservatrice(175.6875,206.625]. Le pilote IA n'émet pas
une commande locale : cette limitation ne devient pas une preuve de clic humain.
Les405traces/horloges originales ont été rejouées strictement sans écart ;
les nouveaux reçus de rejeu ne rendent pas ces observations actuelles.

Les fixtures couvrent capture, neutralisation, perte, contestation, état
inconnu/désactivé, canalisation, véhicule actif et fin. Elles ne prouvent PAS
ces transitions en partie. L'ancienne capture isolée ne peut pas compléter
la recette. Aucun transfert de qualification Volskaya/Braxis.

`DragonObjective.read()` est maintenant borné à DragonShire/build98348,
dans le vrai NativeReader puis le normaliseur et la clé tactique. Les autres
familles/cartes ne sont pas débloquées. Fermer l'allowlist ou fournir une carte
non qualifiée refuse `recette_dragon_absente`. Le PREMIER collecteur privé reste
explicitement `accepted_diagnostic_NOT_PRODUCT`, pas Full.
Le `capture_dragon_pipeline.py` a, séparément, obtenu des Full candidats sur le
vrai `hotstate.live.read_current` en21 :13fenêtres,180s,659acquisitions,
472Full candidats,185lectures déchirées et2objectifs absents, sans dépassement
de budget selon le manifeste opérateur. Cela prouve la traversée consommateur,
pas la publication :21 précède le correctif de confidentialité des beacons.
La commande locale positive UseVehicle n'est pas encore recoupée ; des morts
locales et courses IA ne sont jamais renommées en succès humain.

Recette22 sous le correctif185376b :7fenêtres,120s,435acquisitions,
303Full,131lectures déchirées et1objectif absent ;0budget. Auteur et opérateur
ont rejoué les435traces/TOUTES horloges sans écart ; l'opérateur sur chaque
Python3.12/3.14. Maximum WHOLE2544lectures/89556octets/32ms, incluant contexte,
cœur, objectif, rechecks, normalisation et clé.606propriétaires recoupés sans
écart au replay de la même partie ;1humainStitches+9IA,0observateur, seed/cache
identiques.73observations beaconCURRENTtrue et533unknown ; les1066intervalles
de compteurs/états cachés ou désactivés sont absents du readset physique.

Canal IA VISIBLE réellement normalisé :4booléenstrue à360.8125,361.375,
361.6875,362.25s, tous statueCURRENTtrue. La cible a le même index/génération
natif et tracker ; activation363.4375s par joueurIA2, puis décès428.4375s,
dans la borne native(397,435.875]. Le helper du protocole de repli encode les
tags sur18bits de génération contre22dans game/native : le rapprochement
utilise EXPLICITEMENT index/génération, pas une fausse égalité numérique.
Effet channeled UseVehiclePersistent → Initialapply du marqueur → Finalremove,
références ci-dessous ; aucune durée de canalisation ne vient du marqueur5s.

Une commande LOCALE TargetUnit sur cette même cible à354.3125s est confirmée,
mais le pilote estIA2, pas local1 : aucune causalité cliclocal→canalIA et aucune
prise de contrôle humaine ne sont validées. Ce critère expérimental additionnel
reste NONPASS. Il n'est pas confondu avec le DoD de lecture de canalisation IA
visible, apparition et fin effectivement recoupées. Pas de contestation PUBLIQUE
positive observée en22 : les états/captures privés20 ne sont pas promus en Full.
PC/menu/audio rendus avant19:23, aucune23 ni nouveau budget implicite.

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

Les sanctuaires Sun/Moon sont eux-mêmes FogVisibility=Visible (Moon hérite
deSun), mais leurs unités DISTINCTES DragonballCaptureBeacon sont Dimmed
(unitdata1393–1401). Ni le propriétaire public du sanctuaire, ni une animation
envoyée à PlayerGroupAll ne qualifient CURRENT sur le beacon. Après release21,
le chemin consommateur vérifie séparément CURRENT pour chaque beacon actif,
AVANT toute lecture des compteurs/états de progression. Ces champs cachés ne
sont ni lus ni ajoutés à la cohérence : leur mutation ne peut pas faire tomber
la famille optionnelle et révéler indirectement une activité via la clé.
False/unknown donne state=unknown, contested=null et compteurs=null ; le
propriétaire PUBLIC du sanctuaire reste connu. Une référence non résolue garde,
elle, owner=null. Le normaliseur exige capture_current_visible=true pour tout
état de capture actif, et une preuve explicite false/null pour combiner un
propriétaire connu à une progression inconnue. Ce drapeau ne franchit pas la
projection. Des changements de contestation cachée ne changent pas la clé.
Le diagnostic privé sans perspective conserve son ancienne sémantique ; il ne
peut acquérir un reçu produit. Ces règles sont exercées sur fixtures ET sur
les Full22 : champs courants retenus, champs non qualifiés réellement non lus.

Phases MapMechanicsLib : Idle0, ObelisksWarning1, ObelisksAvailable2,
DragonRampaging3. Les timers start/respawn/warning restent distincts et
vérifient registre, type19, génération, propriétaire, vtable et bornes.
Aucune origine HUD ou échéance exacte n'est reconstruite depuis un replay.

La statue capturable doit être VehicleDragon, possédée par11/12, avec les
deux propriétaires publics courants de la même équipe. Une progression de beacon
inconnue n'efface pas ce contrôle public et n'interdit pas à elle seule la statue.
Le marqueur fini
TransformHeroVehicleBeingCapturedBehavior est ajouté par InitialEffect de
UseVehiclePersistent et retiré par FinalEffect, succès ou interruption.
Sa durée catalogue5s n'est PAS le temps de canalisation3s configuré par
InitTowers ; seul un booléen en est tiré. Le nouveau chemin consommateur
ne lit ce marqueur que si le prédicat natif CURRENT est vrai pour la statue,
avec signatures de visibilité et identité locales revérifiées. False/unknown
reste channeling=null, sans lecture du marqueur. Le catalogue effectif
VehicleDragon déclare FogVisibility=Visible (unitdata3106–3107) ; cela ne
débloque aucune visibilité héroïque ni une carte entière. La projection
exige également l'assertion CURRENT dans son reçu signé, jamais un flag connu
ou un simple propriétaire allié. Les4true normalisés22 exercent ce chemin.

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

`capture_dragon_pipeline.py` emploie réellement `hotstate.live.read_current`
avec les callbacks consommateur `cerveau.state.snapshot` et `tactical_key`.
Contexte, cœur natif, familles optionnelles, rechecks, normalisation et clé
partagent le budget WHOLE. Sa seule ouverture de gate est locale au processus
diagnostique, via l'opt-in explicite `--candidate-dragon`. Un cœur seul ou une
famille omise n'est jamais Full. Le manifeste inclut aussi le normaliseur,
la clé et kb/data/map_timings.json, dépendance du nommage de carte.

## 4. Qualification, limites et publication

1.20 qualifie le décodage natif des deux sanctuaires, captures/pertes/contestation
   et premier cycle Dragon ;22 qualifie le vrai consommateur corrigé, les scopes
   CURRENT et une canalisation IA visible du même véhicule, activation et fin.
2. Les preuves privées/readsets/replays sont préservés hors Git dans le dossier
   durable de la carte ; pas de nouvelle fraîcheur depuis un rejeu historique.
3. Aucun PV/XY/CD/talent/pilote ennemi ni référence brute dans la projection.
   Source incertaine → unknown, pas neutral/ready/destroyed inventé. Le chemin
   de capture visible garde sa qualification par getter/classe et CURRENT,
   sans prétendre qu'une contestation publique positive a été observée en22.
4. Le contrôle local effectif du véhicule reste non qualifié ; la commande sur
   la cible est une tentative, pas le déclencheur démontré du canal IA.
5. L'activation finale est une proposition à contre-revoir DISTINCTEMENT du
   verdict185376b. Aucun PASS implicite du delta allowlist/docs. Main/push et
   tests sur main restent obligatoires avant clôture ; aucun coach/audio requis.

L'ancien opérateur t_d6e15259/default a clos Volskaya après19/24parties.
Le soutien ciblé Dragon t_7d4211b0/default a effectué20/21/22 puis terminé
son seul service GUI/revue borné, sans clore la carte produit. Il a rendu le
menu, l'audio et la caméra avant l'analyse hors ligne. Les sept cartes
produit ne sont ni décomposées ni dupliquées. Cody ne prend pas la GUI.

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
