# Talents choisis : collecte durable et inspection historique

## Commandes

Depuis le checkout gelé, avec Python + `heroprotocol/mpyq` :

```text
python -B -m cerveau.passive_session
python -B -m cerveau.passive_session --collection talents
python -B -m cerveau.passive_session --live --collection talents --player-file <identite-privee-absolue> --output-dir <sortie-absolue-NEUVE> --stop-file <STOP-absolu-neuf> --max-seconds 90 --interval 1
python -B -m cerveau.talents_journal --journal <sortie-absolue>/events.jsonl
```

Sans `--live`, le préflight n'ouvre aucun backend. Voir
[passive-session.md](passive-session.md) pour identité, verrou, arrêt et reprise.
Créer le STOP termine coopérativement ; ne jamais supprimer un ancien STOP.
Une nouvelle partie exige une nouvelle invocation et une sortie neuve. Le STOP
global/reprise propriétaire reste surveillé par l'opérateur (un seul `--stop-file`
est surveillé par le collecteur). Aucun Coach/API/audio/OCR n'est nécessaire.

### Collecte ciblée, pas récupération après refus

`--collection talents` choisit **avant la première lecture** le cœur complet
(build, contexte, identité, dix héros, niveaux, génération, horloges et tous
leurs rechecks) + la famille talents existante. Les autres acquisitions
optionnelles ne sont pas appelées : chrono HUD, positions, visibilité,
objectifs, cooldowns et battlefield. Le chrono de mission du cœur reste lu.
Le journal `acquisition` conserve `collection: "talents"` et `not_selected` ;
ces six familles sont non sélectionnées, ni refusées ni implicitement réussies.
La synthèse conserve aussi le mode. `--collection all`, valeur par défaut,
garde le parcours composé antérieur. Toute autre valeur est rejetée.

Ce n'est pas une stratégie de retry, un découpage du WHOLE en plusieurs
budgets ni une publication partielle après dépassement : un refus du budget
partagé reste fatal, même après une lecture talents réussie. Chaque tentative
repart à neuf. Aucun octet final n'est remplacé par un cache.

La recette précédente lot7 composée a refusé 12/12 acquisitions : neuf au
plafond8192reads, une au délai125ms, deux pour conflit tick initial. Le journal
agrégé ne permet pas d'attribuer rétrospectivement la famille coûteuse. Les
anciennes recettes talents seules ne qualifiaient pas le pipeline futur composé
(voir P2-TALENTS). La nouvelle expérience sélectionne uniquement la famille
utile, sans nouvelle portée ni baisse des gardes. Sur une fixture **synthétique**
multi-familles, les appels physiques passent de2709 à1513 et les octets demandés
de14663 à7982, avec les mêmes lectures ordonnées/octets cœur+contexte+talents.
Ces coûts ne prédisent ni le délai Windows ni le taux de refus live. Un conflit
tick initial reste refusé ; aucune qualification live n'est déduite des tests.

## Ce qui change, sans étendre la couverture

La source native et le normaliseur savaient déjà lire les choix persistés. Le
journal passif ne conservait que la présence du champ `talents`. Il conserve
maintenant un objet `talents` fermé, limité aux cinq acteurs locaux/alliés :

- `status` : `not_attempted`, `refused`, `rejected`, `normalized`, ou `unknown`
  pour une ancienne observation sans qualification. Ce n'est pas un taux de
  réussite live ; les coûts/refus détaillés restent dans `acquisition`.
- `source_mission_t_s`, `age_s`, `read_window_s` : temps de la source, âge du
  **reçu original lors de la normalisation**, et fenêtre de lecture. Un flush
  lent ou un rejeu ne remet jamais l'âge à zéro. Aucun seal, pointeur, génération
  native, session native ou catalogue d'offres n'est exporté.
- `value` : build exact, carte, équipe native, slot local, puis slots/héros/niveaux
  alliés et paliers. L'export revérifie la composition alliée ; aucun talent ennemi.
- Palier `selected` = index choisi réellement observé et résolu dans l'arbre
  courant du héros ; `slot` et `catalog_id` sont présents. `unselected` = lecture
  explicite sans choix sur un palier offert. `unknown` = palier non établi.
  Acteur `unknown` = `tiers: null`, **pas** un arbre vide ou zéro talent.
  Une offre/catalogue, une possession ou un choix précédent ne crée jamais un choix.
  Un reset natif fait disparaître le choix au prochain échantillon accepté.

Aucun cache/historique de choix n'est réinjecté. Reçus frais, identité/génération,
contexte, build entier98348, signatures, rôles, WHOLE125ms/8192reads/1MiB
restent obligatoires. Les décodeurs de familles et les allowlists sont inchangés ;
seule la sélection des acquisitions optionnelles est maintenant explicite.
La politique existante est uniquement DragonShire : Sonya locale ; Arthas,
Dehaka, LtMorales et Tassadar alliés. Cela ne qualifie aucune autre carte, aucun
autre héros/rôle et ne constitue pas une nouvelle validation live de ces cas.

## Libellés : refus explicite

`catalog_id` est un identifiant natif, **pas** un libellé traduit. Ce lot ne
qualifie aucun catalogue de noms ayant une clé exacte héros/build/id/langue et
une provenance vérifiée. Ainsi `label: null`, `label_status: "unknown"`,
`label_provenance: null` sont systématiques, même si l'entrée fournit un nom.
Ni KB approximative ni catalogue d'offres ne servent de fallback. C'est une
limite assumée, pas une nouvelle couverture sémantique.

## Rejeu et exemple synthétique

```text
uv run --offline --no-project --python 3.14 --with heroprotocol python -B -m cerveau.talents_journal --journal examples/talents/SYNTHETIC/events.jsonl
```

L'exemple **entièrement synthétique** illustre choix / reset / inconnu. Le faux
identifiant `SyntheticSelectedTalent` n'est pas une preuve de talent du jeu.
Chaque ligne de sortie est `historical_not_current`, sans nouvelle permission
ni reçu, même si le statut enregistré est `normalized`. L'âge historique est
conservé ; il ne signifie jamais « frais maintenant ». JSON non authentifié :
ce rejeu inspecte un journal, il ne certifie pas sa vérité native ni une référence
HUD. Il re-sélectionne les champs et supprime les libellés non prouvés.
Limites : 64KiB/ligne, 4MiB/fichier, 10000lignes ; entrée invalide ⇒ code1,
message fermé sans donnée privée. Une erreur tardive n'annule pas les lignes
historiques déjà imprimées : exiger aussi le code0 et la synthèse finale.

## Recette indépendante (opérateur uniquement)

Une seule privée +9bots, sur la portée existante ci-dessus, sans changer de
carte pour obtenir une allowlist. Avant de démarrer une collecte, vérifier que
le panneau talents de l'acteur autorisé est lisible : héros, palier, choix
**coché**, pas simplement une option offerte. Une ROI minimap n'est pas une
référence talents. Si ce panneau/choix n'est pas accessible, refuser la
comparaison et ne pas lancer un match d'attente.

L'opérateur choisit manuellement un talent de Sonya locale (ou observe un choix
allié qualifié). Relever indépendamment héros/slot/palier/choix et intervalle
stable sur l'horloge monotone hôte avec incertitude mesurée. Dans cette recette
à intervalle1s, le journal conserve aussi les bornes monotones de `comparison` du
collecteur existant ; agrandir conservativement de `age_s` et `read_window_s`
originaux, puis exiger l'inclusion complète dans la fenêtre HUD stable.
Pas de plus-proche-frame/temps replay/UTC ni d'inférence offre→choix. L'opérateur
atteste explicitement même partie/acteur/perspective : ce lot n'ajoute pas de
comparateur automatique talents et ne modifie pas celui des objectifs.

Vérifier avant/après choix, un inconnu/refus attendu, STOP neuf, fermeture du
lecteur et absence du verrou. Reset uniquement s'il est offert normalement par
le client ; sinon le cas reste testé synthétiquement, non qualifié live. Garder
la référence privée séparée du journal minimisé. Budget inchangé ; pas de scan,
OCR stats, données ennemies cachées, push ou déploiement.
