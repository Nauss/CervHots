# Retrouver les sessions enregistrées — catalogue local

Depuis le checkout CervHots, **sous Windows**, sans jeu, lecteur natif, Coach,
API, audio ou navigateur automatique :

```bash
python -B -m cerveau.passive_session --catalog --sessions-root C:/CervHots-private/sessions --report-dir C:/CervHots-private/catalogue-001
```

La racine doit être un **répertoire local absolu existant**, explicitement choisi.
La sortie doit être **neuve**, absolue, avec un parent existant, **hors de la
racine d’entrée** ; l’entrée ne doit pas être sous la sortie non plus. Les
lecteurs réseau/UNC, chemins de périphérique, flux ADS, `..`, racines de volume,
liens symboliques, jonctions et autres reparse points sont refusés. Les ancêtres
sont également vérifiés, y compris ceux de la sortie. Les alias Windows 8.3
sont résolus après protection des ancêtres pour vérifier les chevauchements.
Les autres OS refusent ce mode : aucun repli de parcours moins protégé.

Ouvrir **manuellement** `catalogue-001/INDEX.html`. `catalog.json` est le même
index minimisé. Les liens relatifs visent uniquement
`session-001/REPORT.html`, etc., générés dans la sortie, jamais les entrées.
Chaque rapport a aussi son `report.json` : ce sont les **mêmes moteurs et
rendus** que `--report-html`, sans fusion d’identité, de valeurs ou de parties.
Aucun chemin source, nom de dossier privé, pseudo ou identifiant de session
n’est exporté. Les identités choisies de talents déjà minimisées et traçables par
le moteur historique ne sont pas renommées ni réinterprétées.

## Ce que la découverte signifie

Un répertoire est candidat s’il contient un nom exact `events.jsonl`,
`status.json` ou `summary.json`. Ces deux derniers sont des **marqueurs de nom
seulement** : leur contenu n’est pas lu. Les répertoires génériques sans marqueur
ne deviennent pas des sessions imaginées. La racine elle-même est examinée.
Les noms et chemins figurant dans les journaux ne sont jamais suivis.

Les ordinaux locaux suivent un parcours profondeur d’abord, avec noms triés
lexicalement, et les candidats du répertoire avant ses enfants. Ce ne sont ni
une identité stable entre catalogues ni un classement temporel. Un lien ou une
entrée inaccessible peut aussi avoir un ordinal explicatif sans rapport.

| État par entrée | Sens historique uniquement |
|---|---|
| `recorded` | Observation admissible selon le moteur historique existant ; familles optionnelles éventuellement inconnues/refusées. |
| `refused` | Journal malformé, limite propre au parseur ou contexte/temps/identité refusés ; rapport explicatif si lisible. |
| `incomplete` | Journal vide/tronqué ou clôture absente/inconnue ; aucune valeur récupérée d’un préfixe. |
| `absent` | Marqueur de session trouvé, mais pas de `events.jsonl`. |
| `unreadable` | Répertoire/entrée/journal inaccessible, fichier non régulier, lien physique multiple ou écriture en cours incompatible. |
| `blocked` | Lien/reparse point refusé, jamais parcouru. |
| `limit` | Ce journal n’a pas été lu, car la borne totale d’octets serait dépassée. |

Une racine sans candidat donne `sessions=[]` et
`discovery.state=no_sessions_found`, pas un faux rapport réussi.
`discovery.complete=false` et les listes fermées `limits_reached` / `refusals`
signalent un parcours partiel. Les sessions non découvertes ne sont pas comptées
comme absentes, et un succès ne rend aucune autre entrée admissible.

**Bornes fermes, non configurables par la CLI :** profondeur 4 (racine = 0),
1024 entrées de répertoire, 64 sessions/objets signalés, 16 Mio de lectures de
journaux au total. Atteindre le plafond d’entrées arrête immédiatement
l’énumération, sans lecture sentinelle au-delà : même un répertoire dont la
dernière entrée serait exactement la 1024e est conservativement signalé partiel.
Aucun préfixe dépendant de l’ordre OS de ce répertoire n’est retenu. Chaque
tentative de lecture est réservée dans le budget
à partir de la taille du handle protégé, au plus 4 Mio + 1 octet pour constater
le dépassement du parseur. Ses limites existantes demeurent **4 Mio, 10000
lignes, 64 Kio/ligne**. Les sous-répertoires au-delà de la profondeur sont omis,
avec `depth_limit`, pas déclarés vides.

## Publication et reprise après erreur

La sortie est réservée par une création **exclusive**. Deux invocations vers
la même sortie ne peuvent pas toutes deux la revendiquer ; une sortie existante,
même vide, n’est jamais réutilisée, effacée ou remplacée. Les ancêtres,
répertoires visités et répertoires de sortie sont protégés par des handles
Windows qui refusent les écritures/renommages de ces objets. Les journaux sont
lus depuis un handle sans réouverture de leur chemin, avec écriture/suppression
interdites pendant leur lecture. Cela peut refuser un journal encore ouvert en
écriture : le catalogue n’établit jamais l’activité du collecteur.

Les rapports individuels sont écrits exclusivement, puis `flush`/`fsync`,
**avant** `catalog.json`, puis `INDEX.html`, également exclusifs et synchronisés.
Une erreur d’écriture d’un rapport ne devient pas une simple erreur d’entrée et
interrompt la publication des index. Aucun index ne référence un rapport absent
à cause d’une écriture échouée. Contrairement au rapport individuel, le catalogue
ne promet **pas** une publication atomique du répertoire entier : conserver les
protections Windows interdit ici le renommage vers un parent protégé.
Un arrêt/échec peut laisser une sortie partielle (y compris un index incomplet si
son écriture a été interrompue), jamais à traiter comme une réussite. Aucun
nettoyage automatique ni garantie contre la panne électrique ou les modifications
ultérieures de la sortie par son propriétaire. Reprendre avec une **nouvelle
sortie**, sans supprimer les entrées, anciens STOP, claims ou verrous.

Code **0** : découverte complète, au moins une session et toutes en `recorded`.
Code **1** : catalogue partiel/refus/absence/incomplétude, ou erreur d’entrée/
publication (message fermé `session_catalog_error`). Les rapports réellement
produits restent inspectables si un catalogue explicatif a été achevé.
Code **2** : arguments invalides. `--catalog` est exclusif des autres modes et
n’accepte que `--sessions-root` et `--report-dir` : ni journal unique, référence
visuelle, identité privée, chemins live, `--collection`, `--max-seconds` ou
`--interval`. Même leurs valeurs par défaut explicitement fournies sont refusées,
avec ou sans `=` ; aucune sortie n’est créée pour ces arguments invalides.

Toujours **historique NON authentifié**, jamais CURRENT, HUD, reçu, conseil,
qualification native nouvelle ou permission de reprise. Inconnu n’est pas zéro.
Voir [rapport individuel](session-html.md) pour les valeurs et refus inchangés.
