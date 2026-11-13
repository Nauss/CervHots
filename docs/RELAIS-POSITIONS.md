# Relais — positions prioritaires après le test live du 11 novembre 2026

## Demande du propriétaire

« Il faut absolument les positions… Pousse en l'état sur github, un autre agent va prendre le relais. »

Publier l'état actuel, sans prétendre avoir étendu la couverture des positions. La prochaine priorité est leur acquisition native utile au coach sur la carte effectivement jouée, puis une qualification reproductible. Aucun nouveau lecteur, match ou audio ne doit être démarré par la simple lecture de ce document.

## Ce qui a été exercé réellement

Chaîne produit : `cerveau.playtest` → `NativeSource` → `read_current` → normaliseur → KB/Coach via API centrale → Piper → Mumble distant.

- Lecture mémoire passive PvP et voix autorisées explicitement pour cet essai ; le propriétaire a déclenché l'activation vocale par bouton.
- Premier essai `--collection positions --coach-mode macro` : 6 lectures acceptées, 0 position disponible, 0 annonce. Le mode macro `outnumbered` est actuellement borné à Volskaya ; il renvoyait `faits_macro_inconnus` sur la carte courante. Arrêt coopératif vérifié avant toute continuation.
- Continuation par l'option existante `--coach-mode free`, sans modification des gardes : 59 lectures acceptées, 6 refusées, 39 passages du coach, 16 propositions vocales, 23 abstentions, 15 propositions périmées, 1 synthèse et 1 annonce envoyée dans Mumble.
- **Le propriétaire a confirmé avoir entendu l'annonce.** Cela valide une livraison audible pendant cet essai, pas la justesse tactique du conseil ni une couverture multi-cartes.
- Fin automatique : `reason=session_changed`, `reader_active=false`, code de sortie 0. Absence de processus `cerveau.playtest` vérifiée après sortie. Aucun redémarrage automatique.
- Suite complète avant publication : `tts/.venv/Scripts/python.exe -B -m unittest discover -s tests -v` : **1099 tests exécutés, OK, 5 ignorés**. Les fixtures SYNTHETIC restent des preuves distinctes de cette observation live.

## Blocage positions — ne pas le masquer

La sélection `positions` fonctionne bien avant acquisition : cœur + positions, sans tenter les autres familles facultatives. Mais l'acquisition de cette partie a explicitement renvoyé :

```json
{"positions": {"code": "recette_positions_absente", "category": "optional_unqualified"}}
```

Aucune coordonnée n'a été fournie au coach : `positions_available=0`. Le journal minimise le nom de carte ; ce relais ne déduit donc pas la carte exacte depuis son identifiant anonymisé. L'identifier à partir d'une référence autorisée avant toute recette spécifique.

Au moment de ce relais, le produit était limité aux **héros principaux alliés vivants, Volskaya, build 98348**. La recette joueur reste bornée à ce périmètre ; distinguer acquisition native, preuve de perspective et validation terrain par carte.

**Complément collecte :** les nouvelles observations passives conservent aussi
les coordonnées alliées normalisées et leur qualification, via l'export commun
`cerveau.positions_journal`, sans nécessiter un appel du Coach. Voir
[`positions-collection.md`](positions-collection.md).

**Acquisition multi-cartes depuis le relais :** le lecteur utilise désormais les
bornes de la simulation active pour les 19 identifiants sourcés du catalogue,
sans élargir `VALIDATED_MAPS`. Les nouvelles cartes portent `native_bounds_only`,
Volskaya `player_recipe`. Le bug de résolution de `Warhead Junction` avec espace
est corrigé. Cette ouverture ne prétend pas ajouter 18 recettes terrain ; les
preuves et refus historiques sont dans `etudes/rea/POSITIONS-MULTICARTES.md`.

### Fichiers à lire en premier

- `hotstate/positions.py` : `VALIDATED_MAPS`, profil, résolveur `AlliedPositions`, contrôles de génération, bornes et cohérence.
- `hotstate/profiles/98348-positions.json` : signatures et bornes structurelles ; bornes connues ≠ carte qualifiée.
- `etudes/rea/P2-POSITIONS.md` et `etudes/rea/P2-POSITIONS-RECETTE.md` : preuves et limites de la qualification existante.
- `hotstate/native.py`, `hotstate/live.py`, `hotstate/reader.py` : sélection des familles, acquisition et refus.
- `cerveau/state.py`, `cerveau/diagnostics.py` : projection normalisée et journal de couverture/coordonnées réellement proposées au coach.
- `cerveau/playtest.py`, `cerveau/macro.py`, `cerveau/runner.py` : parcours réel, périmètre macro, revalidation et âge des propositions.
- `tests/test_positions_collection.py`, `tests/test_playtest.py`, `tests/test_playtest_macro.py`, `tests/test_playtest_ui.py` : contrats et scénarios SYNTHETIC.
- `docs/playtest.md` : préflight, lancement manuel, STOP et lecture des traces.

## Deux autres points importants pour le relais

1. **Latence et fraîcheur :** 15 propositions sont devenues périmées. Le compteur ne prouve pas leur cause exacte. Examiner `coach_response.latency_s` et `freshness.changed_fields` avant de conclure. Le mode `free` conserve la clé tactique globale ; une dérive spatiale pendant le LLM peut invalider un conseil. Ne pas retirer les coordonnées de cette clé ni relever les seuils pour fabriquer davantage de voix.
2. **Destination vocale :** la configuration locale centrale visait localhost, alors que le client du propriétaire était connecté à un serveur distant. Le serveur et le salon courants ont été vérifiés via le pair TCP et l'arbre UI du client. Des surcharges non secrètes `MUMBLE_HOST`, `MUMBLE_PORT`, `MUMBLE_CHANNEL`, limitées au processus, ont servi à cet essai. Aucun serveur local démarré, secret copié ou `.env` modifié. Le panneau/lanceur ne reprend pas automatiquement ces surcharges.

## Traces locales, volontairement non publiées

Dans le checkout d'origine seulement, sous `out/playtest-live/` (ignoré par Git) :

- `2026-11-11-2232/session/summary.json` : essai macro fermé ;
- `2026-11-11-free/session/events.jsonl` et `summary.json` : essai général et livraison ;
- `active-session.json` : chemins exacts, ancien handle et état fermé ;
- mandats locaux et contrôle Mumble silencieux dans les parents de session.

Ces traces privées, identités, endpoints personnels, fichiers de contrôle et secrets ne font pas partie du push. Un autre clone ne les possède pas. Ce document ne vaut pas autorisation de lecture mémoire, de GUI ou de diffusion sonore pour un nouvel essai ; conserver les consentements et leur périmètre actuels, sans en faire une permission permanente.
