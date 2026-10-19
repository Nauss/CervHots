# P2 — évaluation bornée Volskaya, talents et cooldown local

**Date :** 19/10/2026 · **Statut :** PARTIEL, pas une livraison du lot 5.

## 1. Verdict et périmètre

Deux recettes privées Volskaya build98348, joueur local Balafré/Stitches et neuf
IA, zéro observateur, ont été exercées. Le lecteur reste Python. Aucun nouveau
champ n'est activé pour le coach : `hotstate.battlefield.VALIDATED_MAPS=()`.
Les preuves des talents/CD sont des prototypes isolés ignorés sous `out/`, pas
les cartes de production correspondantes ni une couverture tous héros.

## 2. Camps et structures : progrès réel, couverture limitée

Huit fenêtres métier de 6/30s ont produit 152 acquisitions : 41 paquets Full
acceptés, 66 refus de cohérence native et 45 paquets sans section battlefield.
72 PNG ont été enregistrées sur 76 images tentées. Seulement QUATRE paires
avant/PNG/après ont deux acquisitions Full acceptées : ne pas confondre ces
nombres avec 41 doubles brackets. Zéro refus de budget et zéro fuite de champ
sensible ennemi dans le normaliseur. Limites inchangées : 8192 lectures, 1Mio,
125ms par acquisition complète ; maximum observé 7387 lectures, 195513 octets,
78ms. Aucun relevé de transport de 120s n'a été refait.

Camp tourelle bas gauche, index1 : disponible CURRENT, effectivement vaincu et
capturé, minuterie positive, puis disponible avec un nouveau cycle de défenseurs.
Le tracker de la même partie contient les défenseurs et leurs nouvelles
naissances ; la collecte respawn commence APRÈS l'expiration. Elle prouve la
succession entre fenêtres, pas l'instant exact d'apparition dans une acquisition.
Un retrait physique puis retour donnent Unknown (sans propriétaire/cycle/timer
exposés) puis CURRENT/capturé. Les paires PNG de ces deux états ont été relues.

Deux forts alliés du catalogue ont des séries de vie décroissante puis des flags
natifs de destruction, recoupés au tracker par type/équipe/position statique.
La sélection visible montre notamment 16129/17380 puis 10913/17380 dans deux
vraies paires acceptées. Un fort détruit n'est pas déduit d'un slot absent.
Les autres fenêtres ont souvent un seul côté Full : pas de prétention d'atomicité
moteur, ni d'identification d'un remplacement par seule disparition.

Manques du lot 5 : transitions des camps tourelle2, siège3/4 et soutien5 ;
qualification complète des types de structures annoncés, remplacement/type/tag/
génération effectivement observé lorsqu'applicable ; bouclier consommé et cas
spéciaux de vie affichée. Les 90 entrées statiques candidates ne constituent pas
90 cycles de vie testés. Le lot 5 reste non livré, main non modifié par ces recettes.

## 3. Vie du composant versus numérateur HUD

La chaîne CASC `TargetInfoPanelUnitStatusBarTemplate` utilise un
`UnitStatusShieldedHealthLabel`, pas le simple label de vie. Registre de type,
factory, constructeur et vtable ont été suivis hors ligne jusqu'à la méthode
d'actualisation : elle additionne les vies/boucliers COURANTS avec leurs ratios
natifs et un éventuel bonus comportemental, mais son dénominateur est le maximum
DE VIE résolu. Ce n'est pas automatiquement la paire « effectif/effectif_max »
du getter Galaxy, ni la somme des deux maxima.

Les trois anciennes paires de noyau plein/croissant et les deux nouvelles paires
de fort endommagé sont compatibles avec leurs composants réellement acquis.
Cela n'autorise pas une formule universelle « vie+shield » sans les branches de
scaling/bonus. `health_percent` candidat reste un pourcentage de vie DE COMPOSANT,
pas une promesse d'égalité au rapport entier animé du HUD. Les branches non
observées sont maintenues comme limites, pas compensées par un bouclier supposé.

## 4. Deux petits prototypes natifs locaux exercés

Sources suivies avant la sonde : Galaxy `TalentsChooseTalentForPlayer` →
`PlayerAddTalent`, getter `PlayerHasTalent` et catalogue actif ; pour le CD,
`Cost.Cooldown.Location` et `UnitGetCooldown` → liste active de l'unité locale.
Aucune fonction du client n'est appelée, aucune injection/hook/écriture.

Sur la seconde partie, quatre fenêtres donnent 86/86 acquisitions acceptées et
43 doubles paires PNG :

- ensemble de talents possédés vide au niveau1, puis ajout exact de
  `StitchesPatchworkCreation`, choisi manuellement comme « Morceaux choisis » ;
  même choix dans `TalentChosen` du tracker à 44.75s mission ;
- `StitchesSlam`, lien réellement rencontré `Abil/StitchesSlam` : CD nul,
  lancement normal de Choc, valeur positive7.875s, décroissance et retour0 ;
  animation et compteur8 visibles sur le premier PNG, puis icône sans compteur.

Coût maximal du prototype dans cette recette : 1225 lectures, 19834 octets,
16ms mesurées avec horloge quantifiée. Ces maxima d'une sonde étroite ne sont
PAS le coût d'ajouter tous les talents/CD au pipeline produit composé.
`ready` ne veut dire que CD nul, pas mana/portée/CC/légalité complète du cast.
Les valeurs internes ont une précision1/65536s, distincte du retour Galaxy
tronqué au fixed4096. Charges, CD stockés joueur, autres héros et modificateurs
restent hors de cette preuve.

Le bitset `PlayerHasTalent` signifie « possédé », pas « tous choisis manuellement » :
un essai antérieur au niveau15 avait déjà `StitchesFishingHook` sans choix de
palier1. La preuve manuelle repose sur le delta + GUI + tracker. Cet essai a aussi
conservé 18/18 refus `aucune_simulation_active` après fin réelle de partie :
aucun ancien résultat n'a été recyclé en observation fraîche.

## 5. Reproductibilité, coût et stratégie

Les accès ordonnés et horloges Full de la première recette ont été rejoués
152/152, les 72 PNG hachées. Les prototypes des deux parties donnent 120/120
rejeux d'accès/champs, 60 PNG hachées ; leurs temps de calcul rejoués ne sont
pas des reçus live ni une reconstruction de l'horloge de production.

Un contre-audit a d'abord réussi seulement66/152 (86 échecs) : le bundle de 33 sources omettait
`cerveau/__init__.py`. Avec la racine main comme dépendance de secours, Python
importait son ancien package régulier au lieu du normaliseur gelé, et la trace
d'horloge n'était plus consommée intégralement. Le rejeu autonome a été rétabli
avec l'arbre complet du commit de capture et les 33 fichiers capturés inchangés.
Le manifeste commun des collecteurs Full inclut désormais cet initialiseur,
avec test de régression RED→GREEN. Les captures historiques ne sont pas réécrites
ni prétendues issues du nouveau manifeste.

Le profil empirique conserve séparément lectures/octets, durée totale et
enveloppes des lectures instrumentées. Ces temps sont quantifiés et incluent
l'instrumentation : ils n'isolent pas un hotspot CPU Python. Aucune réécriture
Rust globale n'est justifiée par ces mesures. Le principal reste la qualification
sémantique, la cohérence et la couverture, pas une promesse de gain par langage.
Mémoire native en premier, écran comme vérité de contrôle/secours identifié.
Aucun OCR supplémentaire n'était nécessaire pour ces deux preuves natives,
aucun appel vision distant par image n'a été ajouté au collecteur.

Sources brutes, commandes, replays, empreintes, revues et résultat structuré sont
conservés localement hors Git. Pas de matière mémoire privée dans ce document,
ni API coach/TTS/Mumble/son. Le client propriétaire est rendu au menu avec audio
restauré et contrôlé par l'opérateur. Une partie privée et la lecture seule ne
constituent pas une garantie de conformité Blizzard ou d'absence de sanction.
