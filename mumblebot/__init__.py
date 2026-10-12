"""mumblebot — la diffusion Mumble du coach (couche voix CervHots).

`MumbleBot` consomme le contrat `tts.Speech` (PCM s16le 48 kHz mono) et le
diffuse dans un canal. Voir `mumblebot/README.md` et `etudes/mumble/ETUDE.md`.
"""
from .bot import DEMO_PHRASE, MumbleBot, ensure_opus

__all__ = ["DEMO_PHRASE", "MumbleBot", "ensure_opus"]
