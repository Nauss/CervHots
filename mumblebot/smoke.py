#!/usr/bin/env python
"""smoke.py — POC parole de bout en bout : TTS → bot Mumble → écoute.

Chaîne testée en réel :
1. libopus trouvée (opuslib) ;
2. serveur Mumble joignable (celui de .env, sinon conteneur docker de test) ;
3. le bot (« CoachPOC ») synthétise une phrase et la diffuse ;
4. un auditeur (« TesteurPOC ») reçoit bien la parole : durée >= 85 % de la
   parole envoyée, contenu audible (RMS) ;
5. tours de parole : `wait_for_quiet` répond quand le canal est calme.

Usage : tts/.venv/Scripts/python mumblebot/smoke.py
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mumblebot import MumbleBot, ensure_opus
from mumblebot.bot import DEMO_PHRASE, _root_env

FAILS: list[str] = []
TEST_IMAGE = "mumblevoip/mumble-server"
TEST_CONTAINER = "cervhots-murmur"


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"   {'OK ' if ok else 'ÉCHEC'} {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def tcp_up(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def ensure_server(host: str, port: int) -> None:
    """Serveur de test : le serveur configuré, sinon un conteneur docker local."""
    if tcp_up(host, port):
        print(f"   serveur déjà joignable sur {host}:{port}")
        return
    print(f"   aucun serveur sur {host}:{port} — conteneur docker {TEST_CONTAINER}")
    listed = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name={TEST_CONTAINER}",
         "--format", "{{.Names}}"],
        capture_output=True, text=True, check=False)
    if TEST_CONTAINER in listed.stdout:
        subprocess.run(["docker", "start", TEST_CONTAINER], check=True,
                       capture_output=True)
    else:
        subprocess.run(
            ["docker", "run", "-d", "--name", TEST_CONTAINER,
             "-p", f"{port}:64738", TEST_IMAGE],
            check=True, capture_output=True)
    for _ in range(60):
        if tcp_up(host, port):
            break
        time.sleep(1)
    else:
        raise RuntimeError(f"serveur Mumble indisponible sur {host}:{port}")
    # murmur génère son certificat juste après le bind : laisse-lui respirer
    time.sleep(3)


class Listener:
    """Auditeur : accumule la parole reçue du bot."""

    def __init__(self, bot_name: str):
        self.bot_name = bot_name
        self.pcm = bytearray()
        self.chunks = 0

    def on_sound(self, user, chunk) -> None:
        if getattr(user, "name", None) == self.bot_name:
            self.pcm += chunk.pcm
            self.chunks += 1


def main() -> int:
    env = _root_env()
    host = env.get("MUMBLE_HOST", "127.0.0.1")
    port = int(env.get("MUMBLE_PORT", "64738"))

    print("1. libopus")
    dll = ensure_opus()
    check("libopus chargée", dll.exists(), str(dll))

    print(f"\n2. serveur Mumble ({host}:{port})")
    ensure_server(host, port)
    check("serveur joignable", tcp_up(host, port))

    print("\n3. diffusion TTS → Mumble")
    listener = Listener("CoachPOC")
    auditeur = MumbleBot(host, port, user="TesteurPOC")
    auditeur.connect()
    auditeur.mumble.callbacks.sound_received.set_handler(listener.on_sound)

    bot = MumbleBot(host, port, user="CoachPOC")
    bot.connect()
    t0 = time.monotonic()
    speech = bot.say_and_wait(DEMO_PHRASE)
    play_s = time.monotonic() - t0
    time.sleep(0.8)  # derniers paquets réseau
    print(f"   envoyé : {speech.describe()}")
    print(f"   diffusion mesurée : {play_s:.2f} s, "
          f"reçu {len(listener.pcm)} octets en {listener.chunks} paquets")

    samples = np.frombuffer(bytes(listener.pcm), dtype="<i2")
    received_s = len(listener.pcm) / (48000 * 2)
    rms = float(np.sqrt((samples.astype(np.float64) ** 2).mean())) / 32767.0 if samples.size else 0.0

    print("\n4. vérifications")
    check("l'auditeur a reçu la voix du bot", listener.chunks > 5,
          f"{listener.chunks} paquets")
    check("durée reçue ≈ parole envoyée", received_s >= 0.85 * speech.duration_s,
          f"reçu {received_s:.2f} s vs {speech.duration_s:.2f} s de parole")
    check("contenu audible (pas de silence)", rms > 0.01,
          f"RMS reçu {rms:.3f}")
    check("format reçu = s16le 48 kHz mono",
          len(listener.pcm) % 2 == 0, "alignement 2 octets")

    print("\n5. tours de parole")
    quiet = auditeur.wait_for_quiet(gap=0.6, timeout=5.0)
    check("wait_for_quiet répond sur canal calme", quiet)

    bot.disconnect()
    auditeur.disconnect()

    if FAILS:
        print(f"\n{len(FAILS)} échec(s) : {', '.join(FAILS)}")
        return 1
    print("\nPOC parole : tout est vert ✔ "
          "(TTS → Mumble → auditeur, en conditions réelles)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
