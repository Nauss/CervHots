# CervHots en cinq minutes — choisir le bon parcours

**État documentaire : 26 octobre 2026, base MAIN locale vérifiée
`09bf4cdc03272001e605fb70d94ec402d2664472` (lot38 intégré).**
Preuve durable locale : `C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot38/integration/verification.json`
(PASS, intégration locale fast-forward, revue ROGER SAME-CARD run745 et recette depuis MAIN).
Ce SHA désigne la base vérifiée, pas le futur commit documentaire. Lot39 prépare
un dossier hors ligne mutable ; ce n'est ni une livraison produit ni un gel.
**Aucune activation native autorisée par ce guide : aucun droit CURRENT et aucune
annulation de STOP.** Le mot STOP ici n'atteste pas un marqueur STOP week-end
existant ; son absence ne vaut pas autorisation. Ni ancien job ni ancienne partie
ne doivent être réarmés.

Les **voies natives ciblées sont prioritaires**, sans élargissement de qualification.
Vision seulement en recours explicitement autorisé ; captures de référence à
qualifier, pas producteur de statistiques. Aucune garantie juridique/EULA/ToS,
anti-cheat ou de sécurité du compte, même en privé/IA.

| Je veux… | Choix | Ce que j'obtiens |
| --- | --- | --- |
| Voir le produit sans donnée personnelle | **1. Démo SYNTHETIC** | HTML locaux sur données inventées, complétude vérifiable |
| Relire un vrai replay | **2. Débrief historique** | Résumé français/HTML à un instant de mission, perspective hypothétique |
| Comprendre une collecte conservée | **3. Journal natif historique** | Statut disque, diagnostic, valeurs historiques admissibles |
| Préparer une future collecte autorisée | **4. Préflight puis procédure opt-in** | Disponibilité technique seulement ; aucun droit CURRENT |

Aucun de ces parcours n'appelle le Coach/API ou l'audio par défaut. Aucun
n'ouvre de navigateur automatiquement. **Inconnu/null n'est jamais zéro.**

## Préparer le terminal (Bash Windows)

Les commandes ci-dessous utilisent l'interpréteur **déjà installé** du dépôt,
Python 3.12.12. Python 3.14 est également testé. Pas de téléchargement implicite :
la démo et l'inspection historique utilisent la bibliothèque standard ; le replay
requiert `heroprotocol` et `mpyq` déjà installés
([dépendances](../hotstate/requirements.txt)). Le préflight core n'exige pas ces
paquets replay. Ne pas installer un autre venv dans chaque worktree.

```bash
cd C:/root/dev/AI/CervHots
export TMPDIR=C:/Users/Nauss/AppData/Local/hermes/cache/scratch
export TEMP="$TMPDIR" TMP="$TMPDIR" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
```

Le `cd` ci-dessus est le **cwd réellement exercé lors de l'intégration lot38**.
Les commandes sûres suivantes correspondent aux argv conservés dans
`C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot38/integration/recipe-3.12/COMMANDS.json`,
avec codes et empreintes des logs. La recette auteur avait été exercée auparavant
depuis `C:/root/dev/AI/CervHots/.worktrees/t_9b43acb6`, dans des destinations distinctes.
Même interpréteur absolu et trois variables temporaires. Choisir **un** parcours ; pas besoin de tout
exécuter. Les parents de sortie doivent exister. Les destinations lot38 ci-dessous
sont les preuves de cette recette : **déjà présentes après exécution, ne pas les
réutiliser**. Pour réessayer, choisir un autre nom de sortie neuf, sans effacer
l'ancien ni toucher aux sources.

## 1. Démo silencieuse, sans jeu ni replay (recommandé)

**Commandes réellement exercées à l'intégration lot38**, données explicitement **SYNTHETIC** :

```bash
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.offline_demo --destination C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot38/integration/recipe-3.12/demo-SYNTHETIC
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.offline_demo --verify C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot38/integration/recipe-3.12/demo-SYNTHETIC
```

Exiger **code 0 de la génération ET de la vérification** ; un HTML ou un marqueur
seul ne suffit pas. Consulter manuellement `demo-SYNTHETIC/catalog/INDEX.html`.
Les cas absence/refus/inconnu/zéro sont inventés ; aucun match ni valeur native
réelle n'est démontré. Détails et codes 3/4 de vérification : [démo](offline-demo.md).

## 2. Vrai replay conservé, à 60 secondes

**Commande réellement exercée lot38** sur le même fichier autorisé que lot32 :

```bash
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.replay_debrief --replay C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot2/operator/PRIVATE/causal-001.StormReplay --team 0 --perspective player-team --at 60 --allow-protocol-shim --report-dir C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot38/integration/recipe-3.12/replay-60s
```

Lire `replay-60s/REPORT.html` ou `report.json` : **historique indicatif SHIM non certifié**,
build98348/protocole91756. Les corpus conservés causal et recipe reconnaissent
désormais chacun **10 héros sur 10** (lot36 ; causal également rejoué lot37).
Les anciens fichiers lot33 restent inchangés et peuvent refléter l'ancienne couverture.
La vie n'est affichée que si un événement reconnu l'établit ; sinon elle reste
inconnue. L'objectif reste inconnu ; la carte recipe reste inconnue. Ce gain est
documentaire/historique, sans qualification native/live/HUD.
Un replay peut contenir un **préfixe partiel**, sans résultat final ; cela ne
qualifie pas sa lecture comme source live. La perspective `player-team` est
hypothétique, pas une preuve de ce que voyait le joueur local.
L'opt-in `--allow-protocol-shim` n'est pas une certification ;
sans lui, ce corpus est refusé (code 1). `--team 0` est un indice, pas une couleur
HUD ni une identité locale. `60` désigne le temps de **mission**, préparation
incluse, pas le chrono HUD. Aucun événement futur, résultat final, pseudo ou
coordonnée exporté. Code 0 signifie débrief produit, pas fidélité exacte.
Si ce fichier privé n'est pas disponible sur une autre installation, fournir
son propre replay autorisé ; ne pas inventer les données. [Contrat replay](replay-debrief.md).

## 3. Journal natif existant : distinguer état et contenu

**Commandes réellement exercées lot38**, lecture seule de l'ancien corpus lot7
explicitement autorisé ; sorties neuves seulement :

```bash
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --status --output-dir C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot7/operator-revision2/PRIVATE/talents-session-002
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --diagnose --journal C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot7/operator-revision2/PRIVATE/talents-session-002/events.jsonl --report-dir C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot38/integration/recipe-3.12/native-diagnosis
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --report-html --journal C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot7/operator-revision2/PRIVATE/talents-session-002/events.jsonl --report-dir C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot38/integration/recipe-3.12/native-history
```

- `--status` : statut **disque historique**, `reader_active=null` toujours.
  Code 0 = fermeture enregistrée, pas preuve d'arrêt OS ou permission de reprendre.
- `--diagnose` : acquisitions/refus/coûts enregistrés, pas validation des valeurs.
- `--report-html` : `native-history/REPORT.html` et `report.json`, dernière
  observation admissible et chronologie avec ruptures. Lot7 : 46 observations
  locales aux valeurs constantes, **pas une évolution ou continuité prouvée**.
  PV/ressource générique ne prouvent pas du mana ; âge du cœur inconnu.

Ces lectures ne nécessitent ni jeu ni fichier d'identité. Un ancien journal sans
liaison/temps/clôture suffisants peut être refusé : aucun verdict opérateur ne le
répare. Code 1 conserve le refus ; ne pas compléter depuis une autre session.
[Diagnostic](session-diagnosis.md) · [Résumé natif](native-history.md) ·
[HTML et limites](session-html.md).

## 4. Préflight sans backend ; live uniquement sur autorisation distincte

**Commande réellement exercée lot38**, sans ouverture mémoire, mutex ou backend :

```bash
C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -B -m cerveau.passive_session --preflight
```

Sans argument, même préflight **core**. Vérifier `memory_opened=false`,
`chat_called=false`, `audio_enabled=false`, `collection=core` ; les sept familles
optionnelles sont `not_selected`, pas « absentes du jeu ». Code 0 = dépendances
prêtes, 1 = indisponibles, 2 = arguments invalides. Ni contexte privé actuel,
ni absence d'ancien lecteur, ni permission CURRENT ne sont établis.
Le [contrôle core prêt](core-readiness.md) inspecte aussi identité/sortie/STOP,
sans création ni test d'écriture ; lui non plus n'autorise pas une collecte.

**Procédure de démarrage / arrêt / reprise : modèles NON exécutés lot33.**
Ce guide ne permet pas de les lancer ici, ni de lever un STOP éventuel. Lors d'une autorisation
indépendante seulement, suivre les [commandes absolues du quickstart](passive-quickstart.md#2-démarrer-une-seule-session-autorisée) :

1. Confirmer la fin effective de tout ancien collecteur (retour du terminal
   propriétaire, pas statut historique). Confirmer séparément permission/contexte
   privé actuel ; inconnus = ne pas lancer. Préparer le fichier privé par son
   chemin seulement, jamais le pseudo en argument ou log.
2. Réserver **un parent neuf, une sortie inexistante et un STOP neuf hors sortie**.
   Lancement explicite `--live` ; `core` est le défaut. `--collection talents` et
   `--collection all` sont des opt-in, pas une qualification de toutes les familles.
3. Arrêt dans un second terminal : `--request-stop` avec **les deux chemins exacts**
   `--output-dir` et `--stop-file`, liés par le nouveau `control.json`. C'est un
   signal, pas une preuve d'arrêt ; ancien journal sans contrôle = refus, pas de
   réparation. Attendre le retour du premier terminal et sa fermeture de source.
4. Reprise seulement après cette confirmation : **nouvelle invocation, nouveau
   parent, nouvelle sortie, nouveau STOP**. Ne supprimer ni claim ni ancien STOP,
   ne réarmer aucune session. Contexte, sel, identité de comparaison et reçus ne
   sont pas repris. Mutex Windows des lecteurs coopérants ≠ protection des anciens
   lecteurs ni permission CURRENT. Si fermeture inconnue, ne pas lancer un second lecteur.

La [procédure complète](passive-quickstart.md#4-stop-ciblé-puis-reprise-neuve)
précise codes, attente et refus. Aucune collecte live ni demande de STOP sur une
ancienne session n'a été exécutée pour lot33.

## Familles : ce que les preuves permettent réellement de dire

Portée **carte × famille × build/héros**, jamais « toutes cartes ». Base documentaire :
`C:/root/dev/AI/CervHots/out/weekend/2026-10-24/coverage.json`, complétée par les
preuves d'intégration lot32 et lot38 (les statuts de coverage sont des instantanés,
pas l'autorité d'intégration ; ne pas les corriger depuis ce guide).
Les dossiers `out/` sont locaux ignorés, pas des fichiers
distribués par Git ni recopiés dans le worktree. Leur absence ailleurs n'est pas
une preuve négative.

| Famille / périmètre | Preuve utile déjà acquise | Limites qui restent |
| --- | --- | --- |
| Cœur : composition, niveaux, vie, PV/ressources | Lecteur et collecte durable intégrés ; Volskaya historique recoupée au replay ; lot1 comparaison ciblée PV/ressource/niveau sur carte native inconnue | Pas de généralisation carte/héros ; âge cœur historique null ; core-only sans liaison locale explicite ne restitue pas les PV locaux |
| Positions alliées vivantes / Volskaya | Qualification historique bornée du lecteur ; essais de journalisation/comparaison lot10 conservés | Lot10 non intégré, zéro comparaison spatiale causale ; ni positions ennemies ni nouvelle validation indépendante |
| Talents choisis / DragonShire | Lot7 Sonya, palier1 ordinal2, référence discrète sous attestation ; restitution et trace documentaire intégrées | Pas catalogue exhaustif, pas nom choisi FR/build/slot prouvé ; correspondance documentaire EN ≠ libellé choisi |
| Objectif Dragon | Lot4 : valeurs normalisées, exportées et rejouées, produit intégré | Pas de CURRENT indépendant/HUD frame-exact ; lot6 non comparable. Volskaya qualification seulement, pas valeurs ouvertes ; **Braxis non débloqué**, objectif null |
| Cooldown local / DragonShire, Sonya | Lecture historique des paquets legacy intégrée (lot29) ; valeurs réelles qualifiées zéro seulement | Charges inconnues, aucun cycle actif/reset/lancer observé qualifié ; slot natif ≠ touche HUD |
| Camps, structures, visibilité/positions ennemies, autres cartes/familles | Aucun élargissement qualifié par ce parcours | Restent hors périmètre démontré ; absence de preuve ≠ valeur zéro |

Verdicts locaux : `C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot19/verdict.json`
et `C:/root/dev/AI/CervHots/out/weekend/2026-10-24/lot28/operator-001/verdict.json`.
Ces lots ont refusé
l'activation : contexte privé actuel inconnu, aucun lecteur lancé par ces recettes,
coûts physiques live inconnus, STOP produit live non exercé. Leur préparation
technique ne prouve aucun gain live core/all. Le nombre de parties **héritées**
reste inconnu ; aucun total de matchs n'est déduit des observations ou compteurs
ambigus. Historique, SYNTHETIC, intégrité SHA et code 0 ne valent ni HUD, ni identité
authentifiée, ni CURRENT.
