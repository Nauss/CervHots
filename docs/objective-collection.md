# Objectif Dragon : collecte qualifiée et rejeu sans permission live

Ce complément conserve les **valeurs publiques déjà normalisées** de l'objectif
DragonShire et leur qualification dans le collecteur passif. Il n'ouvre aucune
carte/famille : `DragonObjective.read → project_dragon` et les gardes existants
restent inchangés. Ce n'est ni une nouvelle recette native, ni la validation d'un
contrôle du véhicule par le joueur. Volskaya garde sa qualification ; ses valeurs
ne sont pas sélectionnées par ce nouveau journal (`value_status=not_selected`).

## Démarrer / arrêter

Depuis le checkout exact gelé, avec Python et heroprotocol/mpyq installés :

```bash
python -B -m cerveau.passive_session                  # préflight, sans backend
python -B -m cerveau.passive_session --help
python -B -m cerveau.passive_session --live --player-file <identite-privee-absolue> --output-dir <sortie-absolue-NEUVE> --stop-file <STOP-absolu> --max-seconds 300 --interval 5
```

Alternative hors ligne avec les dépendances déjà en cache :
`uv run --offline --no-project --python 3.14 --with heroprotocol python -B -m cerveau.passive_session`.
Le préflight annonce `objective_collection` ; il ne prouve aucune valeur du jeu
actif. Ne pas passer le pseudo en argv, ne pas remplacer le fichier central privé.

Créer le STOP convenu (`touch <STOP>` en bash) ou Ctrl+C. Le fichier n'est jamais
supprimé par l'outil. Nouvelle partie = nouvelle commande, nouveau dossier,
nouveaux backend/probe/sel/reçus. Un seul lecteur. L'opérateur autorisé surveille
aussi le STOP global du mandat et la reprise du PC ; un `--stop-file` ne surveille
pas implicitement d'autres chemins. Voir [passive-session.md](passive-session.md)
pour les frontières, verrous, codes retour et fermeture. Aucun Coach/API/audio/GUI
n'est lancé par ces commandes.

## Lire l'état utilisateur

Chaque `observation` de `events.jsonl` et le `status.json` correspondant contiennent
un objet `objective` distinct des coûts `acquisition` :

| Champ | Sens |
|---|---|
| `status=normalized` | Le normaliseur a accepté la famille dans cette acquisition. Ce mot dans un fichier ne donne aucune permission actuelle. |
| `status=refused` | Refus explicite du producteur optionnel ; `reason` reconstruit depuis un vocabulaire fermé. |
| `status=rejected` | Paquet présent mais non accepté par le normaliseur, ou export malformé ; `objective_packet_rejected` ne prétend pas diagnostiquer la garde précise. |
| `status=not_attempted` | Aucun paquet ni refus fourni au normaliseur ; ce n'est pas une preuve d'absence en mémoire. |
| `status=unknown` | Qualification absente/inconnue (notamment ancien journal). |
| `source` | Canal `native_player` demandé, **pas** preuve que toutes ses gardes ont réussi. |
| `source_mission_t_s`, `read_window_s` | Temps source mission et fenêtre du paquet accepté ; jamais le chrono HUD. |
| `age_s` | Âge du reçu original au moment de la normalisation. Il augmente si le même paquet est réexaminé ; ni le cache, ni la persistance, ni le rejeu ne le remettent à zéro. |
| `value_status=exported` | Valeur Dragon sélectionnée selon un schéma fermé ; `family=dragon`. |
| `value_status=unavailable` | Aucune valeur exportée ; inconnue n'est pas zéro. |
| `value_status=not_selected` | Qualification conservée, export de valeurs hors périmètre de ce lot. |

Les valeurs sont phase, propriété/état/contestation des deux sanctuaires, état/
équipe/canalisation de la statue, état/équipe/durée du dragon et timers publics.
La progression d'un beacon hors CURRENT reste inconnue ; une propriété connue
ne révèle pas une contestation/canalisation hors vue. Ni compteurs bruts de
capture, ni pilote, références/adresses, reçus/signatures in-processus, noms de
joueur ou données tactiques ennemies ne sont exportés. Un `null` est conservé.

Un refus optionnel normal n'empêche pas le cœur accepté et ne consomme pas son
budget de défaillances. En revanche, une option qui épuise le budget **global**
WHOLE refuse légitimement toute l'acquisition : 125ms / 8192 lectures / 1MiB
inchangés, aucun fallback qui contourne ce plafond. Les coûts/refus restent dans
les événements `acquisition` même si aucune observation normalisée ne suit.
`summary.json` et le dernier `status.json` de fin ne récapitulent pas les valeurs :
conserver `events.jsonl`.

## Rejouer une démonstration / un journal enregistré

```bash
python -B -m cerveau.objective_journal --journal <events.jsonl>
python -B -m unittest discover -s tests -p test_objective_collection.py -v
```

Le premier n'ouvre ni processus ni réseau ; il resélectionne les champs autorisés
et étiquette **chaque** sortie `mode=historical_not_current`. Il ne renouvelle
aucun reçu, ne normalise aucun état live et ne prouve pas l'authenticité du
journal. Limites : 64KiB/ligne, 4MiB/fichier, 10000 lignes. En cas d'erreur, code
retour1 et message fermé sans chemin/contenu ; des lignes historiques déjà
émises peuvent précéder l'erreur. Le second exerce les scénarios synthétiques,
le dispatch optionnel réel sur mémoire synthétique, la persistance et le CLI.
Ces tests ne sont **pas une partie live** ni une comparaison HUD/native.

La commande produit `python -B -m cerveau.objective_compare` réalise une
comparaison distincte avec référence HUD manuelle, jeton de session minimisé,
clip OS horodaté et incertitude mesurée. Voir
[objective-comparison.md](objective-comparison.md) pour son schéma fermé, la
démonstration synthétique et les refus (dont horloge replay non calibrée).
Ce raccord ne requalifie pas les anciens journaux sans liaison indépendante.

Recette DEFAULT utile : dans une nouvelle partie privée locale+9bots Dragon,
comparer une phase publique et les propriétés visibles, puis un même beacon hors
CURRENT/avec CURRENT et éventuellement une statue sans/avec vue ; capturer une
référence HUD synchronisée, conserver le cycle/temps source et les coûts/refus,
STOP propre. Ne pas lancer une partie pour attendre un refus déjà connu. Une
absence de fenêtre/valeurs reste un résultat négatif, jamais une promotion de
perspective omnisciente. Aucune recette GUI n'est exécutée par l'auteur.
