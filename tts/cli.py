#!/usr/bin/env python
"""cli.py — synthèse vocale en ligne de commande.

Exemples :
    python -m tts "Ils sont trois à manquer à l'appel."
    python tts/cli.py "phrase" --model piper --style urgent --out tts/out/essai.wav
    python tts/cli.py --list-voices --model kokoro

Sortie : WAV (écoute) et/ou PCM brut s16le 48 kHz mono (``--raw``, pour Mumble).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tts import (DEFAULT_MODEL, DEFAULT_VOICES, MODELS, STYLES, TtsError,  # noqa: E402
                 list_voices, synthesize)

OUT_DIR = Path(__file__).resolve().parent / "out"


def main() -> int:
    ap = argparse.ArgumentParser(description="TTS du coach CervHots (local, gratuit)")
    ap.add_argument("texte", nargs="?", help="phrase à prononcer")
    ap.add_argument("--model", default=DEFAULT_MODEL, choices=MODELS,
                    help=f"moteur (défaut : {DEFAULT_MODEL})")
    ap.add_argument("--voice", default=None,
                    help=f"voix (défaut : {DEFAULT_VOICES[DEFAULT_MODEL]})")
    ap.add_argument("--style", default=None, choices=sorted(STYLES),
                    help="preset de ton (neutre, calme, urgent, enjoue)")
    ap.add_argument("--speed", type=float, default=None,
                    help="vitesse 0.5 à 2.0 (défaut : 1.0)")
    ap.add_argument("--expressivity", type=float, default=None,
                    help="expressivité 0.0 à 1.0 (piper seul)")
    ap.add_argument("--lang", default="fr",
                    help="langue de phonémisation kokoro (défaut : fr)")
    ap.add_argument("--out", default=None,
                    help=f"fichier WAV (défaut : {OUT_DIR / 'speech.wav'})")
    ap.add_argument("--raw", default=None,
                    help="écrit aussi le PCM brut s16le 48 kHz mono (pour Mumble)")
    ap.add_argument("--list-voices", action="store_true",
                    help="liste les voix du modèle et quitte")
    args = ap.parse_args()

    if args.list_voices:
        try:
            for v in list_voices(args.model):
                print(v)
        except TtsError as e:
            print(f"erreur : {e}", file=sys.stderr)
            return 1
        return 0

    if not args.texte:
        ap.error("il manque la phrase à prononcer (ou --list-voices)")

    try:
        sp = synthesize(
            args.texte,
            model=args.model,
            voice=args.voice,
            speed=args.speed,
            expressivity=args.expressivity,
            style=args.style,
            lang=args.lang,
        )
    except TtsError as e:
        print(f"erreur : {e}", file=sys.stderr)
        return 1

    wav = sp.save_wav(args.out or (OUT_DIR / "speech.wav"))
    print(sp.describe())
    print(f"wav : {wav}")
    if args.raw:
        print(f"pcm : {sp.save_pcm(args.raw)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
