#!/usr/bin/env python
"""download_models.py — récupère les modèles TTS dans tts/models/.

    python tts/download_models.py            # kokoro + voix piper par défaut
    python tts/download_models.py --piper fr_FR-upmc-medium   # voix en plus

Kokoro : modèle + voix (releases GitHub thewh1teagle/kokoro-onnx, ~350 Mo).
Piper  : voix unique (HF rhasspy/piper-voices, ~65 Mo) ; les autres voix
piper se téléchargent à la demande à la première synthèse.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tts.engines import MODELS_DIR, TtsError, download_piper_voice  # noqa: E402

KOKORO_RELEASE = ("https://github.com/thewh1teagle/kokoro-onnx/releases/"
                  "download/model-files-v1.1")
KOKORO_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
DEFAULT_PIPER_VOICE = "fr_FR-siwis-medium"


def fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  déjà là : {dest.name} ({dest.stat().st_size // 1_048_576} Mo)")
        return
    print(f"  {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
            print(f"\r    {f.tell() // 1_048_576} Mo", end="", flush=True)
    tmp.rename(dest)
    print(f"\r  ok : {dest.name} ({dest.stat().st_size // 1_048_576} Mo)      ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--piper", default=DEFAULT_PIPER_VOICE, metavar="VOIX",
                    help=f"voix piper à télécharger (défaut : {DEFAULT_PIPER_VOICE})")
    args = ap.parse_args()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"modèles dans {MODELS_DIR}\n\nKokoro :")
    for name in KOKORO_FILES:
        fetch(f"{KOKORO_RELEASE}/{name}", MODELS_DIR / name)

    print(f"\nPiper ({args.piper}) :")
    try:
        download_piper_voice(args.piper)
    except TtsError as e:
        print(f"  erreur : {e}", file=sys.stderr)
        return 1
    for p in sorted(MODELS_DIR.glob(f"{args.piper}*")):
        print(f"  ok : {p.name} ({p.stat().st_size // 1_048_576} Mo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
