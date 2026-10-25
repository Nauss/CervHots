# Démarrer, vérifier, arrêter, reprendre — collecte passive

Ce parcours utilise **uniquement** `cerveau.passive_session`, sans Coach, API,
audio ou lancement/fermeture du jeu. À utiliser depuis MAIN **après intégration
revue** du correctif opérations. Pour vérifier un candidat isolé, remplacer le
`cd` par le chemin absolu de son checkout exact ; ne pas supposer que le venv
est installé dans un worktree.

## 1. Préflight sans jeu

```bash
cd C:/root/dev/AI/CervHots
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --help
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --preflight
```

Aucun argument équivaut aussi au préflight. Sortie réelle (candidat, sans jeu) :

```json
{"event":"preflight","ready":true,"memory_opened":false,"chat_called":false,"audio_enabled":false,"profiles_checked":18,"single_match":true,"objective_collection":{"value_families":["dragon"],"qualification_only_maps":["Volskaya"],"age_basis":"original_receipt_at_normalization","historical_replay_grants_permission":false}}
```

`ready` valide les dépendances locales, **pas** une partie, un build actif ou une
permission current. Dépendances : `hotstate/requirements.txt`.

## 2. Démarrer une seule session autorisée

Exemple de chemins absolus à réserver avant usage : `C:/CervHots-private/player.txt`
est un fichier privé préparé par le propriétaire, **pas** une identité exemple à
inventer. Ces commandes live ne font pas partie du smoke SYNTHETIC ci-dessous.
Ne lancer qu'un lecteur. Réserver un parent neuf par invocation : le claim parent
reste conservé même après arrêt propre (aucune suppression sûre par chemin).
`run-001/session` doit être inexistant et `run-001.STOP` neuf et réservé à elle.

```bash
cd C:/root/dev/AI/CervHots
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --live --player-file C:/CervHots-private/player.txt --output-dir C:/root/dev/AI/CervHots/out/passive-operations/run-001/session --stop-file C:/root/dev/AI/CervHots/out/passive-operations/run-001.STOP --max-seconds 300 --interval 5
```

- **Préflight** : dépendances seulement, aucun processus de jeu recherché/ouvert.
- **Attente privée** : après `--live`, source autorisée ouverte ; avant premier
  cœur accepté, refus menu `aucune_simulation_active` sans panne. Ce n'est pas
  l'assurance qu'une partie privée est active ; son autorisation reste préalable.
- **Acquisition** : tentative native réellement coûtée, gardes build/perspective/
  fraîcheur et WHOLE 125ms/8192 lectures/1MiB inchangées. Refus ≠ valeur zéro.
- **Arrêt** : STOP, borne ou changement de partie ferme la source du collecteur.
  Un échec de fermeture reste inconnu. Aucun jeu/processus du propriétaire tué.

## 3. Vérifier depuis un autre terminal, sans backend

```bash
cd C:/root/dev/AI/CervHots
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --status --output-dir C:/root/dev/AI/CervHots/out/passive-operations/run-001/session
```

Diagnostic minimisé, lecture bornée de `status.json`/`summary.json` uniquement
(64KiB maximum chacun), simple stat du verrou parent. Pas d'identité privée lue,
ni réseau, ni préflight, ni sonde processus. `reader_active=null` **toujours** :
aucune preuve de vie/ownership n'est fabriquée depuis un ancien PID ou timestamp.
Un lecteur mort sans résumé, un verrou périmé ou un propriétaire inconnu restent
`unknown` ; aucun claim/verrou tiers n'est supprimé. Une absence vaut `absent`.

Sorties réelles du smoke **SYNTHETIC**, sans backend (JSON compacté seulement) :

```json
{"event":"session_status","state":"recorded_stopped","reason":"stop_file","reader_active":null,"recorded_reader_active":false,"current_permission":false,"basis":"historical_disk_only","parent_lock":"present_owner_unverified","last_event":"summary"}
{"event":"session_status","state":"unknown","reason":"ownership_unverified","reader_active":null,"recorded_reader_active":null,"current_permission":false,"basis":"historical_disk_only","parent_lock":"present_owner_unverified","last_event":"acquisition"}
```

`recorded_stopped` signifie **fermeture enregistrée historiquement**, pas succès
métier, permission current, ni absence d'un autre lecteur. Le verrou parent est
indépendant : même une ancienne session terminée ne prouve pas son propriétaire.
Sans résumé valide, ne jamais interpréter l'absence de verrou comme « arrêté ».

## 4. STOP ciblé puis reprise neuve

Le statut ci-dessus ne compte pas les acquisitions. Pour examiner le journal
historique explicite après collecte, sans backend ni dépendances live :

```bash
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --diagnose --journal C:/root/dev/AI/CervHots/out/passive-operations/run-001/session/events.jsonl --report-dir C:/root/dev/AI/CervHots/out/passive-diagnostic-001
```

Sortie **neuve**, JSON + résumé lisible, refus dédupliqués par cycle, inconnues et
absence de preuve HUD explicites : [session-diagnosis.md](session-diagnosis.md).
Ce diagnostic historique ne prouve pas la fin du processus et n'autorise pas la reprise.

Dans le second terminal bash, seulement pour la session identifiée ci-dessus :

```bash
touch C:/root/dev/AI/CervHots/out/passive-operations/run-001.STOP
```

Relire son `--status` et la sortie du premier terminal. Le signal seul ne prouve
pas sa prise en compte ; pas de délai dur si lecture OS/disque bloquée. STOP est
vérifié avant ouverture, après lecture et pendant l'attente (200ms au plus).
Ne toucher aucun autre STOP, claim ou processus ; ne pas utiliser `kill`.
Ne pas supprimer les fichiers d'une ancienne session ni forcer un verrou périmé.

Avant toute reprise, vérifier indépendamment que l'ancien collecteur a terminé
(retour du terminal propriétaire, pas seulement statut historique). Si sa fin
reste inconnue, ne pas lancer un deuxième lecteur. Les nouveaux `NativeSource`
s'excluent par mutex kernel Windows `Global\CervHots.PassiveNativeReader.v1`, même
sous parents distincts (acquisition avant probe/backend, libération après fermeture).
En refus `native_reader_unavailable` (code 1), envoyer le STOP ciblé du collecteur
connu et attendre son retour terminal ; ne jamais forcer. L'abandon après crash,
le mutex ou le claim ne donnent aucune permission CURRENT. **Les anciens lecteurs
sans ce protocole ne sont pas couverts : ne pas les réarmer, vérifier leur arrêt
indépendamment.** Préflight/status/diagnose n'acquièrent pas de garde native.
Portée Global intersessions, ACL et refus fail-closed : [détails](passive-session.md#exclusion-système-des-lecteurs-coopérants-windows).
Ne jamais supprimer/renommer/réécrire un ancien claim pour débloquer une reprise.

Pour la partie suivante, nouvelle commande, **parent neuf**, sortie et STOP neufs :

```bash
cd C:/root/dev/AI/CervHots
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --live --player-file C:/CervHots-private/player.txt --output-dir C:/root/dev/AI/CervHots/out/passive-operations/run-002/session --stop-file C:/root/dev/AI/CervHots/out/passive-operations/run-002.STOP --max-seconds 300 --interval 5
```

Ne pas relancer `run-001/session` : un STOP existant est respecté avant toute création
ou lecture d'identité (code 0), jamais consommé/réarmé. Une sortie existante sans
STOP refuse (code 1), comme toute nouvelle sortie sous un parent déjà revendiqué.
Nouvelle invocation = nouveau backend/probe, contexte,
identifiant de comparaison et sel ; aucun reçu/âge ou binding n'est repris.

## Codes de sortie

| Mode | 0 | 1 | 2 | 130 |
|---|---|---|---|---|
| préflight | dépendances prêtes | dépendance/IO refusée | arguments invalides | — |
| `--status` | fermeture historique enregistrée | absent/inconnu/IO ou résumé invalide | arguments invalides | — |
| `--live` | STOP, limite durée ou changement de partie | init/IO, erreurs, plafond défaillances, fermeture échouée | arguments invalides | Ctrl+C |

`--live`, `--status`, `--diagnose`, `--preflight` sont mutuellement exclusifs ; `--status`
exige un `--output-dir` absolu. Le code 0 de statut n'est **pas** une permission
ni un contrôle de santé current. Détails du journal : [passive-session.md](passive-session.md).
Aucun smoke synthétique ne qualifie une nouvelle carte, famille ou valeur native.
