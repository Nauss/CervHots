#!/usr/bin/env python3
"""kb/briefing.py — compile le briefing court (3-4 points) du coach.

Déclenché quand la carte + les 10 héros sont connus (battlelobby ou état
hotstate). Sortie volontairement courte : 3-4 points, pas un cours. Tout ce
qu'il cite vient de kb/data/map_timings.json, kb.db (faits) et
kb/notes/ (jugement) — le cerveau ne reçoit rien d'autre.

Usage :
    python kb/briefing.py --map "Le val maudit" \
        --allies johanna,liming,rehgar,sonya,hanzo \
        --enemies valeera,anubarak,chromie,rehgar,valla [--t 240]

--t : temps de jeu en secondes (optionnel) → le prochain jalon de carte est
calculé de façon déterministe (jamais estimé par le LLM).
"""
import argparse
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "kb.db")
TIMINGS = os.path.join(HERE, "data", "map_timings.json")
NOTES = os.path.join(HERE, "notes")

# Noms français courants des héros (le jeu est en français) → slug canonique.
HEROS_FR = {
    "le boucher": "thebutcher", "les vikings perdus": "lostvikings",
    "sergent hammer": "sgthammer",
}

MAP_ALIASES_FR = {
    "le val maudit": "cursed-hollow", "le comté du dragon": "dragon-shire",
    "menace nucléaire": "warhead-junction",
    "les champs de l'éternité": "battlefield-of-eternity",
    "la tombe de la reine araignée": "tomb-of-the-spider-queen",
    "la passe d'alterac": "alterac-pass",
    "les sanctuaires infernaux": "infernal-shrines",
    "le temple d'hanamura": "hanamura-temple",
    "la mine hantée": "haunted-mines",
    "les jardins de terreur": "garden-of-terror",
    "le temple céleste": "sky-temple",
    "le laboratoire de braxis": "braxis-holdout",
    "la baie de cœur-noir": "blackhearts-bay",
    "la fonderie volskaya": "volskaya-foundry",
    "les tours du destin": "towers-of-doom",
    "la cité d'argent": "silver-city",
}


def norm(s: str) -> str:
    return s.strip().lower().replace("_", "-").replace("'", "").replace("’", "")


def resolve_map(raw: str, con: sqlite3.Connection) -> tuple[str, str]:
    """slug, nom canonique."""
    n = norm(raw)
    row = con.execute("SELECT slug, name FROM maps WHERE slug=?", (n,)).fetchone()
    if row:
        return row
    for slug, name, aliases in con.execute("SELECT slug, name, aliases_fr FROM maps"):
        al = json.loads(aliases)
        if n == norm(name) or any(n == norm(a) for a in al):
            return slug, name
    if n in MAP_ALIASES_FR:
        return resolve_map(MAP_ALIASES_FR[n], con)
    sys.exit(f"carte inconnue : {raw!r} (voir kb/data/map_timings.json)")


def resolve_hero(raw: str, con: sqlite3.Connection) -> str:
    n = norm(raw)
    if n in HEROS_FR:
        n = HEROS_FR[n]
    row = con.execute("SELECT slug FROM heroes WHERE slug=?", (n,)).fetchone()
    if row:
        return row[0]
    row = con.execute("SELECT slug FROM heroes WHERE lower(name)=?", (raw.strip().lower(),)).fetchone()
    if row:
        return row[0]
    # correspondance partielle unique (« morales » → ltmorales, « hammer » → sgthammer)
    hits = [r[0] for r in con.execute("SELECT slug, name FROM heroes")
            if n in r[0] or n in norm(r[1])]
    if len(hits) == 1:
        return hits[0]
    sys.exit(f"héros inconnu ou ambigu : {raw!r} → {hits or 'aucun'} (slugs = kb.db, table heroes)")


def hero_title(slug: str, con: sqlite3.Connection) -> str:
    return con.execute("SELECT name FROM heroes WHERE slug=?", (slug,)).fetchone()[0]


def fiche_section(slug: str, kind: str, section: str) -> str | None:
    """Texte complet de la section **X** : de la fiche (kind = heros|cartes)."""
    path = os.path.join(NOTES, kind, f"{slug}.md")
    if not os.path.isfile(path):
        return None
    text = open(path, encoding="utf-8").read()
    m = re.search(rf"\*\*{re.escape(section)}\*\*\s*:\s*(.+)", text)
    return m.group(1).strip() if m else None


def first_sentence(s: str) -> str:
    for sep in (". ", " ; "):
        if sep in s:
            return s.split(sep)[0].rstrip(".") + "."
    return s.rstrip(".") + "."


def fiche_note(slug: str, kind: str, section: str) -> str | None:
    full = fiche_section(slug, kind, section)
    return first_sentence(full) if full else None


def fmt_min(s: int) -> str:
    return f"{s // 60}:{s % 60:02d}"


def next_milestone(m: dict, t_s: int | None) -> str | None:
    """Prochain jalon de carte, calculé (déterministe)."""
    if t_s is None or not m.get("first_contestable_s"):
        return None
    cycles = m.get("next_after") or []
    best = None  # (t_estimé, « quand », lo, hi, k)
    for c in cycles:
        # hypothèse de calcul : le cycle de référence = médiane de la plage
        lo, hi = c["contestable_after_s"]
        est = (lo + hi) // 2
        k = 1
        while True:
            t = m["first_contestable_s"] + k * est
            if t > t_s:
                break
            k += 1
        if best is None or t < best[0]:
            best = (t, c["when"], lo, hi, k)
    if best is None:
        return None
    t, when, lo, hi, k = best
    if lo == hi:
        return f"prochain jalon estimé après « {when} » : vers {fmt_min(t)}"
    win_lo = fmt_min(m["first_contestable_s"] + k * lo)
    win_hi = fmt_min(m["first_contestable_s"] + k * hi)
    return (f"prochain jalon estimé après « {when} » : vers {fmt_min(t)} "
            f"(fenêtre {win_lo}-{win_hi})")


def build(map_raw: str, allies: list[str], enemies: list[str],
          t_s: int | None) -> str:
    con = sqlite3.connect(DB)
    mslug, mname = resolve_map(map_raw, con)
    with open(TIMINGS, encoding="utf-8") as f:
        tdata = json.load(f)["maps"]
    m = next(v for v in tdata.values() if v["slug"] == mslug)

    a_slugs = [resolve_hero(h, con) for h in allies]
    e_slugs = [resolve_hero(h, con) for h in enemies]

    lines = [f"BRIEFING — {mname}"]
    if t_s is not None:
        lines[0] += f" · {fmt_min(t_s)} de jeu"

    # 1. Carte : objectif + timing principal (fait)
    cyc = (m.get("next_after") or [{}])[0]
    timing = f"1er objectif contestable à {fmt_min(m['first_contestable_s'])}"
    if cyc.get("when"):
        lo, hi = cyc["contestable_after_s"]
        sp = f"{fmt_min(lo)}" if lo == hi else f"{fmt_min(lo)}-{fmt_min(hi)}"
        timing += f", puis +{sp} après « {cyc['when']} »"
    lines.append(f"1. CARTE — {m['objective']}. {timing}.")
    plan = fiche_note(mslug, "cartes", "Plan de jeu")
    if plan:
        lines.append(f"   {plan}")

    # 2. Notre compo : duos présents dans la compo (jugement), sinon rôles
    sy = []
    seen = set()
    for i, a in enumerate(a_slugs):
        for b in a_slugs[i + 1:]:
            if (a, b) in seen:
                continue
            hit = None
            for x, y in ((a, b), (b, a)):
                full = fiche_section(x, "heros", "Synergies") or ""
                name_y = hero_title(y, con)
                mpos = re.search(re.escape(name_y), full, re.IGNORECASE)
                if mpos:
                    lo = max(0, mpos.start() - 35)
                    hi = min(len(full), mpos.end() + 35)
                    snip = full[lo:hi].strip()
                    if lo > 0:
                        snip = "…" + snip.split(" ", 1)[-1] if " " in snip else "…" + snip
                    if hi < len(full):
                        snip = snip.rsplit(" ", 1)[0] + "…"
                    hit = f"{hero_title(x, con)}+{name_y} : {snip}"
                    break
            if hit:
                sy.append(hit)
                seen.add((a, b))
    if sy:
        lines.append("2. NOUS — " + " ; ".join(sy[:2]))
    else:
        roles = [f"{hero_title(s, con)} ({(fiche_note(s, 'heros', 'Rôle') or '').rstrip('.')})"
                 for s in a_slugs[:3]]
        lines.append("2. NOUS — " + " ; ".join(roles) + ".")

    # 3. EUX : comment les contrer (section Menaces de leurs fiches)
    men = [f"contrer {hero_title(s, con)} : {fiche_note(s, 'heros', 'Menaces').rstrip('.')}"
           for s in e_slugs if fiche_note(s, "heros", "Menaces")]
    if men:
        lines.append("3. EUX — " + " ; ".join(men[:3]) + ".")

    # 4. Jalon calculé (fait) ou piège de carte (jugement)
    ms = next_milestone(m, t_s)
    if ms:
        lines.append(f"4. JALON — {ms}.")
    else:
        piege = fiche_note(mslug, "cartes", "Pièges")
        if piege:
            lines.append(f"4. PIÈGE — {piege}")

    con.close()
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map", required=True)
    ap.add_argument("--allies", required=True, help="5 noms/slugs, séparés par des virgules")
    ap.add_argument("--enemies", required=True, help="5 noms/slugs, séparés par des virgules")
    ap.add_argument("--t", type=int, default=None, help="temps de jeu en secondes")
    a = ap.parse_args()
    allies = [x for x in a.allies.split(",") if x.strip()]
    enemies = [x for x in a.enemies.split(",") if x.strip()]
    if len(allies) != 5 or len(enemies) != 5:
        sys.exit("attendu : 5 alliés et 5 ennemis")
    print(build(a.map, allies, enemies, a.t))


if __name__ == "__main__":
    main()
