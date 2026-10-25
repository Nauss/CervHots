# Diagnostiquer une collecte, hors ligne

Le diagnostic est un **mode de la commande passive existante**, pas un autre
collecteur : `python -B -m cerveau.passive_session --diagnose --help`.
Il lit le journal minimisé produit par `Journal` et réutilise la projection
`measured_acquisition`, le vocabulaire de refus fermé et les lectures JSON bornées
de la comparaison existante. Il ne rejoue pas le normaliseur, ne recrée aucun reçu
et n'appelle jamais le lecteur, Coach, API, audio, GUI, OCR ou réseau. Python standard
suffit à ce mode ; les dépendances du préflight live ne sont pas requises.

## Commande

Depuis le checkout exact à examiner (MAIN seulement après intégration revue) :

```bash
cd C:/root/dev/AI/CervHots
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --diagnose --journal C:/CervHots-private/session/events.jsonl --report-dir C:/CervHots-private/diagnostic-001
```

- `--journal` : fichier existant, chemin absolu **explicite**. Aucun parcours de
  dossiers ni choix automatique du « dernier » journal.
- `--report-dir` : chemin absolu **inexistant**, hors du répertoire de la session
  source (et de ses descendants). Les sorties ne remplacent jamais un rapport
  existant. Un échec d'écriture peut laisser un dossier partiel à conserver ;
  recommencer avec une sortie neuve, pas en effaçant une preuve.
- `diagnosis.json` : rapport structuré minimisé ; la même valeur JSON est sur stdout.
- `SUMMARY.txt` : résumé lisible, également sur stderr. Les chemins, noms de joueur,
  tokens et valeurs tactiques ne sont pas recopiés dans ces rapports.
- Codes : **0 = journal syntaxiquement complet et diagnostic écrit**, **1 = journal
  absent/vide/invalide/tronqué/hors bornes ou IO refusée**, **2 = arguments invalides**.
  **0 ne signifie ni session fermée, ni comparaison réussie, ni validation HUD.**
  Les références visuelles inutilisables sont des résultats diagnostiques explicites,
  pas une raison de transformer le code 0 en PASS spatial.

`--diagnose`, `--status`, `--preflight`, `--live` sont exclusifs. Les chemins
live/statut sont refusés en diagnostic, et les options de diagnostic sans
`--diagnose` sont refusées avant tout préflight. Aucun fichier d'identité n'est lu.

Pour **démarrer/arrêter/reprendre** une collecte autorisée, conserver les commandes
existantes du [parcours court](passive-quickstart.md#2-démarrer-une-seule-session-autorisée) :
`--live --player-file <privé> --output-dir <session-neuve> --stop-file <STOP-neuf>`,
puis `touch <STOP-neuf>` et contrôle indépendant du retour du collecteur, accompagné
de `--status --output-dir <session>`. Un diagnostic historique ne remplace pas ce
contrôle. Ne supprimer aucun claim ni ancien STOP ; reprise sous un **parent neuf**.
Aucune de ces actions live n'est nécessaire au diagnostic ou à ses tests.

## Lire le résultat sans convertir l'inconnu en zéro

- `counts.acquisitions` = événements d'acquisition mesurés persistés ;
  `counts.observations` = observations déjà normalisées **selon le journal**.
  `acquisition_outcomes` sépare accepted/refused/error/unknown.
- `refused_cycles` est l'union par cycle des acquisitions refusées et des événements
  `refusal` : une acquisition refusée suivie de son refus ne vaut **pas deux refus**.
  `refusal_events` reste le décompte séparé des lignes de refus. Les refus optionnels
  sont à part, par famille/code. Un code inconnu devient `unknown_refusal`, pas zéro.
- `source_errors`, `errors`, `unknown_events`, `unmeasured_cycles` restent distincts.
  Une ouverture ratée n'a pas de coût inventé à zéro. Les coûts absents ont un maximum
  `null` et un compteur `missing`. Le nombre réel d'essais interrompus avant
  persistance **n'est pas reconstructible** depuis le journal ; ne pas le déduire
  d'accepted+refused, du maximum des cycles ou d'un zéro événement.
- `total_acquisitions` totalise seulement les événements enregistrés, jamais des
  essais non persistés. Sur journal incomplet, il est `null`, et les compteurs
  portent `counts_scope=valid_prefix_only`. Un suffixe JSON même valide mais sans
  LF terminal est tronqué et exclu, pas silencieusement accepté.
- `normalized_fields` compte les présences enregistrées sur le vocabulaire existant,
  **pas une revalidation des valeurs**. Les champs étrangers ne sont jamais recopiés.
  `families` conserve les qualifications enregistrées ; famille/qualification absente
  ou non reconnue ⇒ `unknown`. Ces statuts ne sont pas des attestations authentifiées.
- `metadata` compte disponible versus absent/invalide pour origine déclarée,
  horloge mission, temps écoulé, UTC aware, bracket host-monotonic et identité liée.
  Mission/UTC/flush ne remplacent jamais le bracket de lecture. `family_provenance`
  distingue source, mission et âge/fenêtre **originaux enregistrés**, sans les renouveler.
- `identity` ne publie que le nombre de bindings cohérents et un statut. Un binding
  absent/incomplet ou plusieurs identités donne `incomplete_or_mixed`, jamais une
  association « au plus proche ». Les bindings explicitement reconnus ici sont les
  schémas DragonShire/Volskaya ; une autre carte reste inconnue, sans nouvelle allowlist.
  Le build actif n'est pas enregistré/provable par ce rapport ; `authenticated=false`.
- `stop.recorded_reason` est la dernière frontière enregistrée, sinon `unknown`.
  **Ce n'est pas une preuve de fermeture OS** : `reader_active=null` toujours.
  `--status` existant peut indiquer une fermeture historiquement enregistrée dans
  summary.json ; aucun des deux modes ne prouve l'ownership ou la vie d'un processus.

## Références visuelles facultatives : diagnostic, jamais comparaison

Ajouter explicitement une ou plusieurs références (8 maximum) :

```bash
python -B -m cerveau.passive_session --diagnose --journal C:/CervHots-private/session/events.jsonl --report-dir C:/CervHots-private/diagnostic-002 --visual-reference C:/CervHots-private/clip.zip --visual-reference C:/CervHots-private/image.bmp
```

Le mode inspecte uniquement **BMP non compressés 24/32 bits** ou les ZIP stockés
existants, avec index.json et frames BMP hashées. PNG/JPEG/vidéo/autres formats :
`invalid_or_unsupported`, pas un décodeur implicite. Une référence absente est
`unavailable` ; fichier/ZIP/index/frame incomplet ou incohérent n'est pas accepté.
Un ZIP déclaré partiel ou nommé `.partial` est `partial_reference`.

Heuristique limitée : grille **16×8** ; tuile suspecte si au moins 98% de ses pixels
ont R/G/B ≤8 ; frame suspecte à partir de 4 tuiles. Alpha ignoré. Cela peut signaler
un grand rectangle noir et **peut aussi signaler une zone légitimement sombre**,
ou manquer un masque fin/non noir. `black_or_masked_suspected` est un avertissement,
pas une cause physique prouvée. Une image sans alerte vaut seulement
`pixels_decoded_not_attested` : ni association des slots, ni minimap complète,
ni calibration, ni stabilité temporelle n'en découlent.

Les bornes des frames sont étiquetées `recorded_not_independent` ou
`missing_or_invalid`. Elles ne sont pas une fenêtre visuelle stable manuellement
attestée. Ce mode n'accepte pas une déclaration `hud_validated=true`/`complete=true`
comme preuve indépendante ; il **ne consomme pas** les transcriptions/calibrations
manuelles pour comparer. Identité visuelle, calibration et intervalle stable restent
explicitement manquants/non vérifiés dans ce diagnostic. Pour la comparaison Dragon
manuelle existante et ses preuves liées, voir [objective-comparison.md](objective-comparison.md).
Aucun comparateur de positions n'est ajouté et aucun lot10 n'est intégré ici.

Invariants de toute sortie : `evidence.status=non_comparable`,
`spatial_comparisons=0`, `hud_validated=false`, `current_permission=false`.
Un hash, un CRC, un seal, une fermeture ZIP ou des pixels colorés n'y changent rien.

## Bornes et sécurité

Journal ≤4MiB, ≤10000 lignes, ≤64KiB/ligne ; schéma1, séquence contiguë, cycles
non décroissants ; doublons JSON, valeurs non finies, types invalides et doublons
d'acquisition/observation/refus au même cycle refusés. Fichiers réguliers seulement.
Chaque référence ≤17MiB, répertoire ZIP central ≤64KiB/401 membres avant allocation,
≤512KiB/membre, ≤128KiB/index, ≤400 frames ; stockage ZIP_STORED seulement, noms
fermés, aucun chemin externe, chiffrement ou extraction. Les limites bornent le
travail, pas la santé du stockage : snapshot disque historique, pas authentification
ni promesse de lecture atomique d'un fichier en cours d'écriture. Préférer une
collecte terminée/copie conservée ; une troncature concurrente doit rester visible.

## Exemple réel anonymisé, sans nouvelle collecte

Journal existant lu **sans modification**, issu de la recette lot10 récupérée :
`out/weekend/2026-10-24/lot10/operator-real-capture-001/new/events.jsonl`.
SHA256 `66adafbee7a1f62f88d6926604c7c9e6cf7f9e1d96d11e7ce8c5f6203da957ea`.
La commande a été exercée depuis le candidat sous Python3.12 et3.14, avec sortie
neuve et hashes avant/après. Aucun pseudo/token/coordonnée exporté ici.

```text
Diagnostic historique — NON COMPARABLE / HUD non valide
Journal: complete; portee: recorded_events
Acquisitions: 89; observations normalisees: 80; cycles refuses: 9; evenements refus: 9; arrets: 1
Arret enregistre: stop_file; activite actuelle: inconnue
```

Les 80 observations comportent des positions enregistrées normalized, et les
qualifications objectif/talents sont not_attempted ; gameplay_clock/visibility/
local_cooldowns/battlefield restent unknown. Les brackets/identités sont enregistrés
sur80/80, **pas indépendamment authentifiés**. Deux ZIP explicitement inspectés :
segment4, 9frames sans alerte heuristique ; segment162, 8/8frames avec suspicion de
noir/masquage. Ce dernier nombre est **un résultat heuristique** : il ne remplace pas
les 7/8 masquages signalés par l'inspection humaine historique. Aucun examen des
80ZIP/465frames n'est prétendu. Résultat spatial : **zéro comparaison**, pas zéro écart.

### Limites carte × famille conservées

| Carte × famille | Interprétation de ce diagnostic |
|---|---|
| Volskaya × cœur/positions alliées | présence normalisée enregistrée, pas nouvelle validation HUD ni extension aux ennemis |
| DragonShire × objectif Dragon | export public existant seulement ; comparaison manuelle distincte, jamais implicite |
| DragonShire × talents | sélections/libellés qualifiés par bindings existants seulement, pas tous héros/cartes |
| Volskaya × objectif | qualification seulement ; not_attempted/refus ne vaut pas objectif zéro |
| Braxis × objectif, carte/famille inconnue | aucune ouverture ; inconnu/refus reste tel quel |
| Cooldowns/charges, camps/structures, visibilité ennemie | aucune qualification nouvelle, absence ≠ disponible/zéro |

Les gardes WHOLE125ms/8192/1MiB, build, contexte, perspective, fraîcheur et allowlists
restent inchangés : le diagnostic ne les exécute pas et ne les court-circuite pas.

Régression hors ligne :
`python -B -m unittest discover -s tests -p test_session_diagnosis.py -v`.
La suite complète exige le dossier ignoré `out/` (tests historiques), puis
`python -B -m unittest discover -s tests -q`. Les fixtures synthétiques sont
explicitement des tests, jamais une preuve live/HUD. Revue indépendante du commit
exact et tests depuis MAIN restent nécessaires avant annonce d'intégration.
