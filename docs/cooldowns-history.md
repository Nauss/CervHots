# Cooldowns locaux dans l'historique

Les commandes existantes restituent maintenant `local_cooldowns` :

```bash
python -B -m cerveau.passive_session --summarize --journal C:/chemin/session/events.jsonl --report-dir C:/chemin/nouveau-resume
python -B -m cerveau.passive_session --report-html --journal C:/chemin/session/events.jsonl --report-dir C:/chemin/nouveau-rapport
```

Sortie neuve obligatoire, extérieure au répertoire du journal. Aucun navigateur
n'est lancé. `history.json` / `report.json`, `SUMMARY.txt` / `REPORT.html` sont des
fichiers locaux statiques. Code0 signifie observation historique admissible,
**pas** présence de toutes les familles. Lire le statut de `local_cooldowns`.

## Contrat

- Seulement la projection produit existante, pas les tables diagnostiques.
  Périmètre inchangé : build98348, DragonShire, Sonya, liaison qualifiée
  `BarbarianAncientSpear`. Aucun autre héros, build, carte ou aptitude n'est ajouté.
- Le journal MAIN n'exportait pas cette projection. Le normaliseur retient
  désormais son âge original lors de la normalisation ; `Journal.observation`
  enregistre un schéma fermé. Ni journalisation ni restitution ne renouvelle
  reçu, horloge d'acquisition ou âge. Le défaut `core` et les lectures physiques
  optionnelles restent inchangés. Pour un journal core, la famille reste
  `not_selected`, pas zéro.
- Les anciens journaux lot8 contiennent déjà ce schéma et une collection explicite
  `cooldowns`. Cette sélection est reconnue **uniquement en lecture historique**,
  sans ajouter un mode de collecte live. Une collection absente/invalide reste
  inconnue ; `available_fields` ne peut pas l'autoriser à lui seul.
- Le flux complet doit satisfaire les gardes historiques existantes (fermeture,
  acquisition acceptée, partie, perspective et horloges ordonnées). Le binding
  local des cooldowns est contrôlé sur toutes les observations, y compris les
  ruptures/refus de famille ; un binding talents présent ne peut pas le contredire.
  Chaque valeur est revalidée contre sa propre observation, son roster, carte,
  équipe, vie, mission et provenance d'âge/fenêtre originaux. Un refus optionnel
  simultané à une valeur prétendument normalisée rejette cette valeur.
- Nombres finis, non booléens, bornes de la projection existante ; doublons,
  champ incohérent, âge >1s, fenêtre >125ms ou décalage mission >1s sont rejetés.
  Champs inconnus absents de l'export. Valeurs inconnues/non applicables exposées
  comme `null` dans le rapport, **distinctes de zéro**.
- `provenance` : SHA256 du journal, séquence et JSON Pointer de la valeur originale.
  Les horloges de l'observation restent sous `instant`. Pas de token, pseudo,
  adresse mémoire ou identifiant privé exporté. Le hash prouve une cohérence
  locale des octets, jamais une authenticité de la mesure.

## Limites à lire avant toute interprétation

`cooldown_ready` signifie seulement recharge observée à zéro : **pas lançable**.
Le slot d'instance natif n'est pas une touche/bouton HUD. Corps contrôlé inconnu.
La seule liaison actuelle ne permet **aucun nombre de charges positif** :
`not_applicable_current_max_zero` ou `unknown` ne signifie pas charges disponibles.
Aucune qualification supplémentaire n'est introduite par cet export.

La restitution retient la dernière observation, jamais un succès antérieur à
un manque/refus. Mort avec liste vide n'hérite d'aucune aptitude ; aucune
interpolation, continuité, cast, reset ou reprise de partie n'est inféré.
Il n'y a pas de nouvelle timeline cooldown : la chronologie bornée déjà présente
reste celle du cœur. Toutes les données restent historiques NON authentifiées,
jamais CURRENT, ni validation HUD/replay indépendante, ni conseil.

## Vérification hors ligne

```bash
uv run --offline --no-project --python 3.12 --with mpyq --with heroprotocol python -B -m unittest discover -s tests -v
uv run --offline --no-project --python 3.14 --with mpyq --with heroprotocol python -B -m unittest discover -s tests -v
```

Exécuter ces suites séquentiellement (tests de mutex Windows). Les fixtures de
`tests/test_cooldowns_history.py` sont SYNTHÉTIQUES, pas une qualification native,
HUD, de reset ou de charges. Les preuves lot29 distinguent les deux vrais journaux
lot8 inchangés, un vrai journal lot7 sans cooldown, les refus réels hérités et les
mutations synthétiques. Ne pas modifier les anciens journaux pour leur ajouter
sélection, identité, reçu, âge ou valeur manquante.
