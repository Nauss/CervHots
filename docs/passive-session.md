# Collecte native passive — une partie par commande

Commande produit : `python -m cerveau.passive_session --help`.
Parcours court démarrer/vérifier/STOP/reprendre :
[passive-quickstart.md](passive-quickstart.md).
**Sans option, ou avec `--preflight`, le préflight reste local : aucune ouverture mémoire, découverte
processus, requête réseau, configuration Coach, API ou audio.** Le défaut CLI est
maintenant **core** : découverte des modules sans charger les backends, profils
JSON et données produit ; `mpyq`/`heroprotocol` sont optionnels pour core.
`--collection all` rétablit explicitement le parcours composé antérieur ;
`--collection talents` reste cœur + talents. Ces deux opt-in conservent leur
préflight historique (consommateurs/protocole/mpyq). Les API Python
`NativeSource(player)` et `preflight()` gardent leurs défauts historiques ;
la migration porte sur la CLI, pas sur les appels Python existants.
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
Le claim exclusif `passive-session.lock` est dans ce parent. Il est conservé
après toute sortie, propre ou non : comparer un chemin puis le supprimer ne
garantit pas l'ownership face à une substitution concurrente. Aucune expiration,
suppression ou réécriture automatique. Un parent revendiqué refuse une autre
sortie (code 1), sans identité ni backend. Après arrêt vérifié indépendamment
par l'opérateur, utiliser un parent neuf, une sortie et un STOP neufs ; ne jamais
retirer un claim ancien/tiers pour reprendre. Ce claim n'est pas un verrou global ;
la garde système ci-dessous protège les nouveaux `NativeSource`, même sous des
parents différents. Le statut historique et le claim conservé ne prouvent pas
la vie ou la mort du processus.

### Exclusion système des lecteurs coopérants (Windows)

`NativeSource` acquiert **avant la création de la probe et l'ouverture du backend**
le mutex kernel nommé `Global\CervHots.PassiveNativeReader.v1`, avec attente nulle.
Le nom ne dépend ni du parent, ni du checkout, ni du PID, ni de l'identité joueur.
Il est global à la machine Windows, à travers les sessions terminales. L'ACL Windows
par défaut du créateur reste inchangée : même utilisateur normalement admis,
autre utilisateur/élévation/session selon droits OS ; un accès refusé, un objet
incompatible, une plateforme non-Windows ou un résultat incertain **refusent**
l'ouverture. Aucun fallback fichier/PID, aucune permission élargie.

Le mutex appartient à un **thread OS** : ce runtime synchrone impose le thread
principal pour l'acquisition, et le même thread pour lire/fermer. Une garde locale
non réentrante empêche aussi deux sources dans un même processus (un mutex Windows
seul autoriserait la récursion). La propriété est relâchée **après** fermeture du
backend. Une erreur de fermeture du backend, y compris pendant son initialisation,
conserve la garde jusqu'à la sortie du processus ; `reader_active` reste inconnu
si la fermeture de la source n'est pas établie. Les erreurs API/cleanup incertaines
verrouillent également les nouvelles tentatives du processus.

À la mort du processus, Windows libère sa propriété automatiquement ; aucune
preuve disque n'est effacée. Si un handle externe maintient l'objet abandonné,
`WAIT_ABANDONED` est explicitement refusé : pas d'ouverture de backend ni de
reconstruction d'état. Le handle est libéré/fermé si l'OS le permet. Une invocation
ultérieure doit refaire tous les contrôles, jamais réutiliser les anciens reçus.
Ni l'acquisition, ni l'abandon, ni l'absence du mutex ne prouvent une partie active,
l'absence d'un ancien lecteur ou une permission CURRENT.

En contention : code retour 1, motif `native_reader_unavailable`, résumé avec
consigne `recovery`. Envoyer le **STOP ciblé du collecteur connu**, attendre son
retour au terminal et vérifier indépendamment son arrêt. Si le propriétaire ou sa
fin restent inconnus, suspendre la reprise ; ne pas tuer de processus ni supprimer
un claim. Après vérification, réserver parent/sortie/STOP neufs. `--status`,
`--diagnose`, `--preflight` et un STOP préexistant n'acquièrent pas cette garde.

**Limite impérative :** seuls les lecteurs qui implémentent ce protocole commun
s'excluent. Les anciens outils/anciennes versions, autres lecteurs directs et
processus hostiles n'en sont pas couverts. La garde n'est ni une preuve d'absence
de ceux-ci, ni une autorisation de les réarmer. L'opérateur reste responsable de
leur arrêt indépendant avant toute nouvelle collecte. Aucun claim historique,
ancien STOP, contexte ou capture n'est réutilisé ou modifié.

Références OS : [mutex et abandon](https://learn.microsoft.com/en-us/windows/win32/sync/mutex-objects),
[namespace Global](https://learn.microsoft.com/en-us/windows/win32/termserv/kernel-object-namespaces).

## Arrêt, limites et changement de partie

Publier le STOP exact enregistré par une **nouvelle** session :
`python -B -m cerveau.passive_session --request-stop --output-dir <session-absolue> --stop-file <STOP-absolu-exact>`.
Mode disque seul, sans préflight, identité, journal, garde native ou processus :
il lit seulement le `control.json` minimisé versionné (16KiB maximum, LF final,
schéma fermé `passive_stop_control_v1`, sortie et STOP absolus exacts).
Ce fichier est créé exclusivement, flush/fsync avant identité/backend au démarrage ;
une initialisation interrompue peut le laisser incomplet et donc refusé.
Les anciennes sessions sans ce lien sont refusées ; aucune preuve ancienne n'est
complétée. Le parent STOP doit déjà exister ; liens/reparse/jonctions, fichiers
non réguliers, chemins incohérents ou STOP dans la sortie/claim sont refusés.
La publication ne crée que le STOP, exclusivement, sans modifier un fichier
existant. JSON `published`/`already_present` n'atteste que le signal ; activité
inconnue, `reader_active=null`, `current_permission=false`, jamais ownership
authentifié ni preuve de fermeture. Code 0 signal seulement, 1 refus/IO incertaine
(signal éventuellement déjà créé), 2 arguments invalides. Options live même
explicites par défaut interdites ; aide par `--help` seul.
Voir les limites filesystem Windows/POSIX et la reprise dans le
[parcours court](passive-quickstart.md#4-stop-ciblé-puis-reprise-neuve).
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

Pour deux mots complets de quatre octets lus à **la même adresse de tick**,
`coherence.clock_transition` peut préciser le changement signé en unités fixes
(4096 unités/seconde), sans publier les valeurs :

- `forward_bounded` : les deux valeurs sont dans [0,21600s] et l'avance est
  strictement positive et au plus 1s ; **le snapshot reste refusé**.
- `forward_over_window` : valeurs valides, avance supérieure à 1s.
- `backward` : valeurs valides, recul.
- `out_of_range` : au moins une valeur hors plage. Un garde d'horloge peut déjà
  refuser avant le garde de cohérence et ne porte alors pas ce détail.

Les overlaps partiels, autres groupes ou mots égaux ne sont pas classifiés.
Absence du champ = inconnu, pas stabilité. Les racines restent vérifiées en
égalité complète ; aucun octet n'est masqué. Une avance bornée est compatible
avec une transition réelle mais **ne prouve ni atomicité, ni absence d'ABA, ni
cause des anciens refus**. Les copies du journal sont historiques uniquement.
Cette précision corrige un manque d'explicabilité, pas le taux de refus : une
mesure live distincte doit départager les hypothèses avant tout changement.
Les absences de qualification optionnelle attendues ne constituent pas une
répétition d'erreurs cœur ; les compter séparément dans le brief opérateur.

La commande de lancement ne change pas. Pour une nouvelle mesure autorisée,
utiliser un checkout gelé, une sortie et un STOP neufs selon la préparation
ci-dessus ; compter les détails par phase/groupe avec les coûts de la même
acquisition. Pas de retry interne, de lecture diagnostique supplémentaire,
d'augmentation des 12 défaillances, ni de renouvellement d'âge/reçu. Le coût
CPU de cette instrumentation reste dans WHOLE. STOP après lecture supprime aussi
ce détail avant persistance. Une nouvelle commande crée un suivi entièrement neuf.

## Coût des relectures finales du cœur

Le cœur regroupe ses rechecks **consécutifs et exactement adjacents**, du même
groupe sémantique, dans une requête physique bornée à65536octets. Aucun trou
n'est lu : les octets demandés sont les mêmes, dans le même ordre des champs.
Les horloges (tick et racines), le build et les scopes différents restent
séparés. Tous les conflits entre lectures initiales sont refusés **avant** ce
regroupement ; chaque tranche originale conserve sa comparaison complète et
son détail de refus (groupe/largeur d'origine, pas taille du regroupement).

Ce changement évite21appels de recheck sur la fixture cœur (257→236), sans
nouvel octet. Un test à coût physique déterministe exerce un dépassement WHOLE
avant optimisation puis une acquisition valide après, avec les mêmes125ms.
Ce n'est **pas** une mesure de latence Windows ou du taux de refus en partie.
Les trois avances `initial_overlap/clock_tick/forward_bounded` de la recette
précédente restent légitimement refusées : ce regroupement ne les corrige pas.

Une erreur OS ou une lecture groupée incomplète reste un échec coûté, sans
fallback ni nouvelle tentative. Le regroupement modifie l'instant des samples
finaux ; il ne prouve ni atomicité ni absence d'ABA. Les acquisitions optionnelles
ne sortent pas du bracket existant ; les budgets WHOLE, l'âge et l'instant
d'acquisition originaux des reçus, STOP et le recheck final de contexte restent
inchangés. La commande utilisateur reste `python -m cerveau.passive_session`
pour le préflight sans mémoire, puis le lancement explicite documenté plus haut.

Régression ciblée :
`python -B -m unittest discover -s tests -p test_core_read_batches.py -v`.

## Vérification et recette privée opérateur

### Cycle de vie en vrais processus, sans jeu (Windows)

Depuis le checkout, avec Python 3.12 ou 3.14 et les dépendances de test installées :

```bash
export TMPDIR='C:/Users/Nauss/AppData/Local/hermes/cache/scratch'
export TEMP="$TMPDIR" TMP="$TMPDIR" PYTHONDONTWRITEBYTECODE=1
python -B -m unittest discover -s tests -p test_passive_lifecycle_process.py -v
```

Le dossier scratch doit exister. Exécuter séquentiellement : les tests utilisent
le vrai mutex Windows partagé. `CERVHOTS_LIFECYCLE_EVIDENCE`, facultatif, désigne
un dossier de preuves neuf où conserver les journaux et identités PID/création
avant le nettoyage du seul scratch propre aux tests.

Cette recette ajoute aux tests en mémoire et aux tests de mutex isolés un
collecteur enfant passant par `main`, `NativeSource`, `run_session` et les vrais
consommateurs, avec transport **SYNTHETIC injecté uniquement dans les tests**.
Un autre processus invoque `--request-stop` via `session_control/control_io` ;
le test attend le retour terminal et atteste fermeture backend/source/garde.
La reprise utilise une invocation, un parent, un STOP, une probe, une identité
synthétique de partie et un token neufs. Les contrôles anciens/copiés ne peuvent
cibler le nouveau STOP ; le vieux STOP reste intact et une deuxième observation
confirme que le successeur continue. Un reçu étranger est refusé même avec un
âge de test forcé à zéro ; un reçu émis dans le nouveau processus reste admis.

Deux interruptions déterministes injectent `KeyboardInterrupt` avant publication
ou après écriture partielle du contrôle (ce n'est pas un Ctrl+C console réel).
Une erreur de fermeture injectée laisse l'activité inconnue et bloque un autre
collecteur jusqu'à la sortie du propriétaire. Les timeouts du banc de test et son
cleanup par handles exacts/PID/création ne sont pas une garantie de latence STOP
live. La sortie processus ne transforme pas un close incertain en close attesté ;
les fichiers de contrôle ne sont pas une authentification contre un écrivain
hostile. Aucune qualification live, coût physique, HUD, carte, Braxis ou nouvelle
permission CURRENT n'en découle ; aucune option synthétique produit n'est ajoutée.

### Suites et recette privée

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
   claim conservé ; ou fin/changement partie : arrêt clair sans ancien contexte.
5. Vérifier la fin du collecteur, puis nouvelle commande/parent/sortie/STOP pour
   le prochain match. Conserver les preuves privées
   minimisées et les coûts/refus. Une recette ratée reste une recette ratée.

La livraison candidate hors ligne n'est ni une recette live, ni une intégration
main, ni la fermeture des gates historiques Braxis/talents/cooldowns.
