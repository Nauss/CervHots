"""resample.py — rééchantillonneur qualité, numpy seul.

Les moteurs sortent en 24 kHz (Kokoro) ou 22,05 kHz (Piper) ; le contrat
Mumble est du 48 kHz mono s16le. Une interpolation linéaire dégraderait le
haut du spectre : on utilise une reconstruction par sinc fenêtré (Kaiser),
calculée en polyphase par blocs (mémoire bornée).

Test de qualité dans ``smoke.py`` : sinus 1 kHz rééchantillonné dans les deux
sens, erreur RMS relative < 2 % vs sinus analytique.
"""
from __future__ import annotations

import numpy as np

TAPS = 16    # échantillons d'entrée de part et d'autre du point interpolé
BETA = 8.6   # Kaiser ~ -80 dB d'atténuation en bande atténuée
BLOCK = 65_536


def resample(x: np.ndarray, sr_from: int, sr_to: int,
             taps: int = TAPS, beta: float = BETA) -> np.ndarray:
    """Rééchantillonne un signal mono float32 de sr_from vers sr_to."""
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    if sr_from <= 0 or sr_to <= 0:
        raise ValueError(f"fréquences invalides : {sr_from} → {sr_to}")
    if x.size == 0 or sr_from == sr_to:
        return x.copy()

    ratio = sr_from / sr_to
    n_out = max(1, round(x.size * sr_to / sr_from))
    offsets = np.arange(-taps + 1, taps + 1)            # 2*taps taps
    win = np.kaiser(2 * taps, beta).astype(np.float32)  # fenêtre fixe par tap
    # coupure relative à Nyquist d'entrée : anti-aliasing quand on descend
    cutoff = min(1.0, sr_to / sr_from)

    out = np.empty(n_out, dtype=np.float32)
    for start in range(0, n_out, BLOCK):
        t = np.arange(start, min(start + BLOCK, n_out), dtype=np.float64) * ratio
        centers = np.floor(t).astype(np.int64)
        frac = (t - centers).astype(np.float32)
        # h[k] = sinc((k - frac) * cutoff) * cutoff * win[k], normalisé
        h = np.sinc((offsets[None, :] - frac[:, None]) * cutoff).astype(np.float32)
        h *= cutoff * win[None, :]
        h /= h.sum(axis=1, keepdims=True)
        src = np.clip(centers[:, None] + offsets[None, :], 0, x.size - 1)
        out[start:start + h.shape[0]] = (h * x[src]).sum(axis=1)
    return out
