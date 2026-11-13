# Réactivité du Coach — correction et preuves

## Périmètre

Le playtest et son panneau sélectionnent maintenant `reactive`. Les anciens
modes explicites `macro` et `free`, la CLI historique et la collecte passive
restent disponibles sans changement implicite de parcours.

La correction ne promet pas de sauver les quinze phrases masquées de la session
du 11 novembre : leur texte n'est pas conservé. Elle corrige une voie utile avec
un contrat vérifiable, sans rendre arbitrairement valides des phrases libres.

## Modifications

- **Intention contrôlée avant KB/API.** L'alerte `outnumbered` utilise dix états
  de vie natifs connus, cinq héros par équipe, la perspective locale, le build et
  une carte du catalogue. Le code produit la phrase déjà utilisée par le mode
  macro. Aucun prompt ni requête n'est nécessaire à cette alerte.
- **Revalidation ciblée.** Identité/carte/composition et vecteur exact de vie
  doivent rester identiques, horloge mission non décroissante, précondition
  toujours vraie et âge du conseil au plus 20 s. Les variations de PV, ressource,
  niveau, countdown et coordonnées ne modifient pas la vérité de cette phrase
  non spatiale. Leurs contrôles natifs ne sont pas supprimés.
- **Texte libre inchangé sur le fond.** En dehors de l'alerte, le modèle configuré
  peut proposer une autre phrase. Celle-ci conserve la clé tactique exacte,
  positions comprises. Un champ JSON `intent` fourni par le modèle n'est jamais
  copié vers le contrat contrôlé de `Decision`.
- **Anti-répétition.** Une alerte livrée par épisode ; seule une observation
  complète revenue à l'équilibre réarme. Une proposition non livrée n'est pas
  mémorisée, un état inconnu ne réarme pas. Cooldown inchangé.
- **Cadence début-à-début.** L'attente API n'est plus suivie d'un intervalle
  complet supplémentaire. Pas de requêtes concurrentes ni de file de rattrapage.
- **Budget API restant.** Le timeout ne dépasse ni le réglage du Coach, ni ce qui
  reste des 20 s après préparation/journal, ni la durée restante de session.
  La valeur configurée est restaurée après l'appel, y compris sur erreur.
- **Traces.** `fact_decision`/`fact_decisions` sont séparés des tentatives du
  Coach ; `intent_revalidation` explicite le verdict ciblé. `stage_timing` mesure
  KB, synthèse et livraison terminée. `erreur_api_0` n'est plus masquée sous
  `unknown_decision`. Aucune clé, URL privée ou réponse brute n'est ajoutée.

Le mode historique `macro` reste limité à Volskaya. La voie réactive non spatiale
accepte le catalogue de 19 cartes ; cela ne qualifie ni positions, ni HUD, ni
nouvelles familles. `PLAYER_RECIPE_MAPS` reste `('Volskaya',)`.

## Vérifications réalisées le 13 novembre 2026

- Suite complète : **1 143 tests, OK, 5 ignorés**.
- Contrôles Ruff `E9,F63,F7,F82` et `git diff --check` : OK.
- Préflight réel : `ready=true`, `coach_mode=reactive`, `memory_opened=false`,
  `chat_called=false`, `audio_enabled=false`.
- Tests de la vraie CLI et du vrai `NativeSource` sur mémoire SYNTHETIC, avec
  Piper et Mumble remplacés : alerte et mouvement acceptés sans aucun HTTP ;
  refus de positions optionnelles transparent ; changement de vie/identité,
  refus du cœur et STOP de dernière minute bloquent l'envoi.
- Catalogue entier, faux `intent` du modèle, retour d'allié, changement de carte,
  horloge régressive, composition incomplète, anti-répétition et repli libre
  spatial strict couverts hors ligne.
- Horloge simulée : appels de 8 s démarrant à **0, 15, 30 s**, et non 0, 23 s.
  Appels dépassant l'intervalle : pas de rafale de rattrapage. Timeout après
  4 s de préparation et 3 s de journal : **13 s**, sans relever un réglage plus bas.

### Mesure CPU de la voie contrôlée

500 décisions + revalidations sur fixture SYNTHETIC : médiane **0,0438 ms**, zéro
appel HTTP. Un cycle complet avec lecture factice, mouvement et variations de
PV/niveau a accepté la livraison factice. C'est une mesure locale du code,
**pas** un temps de réaction audible, un coût d'acquisition ou une recette live.
Preuve locale ignorée par Git : `out/performance/reactive-fix/benchmark.json`.

### Comparaison réelle de la passerelle, entrées synthétiques

Six appels alternés au modèle de la configuration centrale, sans modification
persistante, même état fictif et même KB ; trois par réglage :

| Réglage demandé | Médiane | Minimum | Maximum |
|---|---:|---:|---:|
| Actuel, effort non imposé | 7,48 s | 7,08 s | 13,80 s |
| `reasoning_effort=low` | 9,19 s | 7,07 s | 9,99 s |

Aucune erreur API ni réponse invalide. Les six réponses ont été refusées pour
confiance insuffisante : aucune voix n'était possible dans ce benchmark. Trois
mesures par réglage ne constituent pas une comparaison statistique robuste et
ne prouvent pas comment la passerelle interprète l'effort. **Pas de gain
convaincant justifiant de forcer `low` : configuration conservée.** Le gain
certain est la suppression du besoin de requête pour l'intention contrôlée,
pas une accélération prétendue de tous les textes libres.
Preuve locale : `out/performance/reactive-fix/provider-benchmark.json` ; ni
endpoint, token, texte retourné ni donnée réelle de partie dans ce rapport.

## Limites restantes

Aucune nouvelle partie ni diffusion sonore n'a été lancée. La première synthèse
Piper et la connexion Mumble peuvent encore coûter plusieurs secondes. Le modèle
reste nécessaire au texte libre, qui reste strictement revalidé et peut encore
être annulé. Une nouvelle recette manuelle est nécessaire pour mesurer le taux
de livraison audible et l'utilité tactique en conditions réelles.

Commandes de tests : voir `docs/playtest.md`, `tests/test_reactive_coach.py`,
`tests/test_coach_timing.py` et les scénarios réactifs de `tests/test_playtest.py`.
