"""tts — synthèse vocale du coach : phrase + modèle + ton → parole pour Mumble.

Usage court :

    from tts import synthesize
    sp = synthesize("Ils sont trois à manquer à l'appel.",
                    model="kokoro", style="urgent")
    mumble.sound_output.add_sound(sp.pcm)   # PCM s16le 48 kHz mono

CLI : ``python -m tts "phrase" --out out.wav``. Test : ``python tts/smoke.py``.
"""
from .engines import (DEFAULT_MODEL, DEFAULT_VOICES, DEFAULT_STYLE, MODELS,
                      STYLES, TtsError, list_voices, synthesize)
from .speech import SAMPLE_RATE, Speech

__all__ = [
    "Speech", "synthesize", "list_voices", "TtsError",
    "MODELS", "STYLES", "DEFAULT_MODEL", "DEFAULT_VOICES", "DEFAULT_STYLE",
    "SAMPLE_RATE",
]
