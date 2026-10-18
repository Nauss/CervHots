# P2 — lecteur natif du chrono HUD (build 98348)

## Statut exact

Implémentation de branche et vérifications hors ligne, pas encore une livraison
intégrée sur main. La résolution depuis la VM active est établie ci-dessous ;
la recette temporelle ciblée en processus avec HUD reste à coordonner. Aucun
nouveau lancement de partie, accès live, changement de premier plan, appel
coach, TTS ou Mumble n'a été effectué pour cette implémentation.

Les dumps existants permettent de tester le vrai résolveur et ses refus, mais
leurs fenêtres roulantes de plusieurs secondes ne certifient pas le contrat
125 ms. Le lecteur ne transforme pas une relecture mmap rapide en preuve de
synchronisation. La carte ne doit pas être close sur ces seuls résultats.

## Sémantique et contrat public

Sources installées extraites et conservées dans le handoff privé du 18 octobre :

- UILib.galaxy:1020–1049 : `UIUpdateTimeLabels` et `HeroesGameTime` lisent
  `TimerGetRemaining(openTheGatesTimer)`. Si le restant est positif, le temps
  gameplay est son opposé. Sinon, c'est `TimerGetElapsed(gameTimer)` augmenté
  de `DebugGameTimeDelta()*60`. Mise à jour nominale du label : 0,2 s.
- GameLib.galaxy:16316–16331 : `gameStarted=true`, événement `GatesOpen`, puis
  `TimerStart(gameTimer, c_timerDurationInfinite, false, c_timeGame)`.
  `matchGameplayTimer` est un autre timer et n'est pas substitué.
- SupportLib_h.galaxy:127,196 : le delta et son getter sont de type `fixed`.

Empreintes des sources principales du handoff :

- UILib : `a5ddbe757a93d0019d6d17b430a5b8bf51e2e99783574e0a82a3f04e3bcd5309`.
- GameLib : `a6384749fbe8f676cbd6ccb9ec1aeac004815d37a8e1c2f8f9f8f176b2bfca09`.

`meta.t_s` et `meta.clock_kind=mission` gardent exactement leur sens P0/P1 et
replay. Aucun décalage constant n'est soustrait à ce temps. Le champ optionnel
`meta.gameplay_clock` est distinct et ne contient que :

- `status=validated` : gardes structurelles et temporelles de cette lecture ;
- `t_s` : secondes signées, fixed natif /4096, sans extrapolation murale ;
- `phase=preparation|playing` : phase prouvée, pas déduite du seul signe ;
- `timer_paused` : résultat du drapeau `TimerIsPaused` du timer sélectionné ;
- `read_window_s` : durée monotone de la lecture ciblée complète ;
- `mission_t_s` : borne mission de fin, utilisée pour la cohérence avec P0/P1.

`status=validated` n'est pas, à lui seul, une certification de recette produit.
Le champ reste absent en cas d'échec. Aucun zéro, timer prêt ou phase par défaut.
Le delta debug peut rendre négatif un temps de phase `playing` : le signe ne
remplace donc pas la phase. La KB n'utilise que le temps gameplay validé,
non négatif et de phase `playing`. Préparation, mission seule, replay, chrono
inconnu/malformé ou diagnostic hors ligne n'alimentent aucun timing HUD.

Le normaliseur élimine les clés hors contrat, notamment pointeurs et handles.
Les nouveaux tests couvrent aussi les entiers JSON démesurés sans exception de
conversion flottante. Les protections existantes des données ennemies cachées,
le seuil 0,75, le silence et les opt-ins ne sont pas modifiés.

## Chemin réellement actif, et non copies de compilation

Toutes les valeurs ci-dessous sont des RVA/offsets du seul build 98348, jamais
des adresses absolues de tas. Le profil P0/P1 valide déjà PE, build, ASLR et code.
`98348-clock.json` ajoute les empreintes des instructions natives pertinentes.
Les exports Ghidra ont été faits sur le projet existant, en lecture seule,
`-readOnly -noanalysis`, une analyse à la fois.

1. La publication native à RVA `0x1fec318` place le tableau final de fonctions
   dans `0x3b8c5c8`, à partir du tableau `0x2fa7100`. La boucle lui associe les
   index propres à `record+0x50`. Le getter `0x1fed370` retourne le nombre
   effectif `0x2fa70f0`, PAS `0x3b8c5c4` (compteur d'instructions).
2. Le chemin d'appel `0x1ff90b0` choisit une entrée dans cette table active,
   charge `record+8` dans le contexte d'exécution et appelle l'interpréteur
   `0x1ff94a0`. Celui-ci lit le bytecode à `0x3b8c920+offset` et les globals
   à `0x3d0c920+operand`. Sa borne de code utilisée est `0x3b8c904` ; limite
   native du code : `0x180000`, globals : `0x300000`.
3. Le lecteur valide l'égalité des deux racines de table, le nombre <=65536,
   les bornes de code, l'index propre et le nom exact de chaque entrée. Le nom
   seul ne prouve rien : le bytecode complet de la fonction doit aussi avoir
   l'empreinte attendue. La représentation de chaîne est celle de Storm.
4. Les trois fonctions actives sont identiques dans les six images :

| Index | Fonction | Taille | SHA-256 bytecode |
|---|---|---:|---|
| 1445 | GatesOpen timer-expires Func | 646 | `dbc8ac8484fbf3981d8d0c35227f463de94d0f47f38e94704d48b1a60d275f73` |
| 2137 | HeroesGameTime | 47 | `2f5e5926e3c10f554987d8896bf4d6f0f9c556682a43dbc9f24963f95d1c7115` |
| 4217 | DebugGameTimeDelta | 5 | `0e786727f76403557e9cd5956a58f66462752666856bf371fdf4d245998bf5f3` |

Le bytecode empreinté contient les operands globals suivants : gameTimer
`0xc988`, openTheGatesTimer `0x19e67`, gameStarted `0x19e77`, delta fixed
`0x10e56f`. Les accès d'interpréteur aux globals par référence et par valeur,
l'appel de la fonction 4217 et la multiplication fixed par 60 correspondent
aux sources primaires. Les anciennes métadonnées trouvées par scan de noms
ne servent à aucune résolution de production.

### Timers et état de démarrage

- La racine de slots `0x4020970` doit désigner la table native `base+0x4020980`.
  Index ushort >1, génération non nulle, 16 octets par slot ; génération de
  slot égale au handle, références positives et type `0x13`.
- Le timer doit aussi figurer exactement une fois dans la liste enregistrée
  effectivement parcourue par l'updater `0xaee5b0` : nombre `0x2f72670`, tableau
  `0x2f72680`. Budget explicite <=8192 timers ; au-delà, refus et non scan libre.
- Pointeur canonique/aligné, vtable `base+0x26b4f18`, référence propre à +8 égale
  au handle. La native de type `0xae8150` retourne 19 ; taille objet : 0x28.
- TimerStart `0xaee930` écrit répétition +0x10, type d'horloge +0x14, durée +0x1c,
  elapsed=0 à +0x18 et remet les drapeaux +0x11/+0x12 à zéro. TimerIsPaused
  `0xc29fa0` et TimerPause `0xc29ff0` utilisent +0x11. L'updater `0xaee5b0`
  ignore les expirés (+0x12), n'ajoute pas d'elapsed aux pausés et marque
  l'expiration lorsque elapsed atteint ou dépasse la durée. Il ne clampe pas
  systématiquement elapsed : un petit dépassement de la durée est donc admis,
  avec budget conservateur d'une seconde maximum.
- Elapsed est directement lu par `0xc29db0` à +0x18 ; Remaining `0xaee520`
  soustrait elapsed à la durée +0x1c. Les wrappers Galaxy et la table dispatch
  ont aussi été identifiés dans le binaire, sans invoquer de native du client.
- Préparation : restant gates >0, horloge game, pas expiré, gameStarted=false,
  gameTimer encore à elapsed/durée=0. Après portes : gameStarted=true,
  gameTimer infini (-4096), horloge game, pas expiré ; gates fini et expiré.
  Ces gardes permettent le vrai zéro démarré mais rejettent le zéro/zéro initial.

La pause de timer est démontrée statiquement et testée synthétiquement. Aucune
pause/reprise réelle de partie n'a été observée : ce drapeau ne certifie pas
la disponibilité d'une commande Pause ni un état global de pause du client.

## Cohérence temporelle

Le lecteur relit exactement toutes les dépendances : racines, tailles, index,
noms/code actifs, liste enregistrée, globals, slots et objets timer. Tout octet
changé entraîne un refus. Les horloges mission encadrantes doivent être
monotones avec écart <=0,125 s ; la durée monotone doit également être <=0,125 s.
Le contrôle mural subsiste quand le temps mission est à l'arrêt. Pas de retry
qui masquerait une transition, ni cache de pointeurs entre parties.

Cette double lecture ne constitue PAS un verrou ni un instantané atomique :
un changement aller-retour entre lectures peut rester indétectable. Le contrat
annonce une fenêtre ciblée et des contrôles de cohérence, pas une synchronisation
absolue. La liste enregistrée entière fait partie de la seconde passe : une
création/destruction concurrente de timer entraîne un refus conservateur.

Un `DumpBackend` est explicitement non atomique. `read()` le refuse, même si
sa relecture locale dure moins d'une milliseconde. `inspect_saved()` est un
accès de diagnostic séparé, statut `offline_non_atomic`, que le normaliseur
et la KB ne peuvent accepter comme chrono validé.

## Exercice des captures et pixels réellement observés

Six jeux module/tas/manifeste privés existants ont été lus par le nouveau
résolveur. Les nombres ci-dessous viennent de ces octets, PAS de fixtures
synthétiques. Les PNG avant/après sont sélectionnés depuis `frames.jsonl` par
leurs horodatages, hors de la fenêtre du dump, puis relus visuellement.

| Carte / dump | Fenêtre dump (s murales) | HUD avant → après | Résultat structurel, non synchronisé |
|---|---:|---|---|
| Volskaya008 | 2,533 | -00:30 → -00:27 | préparation -27,8125 s |
| Volskaya037 | 2,590 | -00:01 → 00:01 | refus : gameStarted module=0, timer tas déjà positif |
| Volskaya065 | 2,889 | 00:27 → 00:30 | playing 29,6875 s |
| Braxis008 | 3,117 | label vide → -00:34 | refus : zéro/zéro, début non prouvé |
| Braxis037 | 3,199 | -00:09 → -00:05 | préparation -6,875 s |
| Braxis065 | 3,138 | 00:18 → 00:22 | playing 20,9375 s |

Toutes les tentatives de publication via `read()` sont refusées pour les six
ensembles. Le refus Volskaya037 est une preuve utile de la déchirure du dump,
pas un bug à contourner par substitution de mission ou lecture d'un replay.
Les bornes des PNG sont compatibles avec les quatre diagnostics acceptés mais
ne les placent pas à un même instant. La planche Braxis montre également
-00:01, -00:00, 00:00 puis 00:01 : le signe de préparation ne doit pas disparaître
par simple arrondi. Aucun formateur du texte exact HUD n'est livré ici.

Ces captures sont en observateur avec `local_player=null` ; aucun bot n'est
attribué à un humain. Braxis n'est qu'une contre-épreuve technique, jamais une
recette Dragon. Le repli replay protocol91756 pour build98348 reste une limite
des références de recette ; le lecteur ne consomme aucun replay.

Preuves privées du run : `out/p2/active-clock-audit.json`,
`reader-saved-evidence.json`, `hud-brackets.json`, `hud-brackets.png`, exports
`vm-static/` et journaux RED/GREEN. Aucun dump, PNG source, nom de compte,
adresse absolue de tas ou handle réel n'est ajouté à Git.

## Tests, revue et recette restant nécessaire

Tests hermétiques : préparation, zéro ambigu, zéro réellement démarré,
progression, delta debug positif/négatif, pause/reprise de timer, reset,
ASLR, mauvais profil/signature/nom/code/index/bornes/type/génération/propriétaire,
absence d'enregistrement actif, petite sur-expiration native, lectures déchirées,
fenêtres temporelles, rejet des dumps roulants, confidentialité, entiers JSON
malformés, séparation replay/mission et annulation d'un conseil en vol.

Une première revue indépendante a exécuté les 94 tests alors présents sur les
deux Python et reproduit les six diagnostics/refus. Elle a demandé la gestion
des entiers JSON démesurés et ce document ; le débordement a été reproduit RED
puis corrigé et les tests de déchirure/fraîcheur ont été renforcés. Aucun avis de
livraison finale sans recette temporelle n'est déduit de cette revue.

La seconde revue indépendante a rendu PASSED pour le code actuel, exécuté
102 tests verts et réexercé les six ensembles sauvegardés. Elle confirme
explicitement que la recette HUD/lecteur reste bloquante pour la livraison.
Suggestions non bloquantes conservées : simulation complète de la boucle CLI
du collector et tests de frontières supplémentaires du budget de liste/expiry.

La résolution VM hors ligne n'est plus le blocage. Il reste à coordonner UNE
courte recette du lecteur ciblé sur Volskaya : préparation, passage des portes,
zéro réellement démarré et au moins deux instants après portes. Prévoir reset
ou changement de partie si disponible ; ne pas exiger une pause indisponible.
Les PNG doivent être horodatés et encadrés, et les taux de rejet/latences réels
mesurés, avec la cadence 0,2 s du HUD explicitement distinguée du budget 125 ms.
Aucun besoin d'un nouveau dump roulant de plusieurs gigaoctets.

`etudes/rea/scripts/capture_clock.py` est prêt pour cette recette, mais n'a été
exercé qu'avec mémoire synthétique et `--help`, sans ouvrir de processus réel.
Il exige `--live`, est borné à 120 s, n'enregistre que les lectures ciblées du
lecteur et leurs bornes, conserve les refus, écrit exclusivement un nouveau
JSONL privé dans `out/` et ne capture aucun écran. Il doit être couplé au sampler
HUD coordonné, sans prise de premier plan automatique. Il ne lance pas de partie,
ne modifie aucune mémoire et ne produit aucune certification HUD automatique.

Le commit de branche conserve cette implémentation sans l'intégrer prématurément.
Après recette seulement : corriger d'éventuelles divergences réelles, revue
finale, intégration et vérification remote de main. Ne pas libérer le
lot positions en clôturant prématurément cette carte.
