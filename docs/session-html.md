# Rapport de session HTML local

Depuis le checkout CervHots, sans lancer le jeu, le Coach ou un navigateur :

```bash
python -B -m cerveau.passive_session --report-html --journal C:/CervHots-private/session/events.jsonl --report-dir C:/CervHots-private/rapport-001
```

Les deux chemins doivent être absolus. Le dossier de sortie doit être **neuf**, hors du dossier du journal. Ouvrir ensuite **manuellement** `REPORT.html` avec le navigateur de son choix ; `report.json` contient la même projection minimisée pour inspection. Aucun service à arrêter, aucune référence visuelle ou identité privée à fournir. `--report-html` est exclusif de `--summarize`, `--diagnose`, `--status`, `--preflight` et `--live`. Les modes existants sont inchangés.

## Ce qui est lisible

- Dernière observation cohérente, carte et niveaux publics réellement exportés par `native_history` ; pas de reconstitution des autres données du cœur.
- Talents locaux seulement si sélection et preuves historiques valides : palier et **ordinal du choix natif**, jamais un libellé/catalogue inventé. Libellé inconnu reste inconnu.
- Objectif public seulement si déjà exporté et validé par le moteur historique ; inconnues affichées comme telles, jamais comme zéro. Les autres familles n'ont qu'un statut enregistré, pas de valeurs reconstruites.
- Distinction non sélectionné, inconnu, refusé/rejeté, non tenté et normalisé ; sélection absente/invalide laisse les familles inconnues.
- Comptages et codes fermés de refus du diagnostic existant, limités aux événements effectivement enregistrés ; journal incomplet : préfixe seulement, total de session inconnu. Refus/erreur ultérieur signalé sans rafraîchir la dernière observation.

**Historique NON authentifié**, jamais CURRENT, validation HUD, nouveau reçu ou conseil. Aucun âge actuel calculé. Âge du cœur non enregistré, pas zéro ; les âges/fenêtres optionnels sont les originaux. Ni disponibilité live, ni ownership, ni activité actuelle ne sont établis. `references_held=false` pour les exercices du lot17 : pas de nouvelle qualification native/HUD, pas de nouveau match requis.

## Sécurité et refus

Une seule lecture via le parseur borné existant (4 Mio, 64 Kio par ligne, 10 000 enregistrements) alimente les **deux moteurs historiques existants**. Les données non exportées par ces moteurs ne sont pas relues. Pas de chemin, pseudo, token ou identifiant de session brut dans le rapport ; toutes les valeurs HTML sont échappées. CSS embarqué, politique CSP restrictive, aucun script/image/audio/lien externe.

Les deux fichiers sont préparés dans un dossier temporaire frère, écrits et `fsync` avant publication atomique du dossier complet, **sans remplacement**, même si une autre invocation crée une sortie vide pendant la publication. Windows utilise le renommage sans remplacement ; Linux exige `renameat2(RENAME_NOREPLACE)`. Une plateforme ou un système de fichiers sans cette primitive est refusé, sans repli non atomique. L'atomicité de publication n'est pas une garantie de survie à une panne électrique ; un arrêt brutal peut laisser un dossier temporaire non publié. Ne pas prendre ce dossier pour un rapport terminé.

Code 0 : observation historique exportée (des familles peuvent être inconnues/refusées). Code 1 : historique refusé ou erreur de lecture/écriture. Un historique refusé produit quand même un rapport explicatif si la sortie est valide ; une erreur de publication ne produit pas de rapport final. Code 2 : arguments invalides. Une sortie existante, même vide, n'est jamais réutilisée ni effacée. Le journal reste inchangé.
