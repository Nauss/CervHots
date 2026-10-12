"""speech.py — le contrat de sortie de la brique TTS.

Une synthèse renvoie un ``Speech`` : PCM signé 16 bits little-endian,
48 kHz, mono — exactement ce que ``mumble.sound_output.add_sound()`` attend.
L'enveloppe WAV n'est qu'un confort d'écoute (fichier sur disque).
"""
from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from pathlib import Path

# Contrat Mumble (FAISABILITE.md §6) : PCM s16le 48 kHz mono.
SAMPLE_RATE = 48_000
SAMPLE_WIDTH = 2
CHANNELS = 1


@dataclass
class Speech:
    """Un passage de parole prêt à diffuser."""

    text: str
    model: str
    voice: str
    pcm: bytes
    sample_rate: int = SAMPLE_RATE
    sample_width: int = SAMPLE_WIDTH
    channels: int = CHANNELS
    native_rate: int = 0   # fréquence native du moteur avant rééchantillonnage
    synth_s: float = 0.0   # durée de synthèse mesurée (1er appel : + chargement modèle)

    @property
    def duration_s(self) -> float:
        frame = self.sample_rate * self.sample_width * self.channels
        return len(self.pcm) / frame

    def to_wav_bytes(self) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(self.channels)
            w.setsampwidth(self.sample_width)
            w.setframerate(self.sample_rate)
            w.writeframes(self.pcm)
        return buf.getvalue()

    def save_wav(self, path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.to_wav_bytes())
        return p

    def save_pcm(self, path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.pcm)
        return p

    def describe(self) -> str:
        return (
            f"{self.model}/{self.voice} — {self.duration_s:.2f} s de parole "
            f"({self.sample_rate} Hz mono s16le, native {self.native_rate} Hz, "
            f"synthèse {self.synth_s * 1000:.0f} ms)"
        )
