# Étude — REA pour l'accès aux infos de jeu en direct

**Question :** peut-on utiliser [REA](https://github.com/morluto/rea) pour accéder
aux informations de la partie **pendant** le jeu, plutôt que de se contenter des
pixels de la capture d'écran ?

*Sous-projet CervHots · état : étude écrite, pas encore d'expérience exécutée ·
dernière MAJ : 10/10/2026*

---

## 1. REA, c'est quoi (et ce que ce n'est pas)

REA (*Reverse Engineer Anything*) est un **serveur MCP + CLI** qui branche un
agent de code (Claude Code, Codex, Cursor, Gemini CLI…) sur une chaîne d'outils
de reverse engineering. Tout tourne **en local**, licence MIT, `npx rea-agents setup`.

Cibles couvertes (d'après le README) :

| Cible | Ce que REA renvoie | Outil requis |
|---|---|---|
| Binaires natifs | pseudo-code, asm, strings, symboles, appels, références | **Ghidra, Hopper ou IDA** |
| Apps JS / Electron, sites web | le code réellement exécuté | connexion de debug (CDP) |
| Assemblages .NET | décompilation | intégré |
| APK Android | manifeste, classes, méthodes | JADX |
| ELF / EVM / crashes Linux enregistrés | layout, désassemblage | pwntools, GDB |

**Ce que REA n'est pas :** un lecteur d'état de jeu en temps réel. Sur un binaire
Windows natif, il fait de l'**analyse statique** (le volet « runtime » couvre le
web via CDP et les crashes Linux déjà enregistrés). REA ne *donne* pas les infos
pendant la partie : il sert à **trouver où elles vivent** dans le client —
structures, offsets, fonctions du HUD — pour ensuite écrire le petit lecteur qui,
lui, tournera pendant la partie.

## 2. Le vrai problème : où est l'état live ?

L'état qu'on veut (timer, positions des héros, niveaux, PV, ults) n'existe qu'à
deux endroits :

- **à l'écran** (le HUD) — ce que le plan actuel capture ; légal, robuste, mais
  limité à ce qui est dessiné et à ce qu'une IA arrive à en lire ;
- **en mémoire du processus** `HeroesOfTheStorm_x64.exe` — précis, structuré,
  complet (y compris le hors-écran : positions exactes, cooldowns, PV).

Les autres chemins sont déjà écartés : pas d'API live Blizzard pour HotS, le
protocole réseau est chiffré, les replays ne sont écrits qu'en fin de partie.

→ REA est l'outil de l'étape qui coince : comprendre le binaire pour extraire
l'état mémoire. Si ça marche, la vision ne sert plus qu'à la nuance sémantique
(brouillard, lecture de situation) et le coaching devient factuel.

## 3. Environnement vérifié sur la machine (10/10/2026)

- Jeu installé : `C:\Program Files (x86)\Heroes of the Storm` ✔
- Binaire live : `Versions\Base98348\HeroesOfTheStorm_x64.exe` — **x64**,
  sans symboles publics. (L'exe à la racine n'est qu'un launcher x86.)
- Plusieurs builds cohabitants (`Base97039` → `Base98348`) : le jeu se met à
  jour, **les offsets bougeront à chaque patch**.
- Données de jeu : `HeroesData\` (stockage CASC : config, data, hero, indices) —
  les données statiques (héros, talents, valeurs) sont déjà exploitables via
  heroprotocol / dumps de données, sans REA.
- Node v26.7 ✔ (`npx` dispo, REA demande Node 22+).
- **Ghidra / Hopper / IDA absents** → à installer pour l'analyse native
  (Ghidra : gratuit ; Hopper : payant, REA peut l'installer avec accord).

## 4. Risques — le blocage n'est pas technique

1. **ToS / anti-triche Blizzard (décision à prendre avant l'étape 3).**
   Lire la mémoire du client viole les conditions d'utilisation de Blizzard, et
   Warden (l'anti-cheat) peut détecter les ouvertures de processus en lecture.
   Risque réel : **ban du compte**. L'analyse statique du binaire (étapes 1–2) ne
   touche pas le jeu en marche et ne déclenche rien ; c'est la lecture live qui
   pose la question. Usage strictement personnel/local : à trancher sciemment.
2. **Volatilité des offsets.** Chaque patch déplace les structures : prévoir des
   signatures (pattern scans) re-derivable, ou une re-dérivation semi-auto après
   chaque mise à jour — sinon maintenance à chaque patch.
3. **Effort.** Binaire x64 massif, sans symboles. REA + agent rend la chose
   tractable (pseudo-code + recherche guidée), mais c'est la phase la plus longue.
4. **Bénéfice réel.** Même en cas de succès, la capture d'écran garde un rôle
   (comprendre la situation, le brouillard) ; la mémoire apporte les **faits**.

## 5. Protocole d'expérience — et critères go/no-go

| Étape | Contenu | Critère |
|---|---|---|
| **0 · Outillage** | Installer **Ghidra** (gratuit) + `npx rea-agents setup` (enregistre le MCP dans l'agent choisi) | Go si accepté : install d'un gros outil + modif de la config d'agent |
| **1 · Recon statique** | REA sur `HeroesOfTheStorm_x64.exe` : strings, fonctions du HUD (formatage du chrono mm:ss, tables de héros = ancres), carte d'appels | Livrable : note de recon + liste d'ancres candidates |
| **2 · 3 ancres** | Localiser en pseudo-code : **timer de partie**, **niveaux d'équipe**, **position d'un héros** | Go si ≥ 2 ancres localisées avec leurs structures |
| **3 · Lecteur live** | *Décision ToS/Warden d'abord.* Si go : mini-reader x64 (ReadProcessMemory) qui boucle sur les champs pendant une partie vs IA, croisé avec capture écran + replay heroprotocol | Go si les valeurs lues = vérité terrain |
| **4 · Arbitrage** | Mémoire comme source principale (vision en secours) ou retour au plan pixels seul | Décision de conception |

## 6. Verdict

**REA est utilisable et bien choisi** pour l'étape qui coince : Node est bon,
l'outil est gratuit et s'installe ici, et son modèle (agent + decompilation
guidée par pseudo-code) est exactement adapté à « trouver l'état de jeu dans un
binaire sans symboles ». Il ne fournit pas le live par lui-même : le live viendra
d'un petit lecteur mémoire maison que REA rend réaliste à écrire.

**Le vrai point de décision est réglementaire** : la lecture mémoire pendant le
jeu (ToS + Warden, risque de ban). Les étapes 1–2 (statique) sont sans risque et
peuvent partir tout de suite ; l'étape 3 attend une décision explicite.

---

## 7. Progression — 10/10/2026 (suite : objectif « toutes les stats en direct »)

Objectif élargi : *peu importe le moyen, sortir toutes les stats nécessaires de
HotS en direct pour l'agent de décision.* Bilan de l'exploration :

- **Le replay contient déjà presque tout** (vérifié sur 2 parties réelles avec
  l'extracteur `hotstate/`) : niveaux (`LevelUp`), talents (`TalentChosen`),
  morts localisées avec tueurs (`PlayerDeath`), XP par fenêtre de 60 s,
  captures de camps, chutes de structures, **objectifs de map**
  (`TributeCollected`, `RavenCurseActivated`…), positions des héros toutes les
  ~15 s, pings/chat, score final. Voir `hotstate/README.md` pour l'inventaire.
- **Vérifié et tranché : le `.StormReplay` n'existe qu'après la partie.** Le
  fichier n'arrive dans `Documents\...\Replays\` qu'une fois l'écran MVP passé ;
  pendant la partie, les données vivent dans des fichiers temporaires de
  reconnexion (`%LOCALAPPDATA%\Temp\Heroes of the Storm\TempWriteReplayP1\`),
  au format blob **non documenté**, effacés à la fermeture du jeu. Le forum
  Blizzard le résume ainsi : « Replay files aren't created until after the
  match has finished, so there isn't a way to get replay data during a live
  match without breaking the EULA. » **La piste « replay partiel » est
  abandonnée** (`live_probe.py` retiré).
- **Petit bonus gratuit** : parmi ces fichiers temporaires,
  `replay.server.battlelobby` (parsable, cf. Heroes.StormReplayParser) donne
  map, compositions et identités **en direct** — c'est ce que lit HotsStats.
  Utile pour le contexte du coach, pas pour les stats de match.
- **REA + Ghidra = plan B**, à activer **seulement si la vision s'avère
  insuffisante**. Prérequis déjà satisfaits : Java 21 présent, Node 26 présent ;
  il manque Ghidra (gratuit) et l'enregistrement du MCP. La décision
  ToS/Warden (étape 3 du protocole) reste inchangée.
- Hiérarchie finale des chemins : **1. vision (live, légal) → 2. mémoire
  (REA, décision ToS)**. Le replay reste utile **hors ligne** : vérité terrain
  pour évaluer ce que la vision lit vraiment, et débriefing post-partie.

---

## 8. Mise en route de la chaîne mémoire — 10/10/2026

**Décision du propriétaire du compte : la lecture mémoire est validée (ToS
acceptée), et promue plan A** — la vitesse devient un enjeu, et des données
structurées en mémoire coûtent bien moins cher qu'une analyse d'images.

**Chaîne installée et vérifiée (`rea doctor` vert) :**
- Ghidra **12.1.4** → `C:\Users\Nauss\tools\ghidra_12.1.4_PUBLIC`
  (`GHIDRA_INSTALL_DIR` posé, persistant) ;
- décompilateur natif x64, headless, Java 21 — tous les contrôles OK ;
- REA **6.4.0** en CLI (`npx rea-agents`), commandes natives disponibles
  (`function`, `decompile`, `inspect-native-*`, `capture-process`…).

**Recon du binaire cible** (`Versions\Base98348\HeroesOfTheStorm_x64.exe`,
53,5 Mo, x64) : 146 668 chaînes, **917 classes RTTI**. Constat important : les
noms d'événements du protocole replay (`PeriodicXPBreakdown`, `PlayerDeath`…)
sont **absents** du client — ils vivent côté protocole. Les bons ancrages sont
les **classes UI qui affichent exactement les stats visées** :

| Classe RTTI | Ce qu'elle affiche | Champ hotstate visé |
|---|---|---|
| `CTimerFrame` / `CTimerWindow` | le chrono de partie | `meta.duration_s` |
| `CUnitStatusHealth`, `CUnitStatusHealthLabel`, `CUnitStatusShieldedHealthBar` | PV / boucliers | `heroes[].hp` |
| `CTeamHeroLevelFrame`, `CPlayerHeroLevelFrame`, `CUnitStatusLevel` | niveaux | `teams[].level` |
| `CPlayerDeathIndicatorFrame` | timers de mort | `heroes[].respawn_in` |
| `CHeroState`, `CHeroTalentsPanel`, `CHeroTalentTierButton` | état / talents | `heroes[].talents` |
| `CMinimap`, `CMinimapUnitStatusPanel`, `CUnitStatusMinimapIcon` | positions | `position_snapshots` |
| `CGameStatsPanel`, `CPlayerScoreResultFrame` | stats de match | `final_score` |

**Stratégie :** chaque frame UI lit l'état du jeu quelque part → retrouver la
source (objet unité/héros, table de jeu) par les setters/callbacks de ces
classes → en déduire les offsets → petit lecteur (`ReadProcessMemory`) qui
remplit le contrat `hotstate`. Le lecteur devra reposer sur des **signatures**
(pattern scans), pas des offsets bruts, pour survivre aux patches.

**En cours :** analyse headless complète du binaire (projet Ghidra `CervHots`,
`C:\Users\Nauss\ghidra-projects`), puis passage des ancres au crible
(script Ghidra + REA `function`/`decompile`).

---

## 9. Reprise — ce que le binaire dit vraiment (11/10/2026)

Exploration du PE brut (`etudes/rea/scripts/anchors_offline.py`) pendant
l'analyse Ghidra, avec deux découvertes qui changent la méthode :

1. **Le binaire contient bien du RTTI MSVC — mais pas pour les classes UI.**
   807 `CompleteObjectLocator` trouvés par scan structurel (la clé : x64, le COL
   contient sa propre RVA en champ `pSelf`) : ce sont des classes moteur /
   Battle.net (`Stream`, `Log`, `Var`, `GameStream`, `HsBnet`…). Aucune classe
   UI (`CTimerFrame`, `CUnitStatusHealth`, `CMinimap`…) parmi elles.
2. **Les 1892 noms « .?AV…@@ » (dont toutes les classes UI) vivent dans une
   table `.data`** au format `{u64 commun (0x142885B38), u64 0, nom}` — sans
   COL, donc sans RTTI exploitable par le schéma classique. Ce n'est pas du
   RTTI standard : c'est un registre de noms du moteur (probablement le binding
   des frames UI). Les pointeurs de fonction x64 étant des LEA RIP-relatifs,
   seules les xrefs vues par Ghidra permettront de retrouver le code usine qui
   consomme ce registre.

**Méthode retenue :** trouver, pour chaque classe UI, les **xrefs de son entrée
de registre** (script `scripts/anchors.py`, côté Ghidra) → fonctions
concernées (usine/binding, constructeurs) → décompilation (Ghidra / REA
`function`) → structure de jeu lue → offsets → lecteur mémoire.

**Script livrés :**
- `scripts/anchors_offline.py` — chasse RTTI/vtables sur le PE brut (PE parser
  minimal, scan des COL par `pSelf`) ; utile pour toute la partie « classes
  moteur » et pour valider des adresses sans attendre Ghidra.
- `scripts/anchors.py` — chasse des xrefs des entrées de registre UI dans
  Ghidra (à exécuter dès l'analyse terminée).

---

## 10. Le binaire est protégé — pivot dynamique (11/10/2026)

**Constat décisif :** le `.text` de `HeroesOfTheStorm_x64.exe` est **chiffré
sur disque** (entropie 7,3→8,0 sur 40 Mo, aucun prologue x64 valide, ~0 LEA
RIP-relative réelle). En comparaison, le launcher non protégé est à 6,6 et un
code normal à ~6. Seul `.rdata`/`.data` (chaînes, tables) sont en clair.

Cela explique tous les échecs de la journée :
- l'analyse Ghidra « réussie » en 2 h 17 ne produit que ~1 M d'instructions
  (désassemblage de bruit) ;
- **zéro xref** même sur des chaînes certaines (« .StormReplay », messages
  libcurl) — le code qui les référence est illisible ;
- les 3 388 LEA « valides » trouvées étaient du bruit statistique.

**Conséquence : la RE statique sur le fichier est morte. Le protecteur
déchiffre le code au lancement — c'est en mémoire que tout se passe.**

**Nouvelle feuille de route (dynamique) :**
1. **Dump du code déchiffré** (`scripts/dump_unpacked.py`) : le jeu lancé
   (le menu suffit), lecture seule du processus (`ReadProcessMemory`), image
   mémoire complète exportée → **importable dans Ghidra**, où la RE statique
   fonctionnera enfin (xrefs, vtables, décompilation des fonctions trouvées
   par les scripts `anchors*`).
2. **Value scanning live** : pendant une partie (vs IA suffit), repérer l'état
   par valeurs connues (chrono, PV, niveaux — croisés avec la vérité terrain
   `hotstate/extract.py`) ; REA `capture-process` / `compare-process-captures`
   est fait pour ça.
3. Le lecteur mémoire final lira alors les structures identifiées, avec des
   signatures pour survivre aux patches.

**Ce qu'il faut au propriétaire** : lancer le jeu une fois (menu suffit) pour
le dump ; une partie vs IA pour l'exploration live. Aucune injection, aucune
écriture — lecture seule.

---

## 11. Premier en direct : le chrono de jeu trouvé (11/10/2026, partie vs IA)

Session live « La passe d'Alterac » (22 min, Tassadar, victoire) : 4 captures
mémoire (image + tas 3,2 Go) contextualisées (début, 3e mort, objectif pris,
fin) + vérité terrain `hotstate` du replay de la même partie.

Méthode victorieuse : **value scanning par écarts** — les valeurs mémoire dont
les écarts entre captures suivent exactement les écarts temporels (+382 s puis
+427 s), avec tolérance de dérive de simulation, sur image + tas, tous
encodages (u32 sec/ticks/ms, f32/f64). Les scripts `heap_clock_scan3/4/5.py`.
Écueils majeurs rencontrés et documentés : le tas est **plein de petites
valeurs** (600 M de candidats par plage — pas de dictionnaires possibles, il
faut comparer région par région en vectorisé/mmap), et la sim dérive légèrement
du temps réel (le 1:1 exact tue les vrais candidats).

**Résultat : le chrono de partie est localisé** — u32 en boucles 1/16 s
(`ticks/16 = secondes`) : 514 s → 902 s → **1322,5 s qui se fige à la fin**
(la partie = 1321 s au replay). Validation : écarts exacts + borne de fin.

Il vit à `+0x40` d'une **structure de statistiques** avec ~15 compteurs
cumulatifs voisins (croissances régulières = dégâts/XP/globules candidats,
dont deux compteurs qui fluctuent : 56→43→36 et 23→9→17) et une zone
d'identifiants fixes en tête. Deux autres horloges voisines : une horloge
sous-système (+~12 s de dérive) et une horloge uptime processus (ms).

**Prochaines étapes :**
1. Corréler chaque champ de la structure avec les nombres du replay (dégâts,
   XP, globules, morts) — la vérité terrain `hotstate_game1.json` est là pour ça.
2. Trouver dans le code déchiffré (projet Ghidra `CervHotsMem`) les fonctions
   qui écrivent ces champs → offsets stables → signatures.
3. Écrire le lecteur `hotstate` en direct (le contrat est déjà prêt).

---

## 12. Le code s'ouvre (11/10/2026, suite)

- **Les xrefs fonctionnent sur le code déchiffré** (projet `CervHotsMem`,
  `run_mem_scripts.bat`) : validées sur les chaînes libcurl, puis sur les
  ancres moteur. Cartographie obtenue :
  - `replay.tracker.events` → `0x7ff62bed07f0` : initialisateur statique qui
    enregistre le nom de bloc (id **0x15**) dans la **table des blocs replay**
    (`DAT_7ff62f63e240` ; helper `FUN_7ff62bf80150(table, flags, desc, 0)`).
    Les entrées de cette table sont les pointeurs d'entrée vers les écritureurs
    de blocs → **prochaine cible n°1** (le writer du bloc tracker = le code qui
    émet chaque stat = les points de lecture exacts de l'état de jeu) ;
  - `.StormReplay` → `0x7ff62d0844e0` : remplissage du descripteur d'application
    (extensions `.Storm*`, produits, chemins — la config globale du jeu) ;
  - `c_classId*` → `0x7ff62c7eeaa0` : **constructeur géant du registre de
    tokens** (478 Ko décompilés dans `decomp/7ff62c7eeaa0.c`) ; le système
    mappe des noms vers des IDs (`c_classId*`, `c_statFlag*`,
    `c_talentModification*`…), helper `FUN_7ff62c7eea40` /
    `FUN_7ff62c7ee9e0`. Ce n'est pas du RTTI : pas de taille ni de constructeur
    par classe, mais un dictionnaire de tokens exploitable.
- Les noms de stats replay (`LevelUp`, `PlayerDeath`, `PeriodicXPBreakdown`)
  sont **absents de ce registre** comme du reste du client : émis ailleurs
  (données de map / serveur) — à viser par le writer du bloc tracker.
- **Corrélation des champs** (`correlate_fields.py`) : pas de match exact — le
  replay ne date les scores qu'en fin de partie (séries plates). Séries
  temps-résolues disponibles : morts (8,16,21), respawns (8,14,20),
  talents (40,60,70), LevelUp (110,175,220), globules (64,128,170),
  structures (0,3,6). Les compteurs de dégâts/XP se corréleront via le code
  (qui nommera les champs), pas via le replay.

---

## 13. LA source live est trouvée : les triggers de jeu (11/10/2026)

`heap_series_scan6.py` cherche directement les **séries de la vérité terrain**
dans les dumps (valeurs exactes aux 3 instants) : les champs tombent —

| série replay | adresse trouvée | trigger mémoire |
|---|---|---|
| morts (8,16,21) | `0x29cc49bd14c` | `gt_KillLogOnHeroUnitDies_Func` |
| globules (64,128,170) | `0x29cbd88a3bc` | `gt_PlayerRegenGlobeImpactScoreTracking_Func` |
| respawns (8,14,20) | `0x29cbd85839c` | `gt_HeroDeathwingRespawn_Func` |

**Ce que c'est :** le système de **triggers de script** du moteur Storm. La map
et la logique de jeu sont des scripts ; chaque trigger est un enregistrement
nommé `gt_*_Func` qui porte son **état courant en clair dans la mémoire vive**.
Ce sont eux qui comptent les stats avant de les émettre au replay. Les noms de
stats (`PlayerDeath`, `LevelUp`, `TalentChosen`, `JungleCampCapture`) existent
aussi en mémoire vive (données de map chargées) — d'où leur absence du binaire.

**Recette du lecteur live (validée sur 3 counters) :**
1. scanner le tas pour `gt_<nom>_Func\0` ;
2. lire l'état à `nom - 0x1C` (compteur) et `nom - 0x14` (miroir) ;
3. cataloguer : `gt_catalog.py` → **2691 enregistrements** dans cette partie
   (`gt_catalog.json`), dont `gt_CoreDiesGameOver`, `gt_CapturePointLogic`,
   `gt_ChaosCavalrySpawnTimerExpires` (Alterac), `gt_BrettTimers*`
   (timers de mort), etc.

**Correction importante** (§11) : la « structure de stats » et son « chrono »
étaient en réalité un tampon de config réseau Battle.net (`Uri":"test.actual.
battle.net"`) et un timer de session de connexion — utiles mais pas l'état de
jeu. La méthode (scan par séries) restait bonne, c'est la cible qui a été
rattrapée ici.

**Prochaine étape** : mapper les triggers utiles au coach (morts, objectifs,
timers, niveaux) sur le contrat `hotstate`, fiabiliser le layout des
enregistrements (plusieurs variantes observées), et écrire le lecteur
`hotstate` qui lit ces records dans le processus — le contrat JSON est déjà
prêt à le recevoir.

---

### Sources
- github.com/morluto/rea (README : cibles, outils, avertissement « lawful RE »)
- morluto.github.io/rea (guides : native = Hopper/Ghidra/IDA, runtime = CDP/crashes)
- Environnement local : `C:\Program Files (x86)\Heroes of the Storm`, Node v26.7
- Contexte projet : `FAISABILITE.md` (replays post-game, pas d'API live, plan pixels)
