#!/usr/bin/env python3
"""kb/tools/validate_timings.py — confronte kb/data/map_timings.json aux replays.

Lit les *.hotstate.json produits par hotstate/extract.py (régénérés si besoin)
et vérifie, par carte :
  1. le PREMIER événement d'objectif observé ≥ 1er objectif contestable ;
  2. les écarts entre objectifs successifs vs fenêtre prédite (quand la
     sémantique de l'événement s'y prête — voir CHECKS).

Rapport honnête : les cartes sans événement d'objectif dans le flux stat
(Hanamura, Jardins, Alterac) et les écarts hors fenêtre sont signalés, jamais
gommés. Usage : python kb/tools/validate_timings.py
"""
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
HOTSTATE = os.path.normpath(os.path.join(HERE, "..", "..", "hotstate"))
PY = os.path.join(HOTSTATE, ".venv", "Scripts", "python.exe")
EXTRACT = os.path.join(HOTSTATE, "extract.py")
TIMINGS = os.path.normpath(os.path.join(HERE, "..", "data", "map_timings.json"))
REPLAYS = ("C:/Users/Nauss/Documents/Heroes of the Storm/Accounts/405983616/"
           "2-Hero-1-1435752/Replays/Multiplayer")

# carte FR -> (événements objectif, contrôle d'écart optionnel)
# gapcheck = (depuis_nom, vers_nom, index_cycle) : l'écart [depuis -> vers] est
# comparé à la borne basse du cycle n° index_cycle dans map_timings.json.
CHECKS = {
    "Le val maudit": (["TributeCollected"], ("TributeCollected", "TributeCollected", 0)),
    "Les sanctuaires infernaux": (["Infernal Shrine Captured"],
                                  ("Punisher Killed", "Infernal Shrine Captured", 0)),
    "Les champs de l’éternité": (["Boss Duel Started", "Immortal Defeated"],
                                 ("Immortal Defeated", "Boss Duel Started", 0)),
    "Le comté du dragon": (["DragonKnightActivated"], None),
    "Le laboratoire de Braxis": (["BraxisHoldoutMapEventComplete"], None),
    "La tombe de la reine araignée": (["SoulEatersSpawned"], None),
    "Le temple céleste": (["SkyTempleActivated"], None),
    "Les tours du destin": (["Altar Captured"], None),
    "Menace nucléaire": (["WarheadJunctionNukesSpawned"], None),
    "La baie de Cœur-Noir": (["GhostShipCaptured"], None),
    "La mine hantée": (["HauntedMinesGolemsSpawned"], None),
    "La fonderie Volskaya": (["VolskayaCapturePointSpawned"], None),
    # sans événement objectif dans le flux stat (signalé comme tel) :
    "Le temple d’Hanamura": ([], None),
    "Les jardins de terreur": ([], None),
    "La passe d’Alterac": ([], None),
}


def _cle(s: str) -> str:
    return s.lower().replace("’", "").replace("'", "").replace("`", "").strip()


def map_slug_by_fr(name_fr: str) -> str | None:
    with open(TIMINGS, encoding="utf-8") as f:
        for nm, m in json.load(f)["maps"].items():
            if _cle(nm) == _cle(name_fr) or _cle(name_fr) in [_cle(a) for a in m.get("aliases_fr", [])]:
                return m["slug"]
    return None


def main() -> None:
    # map_fr -> listes d'événements par replay
    data = defaultdict(list)  # map_fr -> [(t, name), ...] par replay = liste de listes
    n_replays = 0
    for fn in sorted(os.listdir(REPLAYS)):
        if not fn.endswith(".StormReplay"):
            continue
        m = re.match(r"\d{4}-\d{2}-\d{2} \d{2}\.\d{2}\.\d{2} (.+)\.StormReplay$", fn)
        if not m:
            continue
        n_replays += 1
        carte = m.group(1)
        js = os.path.join(REPLAYS, os.path.splitext(fn)[0] + ".hotstate.json")
        if not os.path.isfile(js):
            subprocess.run([PY, EXTRACT, os.path.join(REPLAYS, fn)],
                           check=True, capture_output=True)
        d = json.load(open(js, encoding="utf-8"))
        if carte in CHECKS:
            evs = [(e["t"], e["name"]) for e in d["timeline"]["stat_events"]
                   if e.get("name") in CHECKS[carte][0]]
            data[carte].append(sorted(evs))

    print(f"replays consultés : {n_replays}\n")
    print(f"{'carte':32s} {'n':>2} {'1er obj. min':>12} {'attendu':>8} "
          f"{'écart min':>9} {'fenêtre':>10}  verdict")
    for carte, (evnames, gapcheck) in CHECKS.items():
        reps = data.get(carte, [])
        reps = [r for r in reps if r]
        if not reps:
            print(f"{carte:32s} {'-':>2} {'pas d’événement objectif dans le flux stat':-^60}")
            continue
        slug = map_slug_by_fr(carte)
        if not slug:
            print(f"{carte:32s} {'?':>2} {'carte non résolue dans map_timings.json':-^60}")
            continue
        with open(TIMINGS, encoding="utf-8") as f:
            mdata = next(v for v in json.load(f)["maps"].values() if v["slug"] == slug)
        first_expected = mdata.get("first_contestable_s")
        firsts = [r[0][0] for r in reps]
        if gapcheck:
            gaps = [b[0] - a[0] for r in reps for a, b in zip(r, r[1:])
                    if a[1] == gapcheck[0] and b[1] == gapcheck[1]]
            cyc = mdata["next_after"][gapcheck[2]]
            lo, hi = cyc["contestable_after_s"]
            gmin_s = lo
            fen = f"{lo}+ s" if lo == hi else f"{lo}-{hi} s"
        else:
            gaps = []
            gmin_s = None
            fen = "-"
        gmin = min(gaps) if gaps else None
        verd = []
        if first_expected is not None and min(firsts) < first_expected:
            verd.append(f"1er obj. TÔT ({min(firsts):.0f}s < {first_expected}s)")
        if gmin_s is not None and gmin is not None and gmin < gmin_s:
            verd.append(f"écart sous la fenêtre ({gmin:.0f}s < {gmin_s}s)")
        print(f"{carte:32s} {len(reps):>2} {min(firsts):>11.0f}s {first_expected or 0:>7}s "
              f"{(f'{gmin:.0f}s' if gmin is not None else '-'):>9} {fen:>10}  "
              f"{'OK' if not verd else ' ; '.join(verd)}")
    print("\nNote : 1er obj. min = plus tôt observé (cap, donc ≥ contestable + channel "
          "+ déplacement). Les écarts hors fenêtre sont à arbitrer : table ou replay.")


if __name__ == "__main__":
    main()
