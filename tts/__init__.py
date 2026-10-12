"""tts — synthèse vocale du coach : phrase + modèle + ton → parole pour Mumble.

Usage court :

    from tts import synthesize
    sp = synthesize("Ils sont trois à manquer à l'appel.", style="urgent")
    mumble.sound_output.add_sound(sp.pcm)   # PCM s16le 48 kHz mono

CLI : ``python -m tts "phrase" --out out.wav``. Test : ``python tts/smoke.py``.
"""
from .engines import (
                      DEFAULT_MODEL,
                      DEFAULT_STYLE,
                      DEFAULT_VOICES,
                      MODELS,
                      STYLES,
                      TtsError,
                      list_voices,
                      synthesize,
)
from .speech import SAMPLE_RATE, Speech

__all__ = [
                      "DEFAULT_MODEL",
                      "DEFAULT_STYLE",
                      "DEFAULT_VOICES",
                      "MODELS",
                      "SAMPLE_RATE",
                      "STYLES",
                      "Speech",
                      "TtsError",
                      "list_voices",
                      "synthesize",
]
