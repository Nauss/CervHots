# Étude — base de connaissances du coach (cartes, héros, builds, synergies, counters)

**Date :** 12/10/2026 · **Statut :** étude close, architecture retenue, **implémentée** (livrable `kb/`) — décisions du proprio actées §8

Le coach a déjà (presque) l'**état du jeu** (`hotstate/`, contrat
`game_state.schema.json`). Cette étude pose la question de l'autre moitié :
le **savoir** qui permet d'interpréter cet état — cartes et objectifs, timings,
builds et talents, synergies d'équipe, counters et interactions adverses.
Le coach doit y accéder au moment de décider, sans se noyer ni inventer.

## 0. Verdict

**Oui, il faut une base de connaissances — mais ce n'est pas un « RAG ».**
Trois constats qui orientent tout :

1. **Le savoir HotS est petit.** Toutes les données de jeu (héros, talents,
   capacités, cartes) tiient en quelques centaines de Ko de JSON ; même avec les
   fiches stratégiques, on reste sous le mégaoctet. Pas de problème de
   recherche sémantique à résoudre — un problème de **sélection** : n'envoyer
   au cerveau que ce qui sert *maintenant*.
2. **L'essentiel de la valeur se joue avant la partie.** Carte + 10 héros sont
   connus dès l'écran de chargement (`replay.server.battlelobby`, déjà
   identifié dans `hotstate/README.md`). On compile alors un **briefing** de
   1–2 k tokens (cette carte, notre compo, leur compo) : c'est ~80 % du gain,
   zéro appel LLM supplémentaire, zéro latence en jeu.
3. **Une seule couche coûte de l'argent : les stats empiriques** (winrates,
   matchups, popularité des builds). Tout le reste — données de jeu, timings,
   fiches curatées — est gratuit et versionnable dans le dépôt.

## 1. Ce que le coach doit savoir — taxonomie

| Famille | Exemples concrets | Nature | Source principale |
|---|---|---|---|
| **Cartes** | objectif de la map, comment il se gagne, channel 3 s ou 5 s, récompense | fait | données de jeu + curaté |
| **Timings** | 1er objectif à 3:00 (+30 s d'annonce), cycle suivant, spawns de camps, boss | fait | curaté, **validable par nos replays** |
| **Héros / talents** | description exacte d'un talent, CD, mana, palier, ce que fait un ult | fait | données de jeu (JSON par build) |
| **Builds** | build standard par palier, variantes, taux de pick / winrate du build | fait + stats | données de jeu + HeroesProfile |
| **Synergies** | combos d'ults, stacks (e.g. Alarak/Cho), qui enable qui dans notre compo | jugement | curaté + stats matchups |
| **Counters / interactions** | « leur Valeera est countered par Cleanse/BW polymorph », « Arthas ancre Illidan » | jugement | curaté + stats matchups |
| **Stats empiriques** | winrate héros par map, matchup A vs B, popularité | fait | HeroesProfile (couche payante) |
| **Pièges de map** | « pas de boss avant 10:00 sans compo dédiée », « les seeds de Garden se font en split » | jugement | curaté |

Règle de découpage : **fait = vérifiable et chiffré, versionné par patch ;
jugement = advice humain sourcé, révisable.** Les deux couches ne se
mélangent jamais dans la même ligne — le coach doit savoir s'il cite un
chiffre ou une opinion.

## 2. Sources de données (vérifiées le 12/10/2026)

### a. Données de jeu — gratuites, exactes, versionnées par build

- **HeroesToolChest/HeroesDataParser** + dépôt **`heroes-data`** : extraction
  JSON complète du jeu (herodata, mapdata, gamestrings), **une version par
  build**, MIT. C'est la source de vérité : descriptions de talents,
  capacités, CD, cartes. Le parser sait aussi tirer directement depuis
  l'installation locale ou les serveurs (`--storage-type online`).
- **`heroespatchnotes/heroes-talents`** (le fork vivant — le dépôt
  `heroesshare` est figé en 2019, 358 commits derrière) : talents et
  capacités dans un JSON simplifié, pratique pour le briefing.

→ Rapatriés une fois par build dans le dépôt, pas appelés à chaud.

### b. Stats empiriques — la seule couche qui coûte

- **API HeroesProfile** (api.heroesprofile.com) : `Heroes/Stats` (winrate,
  banrate, pickrate, **par map**), `Heroes/Matchups` (winrate avec/contre,
  **c'est exactement la table synergies/counters**), `Heroes/Talents Builds`
  (builds populaires + winrates), filtrables par league tier et hero level.
- **Tarifs (page officielle) : Basic 5 $/mo, Intermediate 10 $/mo, Developer
  25 $/mo** ; en Basic/Intermediate « les appels ne peuvent pas servir les
  données directement depuis une application » — il faut **rapatrier et
  stocker** (ce qu'on ferait de toute façon). Un sous-ensemble `/openApi/`
  est gratuit **sans token** (métadonnées : héros, talents, patches, maps) ;
  les stats détaillées demandent l'abonnement.
- **Alternative gratuite honnête** : nos propres replays (`hotstate/extract.py`)
  alimentent une stats maison — mais il faudra des centaines de parties pour
  que les matchups soient significatifs. Réaliste à moyen terme, pas au
  démarrage.

### c. Timings et mécaniques de carte — curaté, validé par nos replays

- Table de timings post-objectif par map (reddit, vérifiée triggers + replays,
  **patch 2.54.4**) : ex. Punisher mort → prochain contestable à +3:00,
  Tomb → +0:15, etc. + temps de channel (Cursed Hollow/Towers 5 s,
  Dragon Shire/Alterac 3 s — Math of the Storm).
- Guides de map (icy-veins, wiki, heroesfire « data collection ») pour les
  mécaniques et pièges.
- **Validation maison gratuite** : la timeline de `hotstate` contient les
  événements d'objectif réels (`TributeCollected`, `RavenCurseActivated`…) ;
  nos replays suffisent à confirmer/corriger chaque ligne de la table. C'est
  le même réflexe que la couche stats : vérité terrain avant usage.

### d. Savoir stratégique (builds, synergies, counters) — curaté

Guides (icy-veins, heroesfire, reddit, scène compétitive CCL/NGS) : c'est du
texte d'opinion, non structuré, en anglais, qui vieillit. **Pas de scraping
automatique ni de RAG dessus** : on en tire des **fiches curatées** courtes
(§3), écrites une fois, relues, sourcées. L'apport d'un LLM : rédiger les
fiches à partir des sources + des stats ; le travail humain : valider.

## 3. Architecture retenue — deux couches, un seul accès

```
kb/
├── data/                     # couche FAIT — régénérée, jamais éditée à la main
│   ├── gamedata/             # heroes-data + heroes-talents, par build (git ou cache)
│   └── kb.db                 # SQLite : maps, timings, talents, builds, matchups, stats
├── notes/                    # couche JUGEMENT — éditée, versionnée par git
│   ├── cartes/<map>.md       # mécanique, timings commentés, pièges, priorités
│   ├── heros/<hero>.md       # faits marquants, menaces, counters, pièges
│   └── compo/*.md            # synergies connues, combos d'ults
├── refresh.py                # pipeline d'alimentation (§6)
└── briefing.py               # compilation du briefing pré-partie (§4)
```

**SQLite, pas de base vectorielle.** Tables minimales :

```sql
heroes(hero_id, name, role, type, release, rework, build)
talents(talent_id, hero_id, tier, name, description, cooldown, mana, build)
maps(map_id, name, objective, channel_s, build)
map_timings(map_id, event, first_s, cycle_s, note, source)   -- ex: ('Cursed Hollow','tribute contestable',150,100,…)
builds(hero_id, label, tiers, pick_rate, win_rate, n_games, patch, source)
matchups(hero_a, hero_b, wr_ally, wr_enemy, n_games, patch, source)
hero_map_stats(hero_id, map_id, win_rate, n_games, patch, source)
```

Les fiches `notes/*.md` restent en markdown (lisibles, diffables, éditables
par un humain ou un LLM) ; le briefing les cite par chemin, jamais recopiées
en base. **Toute la base porte un `build`/`patch`** : le jeu reçoit encore des
patchs, et un counter qui n'est pas à jour est pire que pas de counter.

## 4. Comment le coach y accède — trois canaux, zéro RAG

### a. Briefing pré-partie (le canal principal)

Déclencheur : `battlelobby` lu → carte + 10 héros connus. `briefing.py`
compile alors, **une fois**, un bloc de 1–2 k tokens injecté dans le prompt
système du cerveau :

```
CARTE — Cursed Hollow : tributs (3 = malédiction 70 s), channel 5 s,
  1er tribut ~3:00, cycle ~1:20-2:00 après cap. Pièges : [fiche carte]
NOTRE COMPO — Johanna (tank) : anti-CC blind… ; Li-Ming : reset…
  Synergies : [fiche compo] ; build conseillé Li-Ming : [tiers 1/4/7/…]
LEUR COMPO — Menaces : Valeera (flank, burst) ; Anub'arak (engage, cocoon)
  Counters à viser : Cleanse (Rehgar) dès 7 ; focus Anub'arak ult down…
STATS — Cursed Hollow : Li-Ming 54 % (n=1 200) ; matchup Li-Ming vs Chromie
  58 % (n=310) ; peu de données : Cho (n=40)
TIMINGS — prochain tribut estimé : 5:10 (déterministe, cf. map_timings)
```

Le cerveau reçoit ça **avant le coup d'envoi** : il n'a plus rien à demander
pendant la partie sur le savoir stable, et chaque conseil peut partir d'un
fait précis plutôt que d'une impression.

### b. Requêtes typées pendant la partie (canal secondaire, rare)

Pour le savoir qui ne dépend que d'un événement soudain (« ils ont pris quel
ult à 10 ? », « détail du talent X ») : la couche stats le fournit déjà
(talent choisis = `upgrade` dans la timeline), sinon un outil de requête
`kb_query(heros=…, sujet=…)`. **Vérification à faire** : la gateway Groco
passe-t-elle le champ `tools` (function calling) du format OpenAI ? Si non,
repli sans changer la base : le cerveau émet `{question_kb: "…"}` dans son
JSON de sortie, l'orchestrateur interroge la base et relance une passe.

### c. Calculs déterministes (pas de LLM)

« Objectif dans 45 s », « camps prêts », « ils n'ont plus d'ult X pendant
Y s » : calculés directement depuis `map_timings` + la timeline `hotstate`.
Un LLM ne devrait jamais estimer un timing qu'on peut calculer — c'est le
même principe que la sortie plate du reader : le modèle raisonne sur des
faits, il ne les fabrique pas.

## 5. Anti-hallucination et fraîcheur

- **Provenance obligatoire** : chaque ligne du briefing porte `source`
  (gamedata / HeroesProfile n=… / fiche …), même si le coach ne la cite pas
  à l'oral — elle sert à calibrer sa confiance.
- **Seuils statistiques** : sous ~100 parties, afficher « peu de données » ;
  ne jamais transformer 52 % (n=60) en « bon counter ».
- **Prompt** : interdiction formelle d'affirmer un fait hors briefing/KB ;
  sur un sujet absent, le coach le dit ou se tait (« silence > bruit »,
  déjà posé dans `FAISABILITE.md` §4).
- **Version par patch** : à chaque patch de jeu, la couche fait est
  régénérée et les fiches sont marquées `à relire` — un counter périmé est
  filtré du briefing tant qu'il n'est pas revalidé.

## 6. Alimentation et maintenance

`kb/refresh.py`, exécuté à la main ou à chaque build détecté :

1. rapatrie `heroes-data` / `heroes-talents` (release git, version = build) ;
2. reconstruit `kb.db` (héros, talents, cartes, map_timings) ;
3. si abonnement ou `/openApi/` suffisant : export HeroesProfile
   (matchups, stats par map, builds) — **rapatrié et stocké**, pas appelé
   à chaud pendant une partie ;
4. valide `map_timings` contre les replays du compte (événements d'objectif
   de `hotstate/extract.py`) — écart détecté = ligne signalée, pas auto-corrigée ;
5. marque les fiches `notes/` touchées par le diff de build.

## 7. Risques

| Risque | Gravité | Mitigation |
|---|---|---|
| Le cerveau se noie dans le briefing et parle pour rien | **Élevée** | briefing filtré par pertinence (carte + compo), ≤ 2 k tokens ; une priorité par intervention (déjà posé) |
| Fiches curatées périmées ou fausses | Moyenne | provenance + `à relire` à chaque patch ; le coach descend en confiance plutôt qu'à inventer |
| Stats payantes (HeroesProfile 5–25 $/mo) | Moyenne | démarrer sans (gamedata + fiches + stats maison sur nos replays) ; décision budget au proprio |
| Stats ≠ réalité de partie (le « counter » théorique) | Moyenne | les stats pondèrent, elles ne dictent pas ; le briefing présente matchups comme tendances |
| Traduction EN→FR des sources | Faible | fiches rédigées en français directement, sources citées en anglais |

## 8. Décisions (tranchées par le proprio, 12/10/2026)

1. **Couche stats : gratuit strict.** Pas d'abonnement HeroesProfile. Les
   métadonnées gratuites (`/openApi/`) ne couvrant pas les matchups, la couche
   stats sera **maison**, agrégée depuis nos replays (`hotstate/extract.py`) —
   cf. roadmap v3. La couche fait (gamedata, timings) reste totalement gratuite.
2. **Périmètre complet** : les 16 cartes et les 90 héros, dès le départ.
3. **Briefing court** : 3-4 points actionnables par partie, jamais plus.
4. **Fiches : rédaction LLM + relecture du proprio.** Les fiches sortent
   marquées « à relire » ; la relecture est une étape du flux, pas une option.

## 9. Roadmap — état

- **KB v0 — LIVRÉ** : `map_timings.json` (16 cartes) + fiches de carte.
- **KB v1 — LIVRÉ** : `kb.db` gamedata (90 héros, ~1 900 talents, commit
  épinglé), `briefing.py` (compilation + jalon déterministe), `refresh.py`.
- **KB v2 — LIVRÉ** : 90 fiches héros (synergies, counters, pièges),
  détection de duos dans la compo, garde-fous de provenance. Reste : le canal
  de requêtes typées en cours de partie (dépend du support `tools` de la
  gateway Groco — à vérifier, repli JSON prévu).
- **KB v3 — À FAIRE** : couche stats maison (winrates, matchups agrégés depuis
  nos replays, avec seuils `n`), rafraîchissement automatique à chaque build.

**Validation (12/10/2026, `kb/tools/validate_timings.py`) :** table de timings
confrontée à **76 replays du compte** — 12 cartes contrôlées, aucun 1er
objectif prématuré ; un ajustement réel sorti des replays (Cursed Hollow :
cap→cap dès 63 s, la source annonce 80-120 s) ; 3 cartes sans événement
d'objectif dans le flux stat (Hanamura, Jardins, Alterac) non contrôlables
par ce biais.

## Sources clés

- Données de jeu : github.com/HeroesToolChest/HeroesDataParser,
  github.com/HeroesToolChest/heroes-data (JSON par build),
  github.com/heroespatchnotes/heroes-talents (fork vivant ; `heroesshare`
  figé depuis 2019).
- Stats : api.heroesprofile.com — docs `Heroes/Stats`, `Heroes/Matchups`,
  `Heroes/Talents` et tarifs (Basic 5 $, Intermediate 10 $, Developer 25 $/mo ;
  `/openApi/` gratuit sans token pour les métadonnées ; stockage local obligatoire
  en Basic/Intermediate).
- Timings de map : cheatsheet reddit « every map's post-objective timing »
  (triggers + replays, patch 2.54.4), tempostorm « Math of the Storm — Maps »
  (temps de channel), guides icy-veins par map, heroesfire « My Data Collection ».
- Réutilisation interne : `hotstate/` (timeline d'événements d'objectif =
  vérité terrain des timings), `replay.server.battlelobby` (map + comps au
  chargement = déclencheur du briefing).
