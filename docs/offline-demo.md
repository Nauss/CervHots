# Démonstration produit hors ligne et silencieuse

Depuis la racine du dépôt, sous **Windows local**, Python 3.12 ou 3.14 :

```bash
python -B -m cerveau.offline_demo --help
python -B -m cerveau.offline_demo --destination C:/chemin/existant/demo-SYNTHETIC-neuve
```

Le **parent doit déjà exister**. La destination doit être absolue, locale et
neuve : refus d'un fichier/dossier existant, lien, jonction ou ancêtre reparse,
chemin réseau, parent manquant ou traversée `..`. Aucun écrasement, suppression
ou reprise automatique. Une sortie interrompue est conservée : choisir une
**autre destination**. Les garanties de parcours réutilisent le catalogue Windows ;
les autres OS refusent l'exécution (l'aide reste disponible).

Aucun HotS, compte, clé, fichier d'identité, réseau ou dépendance optionnelle de
replay n'est nécessaire. Aucun navigateur n'est ouvert et aucun son n'est joué.
Le résultat JSON sur stdout est un reçu de démonstration, **pas un reçu natif**.
L'import public `cerveau.Coach` reste compatible, mais n'est plus chargé par
l'import du paquet : ce mode ne charge ni Coach ni client API. Les décodeurs purs
et profils locaux déjà utilisés par les validateurs historiques sont réutilisés ;
le backend OS `hotstate.reader` et la collecte `hotstate.live` ne sont pas importés.

## Ce qui est exercé

La commande invente trois journaux minuscules de trois lignes et un marqueur de
session sans journal, tous explicitement **SYNTHETIC**, sans identité privée.
Elle ne lit aucun ancien journal et ne recherche aucune session de l'utilisateur.
Les horloges et identifiants de forme documentaire sont fixes et fictifs.

| Cas | Résumé historique attendu | Ne signifie jamais |
| --- | --- | --- |
| `absent` | Journal indisponible, catalogue `absent` | Zéro observation valide |
| `refused` | Identité de comparaison absente, résumé `refused` | Valeur récupérée depuis un autre cas |
| `unknown` | Observation enregistrée, sélection absente : recharge `unknown`, valeur null | Toutes les familles sélectionnées ou recharge zéro |
| `zero` | Recharge locale fictive réellement égale à 0 dans le journal ; âge original 0,025 s | Sort lançable, reset observé ou zéro natif nouvellement mesuré |

Les charges restent inconnues/null ; le slot est une **instance native**, pas un
bouton HUD. Aucun conseil n'est produit. `current_permission=false` partout où
ce champ est exposé ; aucune émission de reçu d'acquisition.

Les **mêmes API produit** sont composées :

- `session_diagnosis.run` : équivalent `cerveau.passive_session --diagnose` ;
- `native_history.run` : équivalent `--summarize` ;
- `session_html.build/render` : contenu de `--report-html`, écrit exclusivement
  sous les gardes de la démonstration. Le publieur par renommage de la CLI HTML
  n'est pas utilisé : les parents Windows sont épinglés sans partage d'écriture
  ni suppression ; aucun affaiblissement des gardes pour permettre un renommage ;
- `session_catalog.run` : `--catalog`, uniquement sur les quatre cas créés ;
- `catalog_integrity.run` : `--verify-catalog`, en lecture seule.

Sorties : `SYNTHETIC.txt` décrit la provenance fictive ; `synthetic-sessions/`
contient les cas ; `reports/<cas>/{diagnosis,summary,html}/` contient JSON, texte
et HTML existants ; `catalog/INDEX.html` relie les rapports de catalogue et
`catalog/COMPLETE.json` inventorie les octets. Ouvrir les HTML **manuellement** si
souhaité, en conservant ce contexte SYNTHETIC : leurs schémas minimisés restent les
schémas historiques existants et ne constituent aucune attestation de provenance.
`demo.json` récapitule les codes et la vérification. Les chemins source/identités
ne sont pas réimprimés ; aucune copie de données privées n'entre dans Git.

## Codes et bornes

- **0** : parcours terminé avec tous les codes attendus, catalogue vérifié ;
- **1** : destination refusée, erreur d'E/S ou résultat de composant inattendu ;
  stdout vide, message fermé sur stderr. Conserver toute sortie partielle ;
- **2** : arguments invalides, message fermé sans écho d'argv.

Le code du catalogue est volontairement **1** (absence et refus démontrés), celui
de sa vérification **0** : intégrité locale n'est pas admissibilité des données.
Diagnostic : absent=1, autres=0. Résumé/HTML : absent/refused=1, unknown/zero=0.
`demo.json.commands` conserve ces résultats. Pour HTML le code est dérivé de
l'état produit `build`, pas d'une invocation du publieur CLI.

Quatre cas fixes, trois journaux × trois lignes, aucun paramètre d'expansion.
Les bornes des parseurs/catalogue existants restent inchangées (4 Mio/journal,
10000 lignes, 64 Kio/ligne ; profondeur 4, 1024 entrées, 64 sessions, 16 Mio lus
au catalogue). La démonstration est testée à moins de 512 Kio de fichiers produits.
Octets déterministes entre destinations neuves et Python 3.12/3.14 ; aucune
métadonnée variable dans les fichiers (horloges fixes documentaires, pas l'heure
courante). Les timestamps du système de fichiers ne font pas partie de ce contrat.
Publication exclusive fichier par fichier, **pas de transaction atomique du dossier**.
Seul le marqueur du catalogue bénéficie du protocole d'intégrité existant.

## Ce qui n'est JAMAIS démontré

Ni lecture mémoire/native réelle, ni démarrage/fermeture du lecteur, ni STOP réel,
ni activité actuelle, exclusivité du jeu ou permission CURRENT. La limite
`session_limit` du journal est fictive. Ni validation HUD, carte/build actifs,
comparaison indépendante, coût/WHOLE réel, match ou qualification nouvelle.
Braxis reste non qualifié ; cooldown réel qualifié zéro seulement, charges
inconnues, contexte hérité inconnu. Les profils documentaires ne prouvent pas
l'état du jeu ni l'absence d'ABA.

## Régressions

Tests dédiés : `python -B -m unittest tests.test_offline_demo -v`.
Les gardes en sous-processus interdisent import backend/API/audio/réseau,
construction des décodeurs natifs et émission de reçu. Les tests adversariaux
couvrent refus de chemin, non-écrasement, jonctions Windows réelles, concurrence,
échec d'E/S et libération des handles ; un privilège symlink manquant est un skip
explicite, jamais une réussite simulée.

Pour les suites complètes, les dépendances replay préexistantes sont nécessaires :

```bash
export TMPDIR=C:/Users/Nauss/AppData/Local/hermes/cache/scratch
export TEMP="$TMPDIR" TMP="$TMPDIR" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
uv run --offline --no-project --python 3.12 --with mpyq --with heroprotocol python -B -m unittest discover -s tests -v
uv run --offline --no-project --python 3.14 --with mpyq --with heroprotocol python -B -m unittest discover -s tests -v
```

Exécuter **séquentiellement** : certaines suites existantes partagent un mutex
Windows de production. Vérifier `tempfile.gettempdir()` pour chaque runtime avant
les suites ; aucune utilisation de `Local/Temp`.
