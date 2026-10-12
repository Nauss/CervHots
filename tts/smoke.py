#!/usr/bin/env python
"""smoke.py — test de bout en bout de la brique TTS.

1. qualité du rééchantillonneur (sinus 1 kHz vs analytique) ;
2. synthèse réelle sur chaque moteur, vérification du contrat Mumble
   (s16le, 48 kHz, mono) et du contenu (parole audible, pas d'écrêtage) ;
3. effet des presets de ton (calme vs urgent : débit) ;
4. échantillons WAV dans tts/out/ pour écoute.

Usage : tts/.venv/Scripts/python tts/smoke.py
"""
from __future__ import annotations

import math
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tts import Speech, TtsError, synthesize  # noqa: E402
from tts.resample import resample  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "out"
PHRASE = "Ils sont trois à manquer à l'appel. Devine lesquels."
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"   {'OK ' if ok else 'ÉCHEC'} {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


# ----------------------------------------------------- 1. rééchantillonnage --

def test_resample() -> None:
    print("\n1. rééchantillonneur")
    dur, freq = 1.0, 1000.0
    for sr_from, sr_to in ((22_050, 48_000), (24_000, 48_000), (48_000, 24_000)):
        t_in = np.arange(int(dur * sr_from)) / sr_from
        x = np.sin(2 * math.pi * freq * t_in).astype(np.float32)
        y = resample(x, sr_from, sr_to)
        t_out = np.arange(len(y)) / sr_to
        ref = np.sin(2 * math.pi * freq * t_out)
        # on ignore les 5 ms de bord (fenêtre de reconstruction)
        m = slice(int(0.005 * sr_to), len(y) - int(0.005 * sr_to))
        err = float(np.sqrt(((y[m] - ref[m]) ** 2).mean()) / np.sqrt((ref[m] ** 2).mean()))
        check(f"{sr_from} → {sr_to} Hz", err < 0.02, f"erreur RMS relative {err:.4f}")


# ------------------------------------------------------------ 2. synthèse --

def check_speech(sp: Speech) -> None:
    check(f"{sp.model}/{sp.voice} contrat", sp.sample_rate == 48_000
          and sp.sample_width == 2 and sp.channels == 1
          and len(sp.pcm) % 2 == 0, sp.describe())
    samples = np.frombuffer(sp.pcm, dtype="<i2")
    rms = float(np.sqrt((samples.astype(np.float64) ** 2).mean())) / 32767.0
    clipped = float((np.abs(samples) >= 32767).mean())
    check(f"{sp.model}/{sp.voice} contenu", 0.01 < rms and clipped < 0.001,
          f"RMS {rms:.3f}, écrêtage {clipped * 100:.3f} %")
    check(f"{sp.model}/{sp.voice} durée", 1.5 < sp.duration_s < 12.0,
          f"{sp.duration_s:.2f} s pour « {PHRASE[:28]}… »")

    wav = sp.save_wav(OUT_DIR / f"smoke-{sp.model}.wav")
    with wave.open(str(wav), "rb") as w:  # relecture du WAV écrit
        check(f"{sp.model}/{sp.voice} WAV relu",
              (w.getframerate(), w.getsampwidth(), w.getnchannels()) == (48_000, 2, 1)
              and w.getnframes() == len(samples), str(wav))


def test_synth(model: str) -> None:
    print(f"\n2. synthèse — {model}")
    cold = synthesize(PHRASE, model=model)            # inclut le chargement
    warm = synthesize(PHRASE, model=model)            # modèle déjà en mémoire
    check_speech(cold)
    rtf = warm.synth_s / warm.duration_s
    print(f"   temps : 1er {cold.synth_s:.2f} s (chargement compris), "
          f"puis {warm.synth_s:.2f} s pour {warm.duration_s:.2f} s de parole "
          f"(RTF {rtf:.2f})")


# ------------------------------------------------------------- 3. styles --

def test_styles(model: str) -> None:
    print(f"\n3. presets de ton — {model}")
    durs = {}
    for style in ("calme", "urgent"):
        sp = synthesize(PHRASE, model=model, style=style)
        durs[style] = sp.duration_s
        sp.save_wav(OUT_DIR / f"style-{style}-{model}.wav")
    check(f"{model} urgent plus rapide que calme",
          durs["urgent"] < durs["calme"],
          f"calme {durs['calme']:.2f} s vs urgent {durs['urgent']:.2f} s")


# ------------------------------------------------------------- 4. options --

def test_options() -> None:
    print("\n4. options")
    sp = synthesize(PHRASE, model="piper", expressivity=0.9, speed=1.3)
    check("piper speed+expressivity", sp.duration_s > 0.5 and sp.sample_rate == 48_000,
          sp.describe())
    sp.save_wav(OUT_DIR / "style-enjoue-piper.wav")
    try:
        synthesize("", model="kokoro")
        check("texte vide refusé", False)
    except TtsError:
        check("texte vide refusé", True)
    try:
        synthesize(PHRASE, model="kokoro", speed=3.0)
        check("vitesse hors bornes refusée", False)
    except TtsError:
        check("vitesse hors bornes refusée", True)
    try:
        synthesize(PHRASE, model="bogus")
        check("modèle inconnu refusé", False)
    except TtsError:
        check("modèle inconnu refusé", True)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    test_resample()
    try:
        for model in ("kokoro", "piper"):
            test_synth(model)
        for model in ("kokoro", "piper"):
            test_styles(model)
        test_options()
    except TtsError as e:
        print(f"\nERREUR : {e}")
        print("→ python tts/download_models.py")
        return 1

    print("\nÉCHANTILLONS")
    for p in sorted(OUT_DIR.glob("*.wav")):
        print(f"   {p}")
    if FAILS:
        print(f"\n{len(FAILS)} échec(s) : {', '.join(FAILS)}")
        return 1
    print("\nTout est vert ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
