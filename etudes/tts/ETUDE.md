# Étude — TTS : la voix du coach (CervHots)

**Verdict :** brique `tts/` livrée et validée. Entrée = phrase du coach +
modèle + options de ton ; sortie = PCM s16le 48 kHz mono prêt pour
`mumble.sound_output.add_sound()`. Deux moteurs locaux gratuits derrière une
seule API : **Kokoro** (défaut, qualité) et **Piper** (latence). Smoke test
vert : contrat audio vérifié, presets de ton fonctionnels, RTF 0,04–0,14.

---

## 1. Le besoin

Le coach génère une phrase (couche cerveau) ; il faut la faire prononcer et
diffuser le son dans Mumble. Contraintes :

- **entrée** : la phrase + un choix de modèle + des options de ton ;
- **sortie** : un format audio directement consommable par le bot Mumble ;
- **gratuit strict** (décision du proprio) : ni abonnement ni API payante ;
- **rendu soigné** : la voix porte la crédibilité du coach.

## 2. Options passées en revue

| Option | Coût | Local | Voix FR | Retenu |
|---|---|---|---|---|
| **Kokoro 82M (ONNX)** | gratuit | oui | `ff_siwis`, naturelle | **oui (défaut)** |
| **Piper (VITS)** | gratuit | oui | `fr_FR-siwis-medium` + voix FR variées | **oui** |
| edge-tts | gratuit | non (cloud, ToS gris) | très naturelles | non — hors contrainte « local » |
| Piper « classique » (piper-tts 1.2) | gratuit | oui | correctes | remplacé par piper 1.8 (OHF) |
| Groco `/v1/audio/speech` | selon le pote | non | inconnu | non — gateway : 0 modèle, scope `chat` (12/10/2026) |
| XTTS / F5-TTS | gratuit | oui | bonnes | non — lourd (torch, GPU visé), latence |

L'API Groco est compatible OpenAI : si elle expose un jour `/v1/audio/speech`,
un troisième moteur s'ajoutera au registre sans toucher au contrat de sortie.

## 3. Choix retenus

### 3.1 Deux moteurs, une seule API

Le proprio veut pouvoir choisir le modèle : les deux moteurs libres crédibles
sont derrière le même appel `synthesize(text, model=…, **options)`.
Comparatif mesuré sur cette machine (CPU, phrase de 50 caractères) :

| | Kokoro `ff_siwis` | Piper `fr_FR-siwis-medium` |
|---|---|---|
| Qualité perçue (faisabilité §5) | supérieure | correcte, un peu robotique |
| Synthèse (chaud) | 0,40 s | 0,13 s |
| RTF | 0,14 | 0,04 |
| 1er appel (chargement modèle) | 1,50 s | 1,83 s |
| Voix FR | 1 (`ff_siwis`) | plusieurs (téléchargées à la demande) |
| Réglage expressivité | non | oui (`noise_scale`, `noise_w`) |

Les deux sont largement dans le budget latence 5–12 s bout en bout
(faisabilité §7). **Défaut : kokoro** (exigence de rendu soigné) — un flag
`--model piper` bascule si la latence prime.

### 3.2 Contrat de sortie : PCM s16le 48 kHz mono

C'est ce que `mumble.sound_output.add_sound()` attend (API pymumble). Les
moteurs sortant en 24 kHz (Kokoro) ou 22,05 kHz (Piper), la brique
rééchantillonne en interne (sinc fenêtré Kaiser, numpy seul — erreur RMS
mesurée < 0,01 % vs sinus analytique). L'enveloppe WAV est un confort
d'écoute, pas le contrat.

⚠️ FAISABILITE §6 signalait une ambiguïté : l'exemple officiel pymumble pousse
du s32le. À confirmer au POC bot Mumble ; le format est un paramètre du
`Speech`, le changement ne touchera pas les moteurs.

### 3.3 Options de ton

« Ton » = réglages prosodiques + le texte. La couleur émotionnelle ne peut
pas venir du TTS : elle est portée par la phrase du coach. La brique expose :

- `style` : presets `neutre` / `calme` / `urgent` / `enjoue` → débit,
  expressivité, pauses (vérifié : `urgent` produit bien moins de durée que
  `calme` sur les deux moteurs) ;
- `speed` (0,5–2,0), `expressivity` (0–1, piper seul — kokoro n'a pas ce
  réglage et l'ignore avec avertissement si demandé explicitement) ;
- `sentence_pause` / `clause_pause` (kokoro seul), `lang` (phonémisation).

Un argument explicite écrase toujours le preset.

## 4. Architecture livrée

```
tts/
  speech.py          # Speech : PCM s16le 48 kHz mono + WAV (le contrat)
  resample.py        # rééchantillonneur sinc fenêtré (numpy seul)
  engines.py         # registre kokoro/piper, presets de ton, synthesize()
  cli.py / __main__.py  # python -m tts "phrase" [--model --voice --style …]
  download_models.py # récupère les modèles dans tts/models/ (~415 Mo)
  smoke.py           # test E2E : rééchantillonnage, contrat, ton, options
  models/            # poids ONNX (non versionnés)
```

- modèles : Kokoro v1.0 + voix v1.0 (releases GitHub
  `thewh1teagle/kokoro-onnx`), voix Piper (HF `rhasspy/piper-voices`) ;
- venv dédié `tts/.venv` (Python 3.12, recommandé par la faisabilité ;
  kokoro-onnx n'exige pas le 3.14 système) ;
- téléchargement à la demande des voix Piper absentes
  (`fr_FR-upmc-medium`… : une ligne de config) ;
- langue : espeak attend `fr-fr` (pas de `fr` nu) — alias géré dans la brique.

## 5. Validation (smoke, 12/10/2026)

`python tts/smoke.py` — **tout est vert** :

1. rééchantillonneur 22,05k/24k↔48k : erreur RMS relative 0,0000 vs sinus
   analytique ;
2. synthèse réelle des deux moteurs : 48 000 Hz mono s16le relu depuis le WAV,
   parole audible (RMS 0,085 kokoro / 0,176 piper), écrêtage < 0,001 %,
   durée plausible ;
3. presets de ton : `urgent` < `calme` sur les deux moteurs (2,50 s vs
   3,33 s kokoro ; 2,83 s vs 3,16 s piper) ;
4. options : vitesse + expressivité piper, refus du texte vide, des vitesses
   hors bornes et du modèle inconnu.

Échantillons d'écoute : `tts/out/*.wav` (générés par le smoke).

## 6. Prochain pas

La brique est prête à être consommée par le **POC parole** (faisabilité
phase 0) : bot pymumble qui lit un texte fixe via ce TTS, puis respect des
tours de parole et file « latest-wins ».

## Sources clés

- Faisabilité : `FAISABILITE.md` §5 (TTS), §6 (Mumble), §7 (latence).
- Kokoro 82M : github.com/thewh1teagle/kokoro-onnx (+ releases model-files-v1.1).
- Piper : github.com/OHF-voice/piper1-gpl (API_PYTHON.md), HF rhasspy/piper-voices.
- pymumble : github.com/azlux/pymumble (API.md, `talking_bot.py`),
  fork ~oopsbagel/pymumble (serveurs récents).
