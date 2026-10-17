"""Diagnostic explicite des compteurs : ce n'est PAS du coaching tactique."""
from __future__ import annotations

import json
import time

from grocoapi import GrocoError

from .state import VALIDATED_COUNTERS

SYSTEM = """Tu testes la chaîne technique CervHots, pas une stratégie de jeu.
Les données sont des compteurs GLOBAUX cumulés observés, pas des morts par équipe
ni un état tactique. Aucun PV, position, niveau ou temps de jeu n'est connu.
Sélectionne exactement une des phrases_autorisees, sans la modifier ni ajouter
un conseil. Réponds uniquement par {"texte":"la phrase choisie"}.
Un champ absent est inconnu : ne le remplace jamais par zéro.
"""
LABELS = {"deaths_total": "morts", "respawns_total": "réapparitions",
          "globes_total": "globes"}


def diagnose(client, raw: dict, log, *, model=None, timeout=15.0) -> str:
    """Journaliser les données et accepter seulement une formulation factuelle exacte."""
    stats = {key: raw.get("stats", {}).get(key) for key in VALIDATED_COUNTERS
             if type(raw.get("stats", {}).get(key)) is int
             and raw["stats"][key] >= 0}
    if not stats:
        raise ValueError("aucun compteur mémoire validé disponible")
    state = {"meta": {"source": raw.get("meta", {}).get("source", "unknown")},
             "stats": stats}
    if raw.get("local_player") is not None:
        from .state import snapshot

        clean = snapshot(raw)
        state["meta"].update({k: v for k, v in clean["meta"].items()
                              if k in ("map", "context_source")})
        state.update({k: clean[k] for k in ("local_player", "composition", "ally_team",
                                           "composition_complete") if k in clean})
    values = ", ".join(f"{value} {LABELS[key]}" for key, value in stats.items())
    allowed = [f"Test diagnostic, compteurs globaux au relevé : {values}.",
               f"Au relevé de diagnostic, les totaux globaux sont : {values}."]
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps(
                    {"mode": "diagnostic", "etat": state, "phrases_autorisees": allowed},
                    ensure_ascii=False)}]
    log("observation", state)
    log("api_requete", {"model": model, "messages": messages})
    response = client.chat(messages, model=model, timeout=timeout)
    content = response["choices"][0]["message"]["content"]
    log("api_reponse", {"content": content})
    result = json.loads(content)
    if not isinstance(result, dict) or result.get("texte") not in allowed:
        raise ValueError("réponse diagnostic non conforme aux valeurs observées")
    text = result["texte"]
    log("phrase_validee", {"texte": text})
    return text


def run_session(read_state, client, log, *, model=None, synthesize=None, deliver=None,
                cycles=6, interval=30.0, timeout=15.0, max_age=20.0,
                stop_requested=lambda: False, clock=time.monotonic, wait=time.sleep):
    """Un relevé et un appel à la fois ; arrêt borné, sans rattrapage en rafale."""
    if not 1 <= cycles <= 12 or interval < 20 or max_age <= 0:
        raise ValueError("session limitée à 1–12 cycles, intervalle minimal 20 s")
    completed = 0
    for cycle in range(1, cycles + 1):
        if stop_requested():
            break
        started = clock()

        def fresh(started=started):
            return not stop_requested() and clock() - started <= max_age

        log("cycle_demarre", {"cycle": cycle})
        try:
            raw = read_state()
            log("scan_termine", {"duree_s": round(clock() - started, 3)})
            if not fresh():
                log("observation_perimee", {"phase": "lecture"})
            else:
                text = diagnose(client, raw, log, model=model, timeout=min(timeout, max_age))
                if not fresh():
                    log("observation_perimee", {"phase": "api"})
                elif synthesize is not None:
                    speech = synthesize(text)
                    log("tts_termine", {"duree_audio_s": speech.duration_s})
                    if not fresh():
                        log("observation_perimee", {"phase": "tts"})
                    elif deliver is not None:
                        sent = deliver(speech, fresh)
                        log("mumble_envoye" if sent else "diffusion_annulee",
                            {"texte": text, "ecoute_humaine": "non_confirmee"})
                else:
                    log("diagnostic_sans_audio", {"texte": text})
        except GrocoError as exc:
            # Ne pas recopier une réponse HTTP susceptible de contenir des secrets.
            log("erreur_api", {"status": exc.status})
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            log("cycle_rejete", {"type": type(exc).__name__})
        completed += 1
        if cycle != cycles:
            deadline = max(started + interval, clock())
            while clock() < deadline and not stop_requested():
                wait(min(1.0, deadline - clock()))
    log("session_fin", {"cycles": completed,
                        "raison": "arret_demande" if stop_requested() else "limite_atteinte"})
    return completed


def main(argv=None) -> int:
    """Entrée live dédiée ; aucun accès processus ou audio lors de l'import/help."""
    import argparse
    import datetime as dt
    import os
    from collections import Counter
    from pathlib import Path

    from grocoapi import GrocoClient
    from grocoapi.client import _load_env_file

    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True,
                        help="autoriser explicitement la lecture mémoire HotS")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--player", help="nom local pour résoudre le contexte initData")
    parser.add_argument("--cycles", type=int, default=6)
    parser.add_argument("--interval", type=float, default=30.0)
    parser.add_argument("--model")
    parser.add_argument("--log-dir", type=Path)
    parser.add_argument("--stop-file", type=Path, default=root / "out/test-live/STOP")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--mumble", action="store_true",
                        help="diffuser réellement, après accord et clic manuel")
    output.add_argument("--wav-dir", type=Path, help="fichiers uniquement, aucun son")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=64739)
    parser.add_argument("--channel", default="Root")
    parser.add_argument("--user", default="Coach-Live-Test")
    args = parser.parse_args(argv)
    if not 1 <= args.cycles <= 12 or not 20 <= args.interval <= 120:
        parser.error("1–12 cycles et intervalle de 20–120 secondes requis")

    directory = args.log_dir or root / "out/test-live" / dt.datetime.now().strftime(
        "session-%Y%m%d-%H%M%S-%f")
    directory.mkdir(parents=True, exist_ok=False)
    current = root / "out/test-live/current.json"
    current.parent.mkdir(parents=True, exist_ok=True)
    lock = root / "out/test-live/RUNNING"
    counts = Counter()
    status = "demarrage"
    backend = bot = lock_file = None

    def log(event, data):
        counts[event] += 1
        row = {"timestamp": dt.datetime.now(dt.UTC).isoformat(),
               "event": event, "data": data}
        line = json.dumps(row, ensure_ascii=False)
        with (directory / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
        print(line, flush=True)

    def save_status():
        current.write_text(json.dumps({
            "status": status, "pid": os.getpid(), "log_dir": str(directory),
            "stop_file": str(args.stop_file), "etapes": dict(counts),
            "ecoute_humaine": "non_confirmee",
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        lock_file = lock.open("x", encoding="utf-8")
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        if args.stop_file.exists():
            raise RuntimeError("un arrêt a déjà été demandé ; retirer STOP avant un nouvel essai")
        save_status()
        # Opt-in vérifié par argparse AVANT ces imports et l'ouverture du processus.
        from hotstate.context import make_probe
        from hotstate.reader import ProcessBackend
        from hotstate.reader import snapshot as memory_snapshot

        context = make_probe(args.player, live=True)
        try:
            backend = ProcessBackend(args.pid)
        except SystemExit as exc:
            raise RuntimeError(str(exc)) from None
        mapping = json.loads((root / "hotstate/triggers_map.json").read_text(encoding="utf-8"))
        env = _load_env_file()
        client = GrocoClient()
        model = args.model or os.environ.get("GROCO_MODEL") or env.get("GROCO_MODEL")
        synthesize = deliver = None
        if args.mumble or args.wav_dir:
            from tts import synthesize as tts_synthesize

            synthesize = lambda text: tts_synthesize(text, model="piper", style="neutre")
        if args.mumble:
            from mumblebot import MumbleBot

            from .voice import send_to_mumble

            bot = MumbleBot(args.host, args.port, args.user,
                            os.environ.get("MUMBLE_PASSWORD", env.get("MUMBLE_PASSWORD", "")),
                            args.channel)
            bot.connect()
            log("mumble_connecte", {"host": args.host, "port": args.port,
                                    "channel": args.channel})

            def deliver(speech, fresh):
                myself = bot.mumble.users.myself
                audience = [u for u in bot.mumble.users.by_session().values()
                            if u.session != myself.session and u.channel_id == myself.channel_id
                            and not u.self_deaf and not u.deaf]
                log("mumble_auditeurs", {"nombre": len(audience)})
                return bool(audience) and send_to_mumble(bot, speech, fresh)
        elif args.wav_dir:
            args.wav_dir.mkdir(parents=True, exist_ok=True)
            index = [0]

            def deliver(speech, fresh):
                if not fresh():
                    return False
                index[0] += 1
                path = speech.save_wav(args.wav_dir / f"diagnostic-{index[0]}.wav")
                log("wav_ecrit", {"path": str(path)})
                return False  # Un WAV n'est jamais compté comme envoi Mumble.

        status = "en_cours"
        log("session_demarre", {"pid_jeu": backend.pid, "mode": "diagnostic",
                               "cycles_max": args.cycles, "intervalle_s": args.interval})
        save_status()
        run_session(lambda: memory_snapshot(backend, mapping, context=context), client, log, model=model,
                    synthesize=synthesize, deliver=deliver, cycles=args.cycles,
                    interval=args.interval, stop_requested=args.stop_file.exists)
        status = "arretee" if args.stop_file.exists() else "terminee"
        return 0
    except KeyboardInterrupt:
        status = "arretee"
        log("arret_clavier", {})
        return 130
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        status = "erreur"
        log("erreur_session", {"type": type(exc).__name__,
                               "message": str(exc) if not isinstance(exc, GrocoError)
                               else f"API HTTP {exc.status}"})
        return 1
    finally:
        if bot is not None:
            bot.disconnect()
        if backend is not None:
            import ctypes

            close = backend.k32.CloseHandle
            close.argtypes = [ctypes.c_void_p]
            close.restype = ctypes.c_int
            close(backend.handle)
        if lock_file is not None:
            save_status()
            lock_file.close()
            lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
