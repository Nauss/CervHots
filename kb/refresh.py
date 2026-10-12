#!/usr/bin/env python3
"""kb/refresh.py — construit kb/data/kb.db à partir des sources gratuites.

Sources (couche FAIT) :
  1. heroes-talents (heroespatchnotes, MIT) — héros, talents, capacités.
     Cloné dans kb/data/cache/heroes-talents (sparse: hero/). Commit épinglé
     dans la table meta.
  2. kb/data/map_timings.json — timings d'objectifs par carte.

Zéro dépendance (stdlib uniquement). Usage :
    python kb/refresh.py            # reconstruit kb.db
    python kb/refresh.py --pull     # met à jour le clone avant (nouveau build)
"""
import json
import os
import sqlite3
import subprocess
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "cache", "heroes-talents")
HERO_DIR = os.path.join(CACHE, "hero")
TIMINGS = os.path.join(HERE, "data", "map_timings.json")
DB = os.path.join(HERE, "data", "kb.db")

SCHEMA = """
DROP TABLE IF EXISTS meta;
DROP TABLE IF EXISTS heroes;
DROP TABLE IF EXISTS abilities;
DROP TABLE IF EXISTS talents;
DROP TABLE IF EXISTS maps;
DROP TABLE IF EXISTS map_cycles;

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE heroes (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT,
    expanded_role TEXT,
    type TEXT,
    release_date TEXT,
    release_patch TEXT,
    tags TEXT
);

CREATE TABLE abilities (
    slug TEXT NOT NULL,
    ability_uid TEXT NOT NULL,
    name TEXT,
    hotkey TEXT,
    type TEXT,
    cooldown REAL,
    description TEXT,
    PRIMARY KEY (slug, ability_uid)
);

CREATE TABLE talents (
    slug TEXT NOT NULL,
    tier INTEGER NOT NULL,
    sort INTEGER NOT NULL,
    name TEXT,
    type TEXT,
    description TEXT,
    PRIMARY KEY (slug, tier, sort)
);

CREATE TABLE maps (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    aliases_fr TEXT,
    objective TEXT,
    announcement_s INTEGER,
    first_contestable_s INTEGER,
    channel_s INTEGER,
    notes TEXT
);

CREATE TABLE map_cycles (
    map_slug TEXT NOT NULL,
    seq INTEGER NOT NULL,
    "when" TEXT NOT NULL,
    min_s INTEGER,
    max_s INTEGER,
    detail TEXT,
    PRIMARY KEY (map_slug, seq)
);
"""


def pull() -> None:
    if not os.path.isdir(os.path.join(CACHE, ".git")):
        sys.exit(f"clone absent : {CACHE}\n"
                 "git clone --depth 1 --filter=blob:none --sparse "
                 "https://github.com/heroespatchnotes/heroes-talents "
                 f"«{CACHE}» puis: git -C «{CACHE}» sparse-checkout set hero")
    subprocess.run(["git", "-C", CACHE, "pull", "--ff-only"], check=True)


def hero_files() -> list[str]:
    if not os.path.isdir(HERO_DIR):
        sys.exit(f"dossier absent : {HERO_DIR} (voir --pull / README)")
    return sorted(f for f in os.listdir(HERO_DIR) if f.endswith(".json"))


def build() -> dict:
    files = hero_files()
    commit = subprocess.run(["git", "-C", CACHE, "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)

    n_talents = n_abilities = 0
    for fn in files:
        slug = fn[:-5]
        with open(os.path.join(HERO_DIR, fn), encoding="utf-8") as f:
            d = json.load(f)
        con.execute(
            "INSERT INTO heroes VALUES (?,?,?,?,?,?,?,?)",
            (slug, d.get("name"), d.get("role"), d.get("expandedRole"),
             d.get("type"), d.get("releaseDate"), d.get("releasePatch"),
             json.dumps(d.get("tags", []), ensure_ascii=False)))
        for group, lst in (d.get("abilities") or {}).items():
            for ab in lst:
                con.execute(
                    "INSERT OR REPLACE INTO abilities VALUES (?,?,?,?,?,?,?)",
                    (slug, ab.get("uid"), ab.get("name"), ab.get("hotkey"),
                     ab.get("type"), ab.get("cooldown"),
                     ab.get("description")))
                n_abilities += 1
        for tier, lst in (d.get("talents") or {}).items():
            for t in lst:
                con.execute(
                    "INSERT OR REPLACE INTO talents VALUES (?,?,?,?,?,?)",
                    (slug, int(tier), t.get("sort"), t.get("name"),
                     t.get("type"), t.get("description")))
                n_talents += 1

    with open(TIMINGS, encoding="utf-8") as f:
        tm = json.load(f)
    for name, m in tm["maps"].items():
        con.execute("INSERT INTO maps VALUES (?,?,?,?,?,?,?,?)", (
            m["slug"], name, json.dumps(m.get("aliases_fr", []),
                                       ensure_ascii=False),
            m.get("objective"), m.get("announcement_s"),
            m.get("first_contestable_s"), m.get("channel_s"),
            json.dumps(m.get("notes", []), ensure_ascii=False)))
        for i, c in enumerate(m.get("next_after", [])):
            lo, hi = c["contestable_after_s"]
            con.execute("INSERT INTO map_cycles VALUES (?,?,?,?,?,?)",
                        (m["slug"], i, c["when"], lo, hi, c.get("detail")))

    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    con.executemany("INSERT INTO meta VALUES (?,?)", [
        ("heroes_talents_repo", "https://github.com/heroespatchnotes/heroes-talents"),
        ("heroes_talents_commit", commit),
        ("map_timings_patch", tm["meta"]["patch"]),
        ("built_at", now),
    ])
    con.commit()
    stats = {"heroes": len(files), "talents": n_talents,
             "abilities": n_abilities, "maps": len(tm["maps"]), "commit": commit[:10]}
    con.close()
    return stats


if __name__ == "__main__":
    if "--pull" in sys.argv:
        pull()
    s = build()
    print(f"kb.db reconstruit : {s['heroes']} héros, {s['talents']} talents, "
          f"{s['abilities']} capacités, {s['maps']} cartes "
          f"(heroes-talents@{s['commit']})")
