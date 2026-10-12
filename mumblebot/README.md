# mumblebot — la diffusion Mumble du coach

Le bot qui porte la voix du coach : il consomme le contrat `tts.Speech`
(PCM s16le 48 kHz mono) et le diffuse dans un canal Mumble via
`mumble.send_audio.add_sound()`. Client : fork **pymumble 2.0**
(oopsbagel, compatible serveurs récents). Étude : `etudes/mumble/ETUDE.md`.

## Prérequis

- **venv de la couche voix** : `tts/.venv` (Python 3.12, déjà pourvu de
  kokoro-onnx, piper-tts, pymumble, opuslib) — le coach tournera dans un
  seul process qui importe `tts` et `mumblebot`.
- **libopus** (DLL) : cherchée dans l'ordre `OPUS_LIB` (env) →
  `mumblebot/lib/opus.dll` → `C:\Program Files\Audacity\opus.dll` →
  wheel `pyogg`. `opuslib` ne sait pas chercher elle-même sur Windows,
  `ensure_opus()` s'en charge avant tout import pymumble.
- **un serveur Mumble** : celui de l'équipe (config `.env` racine) ou le
  serveur de test en conteneur :
  `docker run -d --name cervhots-murmur -p 64738:64738 mumblevoip/mumble-server`
  (le smoke le démarre tout seul s'il manque).

## Usage

```bash
tts/.venv/Scripts/python mumblebot/bot.py "Le nœud haut tombe dans vingt secondes."
tts/.venv/Scripts/python mumblebot/bot.py --demo --style urgent
tts/.venv/Scripts/python mumblebot/bot.py "phrase" --channel "Notre équipe" --wait-quiet
```

```python
from mumblebot import MumbleBot

bot = MumbleBot("mumble.delequipe.fr", user="Coach", channel="Notre équipe")
bot.connect()
bot.wait_for_quiet()                 # cède la parole si quelqu'un parle
bot.say_and_wait("Le boss est pris, repliez haut.")
bot.disconnect()
```

Config (priorité : arguments > env > `.env` racine) : `MUMBLE_HOST`,
`MUMBLE_PORT`, `MUMBLE_USER`, `MUMBLE_PASSWORD`, `MUMBLE_CHANNEL`.

## Test de bout en bout

```bash
tts/.venv/Scripts/python mumblebot/smoke.py
```

Chaîne réelle vérifiée : TTS → bot → murmur (1.5.915, conteneur docker) →
auditeur qui reçoit la parole (durée ≥ 85 %, contenu audible) + tours de
 parole. Pour écouter soi-même : lancer `bot.py --demo` et rejoindre le
serveur (`127.0.0.1:64738` pour le conteneur de test) avec un client Mumble.

## Limites connues

- **Tours de parole** : garde-fou simple (attente d'un silence de 0,6 s) ;
  le vrai respect (priorité aux humains, file « latest-wins ») vient avec
  l'orchestration (faisabilité §7).
- **TCP tunneling** : l'audio passe en TCP (défaut `force_tcp_only=True`) —
  parfait pour un bot qui parle, à revoir pour de la voix continue.
- **Pas de certificat client** : le bot se connecte anonymement ; à doter
  d'un compte enregistré si le serveur de l'équipe l'exige.
- **Connexion** : pymumble libère son « prêt » même quand la connexion
  échoue — `MumbleBot.connect()` vérifie la session réelle (`users.myself`)
  et retente (murmur refuse les clients pendant sa génération de certificat).
