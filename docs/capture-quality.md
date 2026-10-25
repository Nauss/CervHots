# Préflight hors ligne des références visuelles

`python -B -m cerveau.capture_quality --help` : commande produit **sans capture,
backend jeu, Coach, API, OCR ni audio** (stdlib seulement, Python 3.12/3.14).
Elle ne lit **aucun journal natif**, ne modifie aucune référence, n'extrait aucun
ZIP et ne calcule aucune UV. À exécuter depuis MAIN après revue/intégration ;
pour un candidat, remplacer le `cd` par son checkout exact.

## Parcours opérateur, avant toute nouvelle recette

1. Réserver des fichiers sources explicites, **fermés**, un rapport neuf hors de
   leurs répertoires et une ROI mesurée dans **l'image**, pas l'écran Windows.
   Origine haut-gauche, `X Y W H`, pixels entiers. Une ROI n'est pas une calibration.
2. Lancer le diagnostic. Exemple **historique borné**, sans match :

```bash
cd C:/root/dev/AI/CervHots
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.capture_quality --input C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot10/operator-real-capture-001/new/UNATTESTED-GDI-segment-00162.zip --roi 0 0 624 204 --report-json C:/root/dev/AI/CervHots/out/visual-preflight-new/quality.json
```

   `--input` peut être répété **dans l'ordre temporel**, 8 fichiers maximum,
   sans recherche récursive. Le rapport ne contient ni pixels, chemins sources,
   textes privés, identité/token, transcription HUD ou valeur de jeu.
3. **Code 1** : refuser la référence pour la recette. `refused` = entrée invalide
   (format/intégrité/ROI/ordre de segments/etc.). `unknown` = insuffisance ou
   suspicion (noir, temps absent, échantillon partiel, contrat manquant).
   Un écran légitimement sombre reste **suspect/inconnu**, pas « défaut prouvé ».
   Corriger la méthode de capture **séparément**, jamais les originaux gelés.
4. Examiner manuellement toute la fenêtre et fournir, si réellement établi,
   `--manual-reference C:/chemin-prive/reference.json`. **Code 0** signifie seulement
   `diagnostic_only` : pixels sans alerte selon les seuils ET contrat cohérent,
   **déclarations opérateur non authentifiées**. Ce n'est ni une référence
   comparable ni une autorisation de match. Le diagnostic ne prouve ni visibilité
   HUD ni identité, stabilité, bon repère, perspective ou calibration.
5. Avant un nouveau match : préflight visuel examiné **ET méthode indépendante
   de comparaison prête et revue** ; autorisation opérateur distincte. Ce lot
   n'implémente pas cette comparaison spatiale. `current_permission=false`,
   `hud_validated=false`, `comparable=false`, `spatial_comparisons=0` toujours.
   Aucun consommateur natif ne lit ce verdict.

## Mesures, seuils et bornes

- BMP BI_RGB 24/32 bits uniquement, DIB40/108/124, au plus 1920×1080 et 8MiB,
  taille/stride/intégralité vérifiés ; alpha ignoré. PNG/JPEG/vidéo non pris en
  charge : convertir dans **une copie distincte** avec provenance conservée,
  jamais modifier une preuve. Les captures produit existantes sont BMP.
- ZIP standard **STORED seulement** : entrée ≤17MiB, répertoire central ≤64KiB
  et 2–401 entrées contrôlés **avant** allocation par ZipFile ; ni ZIP64 ni
  multidisque, chiffrement, compression, doublon ou chemin libre. Membres permis :
  `index.json` (128KiB), `frame-NNNN[NNNN].bmp` (8MiB),
  `segment-NNNN[NNNN].jsonl` / `.seal.json` (512KiB), total déclaré ≤17MiB.
  CRC de tous les membres et SHA256 de chaque frame indexée vérifiés ; index
  1–400 frames, numéros contigus/croissants, aucun BMP non indexé. La sémantique
  du seal/du journal natif n'est **pas** vérifiée ni projetée.
- `--max-frames 32` : préfixe décodé, total global plafonné à128. Intégrité ZIP
  contrôlée sur tout le segment borné ; pixels non inspectés explicitement
  comptés. Un échantillon incomplet ne peut pas donner code0. Une seule image
  est sans temps/ordre attestés. Totaux déclarés inconnus = `null`, jamais zéro.
- Noir proche : `max(R,G,B) <= --black-level 8`. Fraction noire ROI et aire du
  **plus grand rectangle entièrement noir proche** / aire ROI, calcul exact
  par histogrammes (pas de tuiles approximatives). Alerte si fraction
  `>= --black-fraction .15` **ou** rectangle `>= --rectangle-fraction .08`.
  Des masques colorés/transparents/striés peuvent échapper au détecteur ; des
  zones naturellement noires peuvent l'activer. Aucun de ces nombres n'est
  un score de validité HUD. Seuils fractions : ]0,1], niveau : [0,255].
- `--min-frames 3` (1–128), `--min-roi-pixels 256` (1–2073600) : quantité minimum
  de frames sans alerte assez grandes, **pas** attestation de contenu utile.
  Changer de dimensions est refusé même si la ROI tient encore.
- `started_s`, `finished_s` doivent être finis, non négatifs, ≤1e12, ordonnés,
  sans chevauchement ; `--max-gap-s .25` (]0,10]) : continuité au sein de chaque
  segment et entre segments consécutifs. Les temps seuls restent enregistrés,
  non indépendants. `clock_basis=host_monotonic` doit être explicitement déclaré
  au niveau index pour le contrat ; jamais inféré d'une UTC/mission/flush.
  L'ancien segment162 n'a pas ce champ au niveau index : `clock_basis_unknown`
  est conservateur, **pas** contradiction de sa temporalité historique lot10.
- Travail borné : au plus8×17MiB lus séquentiellement, une archive et une image
  décompressées à la fois, mesures O(pixels) / mémoire auxiliaire O(largeur).
  Les métriques concernent uniquement les frames décodées et la ROI choisie.
  Le code2 argparse signale une syntaxe invalide ; code1 couvre aussi IO/sortie
  existante, sans écrasement. Ne pas réutiliser un chemin de rapport.

## Contrat indépendant manuel v1 (JSON privé ≤64KiB)

Ne jamais générer ce contrat depuis les valeurs du journal natif. Il lie les
**SHA256 exacts des fichiers sources, dans leur ordre**, ROI, preuve manuelle
indépendante, identité/perspective, repères, fenêtre stable et horloge. Les hashes
`evidence_sha256` désignent des preuves examinées par l'opérateur ; le diagnostic
n'ouvre pas ces preuves et **ne vérifie pas leur véracité**. Pas de pseudo ni
secret. Un hash seul n'est pas une preuve indépendante. Tous les champs racines
ci-dessous sont requis ; champs racines supplémentaires refusés. Les champs
absents sont `missing`, null=`unknown`, incohérents=`invalid` ; seules les
formes cohérentes deviennent `provided_unverified`, jamais « validées ».

**Gabarit incomplet volontairement non passant** :

```json
{
  "schema_version": 1,
  "source": "independent_manual",
  "capture_sha256": null,
  "roi": null,
  "identity": null,
  "landmarks": null,
  "stable_window": null,
  "clock": null,
  "provenance": null,
  "comparison_method": null
}
```

À remplir seulement depuis une vérification indépendante réelle :

| Champ | Forme requise et sens |
|---|---|
| `capture_sha256` | liste des hashes hex64 minuscules des entrées exactes, dans l'ordre |
| `roi` | `[X,Y,W,H]` exactement égale à la commande |
| `identity` | `{session_token, map_id, perspective:"player", evidence_sha256}` ; token hex32 identique à chaque index, carte identifiant ASCII 1–64 ; preuve indépendante même partie/joueur/perspective sans identité privée exportée |
| `landmarks` | `{coordinate_system:"roi_pixels", points:[[x,y],...], evidence_sha256}` ; 2–16 repères DISTINCTS, finis et à l'intérieur de la ROI (coordonnées locales), manuellement identifiés et immobiles ; ne définissent **aucune transformation UV/monde** |
| `stable_window` | `{started_s,finished_s,margin_s,stationary_attested:true}` ; bornes explicites ordonnées, marge non négative explicitement mesurée, fenêtre après marges contenant toutes les captures de tous les segments |
| `clock` | `{basis:"host_monotonic",evidence_sha256}` ; preuve indépendante même base et instance d'horloge, incertitude dans la marge ; aucune conversion implicite |
| `provenance` | `{kind:"independent_manual",evidence_sha256}` ; preuve indépendante minimisée décrivant opérateur/méthode/source, pas une valeur native recyclée |
| `comparison_method` | `{kind:"manual_spatial",evidence_sha256}` ; protocole indépendant préparé (identification des repères, calibration future, incertitudes, refus) ; aucune comparaison exécutée ici |

Les hashes d'attestations et le token sont des **bindings disque non authentifiés**.
Une stabilité déclarée ne détecte pas un repère mobile ; l'inspection indépendante
reste obligatoire. Le rapport laisse `calibration:"unknown"` même avec tous les
champs présents : pas d'UV inventée, de fallback zéro, ni de qualification spatiale.

## Résultat historique exercé (pas une nouvelle recette)

Segment162 gelé lot10, ROI complète624×204, 8 frames : 7 suspectes,
1 sans alerte, 0 non inspectée ; intégrité disque lisible et temps ordonnés.
Sortie1/`unknown`, référence manuelle absente, horloge explicite manquante.
Originaux conservés et hachés avant/après. Une fixture **SYNTHETIC séparée**
exerce uniquement le chemin cohérent/code0 ; elle n'atteste aucun HUD réel.
