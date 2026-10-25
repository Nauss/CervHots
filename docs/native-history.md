# Relire les observations natives enregistrées (hors ligne)

Pour une lecture directe en navigateur, le nouveau mode explicite
[`--report-html`](session-html.md) produit un HTML autonome et un JSON minimisé
dans un dossier neuf, sans ouvrir automatiquement le navigateur. Il compose les
deux mêmes moteurs historiques sur une seule lecture bornée, sans acquisition.

## Une commande ponctuelle, pas un service

Depuis le checkout exact à examiner (MAIN **après** revue/intégration) :

```bash
cd C:/root/dev/AI/CervHots
python -B -m cerveau.passive_session --summarize --journal C:/CervHots-private/session/events.jsonl --report-dir C:/CervHots-private/historique-001
```

Python standard suffit, sans préflight live, Coach, API, réseau, audio, GUI ou
ouverture de processus. Aucun fichier d'identité n'est nécessaire. La commande se
termine après écriture : rien à arrêter/réarmer ; Ctrl+C peut l'interrompre. Ne pas
supprimer un ancien STOP, un claim, une source ou un rapport pour recommencer.
Choisir un **nouveau** `--report-dir` et conserver une sortie partielle éventuelle.

- `--journal` : chemin absolu explicite d'un journal conservé ; aucun scan,
  sélection automatique, replay ou enrichissement depuis les verdicts opérateur.
- `--report-dir` : chemin absolu inexistant, hors du dossier source et de ses
  descendants. Aucun écrasement, ni écriture dans le journal.
- `history.json` : projection JSON minimisée, également sur stdout.
- `SUMMARY.txt` : résumé français déterministe, également sur stderr.
- Codes : **0** = un instant historique cohérent a été résumé (des familles peuvent
  rester inconnues/refusées) ; **1** = journal/liaison/temps/paire d'acquisition/
  fermeture enregistrée refusés, ou IO refusée ; **2** = arguments invalides.
  Un code0 ne signifie jamais succès d'une nouvelle collecte ni validation HUD.

`--report-html`, `--summarize`, `--diagnose`, `--status`, `--preflight`, `--live` sont exclusifs.
Le résumé refuse les chemins live/statut et les références visuelles. Les options
journal/rapport hors des modes historiques sont refusées avant préflight.
Pour démarrer/arrêter une vraie collecte, voir [passive-quickstart.md](passive-quickstart.md) :
ce résumé n'est ni un contrôle d'activité OS, ni une autorisation de reprise.

## Ne pas confondre trois résultats

| Mode | Question traitée | Ne prouve pas |
|---|---|---|
| `--diagnose` | Pourquoi la collecte a-t-elle accepté/refusé, avec quelles présences/coûts ? | Valeurs joueur, HUD, activité actuelle |
| `--summarize` | Que contenait la **dernière observation enregistrée**, à son instant ? | CURRENT, justesse physique ou HUD, identité authentifiée |
| Recette/qualification indépendante | Que démontre la comparaison réelle précisément liée ? | Couverture d'une autre carte/famille/héros |

Le [diagnostic technique](session-diagnosis.md) reste inchangé dans son rôle.
Les anciennes commandes `cerveau.talents_journal`/`objective_journal` inspectent
les paquets JSON famille ; le débrief `cerveau.replay_debrief` projette un replay
avec perspective hypothétique. Aucun de ces chemins n'est rejoué pour fabriquer
les valeurs absentes d'un journal natif.

## Contenu et refus

Le parseur **réutilisé** du diagnostic impose ≤4MiB, ≤10000 lignes, ≤64KiB/ligne,
JSON sans doublons/non-finis, schéma1, séquences contiguës, cycles non décroissants
et unicité acquisition/observation/refus par cycle. Tout suffixe sans LF, même JSON
valide, refuse **toutes** les valeurs du résumé : aucun préfixe salvateur.

Le résumé exige en plus une seule frontière finale de fermeture reconnue, des
paires acquisition accepted→observation, et la cohérence de **toutes** les observations :
session/carte pseudonymisées, token, carte déjà reconnue DragonShire/Volskaya,
perspective native_player et bracket host-monotonic ; mission, elapsed, UTC aware
et brackets ordonnés. Identité absente/mêlée, régression temporelle ou clôture
manquante ⇒ valeurs nulles/refus, jamais association au plus proche. Les tokens,
aliases, noms/comptes/chat, chemins source, coordonnées et entrées brutes ne sortent
pas. Un hash est une intégrité de ces octets, **pas** leur authentification.

- Le dernier instant, sans remplir depuis un ancien succès : mission/UTC/elapsed,
  séquence/cycle et bracket host sont les **temps enregistrés**, pas un nouveau reçu.
  En complément, `core_timeline` conserve une chronologie bornée des observations
  locales et des ruptures : ordre ordinal du journal, aucune durée fabriquée,
  128 entrées maximum, comptage complet avant limitation d'affichage. Chaque
  observation exige sa propre liaison locale et ses propres valeurs ; un refus
  global même tardif retire toute la série. Voir le
  [contrat et les limites](session-html.md#chronologie-historique-bornée).
- Carte : identifiant reconnu déjà enregistré, jamais déchiffré depuis un alias.
- Niveaux publics : uniquement si dix slots distincts, cinq par équipe et cinq
  niveaux valides identiques dans chaque équipe. Une équipe absente/incohérente
  reste `null`, sans moyenne, maximum ou zéro de substitution. Le journal ne garde
  pas l'âge original du cœur : `original_age_s=null`, explicitement **inconnu**.
  Les indices0/1 ne sont pas des couleurs HUD ni une équipe alliée devinée.
- Cœur local : `local_core` projette santé/maximum, ressource/maximum et vivant/mort
  seulement avec liaison locale validée du même événement ; absent/invalide/inconnu/
  refusé restent distincts. Aucun alias ni âge réutilisé. La ressource générique ne
  prouve pas du mana. Contrat et exemple réel sans identité :
  [session-html.md](session-html.md#contrat-json-du-cœur-local).
- Talents **locaux seulement** : re-sélection par le validateur historique existant,
  build98348/scopes existants, roster/équipe/niveau cohérents, source native et
  âge/fenêtre originaux valides. Héros et niveaux qualifiés, paliers, statut et
  choix natif sont conservés ; pas de catalogue offert ni catalog_id. Les libellés
  français restent `null` : choix natif2 ≠ nom de talent inventé, ni touche HUD.
- Objectif : seulement la projection publique Dragon déjà livrée ; même sélecteur
  fermé, provenance et inconnus conservés. Volskaya/Braxis/autres valeurs ne sont
  pas ouvertes. Le cas positif objectif de la suite est **synthétique**, pas une
  nouvelle qualification réelle.
- Familles non sélectionnées selon acquisition/available_fields, absentes,
  refusées ou rejetées ne reçoivent aucune valeur. `families` décrit des statuts
  enregistrés (sauf rejet supplémentaire des deux exports), pas une certification
  de positions/cooldowns/visibilité/battlefield : **aucune valeur** de ces familles
  n'est exportée. Un statut normalized forgé sur disque ne devient pas permission.
  La sélection optionnelle doit être prouvée par `collection=all` ou `talents`
  dans l'acquisition correspondante. Si `collection` manque ou est invalide,
  toutes les familles optionnelles restent `unknown`, sans valeur ni âge exporté,
  avec `selection_metadata_unknown` ; ni `available_fields`, ni une liste
  `not_selected` déclarée ne remplacent cette preuve. Carte et niveaux publics
  peuvent rester lisibles si leurs propres contrôles passent ; le code0 ne
  certifie pas les familles manquantes.

Toujours : `basis=historical_not_current`, `authenticated=false`,
`hud_validated=false`, `current_permission=false`, `current_age_s=null`,
`closure.reader_active=null`. Même une clôture enregistrée ne prouve pas la vie OS.
Un refus ultérieur est signalé par `later_refusal_or_error`, sans avancer l'instant.
Aucun conseil tactique n'est généré. Aucune garde native/allowlist n'est modifiée.

## Exemple réellement exercé, sans nouvelle collecte

Les deux journaux explicitement autorisés lot1 et lot7 ont été lus immuables sous
Python3.12 et3.14 ; sorties neuves, hashes avant/après, appels réels de la CLI avec
réseau/lecteur/émission de reçu/Coach/audio interdits. Preuves détaillées dans
`out/weekend/2026-10-24/lot16/verification.json` et `HANDOFF.md`.

- **lot7** : SHA256 `db2b054b84ec8434e8b2f6974b5ec524158fbbba836a4c77e77b8273ff4a1440`.
  Dernière observation mission97.4375s, UTC2026-10-24T20:48:16.146000+00:00,
  séquence110 : DragonShire ; niveaux publics équipe0=1, équipe1=2 ; Sonya locale,
  niveau1, palier1 choix natif2, libellé inconnu. Âge talents original
  0.006387499975971878s, non renouvelé ; objectif non sélectionné. C'est un résultat
  joueur historique utile, **pas une nouvelle validation** de Sonya/carte/HUD.
- **lot1** : SHA256 `5f7537171743ca80ae7c3e11bcd7591e4ceed869c912064504e3425f3769daa8`.
  Le format ancien ne contient pas `comparison` (token/carte/perspective/bracket),
  ni provenance des familles : résumé refusé `identity_or_time_refused`, aucune
  valeur retenue. Le verdict externe ne répare pas cette absence.
- Adversaires en mémoire (octets jamais recopiés) : suffixe tronqué, première
  observation d'une autre session, binding manquant, perspective étrangère ⇒ code1,
  aucune valeur. Âge talents absent ou champ non sélectionné ⇒ talents rejetés/
  non sélectionnés sans effacer les autres inconnus, ni reprendre un ancien choix.

Régression ciblée : `python -B -m unittest discover -s tests -p test_native_history.py -v`.
Suites complètes **séquentielles** (elles testent un mutex Windows commun) :

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 uv run --offline --no-project --python 3.12 --with mpyq --with heroprotocol python -B -m unittest discover -s tests -q
PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 uv run --offline --no-project --python 3.14 --with mpyq --with heroprotocol python -B -m unittest discover -s tests -q
```

Le dossier ignoré `out/` doit exister pour quelques tests historiques. Les paquets
supplémentaires servent à ces tests de préflight existants, pas au résumé. Garder
les défauts d'environnement dans les logs, sans les appeler régressions produit.
Revue ROGER du commit gelé puis intégration DEFAULT distincte et tests/smoke depuis
MAIN restent obligatoires avant d'annoncer le produit livré.
