# Braxis : diagnostic natif causal borné

**Cette commande mesure des métadonnées/racines natives, pas l’état de l’objectif.**
Elle ne produit aucun paquet normalisé, aucune acquisition scellée, aucun conseil,
aucun appel API/audio/GUI. `objective=null`, `coach=false`, perspective non validée.
Inconnu n’est jamais zéro. Aucun accès en écriture au jeu ni recherche de tas.

## Démarrer hors ligne

Depuis la racine du dépôt/worktree contenant ce lot :

```bash
python -B -m hotstate.braxis_diagnostic --help
python -B -m hotstate.braxis_diagnostic --preflight
python -B -m hotstate.braxis_diagnostic --preflight --player-file C:/chemin/prive/identite.txt
python -B -m hotstate.braxis_diagnostic --replay C:/chemin/prive/readsets.jsonl
```

Imports/help/préflight/rejeu n’instancient **jamais** `ProcessBackend`.
Le préflight hache les sources/profils locaux et vérifie le format du fichier
identité explicitement fourni, sans en afficher ni contenu ni empreinte.
`map_cache_dependency_available=false` signifie que cet interpréteur ne dispose
pas de `mpyq` : ce n’est pas un préflight live réussi. Installer les dépendances de
`hotstate/requirements.txt` dans l’environnement choisi, ou réutiliser l’environnement
existant approuvé. L’import et la présence de cette dépendance ne prouvent pas le
build actuellement exécuté : les six signatures de code et la taille du module
sont vérifiées de nouveau dans **chaque** diagnostic natif.

Le rejeu accepte les transactions historiques `compiler`/`type` et les lignes
`braxis-causal-v1` produites par cette commande. Il valide exactement, dans l’ordre,
les lectures des canaux compilateur/type et des trois slots de fonctions : surplus,
manque, autre requête ou autre résultat sont refusés. Les canaux absents ne sont
pas reconstruits. Les limites temporelles/erreurs transport ne sont pas rejouées
comme des observations ; leurs slices sont `not_replayed`. Ni le contexte, ni le
build, ni l’horloge ne sont requalifiés par ce rejeu de métadonnées. Une ligne de
résultat JSON par ligne source, 60 lignes maximum, 4 MiB maximum par ligne.
Le vieux canal combiné `frames` n’est pas converti en trois transactions nouvelles.

## Recette live : opérateur DEFAULT, carte distincte uniquement

Aucune partie n’est lancée par l’outil. Un seul lecteur doit être actif sur le PC :
l’opérateur vérifie ce verrou de rôle avant lancement ; l’exclusivité du répertoire
protège une session, **pas** tous les autres outils de lecture. Ne pas lancer le
collecteur lot1 en même temps. Revue hors ligne, recette privée et intégration main
restent trois gates distincts. Utiliser le commit et les hashes du handoff gelé.

Exemple à adapter seulement dans la carte opérateur, avec un **nouveau** répertoire
et des STOP nouveaux/inexistants (ne jamais effacer un ancien STOP) :

```bash
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m hotstate.braxis_diagnostic \
  --live --operator-private-game \
  --player-file C:/chemin/prive/identite.txt \
  --out C:/chemin/prive/nouvelle-session \
  --stop C:/chemin/prive/STOP-session \
  --stop C:/root/dev/AI/CervHots/out/weekend/2026-10-24/STOP \
  --seconds 90 --interval 3 --max-attempts 30
```

Le fichier identité UTF8/UTF8-BOM est absolu, régulier et borné à 261 octets ;
jamais de pseudo en argv. Il ne constitue pas une preuve d’identité active.
Le nom réel reste en mémoire du résolveur natif existant. Les refus publics ont
un vocabulaire fermé ; les exceptions libres ne sortent pas sur stdout.

Créer n’importe lequel des STOP indiqués, ou `STOP` dans le répertoire de session,
arrête coopérativement. STOP est vérifié avant ouverture, avant/après collecte,
après chaque flush et au plus toutes les 50 ms pendant l’intervalle. Ctrl-C ferme
la source et écrit le résumé. Une lecture OS/écriture disque synchrone déjà engagée
ne peut pas être préemptée : aucune promesse de deadline dure pour un OS bloqué.
Les octets d’une collecte finissant après STOP/deadline sont jetés, mais ses coûts
restent comptés ; une écriture privée déjà engagée n’est pas rétroactivement effacée
si STOP arrive pendant son flush, et aucune ligne publique n’est alors ajoutée.

Chaque acquisition partage **WHOLE 125 ms / 8192 lectures / 1 MiB demandé**, build,
contexte, relectures et horloges inclus. Pas de cache de lectures ni déduplication.
Les short reads et erreurs OS tentées coûtent aussi. Les maxima CLI sont 120 s,
60 tentatives, intervalle 1–10 s ; borne cumulée de charge utile : 60 MiB demandés
(30 MiB pour la recette ci-dessus), pas un dump de mémoire brute. Une faute build
ou mauvaise carte identifiée arrête ; changement/perte de l’identité déjà liée
arrête sans publier la tentative concernée. Aucune reprise dans une autre partie :
relancer uniquement avec un nouveau contexte, répertoire, autorisation et STOP.

## Sorties et interprétation honnête

- `PRIVATE/readsets.jsonl` : **preuve privée** exacte, coordonnées ASLR, structures,
  horloges historiques/runtime et octets de contexte susceptibles de contenir les
  noms. Ne jamais joindre/exporter ce fichier. Dossier local privé ; le mode 0700
  n’installe pas d’ACL Windows, conserver l’ACL privée de son parent.
- `attempts.jsonl` : résumé minimisé par tentative persistée, sans noms, pointeurs,
  structures, identité ni valeurs tactiques ; coûts et statuts par canal.
- `summary.json` : UTC début/fin, durée, tentatives, coûts cumulés, motif d’arrêt,
  `persisted` (lignes privées), `public_persisted` (lignes publiques), `discarded`.
  Les coûts cumulés incluent les tentatives jetées ; pas de faux compteur Full.

Ordre : signatures build → horloge avant → contexte natif → compilateur → type
nommé → **6003, 6007, 6122 indépendamment** → recontrôle du contexte → horloge après.
Le type/compilateur ne conditionne aucun slot. Un mauvais premier slot ne masque
plus les deux suivants. Les slots contrôlent nom exact, table, pointeur et record
avant/après, mais ne prouvent ni exécution de la fonction ni objet actif.

- `observed` : décodeur de métadonnées terminé dans sa borne, pas objectif validé.
- `refused` : motif réellement mesuré ; `requests` peut être nul pour un refus
  local (identité privée manquante, capture non atomique).
- `not_attempted` : build/budget a court-circuité le canal ; ce n’est pas absent.
- `not_recorded` au rejeu : octets inexistants dans le corpus, pas un refus live.
- `scoped_absences` : racine compilateur nulle, table globale/fonctions ou slot nul, recherche
  nommée infructueuse **dans ce seul périmètre/instant**. Jamais absence globale,
  couverture temporelle de toute compilation ou preuve de non-existence.

La carte cible n’est `holdout_recorded` qu’avec contexte natif exact
`BraxisHoldout`, contexte recontrôlé après les canaux et intervalle mission borné.
`BraxisOutpost` n’est pas Holdout. Une capture roulante ne peut pas fournir ce
contexte frais ; ses horloges décodées restent historiques. Même sur Holdout, cette
sonde ne valide pas la perspective humaine active et ne livre rien au Coach.

## Question causale et règle de sortie

1. Dans une acquisition dont contexte/horloges/coûts sont enregistrés, les slots
   exactement nommés sont-ils publiés malgré type absent/racine compilateur nulle ?
   Comparer les canaux réellement tentés, pas les polls d’une ancienne sonde.
2. Si une publication est présente, est-elle stable aux recontrôles, avec type et
   extent réellement décrits ? Préserver le readset ciblé pour rattacher ensuite
   la VM/partie et l’allocation ; ne pas déduire un objet actif du seul offset.

Deux expériences **causalement nouvelles** refusées : checkpoint opérateur puis
voie native alternative/autres familles qualifiées, pas une boucle sur le même
refus SCHO ni un nouveau match pour des outils manquants. Deux snapshots identiques
ne sont pas deux expériences nouvelles. Le handoff recette spécifie les scénarios.

B1 (global→agrégat→membre/type/extent exacts), B2 (membership VM/partie/perspective et
reset) et B3 (allocation/capacité/génération/lifetime/writers) restent **unproven**.
La sonde s’arrête aux métadonnées autorisées : aucune nouvelle allowlist, adresse
active historique recyclée ou producer de valeur inventé.

## Provenance et indépendance du lot1

`profiles/98348-braxis.json` cite le candidat offline-v2 approuvé SHA256
`a6e39a424ebd829bbebf324d48fd38056faa6359358dc20491cd3c8542cdd902` et les sources
legacy gelées. Les fonctions pures `hash_name`, `descriptor`, `named_type`,
`compiler_global` ont été extraites sans changer leur AST. Aucun chemin absolu vers
un gel, chargement dynamique, sys.path global ni lanceur legacy dans le produit.
Les nouveaux slots indépendants, recontrôles, comptabilité, CLI, persistance et
rejeu sont propres à ce lot. Aucun fichier lot1 modifié/cherry-pické ; import direct
uniquement des modules déjà dans bbf551e. L’intégration séquentielle avec le lot1
reste à tester sur main après revue, sans lancer simultanément leurs lecteurs.

## Expérience lot3 : racines runtime et alternative native

La publication nommée sur Holdout est déjà démontrée par la recette lot2 : ce
nouveau mode **ne relit ni le compilateur ni le type ni les slots 6003/6007/6122**.
L'audit des 30 readsets lot2 ne trouve aucun des quatre nouveaux points d'entrée.
Ce manque de couverture ne permet pas de conclure que ces racines sont nulles.
Le mode par défaut `--experiment publication` reste compatible avec le lot2.

```bash
python -B -m hotstate.braxis_diagnostic --preflight --experiment runtime-roots
python -B -m hotstate.braxis_diagnostic --replay C:/chemin/prive/readsets.jsonl
```

Recette nouvelle **uniquement par opérateur DEFAULT**, depuis le cwd absolu du
candidat gelé indiqué dans `ready-live.json` (pas depuis un autre main/worktree) :

```bash
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m hotstate.braxis_diagnostic \
  --live --experiment runtime-roots --operator-private-game \
  --player-file C:/chemin/prive/identite.txt \
  --out C:/chemin/prive/session-runtime-neuve \
  --stop C:/chemin/prive/STOP-runtime-neuf \
  --stop C:/root/dev/AI/CervHots/out/weekend/2026-10-24/STOP \
  --seconds 120 --interval 2 --max-attempts 60
```

Un seul lecteur, sources lot2 libérées, nouvelle partie privée Holdout + neuf bots.
Ne pas réarmer un ancien STOP. Au préalable vérifier mandat/STOP global/échéance,
commit, hashes, identité privée, dépendances et nouveau répertoire. Ne lancer la
partie que si cette mesure nouvelle est prête. L'auteur ne lance ni jeu ni lecteur.

Les quatre canaux indépendants, **après les gardes build communes et dans le même
WHOLE**, vérifient chacun leurs fonctions natives épinglées supplémentaires :

| Canal | Mesure privée ciblée et recontrôle | Ce qui n'est pas prouvé |
|---|---|---|
| `roots.selector` | compteur pile de contextes ; si non nul, table et slot `count-1`, tous relus | VM/partie active ou appartenance SCHO ; aucun déréférencement du contexte sélectionné |
| `roots.descriptor_arena` | header de l'arène **des descripteurs**, bloc courant/end/start/cursor et header physique de bloc, tous relus | allocation des globals SCHO, capacité OS effective, retour allocateur ou lifetime |
| `roots.simulation_root` | racine base simulation, membre `+0x2a0`, WORD brut `+0x38` consommé par le chemin reset, tous relus | lien instance globale→VM, liste active/libre/retirée, ordre effectif des writers |
| `roots.unit_pages` | header domaine unités, clés, pages encodées puis seul tag DWORD `+0x10` des slots bornés ; toutes lectures relues | origine balise SCHO, sémantique d'objectif, liste active/libre/retirée ou absence d'ABA |

**Le pool d'unités natif n'est PAS l'allocateur des globals SCHO.** C'est la voie
native alternative utile de ce lot, réutilisant la relation page/slot/tag déjà
présente dans `NativeReader.unit_pointer` et le recensement produit. Un tag dont
l'index correspond au slot est une référence cohérente échantillonnée, pas une
preuve de vie tactique. Aucune recherche de noms/heap, owner, position, vie ou autre
valeur de jeu. Les tags/pages restent dans `PRIVATE` et ne sont jamais exportés.

Pile vide : `observed` + `selector_selection=fallback_only` signifie **aucun
contexte d'exécution échantillonné à cet instant**, pas VM absente. Le fallback
n'est jamais déréférencé ou promu actif. Les caps diagnostiques (pile 4096,
domaine unités 1024, masque alignement 4095) ne sont pas des capacités natives
inventées : au-delà, refus sans clamp ni zéro ni scan partiel. Une page décodée
nulle n'est pas déréférencée. Changement au recontrôle, OS/short-read, pin ou coût
refusé : résultat absent, coûts conservés ; un canal refusé ne masque pas le suivant.

Sortie publique `braxis-runtime-roots-summary-v1` : coûts/statuts/refus fermés,
maillons manquants et `sample_transitions` par canal : `first_sample`,
`sample_equal`, `sample_changed` ou `not_comparable`. La comparaison porte seulement
sur deux tentatives adjacentes Holdout recontrôlées, même identité privée, build
observé, mission monotone avec gap ≤10 s et durée WHOLE <125 ms. Un refus/canal
absent/contexte perdu casse la comparaison ; aucune liaison à travers une nouvelle
partie. Le premier échantillon qualifié après une tentative non qualifiée reste
`not_comparable`, plutôt qu'un faux historique continu. Une égalité ne prouve
**jamais** une génération monotone, la continuité d'allocation ou l'absence d'ABA.
L'état comparé est uniquement en RAM de la session, sans cache de lectures natives.

Readsets privés `braxis-runtime-roots-v1` : le rejeu exact inclut les pins propres
à chaque canal et ses lectures dans l'ordre. Octets/résultat manquants, surplus ou
falsifiés sont refusés. Les timeouts/budgets/erreurs transport ne sont pas rejoués
comme une observation. Build/contexte/perspective/fraîcheur **non requalifiés**,
transitions live non reconstruites à partir des seules slices. Les anciens readsets
publication restent compatibles et n'acquièrent aucun nouveau canal fictif.

Coût du canal `unit_pages` au cap synthétique 1024 : **2182 requêtes / 9248 octets**,
sans pins/contexte/horloges ; ce n'est pas un benchmark live. Le bracket commun
reste 125 ms / 8192 lectures / 1 MiB, tous canaux/erreurs/relectures compris. La
recette 60 tentatives est plafonnée à 60 MiB demandés, non une promesse d'acceptation.
STOP/deadline/journaux/fermeture/absence de reprise conservent le contrat ci-dessus.

Règle de sortie : une recette nouvelle, comparer couverture/refus/transitions aux
maillons absents du lot2. Ne pas refaire une partie pour observer les mêmes noms.
Si sélecteur toujours fallback, cela indique la limite de l'échantillonnage hors
exécution, pas une autorisation de suspendre/injecter/appeler la VM. Sans gain après
deux expériences causalement nouvelles, consigner refus et proposer au contrôleur
la prochaine famille native utile, sans répéter la même sonde. Même avec toutes
les racines observées, B1/B2/B3 restent `unproven`, `objective=null`, Coach désactivé.

Tests hermétiques : `python -B -m unittest tests.test_braxis_roots tests.test_braxis_diagnostic -v`.
Tests synthétiques historiques : `python -B -m unittest tests.test_braxis_diagnostic -v`.
Régressions : `python -B -m unittest discover -s tests -v` (créer `out/` au préalable
pour les tests de découverte existants dans un worktree neuf). Les environnements
réellement exercés et les preuves historiques figurent dans le handoff du lot.
