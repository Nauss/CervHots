# kb — la couche savoir de CervHots

**Mission :** fournir au coach **le savoir qui interprète l'état de jeu** —
cartes et objectifs, timings, talents, builds, synergies, counters — dans deux
couches jamais mélangées :

- **couche FAIT** (`data/`) : vérifiable, versionnée par build, régénérée ;
- **couche JUGEMENT** (`notes/`) : fiches curatées (rédaction LLM + relecture
  du proprio), sourcées, marquées « à relire ».

Étude d'origine : `etudes/kb/ETUDE.md`. Décisions actées (12/10/2026) :
**gratuit strict** (pas d'abonnement HeroesProfile), **périmètre complet**
(16 cartes + 90 héros), **briefing court (3-4 points)**, fiches **LLM +
relecture**.

## Structure

```
kb/
├── data/
│   ├── map_timings.json   # timings d'objectifs par carte (source + validation)
│   ├── kb.db              # GÉNÉRÉ : héros, talents, capacités, cartes (gitignoré)
│   └── cache/heroes-talents/   # clone épinglé de la source (gitignoré)
├── notes/
│   ├── cartes/<slug>.md   # 16 fiches de carte (jugement)
│   └── heros/<slug>.md    # 90 fiches de héros (jugement)
├── tools/
│   ├── seed_cartes.py     # graine des fiches de carte (rejouer = écraser)
│   ├── seed_heros.py      # graine des fiches héros (+ lots _heros_1/2/3.py)
│   ├── discover_events.py # événements d'objectif par carte (via hotstate)
│   └── validate_timings.py# confronte map_timings.json aux replays
├── refresh.py             # sources gratuites → kb.db
└── briefing.py            # compile le briefing court du coach
```

## Utilisation

```bash
python kb/refresh.py            # reconstruit kb.db (90 héros, ~1900 talents)
python kb/refresh.py --pull     # met à jour heroes-talents avant (nouveau build)

python kb/briefing.py --map "Le val maudit" \
    --allies johanna,liming,rehgar,sonya,hanzo \
    --enemies valeera,anubarak,chromie,lili,valla --t 240
```

Le briefing accepte les noms FR ou EN de carte et les slugs/noms de héros ;
`--t` (secondes de jeu) déclenche le calcul **déterministe** du prochain
jalon de carte. Sortie volontairement courte : 4 lignes, 3-4 points.

```
BRIEFING — Cursed Hollow · 4:00 de jeu
1. CARTE — … 1er objectif contestable à 3:00, puis +1:20-2:00 après « capture d'un tribut ».
2. NOUS — Li-Ming+Johanna : …           (duos détectés dans la compo)
3. EUX — contrer Valeera : …            (sections « Menaces » de leurs fiches)
4. JALON — prochain jalon estimé …      (calculé, jamais estimé par le LLM)
```

## Sources (gratuites, épinglées)

- **heroes-talents** (github.com/heroespatchnotes/heroes-talents, MIT) :
  héros, talents, capacités. Commit épinglé dans `kb.db` (table `meta`) ;
  à rafraîchir à chaque build de jeu via `refresh.py --pull`.
- **map_timings.json** : cheatsheet reddit (triggers + replays, patch 2.54.4),
  wiki, icy-veins, tempostorm — **validé sur 76 replays du compte**
  (12/10/2026) par `tools/validate_timings.py` : 12 cartes contrôlées, aucun
  1er objectif prématuré ; Cursed Hollow ajusté (cap→cap observé dès 63 s) ;
  Hanamura / Jardins / Alterac sans événements d'objectif dans le flux stat.
- Les stats empiriques (winrates, matchups) viendront de **nos propres
  replays** (couche v3), pas d'une API payante.

## Relecture

Les 106 fiches ont été **relues et vérifiées sur internet le 12/10/2026**
(agent délégué, sources : wiki, icy-veins, psionic-storm, heroesfire,
tempostorm, liquipedia) : 61 fiches corrigées, 44 confirmées, 1 incertaine
(rexxar — durée de respawn de Misha, chiffre retiré faute de source).
Détail par affirmation : `notes/_relecture/2026-10-12-*.md`. Les en-têtes de
fiches portent le verdict (`vérifiée` / `corrigée (N)` / `partiellement
vérifiée`). Une relecture humaine ponctuelle reste utile sur les fiches
stratégiques les plus jouées.

## Maintenance

- Les fiches `notes/` s'éditent **directement** dans les `.md` après le
  premier remplissage ; `tools/seed_*.py` ne sont que les graines (rejouer
  écrase les modifications manuelles).
- À chaque patch de jeu : `refresh.py --pull`, relire les fiches touchées
  par le diff de build, rejouer `validate_timings.py`.
- Anti-hallucination : aucune affirmation du coach hors briefing/KB ; les
  lignes de stats porteront toujours un seuil `n` (« peu de données » sous
  ~100 parties).
