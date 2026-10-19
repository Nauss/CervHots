# P2 — objectifs Volskaya build98348, candidat privé

Statut : diagnostic non publié. Ce document ne clôt pas le lot4. Aucun champ
objectif n'est encore ajouté à l'observation du coach ; `read()` refuse tant
que recette synchronisée et revue finale n'ont pas permis l'activation.

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
gate candidat activé UNIQUEMENT dans ce processus diagnostic privé. Gate produit
toujours fermé. La recette E2E fraîche demeure exigée ; les tests d'intégration
avec composant simulé ne constituent pas une preuve native supplémentaire.

## Sécurité et limites du candidat

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

Encore obligatoires : vérifier en pixels temps/progression/propriétaires,
contestation/perte/reprise, apparition/vie/durée/fin du protecteur et le chemin
normalisé de bout en bout. Mapping11/12, données du composant et durées doivent
être recoupés dans la nouvelle recette ; toute différence nécessite correctif,
rejeu et revue. L'ancien HUD donne des références de scénario, pas des lectures
objectifs manquantes inventées. Aucune extrapolation Dragon/Braxis, aucun champ
ennemi héros/cooldown débloqué, seuil0.75/silence/opt-ins inchangés.
