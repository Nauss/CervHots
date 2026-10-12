#!/usr/bin/env python3
"""kb/tools/discover_events.py — découvre les événements d'objectif par carte.

Pour 1 replay par carte, lance hotstate/extract.py (déjà présent en venv) et
liste les noms d'événements SStatGameEvent rencontrés. Sert à construire la
table map → événements de validate_timings.py.

Usage : python kb/tools/discover_events.py [--all]
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
HOTSTATE = os.path.normpath(os.path.join(HERE, "..", "..", "hotstate"))
PY = os.path.join(HOTSTATE, ".venv", "Scripts", "python.exe")
EXTRACT = os.path.join(HOTSTATE, "extract.py")
REPLAYS = ("C:/Users/Nauss/Documents/Heroes of the Storm/Accounts/405983616/"
           "2-Hero-1-1435752/Replays/Multiplayer")

BRUIT = {  # non-objectifs : à exclure du comptage
    "GameStart", "PlayerInit", "TownStructureInit", "JungleCampInit",
    "PlayerSpawned", "LevelUp", "TalentChosen", "GatesOpen",
    "RegenGlobePickedUp", "PlayerDeath", "PeriodicXPBreakdown",
    "LootSprayUsed", "EndOfGameXPBreakdown", "EndOfGameTimeSpentDead",
    "EndOfGameTalentChoices", "EndOfGameUpVotesCollected",
    "EndOfGameDownVotesCollected", "PlayerChatMessage", "Ping",
}


def main() -> None:
    by_map = defaultdict(list)
    for fn in sorted(os.listdir(REPLAYS)):
        if fn.endswith(".StormReplay"):
            m = re.match(r"\d{4}-\d{2}-\d{2} \d{2}\.\d{2}\.\d{2} (.+)\.StormReplay$", fn)
            if m:
                by_map[m.group(1)].append(os.path.join(REPLAYS, fn))
    per_map = len(by_map) if "--all" not in sys.argv else 99
    out = {}
    for carte, files in sorted(by_map.items()):
        take = files[:per_map]
        names = Counter()
        for path in take:
            js = os.path.splitext(path)[0] + ".hotstate.json"
            if not os.path.isfile(js):
                subprocess.run([PY, EXTRACT, path], check=True,
                               capture_output=True)
            d = json.load(open(js, encoding="utf-8"))
            for e in d["timeline"]["stat_events"]:
                if e.get("name") not in BRUIT:
                    names[e["name"]] += 1
        out[carte] = dict(names.most_common())
        print(f"{carte:35s} ({len(take)} replays) -> {dict(names.most_common())}")
    with open(os.path.join(HERE, "events_par_carte.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("écrit : kb/tools/events_par_carte.json")


if __name__ == "__main__":
    main()
