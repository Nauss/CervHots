"""Adaptateur de diffusion, importé seulement avec activation explicite de Mumble."""
from __future__ import annotations

import time


def send_to_mumble(bot, speech, fresh, *, timeout: float = 3.0) -> bool:
    """Pas de TTS ici : la fraîcheur a déjà été revérifiée après synthèse."""
    if not bot.wait_for_quiet(timeout=timeout) or not fresh():
        return False
    if bot.mumble is None or bot.mumble.users.myself is None or bot._lost:
        raise RuntimeError("bot Mumble déconnecté")
    event = bot.mumble.send_audio.add_sound(speech.pcm)
    deadline = time.monotonic() + speech.duration_s + 5.0
    while not event.is_set():
        if bot._lost or not bot.mumble.is_alive():
            raise RuntimeError("connexion Mumble coupée pendant la diffusion")
        if time.monotonic() >= deadline:
            raise RuntimeError("diffusion Mumble bloquée")
        event.wait(0.2)
    return True
