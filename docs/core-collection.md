# Collecter explicitement le cœur natif seul

`--collection core` sélectionne **avant lecture** le socle existant : composition,
équipes, niveaux, vie/retour, PV et ressources alliés autorisés, horloge de mission.
L'horloge gameplay optionnelle (préparation/partie) n'est **pas** cette horloge.
Talents, objectifs, positions, visibilité, cooldowns/charges, camps/structures et
leurs diagnostics optionnels ne sont ni acquis ni projetés par le normaliseur.
Aucun nouveau champ, carte ou périmètre de visibilité n'est qualifié.

Le défaut **CLI** est désormais `core` : omettre `--collection` équivaut à
`--collection core`, y compris pour le préflight et `--check-ready`.
Migration du défaut `all` → `core` : les scripts qui veulent conserver le parcours
composé doivent ajouter **`--collection all`** à chaque invocation ;
`--collection talents` conserve cœur + talents, sans les autres familles.
Les seules sélections sont `core`, `talents`, `all` ; une sélection inconnue est refusée.
Les API Python `NativeSource(player)` et `preflight()` gardent leurs défauts
historiques (`all`, vérifications replay) : seul le parcours CLI devient minimal.
Les acquisitions source déclarent maintenant aussi explicitement `all` quand
c'est la sélection effective ; cela ne modifie ni lectures ni normalisation.
Aucun ancien journal sans sélection n'est réinterprété comme core ou all.
Le préflight ne cherche ni n'ouvre le jeu :

```bash
cd C:/root/dev/AI/CervHots
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --preflight --collection core
```

## Contrôler la disponibilité avant de collecter

Utiliser `--check-ready --collection core` avec les trois chemins privés/préparés
pour agréger ce préflight, l'identité, la sortie neuve et le STOP, sans rien créer.
JSON stable + résumé français, codes 0/1/2 : [contrat et exemple réel](core-readiness.md).
**Prêt techniquement n'est jamais une permission ni un contexte privé ACTUEL.**

## Exemple de lancement, STOP et reprise

**Exemple à préparer, pas une autorisation de lancement.** Après intégration
locale revue, contexte joueur/partie autorisé vérifié et fin de tout ancien
collecteur confirmée indépendamment : réserver un parent/sortie/STOP neufs et un
fichier d'identité privé réel, jamais une identité en argv. Aucun Coach/API/audio.

```bash
cd C:/root/dev/AI/CervHots
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --live --collection core --player-file C:/CervHots-private/player.txt --output-dir C:/root/dev/AI/CervHots/out/core-run-001/session --stop-file C:/root/dev/AI/CervHots/out/core-run-001.STOP --max-seconds 300 --interval 5
```

Dans un autre terminal Bash, STOP ciblé (ne jamais effacer un ancien STOP) :

```bash
touch C:/root/dev/AI/CervHots/out/core-run-001.STOP
```

Attendre le retour terminal et vérifier indépendamment la fermeture du collecteur.
Ni un ancien PID, ni `--status`, ni l'absence d'un claim n'établissent son activité.
Si elle reste inconnue, **pas de reprise**. Après confirmation et nouvelle identité
courante autorisée, relancer la même commande avec `core-run-002/session` et
`core-run-002.STOP` **tous deux neufs**. Conserver anciens journaux, STOP et claims.
Le mutex natif global, le recheck final, la fraîcheur originale et les budgets
WHOLE **125 ms / 8192 lectures / 1 MiB** sont inchangés. Cœur seul ne répare pas un
conflit d'horloge, un contexte incohérent, une identité invalide ou une lecture tardive.

## Inspecter le journal fermé, sans backend

```bash
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --diagnose --journal C:/root/dev/AI/CervHots/out/core-run-001/session/events.jsonl --report-dir C:/root/dev/AI/CervHots/out/core-diagnosis-001
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --summarize --journal C:/root/dev/AI/CervHots/out/core-run-001/session/events.jsonl --report-dir C:/root/dev/AI/CervHots/out/core-history-001
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --report-html --journal C:/root/dev/AI/CervHots/out/core-run-001/session/events.jsonl --report-dir C:/root/dev/AI/CervHots/out/core-html-001
```

Les répertoires de rapport doivent être neufs. Les acquisitions enregistrent
`collection="core"` et les sept familles `not_selected` ; cela ne signifie ni zéro,
ni refus, ni absence globale dans le jeu. La qualification interne sans paquet
reste `not_attempted` ; l'inspection recoupe la sélection d'acquisition reconnue.
Sélection historique absente/invalide : inconnue, jamais reconstruite depuis une
liste `not_selected` arbitraire. Les vues historiques ne recréent aucun reçu et
ne promettent **jamais une santé CURRENT**. Âge actuel et âge du cœur non enregistré
restent inconnus/null ; les âges optionnels originaux existants ne sont pas renouvelés.
Le résumé/HTML conserve son vocabulaire de cartes existant (DragonShire/Volskaya) :
une carte hors de ce vocabulaire peut être diagnostiquée mais pas rendue comparable.

## Preuve hors ligne uniquement

Le helper `tests/helpers/core_session_synthetic.py` exerce la vraie CLI et
`NativeSource → read_current → snapshot → tactical_key → Journal`, avec backend
mémoire **SYNTHETIC**, sentinelles optionnelles, STOP après persistance et mutex
réel ; la construction du backend OS, le Coach et le réseau y sont interdits.
Ce helper n'ajoute aucun mode simulé au produit. Il exige un parent neuf :

```bash
# Depuis le checkout exact à examiner, dépendances locales installées.
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B tests/helpers/core_session_synthetic.py C:/root/dev/AI/CervHots/out/SYNTHETIC-core-check-001
```

Sur **la même fixture physique instrumentée**, all : **2709 appels / 14663 octets** ;
core : **1072 appels / 5271 octets**. Les octets et l'ordre du cœur/contexte/rechecks
sont exactement ceux du sous-ensemble all. Cette réduction synthétique n'est
**pas un gain mesuré live**, une promesse de latence ni une qualification HUD.
Aucune partie ni nouvelle référence n'est nécessaire pour prouver ce contrat
hors ligne (`references_held=false`). Voir aussi [le parcours général](passive-quickstart.md).
