#!/usr/bin/env python
"""bot.py — le bot parole de CervHots : phrase du coach → TTS → Mumble.

Consomme le contrat ``tts.Speech`` (PCM s16le 48 kHz mono) et le pousse dans
``mumble.send_audio.add_sound()`` — le format exact exigé par pymumble
(preuve et débats s16/s32 : `etudes/mumble/ETUDE.md`).

Usage (avec l'interpréteur de la couche voix, tts/.venv) :

    tts/.venv/Scripts/python mumblebot/bot.py "Le nœud haut tombe dans vingt secondes."
    tts/.venv/Scripts/python mumblebot/bot.py --demo --style urgent
    tts/.venv/Scripts/python mumblebot/bot.py "phrase" --channel "Notre équipe" --wait-quiet

Config (priorité : arguments > env > .env racine) :
    MUMBLE_HOST, MUMBLE_PORT, MUMBLE_USER, MUMBLE_PASSWORD, MUMBLE_CHANNEL
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------- opus ----
# opuslib ne trouve la DLL Windows que via ctypes.util.find_library, qui ne
# connaît que les répertoires système : on précharge nous-mêmes la DLL et on
# pointe explicitement le chemin AVANT d'importer pymumble (qui importe
# opuslib). Priorité : OPUS_LIB > mumblebot/lib/opus.dll > Audacity > pyogg.
def ensure_opus() -> Path:
    here = Path(__file__).resolve().parent
    candidates: list[Path] = []
    if os.environ.get("OPUS_LIB"):
        candidates.append(Path(os.environ["OPUS_LIB"]))
    candidates += [here / "lib" / "opus.dll",
                   Path(r"C:\Program Files\Audacity\opus.dll")]
    try:
        import pyogg  # wheel Windows qui embarque opus.dll
        candidates.append(Path(pyogg.__file__).parent / "opus.dll")
    except ImportError:
        pass

    for path in candidates:
        if path.exists():
            ctypes.CDLL(str(path))
            orig = ctypes.util.find_library

            def find_library(name, _p=str(path), _orig=orig):
                return _p if name == "opus" else _orig(name)

            ctypes.util.find_library = find_library
            return path
    raise RuntimeError(
        "libopus introuvable — définis OPUS_LIB ou dépose opus.dll "
        "dans mumblebot/lib/ (ex. : copie de celle d'Audacity ou du wheel pyogg)"
    )


ensure_opus()
from mumble import Mumble  # noqa: E402  (après ensure_opus, cf. ci-dessus)


DEMO_PHRASE = ("Un, deux, trois. Test de la voix du coach : "
               "si tu m'entends, la chaîne TTS vers Mumble fonctionne.")
ROOT = Path(__file__).resolve().parent.parent


def _root_env() -> dict:
    """Lit le .env racine (config centralisée du monorepo)."""
    out: dict[str, str] = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


class MumbleBot:
    """Client Mumble qui porte la voix du coach (canal + tours de parole)."""

    def __init__(self, host: str, port: int = 64738, user: str = "Coach",
                 password: str = "", channel: str = "", model: str | None = None,
                 style: str | None = None):
        self.host, self.port, self.user = host, int(port), user
        self.password, self.channel = password or None, channel
        self.model, self.style = model, style
        self.mumble: Mumble | None = None
        self._last_voice = 0.0  # dernier instant où un autre a parlé

    # ---- connexion ----
    def connect(self, timeout: float = 20.0, attempts: int = 3) -> "MumbleBot":
        # pymumble libère son « prêt » même sur échec de connexion : on vérifie
        # la vraie session serveur (users.myself posé par ServerSync), et on
        # retente — murmur accepte mal les clients pendant sa génération de
        # certificat au démarrage.
        last = None
        for attempt in range(1, attempts + 1):
            self.mumble = Mumble(self.host, self.user, port=self.port,
                                 password=self.password, enable_audio=True,
                                 force_tcp_only=True)
            self.mumble.callbacks.sound_received.set_handler(self._on_sound)
            self.mumble.start()
            ok = self.mumble.wait_until_connected(timeout=timeout)
            if ok and self.mumble.users.myself is not None:
                break
            last = f"tentative {attempt}/{attempts} : handshake refusé"
            self.mumble.stop()
            self.mumble.join()
            self.mumble = None
            time.sleep(2)
        else:
            raise RuntimeError(
                f"connexion Mumble impossible vers {self.host}:{self.port} ({last})")
        if self.channel:
            channel = self.mumble.channels.find_by_name(self.channel)
            if channel is None:
                raise RuntimeError(f"canal introuvable : {self.channel!r}")
            channel.move_in()
        return self

    def _on_sound(self, user, chunk) -> None:
        if user is not self.mumble.users.myself:
            self._last_voice = time.monotonic()

    # ---- parole ----
    def say(self, text: str, *, model: str | None = None,
            style: str | None = None, speed: float | None = None,
            ) -> tuple[threading.Event, object]:
        """Synthétise ``text`` et l'envoie. Renvoie (événement buffer vide, Speech)."""
        from tts import DEFAULT_MODEL, synthesize

        if self.mumble is None or self.mumble.users.myself is None:
            raise RuntimeError("bot non connecté — appelle connect() d'abord")
        speech = synthesize(text,
                            model=model or self.model or DEFAULT_MODEL,
                            style=style or self.style, speed=speed)
        return self.mumble.send_audio.add_sound(speech.pcm), speech

    def say_and_wait(self, text: str, **kw) -> object:
        """Synthétise, diffuse et attend la fin réelle de la diffusion."""
        event, speech = self.say(text, **kw)
        event.wait()
        return speech

    def wait_for_quiet(self, gap: float = 0.6, timeout: float = 15.0) -> bool:
        """Cède la parole : attend qu'aucun autre utilisateur ne parle (``gap`` s)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if time.monotonic() - self._last_voice >= gap:
                return True
            time.sleep(0.1)
        return False

    def disconnect(self) -> None:
        if self.mumble is not None:
            self.mumble.stop()
            self.mumble.join()
            self.mumble = None


def main() -> int:
    env = _root_env()
    ap = argparse.ArgumentParser(description="Bot parole CervHots (TTS → Mumble)")
    ap.add_argument("texte", nargs="*", help="phrase à prononcer")
    ap.add_argument("--demo", action="store_true", help="phrase fixe du POC")
    ap.add_argument("--model", default=None, help="modèle TTS (défaut : piper)")
    ap.add_argument("--style", default=None,
                    help="ton : neutre, calme, urgent, enjoue")
    ap.add_argument("--speed", type=float, default=None, help="vitesse 0.5-2.0")
    ap.add_argument("--host", default=os.environ.get("MUMBLE_HOST",
                                                     env.get("MUMBLE_HOST", "127.0.0.1")))
    ap.add_argument("--port", type=int, default=int(os.environ.get(
        "MUMBLE_PORT", env.get("MUMBLE_PORT", "64738"))))
    ap.add_argument("--user", default=os.environ.get("MUMBLE_USER",
                                                     env.get("MUMBLE_USER", "Coach")))
    ap.add_argument("--password", default=os.environ.get(
        "MUMBLE_PASSWORD", env.get("MUMBLE_PASSWORD", "")))
    ap.add_argument("--channel", default=os.environ.get(
        "MUMBLE_CHANNEL", env.get("MUMBLE_CHANNEL", "")))
    ap.add_argument("--wait-quiet", action="store_true",
                    help="attend que personne ne parle avant de parler")
    ap.add_argument("--linger", type=float, default=0.0,
                    help="reste connecté N secondes après la phrase")
    args = ap.parse_args()

    text = " ".join(args.texte).strip() or (DEMO_PHRASE if args.demo else "")
    if not text:
        ap.error("il manque la phrase à prononcer (ou --demo)")

    bot = MumbleBot(args.host, args.port, args.user, args.password,
                    args.channel, model=args.model, style=args.style)
    print(f"connexion {args.host}:{args.port} en {args.user!r}…")
    bot.connect()
    print("connecté." + (f" canal : {args.channel!r}" if args.channel else ""))

    if args.wait_quiet:
        print("respect des tours de parole…")
        bot.wait_for_quiet()

    speech = bot.say_and_wait(text, speed=args.speed)
    print(f"diffusé : {speech.describe()}")

    if args.linger > 0:
        time.sleep(args.linger)
    bot.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
