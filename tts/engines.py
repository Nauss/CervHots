"""engines.py — moteurs de synthèse (Kokoro, Piper) derrière une seule API.

Entrée : la phrase du coach + un modèle + des options de ton.
Sortie : un ``Speech`` (PCM s16le 48 kHz mono, prêt pour Mumble).

Tout est local et gratuit : deux modèles ONNX exécutés par onnxruntime,
aucun appel réseau à la synthèse. Les modèles vivent dans ``tts/models/``
(téléchargés par ``python tts/download_models.py``).

Options :
- ``model``        : "piper" (défaut, acté à l'écoute du proprio) ou
                     "kokoro" (qualité) ;
- ``voice``        : voix du modèle (kokoro : 54 voix, ex ``ff_siwis`` FR ;
                     piper : ``fr_FR-siwis-medium``, téléchargée à la demande) ;
- ``style``        : preset de ton — "neutre", "calme", "urgent", "enjoue" ;
- ``speed``        : 0.5 à 2.0 (1.0 = normal) ;
- ``expressivity`` : 0.0 à 1.0, variation prosodique (piper seul : bruit de
                     durée/phonèmes ; kokoro n'a pas ce réglage, ignoré) ;
- ``lang``         : langue de phonémisation de kokoro ("fr" par défaut) ;
- ``sentence_pause`` / ``clause_pause`` : pauses en secondes (kokoro seul).

Un argument explicite écrase toujours la valeur du preset.
"""
from __future__ import annotations

import os
import time
import urllib.request
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .resample import resample
from .speech import SAMPLE_RATE, Speech

MODELS_DIR = Path(
    os.environ.get("CERVHOTS_TTS_MODELS", Path(__file__).resolve().parent / "models")
)

MODELS = ("kokoro", "piper")
# Défaut acté par le proprio après écoute comparative (12/10/2026) :
# « Piper semble très bien » — rendu suffisant, latence supérieure.
DEFAULT_MODEL = "piper"
DEFAULT_VOICES = {"kokoro": "ff_siwis", "piper": "fr_FR-siwis-medium"}

# Ton → prosodie. La couleur émotionnelle vient du texte du coach ; ici on ne
# règle que le débit, la variation prosodique et les pauses.
STYLES = {
    "neutre": {"speed": 1.00, "expressivity": 0.50,
               "sentence_pause": 0.25, "clause_pause": 0.10},
    "calme":  {"speed": 0.92, "expressivity": 0.35,
               "sentence_pause": 0.35, "clause_pause": 0.15},
    "urgent": {"speed": 1.12, "expressivity": 0.75,
               "sentence_pause": 0.15, "clause_pause": 0.06},
    "enjoue": {"speed": 1.05, "expressivity": 0.90,
               "sentence_pause": 0.25, "clause_pause": 0.12},
}
DEFAULT_STYLE = "neutre"

PIPER_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# espeak (phonémisation de kokoro) attend les codes de voix exacts :
# il n'existe pas de « fr » nu, seulement fr-fr/fr-be/fr-ch.
LANG_ALIASES = {"fr": "fr-fr", "en": "en-us"}


class TtsError(RuntimeError):
    """Erreur de la brique TTS (modèle absent, voix inconnue, texte vide…)."""


@dataclass
class SynthParams:
    speed: float
    expressivity: float
    sentence_pause: float
    clause_pause: float
    lang: str
    expressivity_explicit: bool = False  # demandée telle quelle (pas issue d'un preset)


def resolve_params(*, speed: float | None = None,
                   expressivity: float | None = None,
                   style: str | None = None,
                   lang: str = "fr",
                   sentence_pause: float | None = None,
                   clause_pause: float | None = None) -> SynthParams:
    """Fusionne preset de style et arguments explicites (l'explicite gagne)."""
    if style is not None and style not in STYLES:
        raise TtsError(f"style inconnu : {style!r} (choix : {', '.join(STYLES)})")
    preset = STYLES[style or DEFAULT_STYLE]

    def pick(value, key, lo, hi):
        v = preset[key] if value is None else value
        if not lo <= v <= hi:
            raise TtsError(f"{key}={v} hors bornes [{lo}, {hi}]")
        return float(v)

    return SynthParams(
        speed=pick(speed, "speed", 0.5, 2.0),
        expressivity=pick(expressivity, "expressivity", 0.0, 1.0),
        sentence_pause=pick(sentence_pause, "sentence_pause", 0.0, 2.0),
        clause_pause=pick(clause_pause, "clause_pause", 0.0, 2.0),
        lang=lang,
        expressivity_explicit=expressivity is not None,
    )


# ---------------------------------------------------------------- Kokoro ----

class KokoroEngine:
    """Kokoro 82M (ONNX) — voix neuronales naturelles, 24 kHz natif."""

    name = "kokoro"
    native_rate = 24_000

    def __init__(self):
        self._kokoro = None

    def _load(self):
        if self._kokoro is None:
            model = MODELS_DIR / "kokoro-v1.0.onnx"
            voices = MODELS_DIR / "voices-v1.0.bin"
            if not (model.exists() and voices.exists()):
                raise TtsError(
                    f"modèle Kokoro absent de {MODELS_DIR} — "
                    "lance `python tts/download_models.py`"
                )
            from kokoro_onnx import Kokoro
            self._kokoro = Kokoro(str(model), str(voices))
        return self._kokoro

    def voices(self) -> list[str]:
        return list(self._load().get_voices())

    def synth(self, text: str, voice: str, p: SynthParams) -> tuple[np.ndarray, int]:
        if p.expressivity_explicit:
            warnings.warn(
                "kokoro ignore `expressivity` (pas de réglage prosodie équivalent) ; "
                "utilise `speed` ou un preset de style",
                stacklevel=2,
            )
        audio, sr = self._load().create(
            text,
            voice=voice,
            speed=p.speed,
            lang=LANG_ALIASES.get(p.lang, p.lang),
            sentence_pause=p.sentence_pause,
            clause_pause=p.clause_pause,
        )
        return audio, sr


# ----------------------------------------------------------------- Piper ----

def piper_voice_files(voice: str) -> tuple[Path, Path]:
    return MODELS_DIR / f"{voice}.onnx", MODELS_DIR / f"{voice}.onnx.json"


def download_piper_voice(voice: str) -> tuple[Path, Path]:
    """Télécharge une voix Piper absente (nom type ``fr_FR-siwis-medium``)."""
    parts = voice.split("-")
    if len(parts) != 3 or "_" not in parts[0]:
        raise TtsError(
            f"nom de voix Piper invalide : {voice!r} "
            "(attendu langue_variante-nom-qualité, ex fr_FR-siwis-medium)"
        )
    lang_variant, name, quality = parts
    lang2 = lang_variant.split("_")[0]
    base = f"{PIPER_HF_BASE}/{lang2}/{lang_variant}/{name}/{quality}/{voice}"

    onnx, js = piper_voice_files(voice)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for url, dest in ((base + ".onnx", onnx), (base + ".onnx.json", js)):
        try:
            with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
                while chunk := r.read(1 << 16):
                    f.write(chunk)
        except OSError as e:
            raise TtsError(f"téléchargement impossible : {url} ({e})") from e
    return onnx, js


class PiperEngine:
    """Piper (VITS) — rapide, sobre, voix FR correctes, 22,05 kHz natif."""

    name = "piper"

    def __init__(self):
        self._voices: dict[str, object] = {}

    def voices(self) -> list[str]:
        return sorted(p.name[: -len(".onnx")] for p in MODELS_DIR.glob("*.onnx"))

    def _load(self, voice: str):
        if voice not in self._voices:
            onnx, js = piper_voice_files(voice)
            if not (onnx.exists() and js.exists()):
                onnx, js = download_piper_voice(voice)
            from piper import PiperVoice
            self._voices[voice] = PiperVoice.load(str(onnx))
        return self._voices[voice]

    def synth(self, text: str, voice: str, p: SynthParams) -> tuple[np.ndarray, int]:
        from piper.config import SynthesisConfig

        e = p.expressivity
        syn = SynthesisConfig(
            length_scale=1.0 / p.speed,
            noise_scale=0.30 + 0.70 * e,    # variation de prosodie
            noise_w_scale=0.40 + 0.70 * e,  # variation de durée des phonèmes
        )
        parts: list[np.ndarray] = []
        sr = 0
        for chunk in self._load(voice).synthesize(text, syn_config=syn):
            sr = chunk.sample_rate
            parts.append(np.asarray(chunk.audio_float_array, dtype=np.float32))
        if not parts:
            raise TtsError(f"aucun audio produit pour {text!r}")
        return np.concatenate(parts), sr


# ------------------------------------------------------------- registre ----

_ENGINES = {"kokoro": KokoroEngine, "piper": PiperEngine}
_instances: dict[str, object] = {}


def get_engine(model: str):
    if model not in _ENGINES:
        raise TtsError(f"modèle inconnu : {model!r} (choix : {', '.join(MODELS)})")
    if model not in _instances:
        _instances[model] = _ENGINES[model]()
    return _instances[model]


def list_voices(model: str) -> list[str]:
    return list(get_engine(model).voices())


def synthesize(text: str, *, model: str = DEFAULT_MODEL, voice: str | None = None,
               speed: float | None = None, expressivity: float | None = None,
               style: str | None = None, lang: str = "fr",
               sentence_pause: float | None = None,
               clause_pause: float | None = None) -> Speech:
    """Synthétise ``text`` et renvoie un ``Speech`` prêt pour Mumble."""
    text = (text or "").strip()
    if not text:
        raise TtsError("texte vide")
    params = resolve_params(speed=speed, expressivity=expressivity, style=style,
                            lang=lang, sentence_pause=sentence_pause,
                            clause_pause=clause_pause)
    engine = get_engine(model)
    voice = voice or DEFAULT_VOICES[model]

    t0 = time.perf_counter()
    audio, native_rate = engine.synth(text, voice, params)
    pcm_f32 = resample(np.asarray(audio, dtype=np.float32), native_rate, SAMPLE_RATE)
    pcm = (np.clip(pcm_f32, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    dt = time.perf_counter() - t0

    return Speech(text=text, model=model, voice=voice, pcm=pcm,
                  native_rate=native_rate, synth_s=dt)
