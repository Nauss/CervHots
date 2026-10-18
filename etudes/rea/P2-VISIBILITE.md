# P2 — visibilité courante joueur : travail conservé, recette manquante

État au 18 octobre 2026 : **NON LIVRÉ, publication ennemie fermée**.
Base de départ vérifiée : main `12bbe713a06807200c5c9edfdf8ccf38a91d03df`,
contenant la livraison du lot positions alliées. Carte `t_92c40f76`.
Ce document ne remplace ni la recette humaine ni la revue avant intégration.

## Implémentation exécutée

- `hotstate/visibility.py` : lecteur RO diagnostic du prédicat CURRENT de la
  perspective native humaine active, pas du joueur spectaté. Résolution CPlayer
  → héros principal → tag/génération/propriétaire ; contrôle build98348,
  signatures, racines ASLR, carte/bornes, fenêtre <=125 ms et relecture de toutes
  les lectures réussies. Observateur, replay et dump roulant sont refusés par
  `diagnose`. Aucun résultat précédent n'est mémorisé comme visibilité courante.
- Résultat diagnostic par héros : `visible=true`, `false` ou `null` avec motif.
  Une empreinte étendue ou un callback de comportement non résolu reste inconnu.
  Un point hors champ ne suffit pas à conclure caché si le moteur peut regarder
  l'empreinte de l'unité. Les héros morts restent hors périmètre de ce lecteur.
- Aucun champ tactique ennemi n'est débloqué. Aucun reçu de publication n'est
  émis par ce lecteur ; `read()` refuse tant que la recette joueur manque.
  Le normaliseur ne transmet pas les diagnostics au modèle et conserve ses
  allowlists : ni XY/PV/ressources ennemis, ni talents/cooldowns, même si le
  diagnostic courant dit visible. Ce lot n'est pas une implémentation de ces
  autres familles ni une promesse de leur accès légitime.
- `etudes/rea/scripts/capture_visibility.py` : collecteur privé borné, profil et
  sources gelés au commit, lectures avant et après PNG, ordre et bytes demandés
  enregistrés. Réutilise `TraceMemory`, `ReplayTrace` et la capture exclusivement
  fenêtre jeu foreground du collecteur positions. Ne lance/focalise pas le jeu.
  Aucune API, aucun coach, aucun audio. Le collecteur n'a PAS été lancé en live
  pendant cette exécution ; ses chemins et rejouages ont été exercés sur fixture.

## Sémantique native suivie, pas déduite d'un masque isolé

Sources CASC build installé préservées dans le handoff privé :

- NativeLib initialise `libNtve_gv_visibleFilter` avec
  `UnitFilter(1 << c_targetFilterVisible, 0, 0, 0)` (ligne118).
- `libNtve_gf_UnitIsVisibleToPlayer(unit, player)` appelle `UnitFilterMatch`
  avec ce filtre (lignes4550–4553).
- UILib utilise ce prédicat notamment pour les pings et le ciblage d'un héros.
- La déclaration native de la constante donne31 ; cas dispatch Galaxy1793,
  wrapper RVA `0x206b510`, filtre `0x63fc20`, prédicat `0x99dea0`.
  La branche bit31 exige le statut natif4 ; ses flags sont `0xf` à la RVA
  `0x2fadd9c` et sont vérifiés avant acquisition.
- Le statut4 combine masquage explicite, propriétaire/vision partagée, vision
  courante au point (RVA `0x99e410`, grille `0x9b1df0`, raffinement diagonal
  `0x640020`/`0x640ff0`), révélation (`0x99ef60`) et détection (`0x99e250`).
  Révéler ne détecte pas automatiquement un héros furtif. Le lecteur conserve
  les branches non résolues à `null`, jamais une exécution de vtable du client.
- Dix nouvelles empreintes sont dans `98348-visibility.json`. Les sources C et
  le désassemblage Ghidra ont été exportés en lecture seule, `-noanalysis` ;
  aucun appel de fonction, injection ou écriture dans le jeu.

Limites : le fallback d'empreinte étendue et les callbacks de comportements ne
sont pas traduits. Ils peuvent réduire la couverture. La relecture détecte des
lectures déchirées mais n'est pas un verrou : un ABA entre prélèvements demeure
possible. Le stamp des racines identifie les objets natifs de cette acquisition,
pas un seed/cache replay. Il ne prouve pas à lui seul que le match_id d'un
initData ancien désigne la partie active ; ce point reste à recouper pendant la
recette et ne justifie aucune ouverture de données ennemies.

## Durcissement connexe PV/ressources alliés

Les tests RED ont montré que l'ancien `NativeReader.read_state` déterminait les
PV autorisés à partir de l'équipe du contexte initData sans revérifier la vraie
perspective locale. Une équipe native modifiée pouvait donc utiliser un contexte
périmé comme permission. Ce chemin a été corrigé :

1. Validation native humaine/équipe/composition avant lecture des PV, mêmes
   signatures d'identité que le lot positions mesuré. Un contexte incohérent
   refuse l'enrichissement, sans repli vers une ancienne observation.
2. Relecture de tout le read-set du cœur natif, budget mural125 ms et contexte
   inchangé. Tag/propriétaire/racines/équipe modifiés pendant lecture => refus.
   Les lecteurs optionnels conservent des read-sets séparés : une lecture XY
   refusée ne doit pas invalider les niveaux/états de vie indépendants.
3. Reçu HMAC éphémère du même processus, liant identité, match déclaré, données
   héroïques et fenêtre. Le normaliseur exige ce reçu frais (âge0..1 s), le même
   héros local, l'équipe, le match, les données et une source live avant PV ou
   ressources alliés. Un changement d'identité/match ou une altération les omet.
4. Les vitaux d'un JSON externe/ancien ou dump historique ne sont plus autorisés
   au modèle. Un chrono mission en pause ne prolonge pas leur fraîcheur.
   Les niveaux/états de vie publics restent indépendants. Le budget mission
   historique1 s subsiste en plus du budget mural125 ms, plus strict.

Ce durcissement est exercé synthétiquement et structurellement hors ligne ; sa
cadence live doit être mesurée lors de la recette. Il n'implique pas que tous les
anciens relevés passeront le nouveau détecteur de lecture déchirée.

## Preuves existantes réellement réexaminées

Audit privé : `out/visibility/offline-audit.json` dans le worktree, à préserver
hors worktree avant blocage. Ne pas versionner dumps, traces privées ou PNG.

- Sept jeux module/tas relus ; les dix empreintes visibilité concordent sur les
  sept. Six observations Volskaya/Braxis sont omniscientes : la perspective est
  refusée. Braxis reste une contre-épreuve, pas une carte livrée.
- L'ancien dump Dragon donne une perspective native humaine, joueur anonyme6,
  équipe1, à1163,5625 s mission. Le chemin structurel trouve une différence de
  visibilité entre ennemis, mais il s'agit d'UN dump roulant, non atomique, sans
  comparaison temporelle/pixels applicable. `diagnose` le refuse explicitement.
  Cela n'est PAS une validation de visibilité joueur, ni une recette Dragon.
- Le cœur P0/P1 durci a aussi été exercé sur ce dump historique : dix héros
  conservés, aucun reçu de perspective/positions émis, aucun PV/ressource au
  normaliseur. Le contexte de cette sonde utilise un label match synthétique,
  explicitement sans prétendre résoudre le seed/cache actif.
- Les trois traces de la recette positions Volskaya précédente contiennent872
  tentatives ; les racines/champs du brouillard n'y étaient pas demandés.
  Elles peuvent corroborer la perspective joueur, mais ne permettent pas de
  rejouer ce nouveau prédicat ou d'étiqueter ses transitions. Aucune donnée de
  replay futur n'a été utilisée pour combler ce manque.

## Vérification automatisée

160 tests passent sur Python système et sur Python du coach après correction
du premier retour de revue indépendante.
Les journaux RED de confidentialité et GREEN complets sont dans l'audit privé.

Couverture ajoutée : visible → brouillard → révélé → brouillard → visible,
vision d'un autre joueur, historique ignoré, furtivité/détection, état masqué,
callbacks/empreintes inconnus, référence/génération/propriétaire corrompus,
profil/couche/racines, lecture déchirée et budget, joueur absent/IA/observateur,
ASLR, dump non atomique, reçu absent/altéré/périmé avec mission en pause,
changement d'équipe/partie/identité, rejet des données ennemies et cooldowns au
normaliseur. Le collecteur est rejoué dans l'ordre exact, lectures et horloges
consommées, et le refus observateur est aussi rejoué. Aucun de ces tests ne
constitue une mesure réelle de visible → brouillard → révélé chez un joueur.

La première revue indépendante du commit `1303bf0` a validé le périmètre
diagnostic/confidentialité, mais reproduit une régression : le read-set externe
incluait les XY d'un enrichissement optionnel pourtant déjà refusé. Un test RED
reproduit le défaut ; les lecteurs optionnels utilisent maintenant leur propre
acquisition, le cœur conservant sa relecture obligatoire. Le test GREEN vérifie
que XY déchiré => positions absentes, dix héros/niveaux et PV alliés frais
conservés. La liaison native seed/cache au match déclaré reste une limite,
pas un critère satisfait par cette correction.

## Recette précise nécessaire, sans nouvelle demande d'autorisation de P2

Demander un créneau coordonné d'environ10 minutes, sans prendre le premier plan
ni lancer de partie de façon autonome. Partie privée Volskaya build98348, vrai
joueur local + neuf IA, perspective joueur et non observateur. Silence conservé.

Après gel du commit et préflight, exécuter des séquences bornées120 s à0,5 s,
PNG fenêtre jeu explicitement activés. Le joueur place/maintient la caméra et
conduit un même héros ennemi par au moins deux transitions complètes : visible
avec marqueur/barre, perdu sous brouillard, puis révélé/revisible. Étiqueter les
images et leurs fenêtres ; une transition entre lectures discordantes reste
ambiguë, pas une preuve. Furtivité/détection à distinguer si un cas est disponible.

Commande (remplacer SHA par le commit réel gelé, et seulement pendant le créneau) :

    tts/.venv/Scripts/python.exe etudes/rea/scripts/capture_visibility.py --live --expected-commit SHA --out out/visibility-player/volskaya-001.jsonl --duration 120 --interval 0.5 --png

Depuis ce worktree, utiliser le Python du coach par son chemin absolu si le venv
n'y existe pas. Le collecteur refuse un commit différent ou des sources suivies
modifiées ; sortie nouvelle uniquement, jamais écrasement des preuves.

Ensuite : replay exact des accès, comparaison temporelle aux PNG indépendamment
annotés, mesure des refus/latences et de la couverture `null`, corriger les
branches natives nécessaires, revue indépendante puis seulement intégration et
push main si les critères sont satisfaits. Ne pas ouvrir les positions ennemies
par la seule observation du booléen. Ne pas clore cette carte ni libérer le lot
objectifs tant que la recette/résolution des limites n'est pas terminée.
