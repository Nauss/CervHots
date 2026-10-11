#!/usr/bin/env python
"""hotstate/live_probe.py — l'expérience « le replay est-il écrit en direct ? »

À lancer PENDANT une partie de HotS : il surveille le dossier de replays,
suit le fichier en cours d'écriture et tente de le décoder à chaque cycle.
À la fin, il répond noir sur blanc : quelles stats étaient déjà lisibles,
et à partir de quand.

C'est LA question qui décide de la source live du coach :
  - si le fichier se décode pendant la partie  -> replay partiel = stats
    complètes et légales, sans toucher à la mémoire du jeu ;
  - sinon -> retour au plan B (lecture mémoire, cf. etudes/rea) et au
    plan C (vision).

Usage:
    python live_probe.py [--interval 10] [--out rapport_live.jsonl]
                         [--replays-dir "C:/Users/.../Replays/Multiplayer"]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from collections import Counter
from pathlib import Path

import mpyq
from heroprotocol import versions

DEFAULT_REPLAYS_DIR = Path.home() / (
    "Documents/Heroes of the Storm/Accounts/405983616"
    "/2-Hero-1-1435752/Replays/Multiplayer"
)


def probe_once(path: Path) -> dict:
    """Tente de décoder l'état courant du fichier ; renvoie un instantané."""
    snap = {
        "wall": dt.datetime.now().isoformat(timespec="seconds"),
        "file": path.name,
        "size": path.stat().st_size if path.exists() else 0,
    }
    try:
        archive = mpyq.MPQArchive(str(path))
        header = versions.latest().decode_replay_header(
            archive.header["user_data_header"]["content"])
        snap["header_ok"] = True
        snap["build"] = header["m_version"]["m_baseBuild"]
        snap["loops"] = header.get("m_elapsedGameLoops")
        try:
            proto = versions.build(header["m_version"]["m_baseBuild"])
        except Exception:
            proto = versions.latest()
        for block, decoder in (
            ("details", lambda: proto.decode_replay_details(archive.read_file("replay.details"))),
            ("tracker", lambda: proto.decode_replay_tracker_events(archive.read_file("replay.tracker.events"))),
        ):
            try:
                data = decoder()
                if block == "details":
                    snap["details_ok"] = True
                    snap["players"] = len(data.get("m_playerList") or [])
                else:
                    events = list(data)
                    snap["tracker_ok"] = True
                    snap["tracker_counts"] = dict(
                        Counter(e.get("_event", "").rsplit(".", 1)[-1] for e in events))
            except Exception as exc:
                snap[f"{block}_error"] = f"{type(exc).__name__}: {exc}"[:200]
    except Exception as exc:
        snap["header_ok"] = False
        snap["error"] = f"{type(exc).__name__}: {exc}"[:200]
    return snap


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replays-dir", type=Path, default=DEFAULT_REPLAYS_DIR)
    ap.add_argument("--interval", type=int, default=10)
    ap.add_argument("--out", type=Path,
                    default=Path("live_probe_report.jsonl"))
    ap.add_argument("--idle-stop", type=int, default=180,
                    help="s'arrête après N s sans fichier actif (fin de partie)")
    args = ap.parse_args()

    seen_sizes: dict[str, int] = {}
    last_active = time.time()
    print(f"Surveillance de {args.replays_dir} (toutes les {args.interval} s)…")
    print("Lance une partie de HotS. Ctrl+C pour arrêter.")

    with args.out.open("a", encoding="utf-8") as out:
        while True:
            files = sorted(args.replays_dir.glob("*.StormReplay"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            active = None
            if files:
                f = files[0]
                recently_touched = time.time() - f.stat().st_mtime < 60
                growing = seen_sizes.get(f.name, f.stat().st_size) != f.stat().st_size
                if recently_touched and (growing or f.name not in seen_sizes):
                    active = f
                    seen_sizes[f.name] = f.stat().st_size

            if active is not None:
                last_active = time.time()
                snap = probe_once(active)
                out.write(json.dumps(snap, ensure_ascii=False) + "\n")
                out.flush()
                print(f"[{snap['wall']}] {snap['size'] / 1e6:6.2f} Mo | "
                      f"header={snap.get('header_ok')} "
                      f"details={snap.get('details_ok')} "
                      f"tracker={snap.get('tracker_ok')} "
                      f"loops={snap.get('loops')} "
                      + (f"| err={snap.get('error')}" if snap.get("error") else ""))
            else:
                if time.time() - last_active > args.idle_stop:
                    print("Plus de fichier actif depuis "
                          f"{args.idle_stop}s — fin de la surveillance.")
                    print(f"Rapport : {args.out.resolve()}")
                    break
                time.sleep(args.interval)
                continue
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
