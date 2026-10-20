# Talents choisis natifs 98348 — portée qualifiée

Statut : producteur fonctionnel qualifié sur cette branche, avant intégration
main/remote. DragonShire uniquement : Sonya locale ; Arthas, Dehaka,
LtMorales et Tassadar en alliés. Ces rôles ne sont pas interchangeables dans
le gate. Aucun support toushéros/cartes ni carte produit livrée implicite.

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
hots_unpacked.bin, pas du fichier disque chiffré. Elles ont passé sur le
client courant pendant les recettes ci-dessous. Profil build98348
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
du même match :177comparaisons exactes,0écart. Aucun paquet Full dans ce diagnostic.

Le candidat actuel lit aussi HeroData+0x518/0x528, tableau stride12(tier,level,
type) suivi par la garde native de sélection c80e6e0 et HeroesLib2022.
Il n'utilise pas une séquence fixe1/4/7/10. Un palier connu sans options
résolues reste unknown, pas « non choisi ». Niveau/ID/palier invalide refuse.

NativeTalentChoices fournit un receipt enprocessus lié au match, héros,
racinesession et génération locale du cœur. La projection cerveau/talents.py
ne conserve que joueur local et alliés anonymes, paliers/niveaux/statuts/colonnes et
IDs sélectionnés ; aucun catalogue offert ni pointeur. La vraie clé tactique
varie au choix/reset et pas à chaque lecture du même état. Le hook famille
est dans NativeReader avant le dernierchrono (pas dans reader.py).

capture_talents_pipeline.py exerce read_current→normaliseur→tactical_key
avec le WHOLE8192/1MiB/125ms et recheckcontexte. --qualified-talents utilise
le gate réel du profil, sans élargissement candidat. --candidate-talents et
--candidate-allies sont des modes de recherche séparés, jamais une qualification
du catalogue. Les sources de capture10871ff/1d9f27d/2502773 restent figées
séparément ; les changements de politique ne réécrivent pas leur provenance.

## Recettes réelles et limites

- V2 local1d9f27d réellement exercée day002 :68Full/103acquisitions,
  103rejeux stricts sur50sources exactes ;35refus déchirés conservés,
  aucun refus budget. Max2930lectures/93400octets/47msquantifiés.
  Baseline15FullN1sanschoix, puis choix BarbarianWarPaint tier1/colonne2,
  puis12Fulldansunprocessusfroid. Niveaux natifs1/4/7/10/13/16/20 lus.
  Référence replayday002 :67comparaisons certaines,1fenêtre de transition
  conservativement ambiguë (≤125ms),0écart. Aucun accord inventé sur cette fenêtre.
- V3 étend la même source aux cinq alliés, après filtrage équipe AVANT
  toute lecture de talents. Le cœur scelle allied_generations ; chaque
  ligne est liée au héros/niveau/génération de ce roster courant.
  Un héros non qualifié ou une branche non normale est unknown/tiers=null,
  jamais une liste « aucun talent ». Un paquet entièrement unknown est refusé.
  Recette2502773day003 :22Full/46tentatives,46rejeux stricts sur50sources,
  110observations d'acteurs ;110comparaisons au tracker indépendant,0écart,
  0ambiguïté,0acteurunknown dans ces cas. Les24déchirures sont conservées.
  Max4361lectures/114949octets/47msquantifiés ;0lecture de table talents
  ennemie dans les readsets. Le tableau visible confirme5lignes/icônesN1,
  sans hoverlabels alliés : les IDs sont recoupés par le tracker, pas par les pixels.
- --candidate-allies est un opt-in de recherche explicite : il tente la source
  commune sur les héros ALLIÉS du match, jamais les ennemis. Il ne qualifie
  pas tout le catalogue : les qualified_cases du profil bornent chaque rôle.
- Les replays de référence sont NORMAL/postmatch, protocole91756 shim98348
  explicitement signalé. Ils ne remplissent jamais la source live ni ne lui
  accordent une nouvelle fraîcheur. Alias héros issus des naissances tracker,
  seed/cache et IDs/équipes recoupés indépendamment.
- Le code final est aussi exercé par rejeu ordonné du chemin à scopes produit
  réels, sans override candidat :46issues identiques, dont22Full.
  Ce n'est pas une nouvelle acquisition ni une mesure de performance fraîche.
- Les sélections alliées réelles observées sont N1 ; les autres paliers sont
  décodés par le même getter paramétré et restent explicitement non choisis.
  Aucun exercice exhaustif de tous talents/transformations/arbres spéciaux.
- Reset/changement de clé, absent/invalide/unknown, observateur, stale,
  filtrage ennemi et génération sont exercés par tests hermétiques. Aucun
  reset live ni nouvel observateur réel n'est revendiqué par ces recettes.
- Les coûts ci-dessus sont standalone talents + cœur existant, PAS une somme
  ni une validation du pipeline futur composé avec Dragon/CD. L'intégrateur
  doit mesurer le chemin combiné sans augmenter les plafonds.
- Aucune généralisation toushéros/cartes.
- Une entrée non sélectionnée n'est pas un palier absent : unselected_tiers
  utilise les paliers réellement proposés ; source illisible reste unknown/refus,
  jamais une liste vide supposée.
- L'indice zéro est une entrée valide ; 0xffffffff est la sentinelle native
  de sélection absente. Tier0 est réservé/invalide dans ce premier candidat,
  à requalifier pour toute famille non standard avant support.

Contrat public : talents.players contient exactement les cinq membres alliés,
avec status observed/tiers ou unknown/tiers=null. Chaque palier connu porte
tier, required_level, status selected/unselected/unknown, slot et catalog_id.
Les champs internes, générations, reasons et options offertes ne sont pas projetés.

Les reçus, manifestes et audits exacts restent sous out/day-fleet/2026-10-20,
hors Git ; aucun raw/pointeur/nom privé n'est publié. La clôture de préparation
ne vaut pas intégration ni livraison de t_8e0efa84 : ces gates restent séparés.
