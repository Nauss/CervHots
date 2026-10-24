# Comparer une référence HUD indépendante à l'objectif Dragon

`python -B -m cerveau.objective_compare` est une **commande produit hors ligne**.
Elle ne lit aucun processus, ne produit aucune statistique depuis l'écran, ne
réémet aucun reçu et ne change ni CURRENT, ni allowlists, ni gardes natives.
Un rejeu du même journal ne constitue jamais la référence indépendante.

## Démonstration synthétique reproductible

Depuis la racine du checkout :

```bash
python -B -m cerveau.objective_compare --help
python -B -m cerveau.objective_reference --help
python -B -m cerveau.objective_reference  # préflight stdlib, aucune capture
python -B -m cerveau.objective_compare --journal examples/objective-comparison/SYNTHETIC/synthetic-events.jsonl --references examples/objective-comparison/SYNTHETIC/synthetic-reference.json --evidence examples/objective-comparison/SYNTHETIC/evidence.synthetic --match-link examples/objective-comparison/SYNTHETIC/match_link.synthetic --clock-evidence examples/objective-comparison/SYNTHETIC/clock_evidence.synthetic
```

Les fixtures, y compris les octets tenant lieu d'images, sont **SYNTHÉTIQUES**.
La phase `shrines` égale est un test logiciel, pas une observation du jeu.
Alternative : préfixer chaque commande par
`uv run --offline --no-project --python 3.14 --with heroprotocol`.
Le comparateur et le clip utilisent seulement la bibliothèque standard ; le
collecteur natif exige les dépendances habituelles (`heroprotocol/mpyq`).

## 1. Collecter une NOUVELLE partie autorisée

Voir [objective-collection.md](objective-collection.md). Le journal passif ajoute
à chaque observation `comparison` : jeton aléatoire de 128 bits par invocation,
carte canonique Dragon seulement si l'objectif validé l'identifie, perspective
`native_player`, base `host_monotonic`, début/fin de l'appel réel `source.read`.
Aucun nom, identifiant de compte ou adresse n'entre dans ce jeton. Changement de
partie/perspective/carte ou recul mission : frontière existante, aucune seconde
observation de la nouvelle partie. Reprise : nouvel appel et nouveau jeton.

Ni le temps source mission, ni le temps gameplay/HUD/replay, ni l'UTC écrit après
persistance ne sont substitués à cette base monotone. Un ancien journal sans ce
raccord reste non comparable ; on ne lui invente pas un alignement rétrospectif.
L'âge du reçu est celui mesuré à la normalisation, inchangé dans le journal.

## 2. Référence indépendante : clip HUD minimisé, sans OCR

**Opérateur autorisé seulement**, jeu déjà au premier plan, écran principal.
Ne pas lancer une partie avant d'avoir préparé et testé les outils hors ligne.
Choisir un rectangle HUD sans pseudonymes, chat, notifications ou autre fenêtre
(par exemple 200×100 pixels, à ajuster sur le vrai HUD, jamais des coordonnées
supposées). Les coordonnées sont relatives au RECT de la fenêtre du jeu ; les
bordures/titres font partie de ce repère. Aucun changement automatique de focus.

```bash
python -B -m cerveau.objective_reference --record --session-token <JETON32HEX_DU_STATUS_DE_CETTE_SESSION> --output-file <PRIVATE_ABSOLU_NEUF/hud.zip> --stop-file <STOP_RECETTE_ABSOLU> --stop-file <STOP_GLOBAL_ABSOLU> --region <X> <Y> <LARGEUR> <HAUTEUR> --max-seconds 8 --interval 0.05
```

Cette commande vérifie l'exécutable du jeu au premier plan par une requête
Windows d'identité uniquement (`PROCESS_QUERY_LIMITED_INFORMATION`, **pas** de
lecture VM), effectue des captures OS GDI du rectangle, vérifie fenêtre/géométrie
avant/après, libère les objets GDI et ferme le handle d'identité. Ni souris,
clavier, mémoire client, appel/injection client, audio ni réseau. Une fenêtre
incorrecte, déplacée, hors écran, une erreur ou STOP refuse/arrête. Un overlay
qui ne modifie pas le focus peut échapper à cette vérification : l'opérateur doit
**rejeter visuellement** ces images, ainsi que les images noires/partielles.

Archive ZIP non compressée, frames BMP et `index.json` fermé : bornes monotones
avant/après CHAQUE capture, hashes, plus grand intervalle entre captures et plus
grande durée de capture. `complete=false` sur erreur : archive inexploitable.
Bornes : 10s maximum, intervalle25–100ms (ce n'est PAS une fréquence garantie),
400 frames, 512×200 pixels maximum, 512KiB/frame, 16MiB d'images. Un grand rectangle
peut atteindre la limite avant8s : conserver le refus, pas de relance aveugle.
Un STOP vérifié après capture jette la frame en cours. Le clip ne lit pas le
journal natif et ne décide JAMAIS d'une valeur d'objectif.

Conserver les images dans PRIVATE avec les permissions restrictives du chantier ;
ne pas les joindre aux sorties publiques. Lire manuellement **toutes** les frames
d'une fenêtre stable, pas seulement les deux extrémités. Une séquence échantillonnée
n'exclut pas un changement plus bref que sa résolution : cette limite accompagne
le verdict. Ne pas affirmer une égalité frame-exacte ou une stabilité continue
mathématique. Si la résolution ne permet pas le champ exact, laisser `value=null`.

## 3. Rédiger manuellement les deux JSON minimisés

Fermer le collecteur/clip et hasher leurs fichiers définitifs. Copier les octets
`index.json` du ZIP vers le fichier `clock.json` (sans réencoder le JSON). Les
hashes portent sur les octets réels, pas sur leur représentation en texte.

Le témoin `match-link.json` est une déclaration de l'opérateur, pas une identité
native réexportée ni une authentification cryptographique. Il atteste que ce
collecteur ET ce clip ont été observés dans LA même partie privée ininterrompue,
carte et point de vue joueur vérifiés indépendamment ; pas seulement « même carte ».
Si cette chaîne n'est pas disponible, ne pas déclarer `true`.

```json
{
  "schema_version": 1,
  "dataset": "operator",
  "session_token": "<32 minuscules hex du collecteur ET du clip>",
  "map_id": "DragonShire",
  "perspective": "native_player",
  "scenario": "private_local_9bots",
  "same_uninterrupted_match": true,
  "identity_verified_privately": true,
  "journal_sha256": "<SHA256 events.jsonl fermé>",
  "evidence_sha256": "<SHA256 hud.zip fermé>"
}
```

Puis `references.json` ; aucune clé supplémentaire, texte libre, pseudo, chemin,
secret ou adresse. Les `<...>` sont des emplacements à remplir, pas un JSON valide
à soumettre. Ne jamais copier les valeurs natives dans les valeurs de référence.

```json
{
  "schema_version": 1,
  "dataset": "operator",
  "journal_sha256": "<SHA256 events.jsonl fermé>",
  "binding": {
    "session_token": "<même jeton32hex>",
    "map_id": "DragonShire",
    "perspective": "native_player"
  },
  "provenance": {
    "kind": "hud_video",
    "transcription": "manual",
    "same_match": true,
    "same_player_perspective": true,
    "evidence_sha256": "<SHA256 hud.zip>",
    "match_link_sha256": "<SHA256 match-link.json>",
    "clock_evidence_sha256": "<SHA256 clock.json = index.json du ZIP>"
  },
  "clock": {"basis": "host_monotonic", "uncertainty_s": null},
  "samples": [
    {"cycle": 1, "field": "sun.owner", "value": null,
     "stable_from_s": null, "stable_to_s": null,
     "boundary_uncertainty_s": null}
  ]
}
```

`cycle` vise une observation UNIQUE, pas le voisin le plus proche. Transcrire une
valeur lisible dans la portion stable du clip (par exemple `neutral`, seulement si
la propriété neutre est explicite ; un sanctuaire désactivé ne prouve pas sa
propriété). Laisser les inconnues `null`, jamais0. Renseigner les bornes de cette
portion dans le repère monotone de l'index. Les nombres ne sont pas le chrono HUD.
`clock.uncertainty_s` doit couvrir au moins `max_capture_s` mesuré ; pour chaque
sample, `boundary_uncertainty_s` doit couvrir au moins
`max_gap_s + max_capture_s` recomputés depuis les frames. Arrondir vers le haut,
jamais diminuer les mesures pour faire passer une comparaison.

Champs fermés : `phase` (`waiting/warning/shrines/dragon/unknown`), `sun.owner` et
`moon.owner` (`neutral/0/1/null`), `statue.state` (`capturable/inactive/unknown`),
`dragon.state` (`inactive/active/ended/unknown`). Ne pas déduire un état complexe
d'une couleur ambiguë. **Équipes0/1 refusées** (`team_mapping_unqualified`) : le
bleu/rouge relatif du HUD ne prouve pas l'index d'équipe natif. La propriété
`neutral` n'a pas cette ambiguïté. Aucun timer interpolé, progression, CURRENT,
pilote, talent, cooldown, position, Braxis ou export Volskaya ajouté.

## 4. Comparer et interpréter

```bash
python -B -m cerveau.objective_compare --journal <events.jsonl> --references <references.json> --evidence <PRIVATE/hud.zip> --match-link <match-link.json> --clock-evidence <clock.json>
```

Le programme vérifie les hashes, le schéma fermé du témoin et du clip, le même
jeton, la carte/perspective, les timestamps et hashes de chaque frame, les gaps
recalculés et l'identité byte-exacte du `clock.json`. Il n'authentifie ni l'opérateur
ni la vérité visuelle de sa transcription. Un fichier fabriqué puis attesté ne
constitue pas une validation réelle ; conserver cette limitation dans la recette.

Pour chaque cycle ciblé, cinq lignes de verdict sont produites : `compared`
(égalité exacte), `divergent` (valeurs connues différentes), `non_comparable`
(raison fermée). Un champ sans référence reste non comparable ; doublon ou cycle
ambigu aussi. L'audit porte sur **toutes les observations du journal**, même
hors du cycle ciblé : session, jeton, carte et perspective doivent rester uniques.
Une observation sans liaison (absente, nulle ou malformée) dans un flux lié rend
**tout le flux non comparable** (`journal_context_ambiguous`), même après recalcul
des hashes et du témoin. Un ancien journal isolé sans liaison reste non comparable
(`binding_missing`). Ne pas concaténer des parties ou reprises.
Rien n'est moyenné, interpolé, arrondi comme une valeur exacte, ni promu depuis
unknown. Les refus survenant hors du cycle ne sont pas des valeurs.

L'intervalle source conservateur est
`[read_started_s - age_s - read_window_s, read_finished_s]` : il englobe le reçu
original et l'appel ayant effectué sa normalisation, pas la date du flush.
Il doit avoir une largeur≤0,5s. L'intervalle de stabilité manuel, **réduit** de
`clock.uncertainty_s + boundary_uncertainty_s` à chaque bord, doit contenir cet
intervalle EN ENTIER et être inclus dans le clip. Simple chevauchement ou frame
ponctuelle : refus. Chaque incertitude est≤0,25s ; portion stable≤30s.
Ces plafonds sont des critères de comparaison historique, pas un assouplissement
des budgets mémoire/âge/WHOLE de la collecte.

`kind=replay_video`, base `replay` ou `utc` restent explicitement non comparables :
aucune calibration fiable replay↔source n'est établie ici, ne pas inventer un
offset. Les anciennes images lot4 et les28/28 du même journal ne sont pas promus.
Toutes les sorties portent `mode=historical_not_current`, `current_permission=false`
et le label `dataset`. `provenance=operator_attested` rappelle la nature du témoin,
y compris pour la démonstration synthétique (qui reste `dataset=synthetic`).

Bornes : références64KiB/128 samples (640 verdicts maximum), témoin64KiB,
journal4MiB/10000lignes/64KiB par ligne, clip17MiB, index128KiB, artefact témoin
haché64MiB maximum avant validation plus stricte. Clés JSON dupliquées refusées.
Erreur de format/IO : code1 et message fermé sans contenu/chemin. Comparaison
exécutée : code0 **même si aucun champ comparable ou s'il existe une divergence** ;
lire les compteurs, pas le seul code retour. Aucun effet sur le produit live.

Après recette : STOP conservés, lecteur fermé/verrou absent, captures terminées,
archives/handles/libérations vérifiés, menu restauré par l'opérateur. Conserver
hashes et sources gelées jusqu'à libération explicite de la recette ET revue.
Revue indépendante exacte puis intégration locale/test main sont des gates séparées.
