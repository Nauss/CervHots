# Talents choisis — candidat natif 98348

Statut : candidat Full en recette, publication fermée ; diagnostic local Sonya/Dragon
exercé, aucun support toushéros/cartes.

## Source sémantique

GameLib installé (extraction CASC locale du 18 octobre 2026), fonction
TalentsChooseTalentForPlayer, lignes11833–11865 : écrit lv_selection,
émet TalentChosen, appelle PlayerAddTalent puis TalentTreeSetSelectedHeroTalent.
Le bitset PlayerHasTalent n'est donc pas la sélection persistée : un talent
accordé automatiquement peut y figurer sans choix. Aucun delta antérieur
n'est nécessaire pour lire la source sélectionnée étudiée ici.

Native1002 → setter sélection (RVA0xb10600) recherche l'entrée Hero dont
les champs tier+8/column+12 correspondent aux arguments. Native1003 →
setter index (RVA0xb10720) écrit le tableau courant joueur×32paliers.
Native1004 → getter index (RVA0xb0f720) lit exactement ce tableau.
Native1005 → getter colonne (RVA0xb0f640) résout le même index dans
l'arbre du Hero actif. Les exports Ghidra readOnly/noanalysis restent privés
sous out/talents-native ; aucun appel natif n'est effectué par Python.

Résolution : CPlayer+0x50 → descripteur Hero / index ushort+0x40 ;
racine catalogue+0x148 → table+0x48, borne+0x38 → données Hero non taguées ;
count+0x500 / array+0x510, pas0x40. Entrée = lien talent / tier / colonne.
Le nom est résolu depuis le lien catalogue et son objet chaîne, pas depuis
une traduction ni une option choisie arbitrairement. Entrées lazy/taguées,
IDs absents, sélections hors palier et mémoire partielle sont refusés.

Les signatures sont dérivées de l'image mappée historique existante
hots_unpacked.bin, pas du fichier disque chiffré. Elles doivent encore passer
sur le client courant avant toute revendication de recette. Profil build98348
strict, aucune compatibilité interbuild ni atomicité moteur revendiquée.

## Acquisition

capture_talents.py --preflight n'ouvre jamais de processus. Seul le pilote
coordonné peut utiliser --live sur le commit exact gelé. La lecture locale
comprend contrôle de contexte natif courant, racine active/match, perspective
humaine non observateur, héros/équipe, tag/génération/propriétaire, signatures,
rechecks et intervalle mission. Budget WHOLE8192lectures/1MiB/125ms.
Aucun talent ennemi n'est lu. Les états du héros mort ne sont pas convertis
en absence de talents. Le niveau du héros est distinct du niveau requis du palier.

La trace privée archive les ticks monotones et les résolutions de carte du
contexte pour le rejeu strict sans dépendre du cache local. Rejouer l'archive
n'accorde jamais de fraîcheur live. Aucun PNG/OCR/GUI/son/API/coach.

## Diagnostic réel et candidat Full

Révision10871ff : troisfenêtres30s du pilote day001 Sonya/Dragon,177/177
diagnostics acceptés et177/177 rejoués dans l'ordre sur sources exactes archivées
(33sources hachées). Première acquisition sans historique : quatrechoix déjà
présents ; transition niveau13/tier5/colonne1 vers BarbarianMysticalSpear,
47samples avant puis12après, et59/59 dans un processus ultérieur froid.
Le pilote a comparé « Lance mystique » au tableau visible ; les alternatives
offertes n'ont pas été publiées comme choix. Référence replay indépendante
du même match à vérifier séparément. Aucun nouveau paquet Full dans ce diagnostic.

Le candidat actuel lit aussi HeroData+0x518/0x528, tableau stride12(tier,level,
type) suivi par la garde native de sélection c80e6e0 et HeroesLib2022.
Il n'utilise pas une séquence fixe1/4/7/10. Un palier connu sans options
résolues reste unknown, pas « non choisi ». Niveau/ID/palier invalide refuse.

NativeTalentChoices fournit un receipt enprocessus lié au match, héros,
racinesession et génération locale du cœur. La projection cerveau/talents.py
ne conserve que joueurs locaux anonymes, paliers/niveaux/statuts/colonnes et
IDs sélectionnés ; aucun catalogue offert ni pointeur. La vraie clé tactique
varie au choix/reset et pas à chaque lecture du même état. Le hook famille
est dans NativeReader avant le dernierchrono (pas dans reader.py).

capture_talents_pipeline.py exerce read_current→normaliseur→tactical_key
avec le WHOLE8192/1MiB/125ms et recheckcontexte. Son gate candidat est ouvert
seulement dans le processus diagnostic explicite ; VALIDATED_SCOPES reste fermé
dans le produit jusqu'aux recettes exactes. Les sources du diagnostic10871ff
sont figées séparément ; elles ne sont pas remplacées par le nouveau code.

## Limites avant intégration

- Acquisition Full actuelle et niveau requis encore à exercer réellement.
- Normaliseur/clé/receipt exercés sur fixtures seulement à ce stade.
- Alliés non implémentés ; local seulement. Aucune généralisation toushéros/cartes.
- Une entrée non sélectionnée n'est pas un palier absent : unselected_tiers
  utilise les paliers réellement proposés ; erreur de lecture reste refus.
- L'indice zéro est une entrée valide ; 0xffffffff est la sentinelle native
  de sélection absente. Tier0 est réservé/invalide dans ce premier candidat,
  à requalifier pour toute famille non standard avant support.

Le résultat de ce diagnostic n'est ni une préparation complète prête pour
intégration ni la livraison de t_8e0efa84.
