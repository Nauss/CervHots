# P2 — objectifs courants Volskaya build98348

Activation bornée à Volskaya98348 après recette réelle joueur+9IA et revue
indépendante. Les autres cartes, snapshots périmés, observateur et références
invalides restent refusés. Aucun champ tactique héroïque ennemi supplémentaire.
Source nouvelle `initdata_native_fields` : config C++ courante, pas blob fabriqué.

Recette réelle11 au gel ef9afd4 : court8frames puis DEUX fenêtres300s finies,
368 et367frames. Toutes les tentatives ont été rejouées en ordre exact avec les
horloges originales et tous les PNG relus par SHA ; aucune réception ancienne
n'est devenue une donnée actuelle. Deux cycles A/B, bleu→rouge→bleu sur A,
neutralisation, contestation/prolongations, attribution rouge du protecteur,
transfert réel propriétaire12→piloteIA7, vie/durée variables et fin ont été
observés. Pas de victoire bleue ni de contrôle humain de l'objectif inventés.
Les PNG A325/345 montrent35%/5% et0:24/0:07 ; les paquets acceptés donnent
34.781294/4.2818% et23.13745/6.51245s. L'affichage entier arrondi ne remplace
pas les valeurs natives. A300 montre83% mais ses deux acquisitions refusées
ne sont PAS transformées en preuve native. Le panneau disparaît A360 et le
paquet devient waiting/guardianunknown avec cooldown positif, pas détruit0.
Les preuves brutes et images sont privées hors Git. Le client11 a quitté la
partie à06:05:42 avant borne06:06, puis fermé normalement ; audio009 restauré.
Sans API coach, audio, Mumble, injection ou écriture mémoire pendant la recette.

## Sources actuelles, pas un dernier événement

Le lecteur `hotstate/objectives.py` suit la racine VM active déjà établie pour
le chrono. Profil strict `98348-objectives.json` : signatures natives et29
fonctions Galaxy de la même image ; noms, indices, bornes et empreintes sont
relus à chaque acquisition. Les fonctions `gt_*` du profil prouvent uniquement
les écritures des timers/variables ; aucun compteur d'invocation n'est lu.
Les scripts installés ont été extraits RO du CASC et empreintés sous le out/
privé du lot. `LibVLSK` SHA256 :
210ec2826f204912a6c3a4e108cc0382186392166d85e9db658b8e078d177da5.

Les getters actifs6073/6076 donnent les champs propriétaire/état de chaque
point ; stride113 octets,3 points. Le monitor6063, les fonctions6064–6071 et
les producteurs UI6117/6118 distinguent :

- propriétaire neutre (script0) ou équipe (script1/2 convertis0/1) ; une lecture
  absente ne devient jamais neutre ;
- état capturing/contested/empty/resetting ; `isContested` est un autre flag UI,
  pas un substitut de cet état. Empty peut garder un propriétaire ;
- contestation3 secondes, victoire45 secondes, valeurs Galaxy fixed12 ;
- pourcentage entier calculé avec division fixed12 AVANT multiplication100,
  puis troncature entière, comme le script. Exemple synthétique9/45 :19%,
  et non un arrondi Python20% ;
- cooldown/avertissement comme objets timer enregistrés, type19, génération,
  propriétaire, vtable, horloge et bornes vérifiés ; initialisé sans départ
  reste restant inconnu, pas un compte à rebours zéro.

Le protecteur vient de la variable unité courante affectée après création
VolskayaVehicle, pas d'un événement historique. Résolution de tag unité,
génération et propriétaire de création ou pilote courant ; bit UnitIsAlive,
PV maximum/dommages distincts de la progression du point. Sa durée vient du
composant actif VehicleDragonTimedLife, catalogue courant+nom, liste bornée des
instances ; conversion fixed16 native vers fixed12 Galaxy par décalage4bits.
La source UI affiche `FixedToInt(duration)+1`, pas la durée brute exacte.
Les parcours sont RO : aucune fonction du client n'est invoquée.

Premier diagnostic joueur partie10 : l'état inactif du point terminé conserve
un dépassement de45s, parce que AdvanceVictory incrémente d'un pas0.0625s AVANT
Award/Disable et ne reclamp pas ensuite. Valeur réelle184396fixed12, soit
45.0185546875s, supérieure au but184320 de76fixed, inférieure à un pas256.
Correction bornée : seul un point INACTIF admet jusqu'à un pas supplémentaire ;
un point actif, une valeur négative ou un dépassement supérieur restent refusés.
La première trace et ses refus restent intacts sous leur commit d'acquisition.

La courte recette suivante c41 montre un autre cas réel : le global protecteur
garde le tag d'index270/génération81, mais ce slot contient désormais génération158.
Le nouveau lecteur renvoie protecteur UNKNOWN, sans lire le propriétaire/PV/
composants du remplaçant et sans transformer inconnu en détruit/0. Les champs du
point B, indépendants et courants, restent lisibles. La durée/vie d'un protecteur
actif requiert TOUJOURS son propre tag/génération/propriétaire stricts.
Un troisième cas réel a été capturé par le pipeline complet550f : propriétaire
12 à la création, puis9 après embarquement IA, tag toujours valide. Les
propriétaires1..10 nécessitent désormais un CPlayer ACTUEL résolu, rôle humain/IA
et équipe0/1, et cette équipe doit correspondre au vainqueur du point courant
avant toute lecture de vie/durée active. Les autres propriétaires restent
refusés. Un tag recyclé reste inconnu AVANT tout accès au remplaçant.
FixedToInt natif (RVA2062460) a été désassemblé : SAR12 puisRET, troncature
pour nos valeurs positives. L'ancien HUD1:15 face au natif73.95 dans la courte
550f ne constitue PAS une égalité exacte de durée affichée ; la nouvelle recette
doit comparer les brackets et la cadence/animation réelle. On ne rajoute pas
une seconde au champ natif pour fabriquer cet accord.

La première découverte de11 a épuisé son plafond256MiB sans aucun décodeur,
puis le scout du seul segment raciné a échoué sans prétendre à une frame.
Le correctif lit maintenant les champs C++ InitData de la config COURANTE
GameMapPath, schéma775 : users107/82 stride3120, slots760/730 stride3880,
options userId/workingSet, contrôle/équipe/observe/héros, seed/cache versionnés.
Leurs descripteurs ET offsets natifs sont fingerprintés98348. Les trois chaînes
réelles (libellé humain privé, Muradin, Anduin) ont été comparées par l'opérateur :
inline UTF8+16, deux extents égaux ; les hypothèses pointeur/UTF16/UTF32 ont
échoué. Les représentations inégales/inconnues sont REFUSÉES, pas devinées.
Les16 slots incluent6 inactifs qui ne deviennent pas des observateurs actifs ;
les héros IA vides restent inconnus à ce stade et sont ensuite effectivement lus
dans les CPlayer/Unit/catalog du cœur existant. Aucun roster/composition injecté.
Le nouveau label distinct est `initdata_native_fields`, explicitement admis
avec les mêmes gardes natives/HMAC que `initdata_memory`, sans assouplissement
pour une autre source. `--native-context` relit/recontrôle la racine à CHAQUE
échantillon et traverse le VRAI snapshot/NativeReader/normaliseur/clé. Aucun
blob bitpacké artificiel, scan de tas, ancienne adresse, API ou capture en pause
n'est utilisé comme validation live. Le gate produit était fermé avant recette11.
La fonction active1239 ComputerPlayerInTeam (1→11,2→12) et le getter natif de vie
courante sont désormais eux aussi empreintés. Les tests de non-lecture du
remplaçant sont distincts des observations live.

`cerveau/objectives.py` projette seulement les champs typés et reçus frais du
même processus/match/perspective, sans tableaux inactifs, pointeurs, labels,
comptes ou information héros ennemi. Phase/point/contrôle et protecteur restent
séparés. La clé tactique tient compte du propriétaire/état/contestation, des
bandes de progression/vie et de l'urgence, pas de chaque tick de timer.
`capture_objectives_pipeline.py` exerce le vrai reader.snapshot → lecteur natif
→ normaliseur → tactical_key avec le contexte relu à chaque échantillon et le
gate candidat activé UNIQUEMENT dans ce processus diagnostic privé pendant la
recette11. Le gate produit est maintenant limité à Volskaya98348 ; les tests
d'intégration simulés ne constituent pas une preuve native supplémentaire.

## Sécurité et limites

Acquisition limitée à Volskaya, perspective humaine locale actuelle5v5 et
identité native de partie ; origine des scripts active, doubles lectures de
TOUS les accès acceptés, horloges mission et monotone≤0.125s. Ni cache de pointeur
ni état extrapolé. Comme les autres lecteurs, la relecture ne constitue pas un
verrou moteur ; ABA reste possible. Dumps roulants uniquement inspect_saved,
statut offline_non_atomic et jamais preuve d'une perspective joueur synchronisée.

Le collecteur `capture_objectives.py` capture avant/PNG/après et tous les accès
ordonnés, y compris les refus. PNG limité à la fenêtre du jeu au premier plan,
sans changement de focus. Source manifestée au commit gelé, fichiers neufs
sous out/, fenêtres≤300s, intervalle≥0.25s ; replay strict ordonné disponible.
Aucun coach/API/audio. Les traces/mémoires restent privées hors Git.

Exercé hors ligne : trois dumps conservés avant apparition du premier point
(008/037/065), sans prétendre observer une capture/protecteur absent des données.
Fixtures synthétiques séparées : états, perte/reprise/reset, corruption,
réutilisation génération, vie/durée protecteur, refus et readsets. Revue RO
préliminaire deleg_1f7adad3 : diagnostic-ready avec réserves, pas revue finale.

La recette11 recoupe les pixels temps/progression/propriétaires, contestation,
perte/reprise, apparition/vie/durée/fin du protecteur et le chemin normalisé.
Mapping11/12 et transfert au pilote courant ont été exercés ; les valeurs
natives restent distinctes des entiers HUD et de sa cadence d'affichage.
Le second cycle B ne prouve pas une seconde fin du protecteur. L'ancien HUD
n'invente aucune lecture manquante. Aucune extrapolation Dragon/Braxis, aucun
champ ennemi héros/cooldown débloqué, seuil0.75/silence/opt-ins inchangés.
