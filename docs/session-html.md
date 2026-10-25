# Rapport de session HTML local

Depuis le checkout CervHots, sans lancer le jeu, le Coach ou un navigateur :

Pour retrouver plusieurs sessions sans connaître le chemin de chaque journal,
voir le [catalogue local borné](session-catalog.md) :
`--catalog --sessions-root <répertoire-absolu> --report-dir <sortie-neuve-absolue>`.

```bash
python -B -m cerveau.passive_session --report-html --journal C:/CervHots-private/session/events.jsonl --report-dir C:/CervHots-private/rapport-001
```

Les deux chemins doivent être absolus. Le dossier de sortie doit être **neuf**, hors du dossier du journal. Ouvrir ensuite **manuellement** `REPORT.html` avec le navigateur de son choix ; `report.json` contient la même projection minimisée pour inspection. Aucun service à arrêter, aucune référence visuelle ou identité privée à fournir. `--report-html` est exclusif de `--summarize`, `--diagnose`, `--status`, `--preflight` et `--live`. Les modes existants sont inchangés.

## Ce qui est lisible

- Dernière observation cohérente, carte et niveaux publics réellement exportés par `native_history`.
- **Santé locale et ressource locale, avec leurs maximums**, ainsi que vivant/mort si enregistré. Les valeurs viennent exclusivement du même événement que l'instant affiché. La liaison locale exige les talents locaux validés de cet événement (sélection, provenance, âge original, carte, slot, équipe et niveau cohérents), puis le roster complet et l'alias de héros minimisé. Aucun « premier allié » deviné, aucune identité privée consultée, aucune fusion avec une observation antérieure. Un changement d'alias/équipe locale enregistré dans le flux refuse l'historique, même sur une observation aux talents refusés.
- Le schéma durable nomme les champs `resource` / `resource_max`, **pas leur type** : la ressource n'est donc pas renommée « mana », ni convertie. Un héros peut utiliser une autre ressource ; mana reste non établi. Les journaux `core` sans liaison locale explicite restent inconnus pour ces valeurs, même si des PV alliés sont enregistrés.
- Talents locaux seulement si sélection et preuves historiques valides : palier, **ordinal du choix natif** et désormais identité choisie traçable (hash du journal, séquence, clé exacte, build/héros). Une correspondance documentaire anglaise épinglée peut être affichée **séparément**, sans en faire le nom du talent choisi. Libellé choisi inconnu reste inconnu ; les preuves manquantes sont explicites. Voir [le contrat talents](talents-collection.md#restitution-joueur-traçable-hors-ligne).
- Objectif public seulement si déjà exporté et validé par le moteur historique ; inconnues affichées comme telles, jamais comme zéro. Les autres familles n'ont qu'un statut enregistré, pas de valeurs reconstruites.
- Distinction non sélectionné, inconnu, refusé/rejeté, non tenté et normalisé ; sélection absente/invalide laisse les familles inconnues.
- Comptages et codes fermés de refus du diagnostic existant, limités aux événements effectivement enregistrés ; journal incomplet : préfixe seulement, total de session inconnu. Refus/erreur ultérieur signalé sans rafraîchir la dernière observation.

**Historique NON authentifié**, jamais CURRENT, validation HUD, nouveau reçu ou conseil. Aucun âge actuel calculé. Âge du cœur non enregistré, pas zéro ; les âges/fenêtres optionnels sont les originaux. Ni disponibilité live, ni ownership, ni activité actuelle ne sont établis. `references_held=false` pour les exercices du lot17 : pas de nouvelle qualification native/HUD, pas de nouveau match requis.

## Contrat JSON du cœur local

`history.local_core` est un ajout minimisé au schéma historique v1, également disponible via `--summarize`. Aucun alias/slot/session/token n'y est exporté. Chaque paire utilise `status`, `value`, `maximum` :

- `recorded` : deux nombres finis non booléens, entre 0 et 100000, maximum strictement positif et valeur ≤ maximum ; zéro enregistré reste zéro.
- `absent` : membre non enregistré, sans membre présent malformé ; paire entière nulle, jamais complétée par un autre événement.
- `invalid` : type/bornes/relation invalides ; paire entière nulle. Un membre malformé reste invalide même si l'autre manque.
- `unknown` : liaison locale non établie ou sélection/provenance talents insuffisante ; valeurs nulles. Roster ou alias invalide donne `invalid` au niveau du cœur.
- `refused` : historique entier refusé ; aucune valeur retenue. Ces états ne modifient pas les qualifications des familles optionnelles et ne comptent pas comme validation HUD.

`original_age_s` reste **null** : l'âge des talents ne devient pas l'âge du cœur. `alive` est booléen strict ou null ; aucun respawn/ratio/dégât/delta/âge n'est dérivé. Les nombres JSON conservent leurs valeurs ; le texte utilise au plus 15 chiffres significatifs.

Extrait minimisé d'une sortie sur corpus **réel historique** lot7, mission 97.4375 s (pas un état actuel) :

```json
{
  "status": "recorded",
  "identity_basis": "validated_recorded_local_talents",
  "original_age_s": null,
  "health": {"status": "recorded", "value": 2548.095703125, "maximum": 2548.095703125},
  "resource": {"status": "recorded", "value": 0.0, "maximum": 100.0},
  "alive": true
}
```

Gain : PV et ressource auparavant présents sur disque mais non affichés, désormais lisibles sans réacquisition. Inconnues conservées : type de ressource/mana, âge du cœur et âge actuel. Le journal legacy lot1 reste refusé pour liaison identité/temps insuffisante : pas de récupération opportuniste des PV. Les fixtures de test portent explicitement `SYNTHETIC` ; elles ne sont pas des mesures natives.

## Chronologie historique bornée

Le tableau « Chronologie du cœur local » et `history.core_timeline` montrent les
observations du cœur local, pas seulement la dernière. La CLI `--summarize` expose
la même projection et les mêmes cellules en texte. Les gardes historiques globales
(clôture unique finale, intégrité, identités et temps, acquisitions) restent un
prérequis : un refus même tardif retire **tous** les points, sans sauver un préfixe.
Une divergence locale enregistrée reste refusée même si elle déséquilibre le roster.

- `order_basis=journal_ordinal_not_time` : `journal_ordinal` est la position 1-based
  de l'enregistrement dans le journal complet, pas une seconde ni un cycle de jeu.
  Aucun âge, delta, DPS, causalité ou conseil n'est calculé ; aucune courbe ni
  interpolation ne relie les lignes. Les champs temporels du dernier instant
  restent séparés de cette chronologie.
- Chaque observation repasse par **les mêmes** `_packet`, `_talents` et `_core` que
  le dernier instant, avec sa propre acquisition/sélection/liaison. Les valeurs
  absentes ou invalides et les observations sans liaison restent visibles sans
  valeurs de remplacement. Aucun souvenir d'identité ne fournit de valeur locale.
- Les refus, erreurs, erreurs de source, acquisitions explicitement refusées/en
  erreur et la frontière finale occupent leurs propres lignes, sans valeurs.
  Deux marqueurs du même cycle restent deux événements, pas deux points locaux.
- Maximum **128 entrées affichées**, dernières entrées dans l'ordre du journal,
  ruptures et frontière comprises : donc **au plus 128 points**, généralement moins.
  `total_entries`, `total_observations`, `total_points` comptent tout le flux
  admissible, même ce qui n'est plus affiché. Un point est une observation liée
  ayant au moins une paire PV/ressource valide ou un booléen vivant connu.
  `displayed_points`, `omitted_entries` et `truncated` rendent la limite explicite.
  La validation et le comptage ne s'arrêtent jamais au plafond d'affichage.
- En refus : `status=refused`, entrées vides, `counts_complete=false`, totaux et
  troncature inconnus (`null`), pas de zéro qui prétendrait compter le flux entier.
  Les limites du parseur (4 Mio, 10 000 lignes, 64 Kio/ligne) restent inchangées.

Le corpus réel lot7 exercé dans lot22 contient **46 observations locales admissibles**,
9 acquisitions refusées et leurs 9 événements de refus, puis une frontière :
65 entrées affichées. Les 46 valeurs sont **constantes** : PV
2548.095703125 / 2548.095703125, ressource 0 / 100, vivant. Il ne démontre donc
aucune variation réelle, ni durée ou stabilité entre lectures. Le gain est de
conserver ces observations et ruptures auparavant perdues par l'affichage du seul
dernier instant. Les variations et les limites d'affichage sont exercées séparément
sur des séries **SYNTHETIC**, dont 350 observations. Historique non authentifié,
aucun reçu/live/HUD.

## Sécurité et refus

Une seule lecture via le parseur borné existant (4 Mio, 64 Kio par ligne, 10 000 enregistrements) alimente les **deux moteurs historiques existants**. Les données non exportées par ces moteurs ne sont pas relues. Pas de chemin, pseudo, token ou identifiant de session brut dans le rapport ; toutes les valeurs HTML sont échappées. CSS embarqué, politique CSP restrictive, aucun script/image/audio/lien externe.

Les deux fichiers sont préparés dans un dossier temporaire frère, écrits et `fsync` avant publication atomique du dossier complet, **sans remplacement**, même si une autre invocation crée une sortie vide pendant la publication. Windows utilise le renommage sans remplacement ; Linux exige `renameat2(RENAME_NOREPLACE)`. Une plateforme ou un système de fichiers sans cette primitive est refusé, sans repli non atomique. L'atomicité de publication n'est pas une garantie de survie à une panne électrique ; un arrêt brutal peut laisser un dossier temporaire non publié. Ne pas prendre ce dossier pour un rapport terminé.

Code 0 : observation historique exportée (des familles peuvent être inconnues/refusées). Code 1 : historique refusé ou erreur de lecture/écriture. Un historique refusé produit quand même un rapport explicatif si la sortie est valide ; une erreur de publication ne produit pas de rapport final. Code 2 : arguments invalides. Une sortie existante, même vide, n'est jamais réutilisée ni effacée. Le journal reste inchangé.
