#!/usr/bin/env python3
"""kb/tools/seed_heros.py — écrit kb/notes/heros/<slug>.md à partir des lots
_heros_1/2/3.py (couche jugement, rédigée par LLM le 12/10/2026).

Graine uniquement : APRÈS usage, les fiches s'éditent directement dans
kb/notes/heros/ (rejouer ce script écrase les modifications manuelles).
Les faits chiffrés (talents, CD, descriptions) sont dans kb.db, pas ici.

Usage : python kb/tools/seed_heros.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _heros_1 import HEROS as H1  # noqa: E402
from _heros_2 import HEROS as H2  # noqa: E402
from _heros_3 import HEROS as H3  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "notes", "heros")

HEADER = (
    "> Fiche rédigée par LLM le 12/10/2026 — **à relire** (couche jugement).\n"
    "> Les faits chiffrés (talents, CD, descriptions) sont dans `kb/data/kb.db`,\n"
    "> pas ici. Source des jugements : méta HotS connue (guides, compétitif).\n"
)


def main() -> None:
    heros = {}
    for part in (H1, H2, H3):
        overlap = set(heros) & set(part)
        if overlap:
            sys.exit(f"doublons entre lots : {sorted(overlap)}")
        heros.update(part)
    os.makedirs(OUT, exist_ok=True)
    con = sqlite3.connect(os.path.join(HERE, "..", "data", "kb.db"))
    for slug, body in heros.items():
        row = con.execute("SELECT name FROM heroes WHERE slug=?", (slug,)).fetchone()
        title = row[0] if row else slug
        with open(os.path.join(OUT, f"{slug}.md"), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(HEADER + "\n# " + title + "\n\n" + body)
    con.close()
    print(f"{len(heros)} fiches héros écrites dans {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
