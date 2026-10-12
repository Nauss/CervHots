# tts — la voix du coach

Phrase du coach + modèle + ton → **parole audio prête pour Mumble**.
Local et gratuit : deux moteurs ONNX exécutés par onnxruntime, aucun appel
réseau à la synthèse. Étude et décisions : `etudes/tts/ETUDE.md`.

## Contrat de sortie

`synthesize()` renvoie un `Speech` dont le champ `pcm` est du **PCM signé
16 bits little-endian, 48 kHz, mono** — exactement ce que
`mumble.sound_output.add_sound()` attend. `save_wav()` / `save_pcm()` pour
écrire sur disque (écoute, debug).

## Installation

```bash
uv venv tts/.venv --python 3.12
uv pip install --python tts/.venv/Scripts/python.exe kokoro-onnx piper-tts
python tts/download_models.py        # ~415 Mo dans tts/models/
```

## Usage

```python
from tts import synthesize

sp = synthesize("Ils sont trois à manquer à l'appel. Devine lesquels.",
                model="kokoro", style="urgent")
mumble.sound_output.add_sound(sp.pcm)     # prêt à diffuser
sp.save_wav("tts/out/extrait.wav")        # confort d'écoute
print(sp.describe())                      # modèle, durée, temps de synthèse
```

```bash
python -m tts "phrase à prononcer" --model piper --style urgent --raw out.pcm
python tts/cli.py --list-voices --model kokoro
python tts/smoke.py                       # test de bout en bout
```

## Options

| Option | Valeurs | Effet |
|---|---|---|
| `model` | `kokoro` (défaut) ou `piper` | moteur : qualité (Kokoro) ou latence (Piper) |
| `voice` | kokoro : 54 voix (`ff_siwis` = FR, défaut) ; piper : `fr_FR-siwis-medium` (défaut), toute voix `xx_XX-nom-qualité` téléchargée à la demande | timbre |
| `style` | `neutre` (défaut), `calme`, `urgent`, `enjoue` | preset de ton : débit, expressivité, pauses |
| `speed` | 0.5 – 2.0 | vitesse (1.0 = normal) |
| `expressivity` | 0.0 – 1.0 | variation prosodique — **piper seul** (bruit de durée/phonèmes) ; kokoro l'ignore avec avertissement |
| `lang` | code espeak (`fr`, `en`… défaut `fr`) | phonémisation kokoro |
| `sentence_pause`, `clause_pause` | secondes (0 – 2) | pauses kokoro (ponctuation forte / faible) |

Un argument explicite écrase toujours la valeur du preset ; la couleur
émotionnelle, elle, vient du texte écrit par le coach.

## Mesures (smoke, Windows, CPU)

| Moteur | Parole | Synthèse (chaud) | RTF | 1er appel |
|---|---|---|---|---|
| kokoro `ff_siwis` | 2,95 s | 0,40 s | 0,14 | 1,50 s (chargement compris) |
| piper `fr_FR-siwis-medium` | 3,01 s | 0,13 s | 0,04 | 1,83 s (chargement compris) |

## Limites connues

- **Ton** : les presets ne règlent que la prosodie (débit, expressivité,
  pauses). Le ton émotionnel est porté par le texte du coach.
- **Kokoro FR** : une seule voix française (`ff_siwis`) dans le jeu de voix
  v1.0 ; piper offre plusieurs voix FR (`fr_FR-tom-medium`,
  `fr_FR-upmc-medium`… téléchargeables à la demande).
- **Format Mumble** : le contrat est s16le 48 kHz mono (API pymumble) ;
  l'exemple officiel pousse du s32le — à confirmer au POC bot Mumble
  (`Speech` rend le changement de format trivial).
- **Modèles** : `tts/models/` n'est pas versionné (poids ONNX) ;
  `download_models.py` les récupère de façon reproductible.
