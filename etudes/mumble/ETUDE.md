# Étude — Diffusion Mumble : le bot parole (CervHots)

**Verdict :** POC parole (faisabilité, phase 0) **réussi en conditions
réelles**. Brique `mumblebot/` livrée : bot pymumble qui consomme le contrat
`tts.Speech` et diffuse dans un canal. **Format audio tranché : PCM s16le
48 kHz mono** (l'exemple s32le du dépôt pymumble est erroné). Smoke E2E
vert : TTS → bot → murmur 1.5.915 → auditeur, 6,28 s reçues sur 6,27 s
envoyées.

---

## 1. Le besoin

Faisabilité phase 0 : « bot pymumble qui lit un texte fixe via TTS et le
diffuse dans un canal ». La brique doit consommer le contrat de `tts/`
sans conversion : la chaîne complète phrase → TTS → Mumble doit fonctionner
avant d'attaquer l'orchestration (tours de parole, file latest-wins).

## 2. Choix du client : fork pymumble 2.0

| Option | État | Retenu |
|---|---|---|
| azlux/pymumble 1.6.1 (PyPI) | 2021, TCP tunneling seul, version string datée | non |
| **fork ~oopsbagel/pymumble 2.0** | maintenu, UDP chiffré AES-OCB2, serveurs récents, Python ≥ 3.12, callbacks typés | **oui** |
| mumpy (ianling) | autre implémentation, plus jeune | non |

Le fork s'installe depuis GitHub (`uv pip install git+https://github.com/
oopsbagel/pymumble.git`), import `from mumble import Mumble`. Serveur récent
validé contre murmur **1.5.915** (image docker officielle `mumblevoip/
mumble-server`).

## 3. Format audio : tranché — s16le 48 kHz mono

L'ambiguïté signalée en faisabilité §6 (API.md dit s16le, l'exemple officiel
pousse du s32le) est levée par la lecture du code du fork, confirmée par le
POC :

- docstring de `SendAudio.add_sound` : *« Audio encoded in Linear PCM
  16-bit 48kHz little endian signed format »* ;
- `SoundChunk.duration = size / 2 / SAMPLE_RATE` → **2 octets par échantillon** ;
- l'exemple `talking_bot.py` convertit en s32le via ffmpeg… mais `add_sound`
  hache alors du s32 comme du s16 : son dédoublé en durée, bourdonnant.
  **L'exemple est faux**, il ne fait foi de rien.

Conséquence heureuse : `Speech.pcm` (s16le 48 kHz mono) est consommé
**tel quel**, sans ffmpeg ni conversion.

## 4. libopus sur Windows

`opuslib` charge la DLL via `ctypes.util.find_library("opus")`, aveugle aux
DLL hors répertoires système. `mumblebot.bot.ensure_opus()` précharge la
DLL et pointe explicitement le chemin **avant** tout import pymumble.
Recherche dans l'ordre : `OPUS_LIB` (env) → `mumblebot/lib/opus.dll` →
`C:\Program Files\Audacity\opus.dll` → wheel `pyogg` (qui embarque
`opus.dll`). Validé avec la libopus 1.5.2 d'Audacity.

## 5. Serveur de test

- conteneur docker `mumblevoip/mumble-server` (murmur 1.5.915),
  `cervhots-murmur`, port 64738 : démarre automatiquement dans le smoke
  si aucun serveur n'est joignable ; jetable (`docker rm -f cervhots-murmur`) ;
- pour l'écoute humaine : rejoindre `127.0.0.1:64738` avec le client Mumble
  pendant que `bot.py --demo` tourne ;
- serveur de l'équipe en prod : config `.env` racine (`MUMBLE_HOST`…).

**Pièges actés** (rencontrés en POC) :

- murmur génère son certificat **après** le bind : les clients qui arrivent
  dans cette fenêtre meurent en `ConnectionRejectedError` → laisser 3 s de
  sursis + retentatives dans `MumbleBot.connect()` ;
- pymumble **libère son verrou « prêt » même sur échec de connexion** :
  `wait_until_connected()` renvoie alors `True` frauduleusement : vérifier
  `users.myself` (posé par ServerSync) pour valider la session.
- pymumble **meurt silencieusement sur toute coupure socket** (les
  `socket.error` sont avalés dans sa boucle, callback `disconnected` seul
  témoin) : ne jamais attendre son événement « buffer vide » sans borne.
  `say_and_wait()` attend au plus durée de parole + 5 s, suit le callback
  de déconnexion et lève une erreur explicite (vérifié en coupant le murmur
  en pleine diffusion : erreur claire, sortie 1, aucun blocage).

## 6. Architecture livrée

```
mumblebot/
  bot.py       # ensure_opus() + MumbleBot (connect, say, wait_for_quiet) + CLI
  smoke.py     # POC E2E : serveur de test, bot, auditeur, vérifications
  README.md
  lib/         # dépôt d'opus.dll local (gitignoré, optionnel)
```

- `say(text)` → `tts.synthesize(...)` → `send_audio.add_sound(pcm)` ; renvoie
  l'événement « buffer vide » (fin de diffusion réelle) ;
- `wait_for_quiet(gap)` : cède la parole (aucun son reçu depuis `gap` s) ;
- venv unique de la couche voix (`tts/.venv`) : `tts` et `mumblebot`
  partageront le process du coach (faisabilité §7).

## 7. Validation (smoke, 12/10/2026)

`tts/.venv/Scripts/python mumblebot/smoke.py` — **tout est vert**, chaîne
réelle : Piper (`fr_FR-siwis-medium`) → bot « CoachPOC » → murmur 1.5.915 →
auditeur « TesteurPOC » :

| Vérification | Mesure |
|---|---|
| parole envoyée | 6,27 s (s16le 48 kHz mono) |
| parole reçue par l'auditeur | 6,28 s en 314 paquets opus |
| contenu reçu | RMS 0,152 (parole audible, pas de silence) |
| tours de parole | `wait_for_quiet` répond sur canal calme |
| latence diffusion | diffusion en temps réel (8,28 s mesurées = synthèse + lecture) |

## 8. Décisions du proprio (actées)

| Date | Décision |
|---|---|
| 12/10/2026 | POC parole lancé : bot pymumble + TTS local, validé avant orchestration. |
| 12/10/2026 | Format contrat confirmé s16le 48 kHz mono (cf. §3) ; `Speech` reste paramétrable. |

## Sources clés

- Faisabilité : `FAISABILITE.md` §6 (diffusion Mumble), §7 (orchestration).
- pymumble fork 2.0 : github.com/oopsbagel/pymumble (docs/, examples/).
- Serveur de test : hub.docker.com/r/mumblevoip/mumble-server (murmur 1.5.915).
- libopus Windows : opus-codec.org ; wheel `pyogg` ; DLL livrée avec Audacity.
