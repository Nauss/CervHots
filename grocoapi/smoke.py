#!/usr/bin/env python
"""smoke.py — test de bout en bout de l'API de Groco via grocoapi.

health -> me -> models -> accounts -> (chat si un compte est rattaché).
Usage : python grocoapi/smoke.py [--force-chat]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grocoapi import GrocoClient, GrocoError  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-chat", action="store_true",
                    help="tente un appel chat même sans compte listé")
    args = ap.parse_args()

    c = GrocoClient()
    print(f"base_url : {c.base_url}")

    print("\n1. health      :", c.health())
    me = c.me()
    print(f"2. me          : {me.get('name')} (role={me.get('role')}, "
          f"scopes={me.get('scopes')})")

    models = c.models()
    print(f"3. models      : {len(models)} modèle(s)")
    for m in models[:10]:
        print("   -", m.get("id"))

    accounts = c.accounts()
    print(f"4. accounts    : {len(accounts)} compte(s)")
    for a in accounts[:5]:
        print(f"   - {a.get('id')} | {a.get('name')} | {a.get('provider', '?')}")

    if not accounts and not args.force_chat:
        print("\n5. chat        : SKIPPED — aucun compte LLM rattaché.")
        print("   (côté Groco : POST /v1/accounts + login SSO, puis réessayer)")
        return

    print("\n5. chat        : appel de test…")
    try:
        answer = c.ask("Dis bonjour en un mot.", timeout=120)
        print(f"   réponse     : {answer.strip()[:120]!r}")
    except GrocoError as e:
        print(f"   ÉCHEC       : {e}")


if __name__ == "__main__":
    main()
