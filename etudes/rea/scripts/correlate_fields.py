#!/usr/bin/env python
"""correlate_fields.py — identifie chaque champ de la structure de stats.

La structure (autour du chrono, base 0x29be0293950 dans la session) a été lue
dans les 3 dumps. Ce script construit, depuis la vérité terrain replay
(hotstate_game1.json), les séries attendues aux mêmes instants (514 / 902 /
1322 s — la base temporelle du replay et celle du chrono mémoire coïncident :
le chrono se fige à 1322 s, la partie fait 1321 s), puis cherche quelle série
explique chaque champ.
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(r"C:\Users\Nauss\ghidra-projects")
T = (514, 902, 1322)          # instants des captures (secondes de jeu)

# Champs de la structure, lus dans les dumps (u64 sauf mention) — valeurs aux 3 instants
FIELDS = {
    "+0x20 u32 A": (56, 43, 36),
    "+0x24 u32 B": (23, 9, 17),
    "+0x28 u64": (222148, 378720, 547568),
    "+0x30 u64": (150412, 253300, 364511),
    "+0x38 u64": (11440, 20059, 29407),
    "+0x50 u64": (325628, 571070, 849008),
    "+0x58 u64": (11700, 20562, 30115),
    "+0x60 u64": (74, 116, 180),
    "+0x68 u64": (8, 11, 18),
    "+0x70 u64": (80, 124, 192),
    "+0x78 u64": (1053, 1625, 2536),
    "+0x80 u64": (82, 127, 197),
    "+0x88 u64": (518797, 901922, 1316109),
}

state = json.loads((BASE / "hotstate_game1.json").read_text(encoding="utf-8"))
he = state["timeline"]["hero_events"]
se = state["timeline"]["stat_events"]
fs = state["final_score"]


def count_before(events, pred, t):
    return sum(1 for e in events if e["t"] <= t and pred(e))


def score_sum_at(stat, t):
    """Somme tous joueurs de la dernière valeur connue à t <= t."""
    total = 0
    for sample in fs.get(stat, []):
        if sample["t"] <= t and sample["value"] is not None:
            total += sample["value"]
    return total


def score_sum_before(stat, t):
    """Somme des valeurs dont l'échantillon est daté <= t (dernier par joueur)."""
    best = {}
    for sample in fs.get(stat, []):
        if sample["value"] is None:
            continue
        key = sample["player"]
        if key not in best or best[key][0] < sample["t"] <= t:
            if sample["t"] <= t:
                best[key] = (sample["t"], sample["value"])
    return sum(v for _, v in best.values())


# séries dérivées de la vérité terrain
series = {
    "morts héros (cumul)": tuple(count_before(he, lambda e: e["type"] == "death", t) for t in T),
    "respawns (cumul)": tuple(count_before(he, lambda e: e["type"] == "respawn", t) for t in T),
    "talents choisis (cumul)": tuple(count_before(se, lambda e: e["name"] == "TalentChosen", t) for t in T),
    "LevelUp (cumul)": tuple(count_before(se, lambda e: e["name"] == "LevelUp", t) for t in T),
    "globules (cumul)": tuple(count_before(se, lambda e: e["name"] == "RegenGlobePickedUp", t) for t in T),
    "camps capturés (cumul)": tuple(count_before(se, lambda e: e["name"] == "JungleCampCapture", t) for t in T),
    "structures détruites (cumul)": tuple(count_before(se, lambda e: e["name"] == "TownStructureDeath", t) for t in T),
    "PlayerDeath events (cumul)": tuple(count_before(se, lambda e: e["name"] == "PlayerDeath", t) for t in T),
}
for stat in ("Takedowns", "Deaths", "HeroDamage", "SiegeDamage", "Healing",
             "DamageTaken", "ExperienceContribution", "TimeSpentDead",
             "TownKills", "MetaExperience", "SoloKill", "Assists",
             "MinionKills", "MercCampCaptures", "WatchTowersActivated"):
    try:
        series[f"score:{stat}"] = tuple(score_sum_before(stat, t) for t in T)
    except Exception:
        pass

# XP cumulée depuis PeriodicXPBreakdown (fix data = valeurs fixed-point)
xp = [0, 0, 0]
for e in se:
    if e["name"] != "PeriodicXPBreakdown":
        continue
    data = e.get("data", {})
    parts = [data.get(k) or 0 for k in ("MinionXP", "CreepXP", "StructureXP", "HeroXP", "TrickleXP")]
    parts = [p if isinstance(p, int) else 0 for p in parts]
    val = sum(parts) / 4096.0
    for i, t in enumerate(T):
        if e["t"] <= t:
            xp[i] += val
series["XP (PeriodicXPBreakdown)"] = tuple(round(x) for x in xp)

print("=== séries de référence (vérité terrain) ===")
for k, v in series.items():
    print(f"  {k:32s} {v}")

print("\n=== correspondances ===")
found = {}
for fname, fvals in FIELDS.items():
    matches = [k for k, v in series.items()
               if all(abs(a - b) <= max(2, abs(b) * 0.01) for a, b in zip(fvals, v))]
    if matches:
        found[fname] = matches
        print(f"  {fname:14s} {fvals}  ->  {matches}")
    else:
        # plus proche (écart relatif moyen)
        def err(v):
            return sum(abs(a - b) / (abs(b) + 1) for a, b in zip(fvals, v)) / 3
        near = sorted(series.items(), key=lambda kv: err(kv[1]))[:2]
        print(f"  {fname:14s} {fvals}  ->  (aucun) plus proches : "
              + ", ".join(f"{k} {v}" for k, v in near))

(BASE / "fields_correlation.json").write_text(json.dumps(found, indent=1), encoding="utf-8")
print("écrit: fields_correlation.json")
