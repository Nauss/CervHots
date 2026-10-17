"""python -m cerveau : silencieux par défaut ; Mumble uniquement sur demande."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

from grocoapi import GrocoClient, GrocoError
from grocoapi.client import _load_env_file

from .brain import Coach
from .runner import ROOT, Pipeline
from .state import snapshot


def positive(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("un nombre strictement positif et fini est requis")
    return value


def make_source(args):
    options = {"at": args.at, "team": args.team, "map_name": args.map,
               "allies": args.allies, "enemies": args.enemies}
    if args.state:
        def read_file():
            raw = json.loads(args.state.read_text(encoding="utf-8"))
            state = snapshot(raw, **options)
            source = state["meta"].get("source")
            if (source != "replay" and (source != "dump" or args.watch)
                    and time.time() - args.state.stat().st_mtime > args.max_age):
                raise ValueError("fichier d'état périmé : le producteur hotstate doit l'actualiser")
            return state
        return read_file, None

    # Aucun import/accès mémoire tant que --dump ou --live n'est pas demandé.
    from hotstate.context import make_probe
    from hotstate.reader import DumpBackend, ProcessBackend
    from hotstate.reader import snapshot as memory_snapshot

    mapping = json.loads((ROOT / "hotstate/triggers_map.json").read_text(encoding="utf-8"))
    context = make_probe(getattr(args, "player", None), live=not args.dump)
    backend = (DumpBackend(*map(Path, args.dump), image=getattr(args, "image", None)) if args.dump
               else ProcessBackend(args.pid))
    return lambda: snapshot(memory_snapshot(backend, mapping, context=context), **options), backend


def main(argv=None) -> int:
    env = _load_env_file()
    def config(key, fallback=None):
        return os.environ.get(key, env.get(key, fallback))

    parser = argparse.ArgumentParser(description=__doc__)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--state", type=Path, help="JSON hotstate (replay ou mémoire)")
    source_group.add_argument("--dump", nargs=2, metavar=("HEAP_BIN", "HEAP_JSON"))
    source_group.add_argument("--live", action="store_true", help="lecture mémoire du jeu, opt-in")
    source_group.add_argument("--check", action="store_true", help="santé et modèles, sans chat ni son")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--player", help="nom local pour résoudre le contexte initData (mémoire)")
    parser.add_argument("--image", type=Path, help="module capturé avec --dump, pour l'état natif")
    parser.add_argument("--at", type=float, help="temps observé du replay, requis pour éviter le futur")
    parser.add_argument("--team", type=int, choices=(0, 1),
                        help="équipe observée ; sinon équipe locale détectée, ou 0 sans contexte")
    parser.add_argument("--map", help="carte si absente de hotstate")
    for name in ("allies", "enemies"):
        parser.add_argument(f"--{name}", type=lambda s: [x.strip() for x in s.split(",") if x.strip()],
                            help="héros séparés par des virgules, si absents de hotstate")
    parser.add_argument("--model", default=config("GROCO_MODEL"), help="compte/modèle de /v1/models")
    parser.add_argument("--reasoning-effort", default=config("GROCO_REASONING_EFFORT"))
    parser.add_argument("--timeout", type=positive, default=25.0)
    parser.add_argument("--max-age", type=positive, default=20.0)
    parser.add_argument("--cooldown", type=positive, default=15.0)
    parser.add_argument("--min-confidence", type=float, default=0.75)
    parser.add_argument("--watch", action="store_true", help="boucle ; sinon un seul cycle")
    parser.add_argument("--interval", type=positive, default=25.0)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--wav", type=Path, help="synthétiser un WAV, SANS lecture sonore")
    output.add_argument("--mumble", action="store_true", help="ACTIVER la diffusion sonore")
    parser.add_argument("--tts-model", choices=("piper", "kokoro"), default="piper")
    parser.add_argument("--host", default=config("MUMBLE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(config("MUMBLE_PORT", "64738")))
    parser.add_argument("--user", default=config("MUMBLE_USER", "Coach"))
    parser.add_argument("--channel", default=config("MUMBLE_CHANNEL", ""))
    args = parser.parse_args(argv)
    if args.player is not None and not (args.live or args.dump):
        parser.error("--player nécessite --live ou --dump")
    if args.image is not None and not args.dump:
        parser.error("--image nécessite --dump")
    if not math.isfinite(args.min_confidence) or not 0 <= args.min_confidence <= 1:
        parser.error("--min-confidence doit être entre 0 et 1")
    if args.watch and args.interval < 15:
        parser.error("--watch exige un intervalle d'au moins 15 secondes")
    if args.watch and args.at is not None:
        parser.error("--at est un instant figé de replay : pas de --watch")
    if args.watch and args.dump:
        parser.error("--dump est un instant figé : pas de --watch")

    bot = backend = None
    try:
        if args.check:
            client = GrocoClient()
            print(json.dumps({"health": client.health(),
                              "models": [m["id"] for m in client.models()]}, ensure_ascii=False))
            return 0
        read_state, backend = make_source(args)
        read_state()  # Valider la source avant tout appel LLM ou connexion sonore.
        client = GrocoClient()
        coach = Coach(client, args.model, min(args.timeout, args.max_age),
                      args.min_confidence, args.reasoning_effort)
        synthesize = deliver = None
        if args.wav or args.mumble:
            from tts import synthesize as tts_synthesize
            synthesize = lambda d: tts_synthesize(d.texte, model=args.tts_model, style=d.style)
        if args.wav:
            def deliver(decision, speech, valid):
                if not valid():
                    return False
                speech.save_wav(args.wav)
                return True
        if args.mumble:
            from mumblebot import MumbleBot

            from .voice import send_to_mumble
            bot = MumbleBot(args.host, args.port, args.user,
                            config("MUMBLE_PASSWORD", ""), args.channel)
            bot.connect()
            deliver = lambda d, speech, valid: send_to_mumble(bot, speech, valid)
        pipeline = Pipeline(coach, read_state, synthesize=synthesize, deliver=deliver,
                            cooldown=args.cooldown, max_age=args.max_age)
        while True:
            started = time.monotonic()
            decision = pipeline.cycle()
            print(json.dumps(asdict(decision), ensure_ascii=False), flush=True)
            if not args.watch:
                return 1 if decision.raison.startswith("erreur_api_") else 0
            # Jamais de rattrapage en rafale : un cycle lent décale le suivant.
            time.sleep(max(1.0, args.interval - (time.monotonic() - started)))
    except KeyboardInterrupt:
        return 130
    except (GrocoError, OSError, ValueError, TypeError, RuntimeError, ImportError) as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 1
    finally:
        if bot is not None:
            bot.disconnect()
        if backend is not None and hasattr(backend, "close"):
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
