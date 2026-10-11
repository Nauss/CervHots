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

### Sources
- github.com/morluto/rea (README : cibles, outils, avertissement « lawful RE »)
- morluto.github.io/rea (guides : native = Hopper/Ghidra/IDA, runtime = CDP/crashes)
- Environnement local : `C:\Program Files (x86)\Heroes of the Storm`, Node v26.7
- Contexte projet : `FAISABILITE.md` (replays post-game, pas d'API live, plan pixels)
