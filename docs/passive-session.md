# Collecte native passive — une partie par commande

Commande produit : `python -m cerveau.passive_session --help`.
**Sans `--live`, le préflight reste local : aucune ouverture mémoire, découverte
processus, requête réseau, configuration Coach, API ou audio.** Il importe les
vrais consommateurs, vérifie les profils JSON, le protocole installé et mpyq.
Il ne qualifie ni le build du jeu actif, ni le cache de cartes, ni une recette.
Aucune KB SQLite ni `.env` Coach n'est nécessaire.

## Préparation et lancement

Depuis le checkout exact à tester (ne pas supposer un venv dans le worktree) :

```text
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --help
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session
```

Dépendances Python : `hotstate/requirements.txt` (heroprotocol et mpyq).
Le chemin d'interpréteur ci-dessus est un exemple de runtime installé, pas une
constante de l'outil. Python 3.12 et 3.14 sont couverts par les tests hors ligne.

L'opérateur autorisé, seul lecteur actif, fournit **trois chemins absolus** :

```text
python -B -m cerveau.passive_session --live --player-file <fichier-identite-prive-absolu> --output-dir <session-absolue-NEUVE> --stop-file <STOP-absolu> --max-seconds 300 --interval 5
```

Le nom du joueur n'est jamais un argument CLI, une variable globale ou une
sortie. `--player-file` est lu via `cerveau.player_identity` : UTF8/UTF8sig,
2–64 caractères, 261 octets au plus, un LF/CRLF terminal permis ; pas de contrôles,
retours intérieurs ou espaces extérieurs. Ce label **n'est pas une preuve active** :
NativeContextProbe et la garde de perspective doivent trouver un seul acteur
local réel. Pas d'identité synthétique, de remplacement de perspective ni de
fallback replay pour une recette live.

Le dossier de sortie doit être inexistant. Il n'est jamais repris ni nettoyé
par l'outil, même après une initialisation ratée. Le parent peut être créé.
Le verrou exclusif `passive-session.lock` est dans ce parent : toutes les
sessions d'une campagne doivent partager ce parent pour être mutuellement
exclusives. Cela ne verrouille pas les anciens outils ni des parents différents :
l'opérateur vérifie aussi l'absence de tout autre lecteur. Après un crash, ne
retirer un verrou qu'après vérification du processus ; jamais d'expiration forcée.

## Arrêt, limites et changement de partie

Créer le fichier STOP convenu (par exemple `New-Item -ItemType File <STOP>` en
PowerShell, ou `touch <STOP>` en bash). Ne pas le confondre avec le fichier
d'identité, events.jsonl, summary.json, status.json ou le verrou.
Le collecteur **ne supprime jamais STOP**, y compris au lancement. Un STOP déjà
présent termine avant lecture de l'identité, création de sortie ou ouverture du
backend. Une erreur de stat STOP refuse la continuation, même sous Python3.14.

La boucle vérifie STOP avant ouverture, avant acquisition, après acquisition,
avant émission des mesures/observations et toutes les 200ms au plus pendant
l'attente. Les mesures de read_current sont tamponnées en mémoire jusqu'au
contrôle après lecture : un STOP apparu pendant celle-ci supprime aussi leur
émission. Une lecture OS synchrone déjà engagée n'est pas interrompue ; pas de
promesse de délai dur si l'OS ou le disque bloque. Ctrl+C ferme également la source.
Les bornes de durée incluent ouverture/acquisitions/attentes de la boucle ; le
préflight et la lecture initiale du petit fichier privé sont en amont.

Durée 1–1800s, intervalle 1–300s (défaut 300s/5s). L'intervalle est un délai
**après** traitement, pas une cadence à rattraper ; aucune boucle de lecture
agressive. Le polling STOP ne lit pas la mémoire du jeu.

Avant le premier cœur accepté, `aucune_simulation_active` signifie attente au
menu, pas panne. Les refus natifs non-menu et les ouvertures processus absentes/
refusées consomment un budget **cumulatif de 12 défaillances** par commande.
Ni un menu ni un succès ne remettent ce compteur à zéro : la borne est réelle.
Les erreurs backend inattendues et IO arrêtent immédiatement, sans exporter leur
message. Les refus de familles optionnelles ne consomment pas ce budget cœur.

Après la première observation, changement de match, acteur/équipe/carte, retour
en arrière de l'horloge mission, retour menu ou certains refus de continuité
natif ⇒ `session_changed`, fermeture et arrêt. **Pas de reprise multi-match en
processus dans ce lot.** Une nouvelle partie exige une nouvelle commande et une
sortie neuve : nouveau backend, nouvelle probe, nouveau sel Journal et nouveaux
reçus in-processus. Aucune copie de readset, contexte, reçu ou âge ancien.

## Chaîne réelle et budgets

`NativeSource.read` appelle exactement :

`hotstate.live.read_current → cerveau.state.snapshot → cerveau.runner.tactical_key`

Un seul backend/probe est détenu par la session. Chaque tentative repasse par la
capture native courante, les rechecks et les vrais consommateurs dans la fenêtre
WHOLE **125ms / 8192 requêtes physiques / 1MiB**, sans assouplissement. Le build
strict reste celui des profils produit (98348 actuellement). Aucun scan de tas,
hook, injection, appel ou écriture client. Pas de Coach/API, voix, GUI, OCR,
sonde Braxis annexe ni ouverture de famille/carte supplémentaire.
Un coût de cache froid peut donc provoquer un refus de budget légitime.

## Sorties et minimisation

- `events.jsonl` : journal synchrone, séquence, cycle/tentative, temps monotone
  écoulé et timestamp UTC aware ; mesures d'acquisition et refus séparés des
  observations. Phases `open`/`read` sur les erreurs, étapes internes snapshot,
  context_recheck, normalize, key et coûts mesurés par read_current (ms, requêtes,
  octets). L'émission disque est **hors** mesure WHOLE. Les coûts peuvent dépasser
  125ms lorsqu'une tentative a justement été refusée. Une ouverture impossible
  n'a pas de coût mémoire inventé à zéro.
- `status.json` : dernier événement persisté, remplacement atomique local via
  `status.pending` ; initialisation avec PID du collecteur, puis dernière activité,
  puis résumé. Ce n'est pas une preuve que le processus est encore vivant.
- `summary.json` : arrêt propre de boucle avec accepted/refused/attempts/failures,
  motif, fin UTC, `reader_active=false` après fermeture. Si close échoue, ce champ
  vaut `null` (inconnu), jamais faux par défaut. En panne IO, un résumé peut manquer :
  une ancienne ligne status ou l'absence de résumé ne prouve pas un arrêt propre.

`attempts` compte aussi l'ouverture échouée et les acquisitions écartées par
STOP/limite/changement de partie ; ce n'est pas accepted+refused. `accepted`
compte uniquement les observations effectivement émises par cette boucle, pas
une comparaison HUD ni la qualification d'une famille. Un coût d'acquisition
accepté peut précéder une frontière de session sans observation correspondante.

Le `Journal` existant garde des alias HMAC aléatoires propres au processus pour
carte/session/héros, horloges mission/gameplay distinctes, slots0–9, équipe,
vie/niveau et vitaux alliés bornés. Aucun pseudo, compte, match_id brut, pointeur,
trace mémoire, reçu brut, contenu de clé tactique, coordonnées cachées ou autre
champ arbitraire ne sort. Les ennemis n'ont pas leurs PV/ressources exportés.
L'observer est reconstruit sur une liste fermée ; code non reconnu ⇒
`unknown_refusal/unknown`. Les familles optionnelles connues sont séparées,
les familles absentes restent inconnues, **pas zéro**. Aucune prétention à
reconstruire un replay ou une recette sémantique complète à partir de ce journal.

Code retour : 0 pour STOP, limite de durée et changement de partie ; 1 pour
échec préflight/initialisation/IO/backend, budget de défaillances ou fermeture ;
130 pour interruption clavier ; 2 pour arguments refusés. Toujours lire le
motif du résumé : 0 ne veut pas dire qu'une observation a été acceptée.

## Objectif Dragon : complément de collecte

Les observations conservent désormais la qualification de l'objectif et les
valeurs publiques Dragon déjà normalisées, avec temps source/âge du reçu initial,
refus explicites et rejeu historique borné. Voir
[objective-collection.md](objective-collection.md) pour le schéma, les limites
Volskaya et `python -m cerveau.objective_journal --journal <events.jsonl>`.
Ce complément ne change ni les allowlists, ni le budget WHOLE, ni les permissions
CURRENT ; aucune preuve native/live nouvelle n'est revendiquée par le code.

## Comprendre un refus de cohérence du cœur

`lecture_native_dechiree` conserve exactement son refus. Son événement
`acquisition` peut désormais contenir un objet fermé `coherence` :

```json
{"phase":"initial_overlap","field":"clock_tick","width":4}
```

- `initial_overlap` : deux lectures sources déjà effectuées se contredisent,
  même si leurs intervalles ne se recouvrent que partiellement.
- `final_equality` : une relecture physique finale diffère de sa source.
- `field` : groupe du premier consommateur de cet intervalle exact parmi
  `build`, `identity`, `clock_roots`, `clock_tick`, `roster`, `life`, `level`,
  `respawn`, `vitals`, `generation`, `core_state`, `unclassified`.
- `width` : taille de la lecture comparée (1–65536 octets), pas nombre d'octets
  différents. Seul le premier conflit est décrit, pas une liste exhaustive.

Aucune adresse, valeur avant/après, identité ni reçu n'est exporté. Un détail
absent reste inconnu (anciens journaux, autre refus ou donnée invalide), jamais
un tick supposé. Un tick divergent n'est pas accepté : ce diagnostic permet
justement de distinguer l'horloge des racines ou des vitaux **avant** de changer
une politique. Il n'explique pas rétrospectivement un ancien refus sans trace.
Les enrichissements optionnels gardent leurs propres acquisitions/refus.

La commande de lancement ne change pas. Pour une nouvelle mesure autorisée,
utiliser un checkout gelé, une sortie et un STOP neufs selon la préparation
ci-dessus ; compter les détails par phase/groupe avec les coûts de la même
acquisition. Pas de retry interne, de lecture diagnostique supplémentaire,
d'augmentation des 12 défaillances, ni de renouvellement d'âge/reçu. Le coût
CPU de cette instrumentation reste dans WHOLE. STOP après lecture supprime aussi
ce détail avant persistance. Une nouvelle commande crée un suivi entièrement neuf.

## Vérification et recette privée opérateur

Tests synthétiques : `python -B -m unittest discover -s tests -p test_passive_session.py -v`.
Ils ne sont **jamais** une validation live. Pour la suite complète, créer le dossier
ignoré `out/` dans le checkout (précondition des tests historiques de discovery),
puis `python -B -m unittest discover -s tests -q`.

Recette privée attendue sur la révision gelée du handoff ready-live :
1. Préflight réel et --help ; vérifier l'absence d'autre lecteur, sortie neuve.
2. STOP préexistant : aucune identité lue ni mémoire ouverte, aucun output créé.
3. Session au menu : refus menu mesuré sans épuiser failures, puis entrée dans
   une partie privée autorisée ; obtenir un cœur et comparer champs/références
   HUD exactes selon scénario opérateur, sans prétendre qualifier Braxis.
4. STOP pendant attente/lecture : aucune observation ultérieure, backend fermé,
   verrou libéré ; ou fin/changement partie : arrêt clair sans ancien contexte.
5. Nouvelle commande/sortie pour le prochain match. Conserver les preuves privées
   minimisées et les coûts/refus. Une recette ratée reste une recette ratée.

La livraison candidate hors ligne n'est ni une recette live, ni une intégration
main, ni la fermeture des gates historiques Braxis/talents/cooldowns.
