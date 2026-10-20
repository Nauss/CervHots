# Recette diagnostique silencieuse

Outil : `python -m cerveau.diagnostic_session --help`. Sans `--live`, uniquement
précontrôle local : dépendance mpyq (même runtime_dependencies que les collecteurs),
KB SQLite ouverte en lecture seule et explicitement fermée, profils JSON,
protocole installé et map_timings. Pas de processus, compte, chat ou audio.
Ce contrôle ne qualifie ni les archives de carte ni une acquisition.

Le worktree doit disposer de `kb/data/kb.db` (fichier ignoré, copie du runtime
principal), de ses profils versionnés et des dépendances installées dans
l'interpréteur absolu du coach. Ne pas présumer un `tts/.venv` local au worktree.
Le cache Battle.net est vérifié comme dossier uniquement, pas comme observation.

En recette privée autorisée, l'opérateur fournit --live et trois chemins absolus :
--player-file (identité locale privée jamais exportée), --output-dir (session
inédite), --stop-file. Exemple :

    C:/root/dev/AI/CervHots/tts/.venv/Scripts/python.exe -m cerveau.diagnostic_session --live --player-file <privé> --output-dir <session-absolue-inédite> --stop-file <STOP-absolu> --max-seconds 300 --interval 30

Un verrou exclusif `diagnostic-session.lock` dans le parent du dossier de session
empêche deux collecteurs partageant ce répertoire. Un crash laisse le verrou :
vérifier l'absence du processus avant de l'enlever manuellement. Le STOP n'est
jamais effacé par l'outil. Durée maximale 1800s, intervalle minimal15s, pas de
rattrapage. Pas de GUI/audio, pas de collecte brute ni lecteur secondaire.

Un backend est conservé entre les cycles réussis et fermé au refus, changement
de partie, STOP ou limite. La prévalidation initiale n'est jamais réutilisée comme
observation du cycle : le Pipeline acquiert après l'initialisation du coach. La source
est réellement make_source -> read_current -> snapshot -> tactical_key -> Pipeline.
Aucun gate remplacé, aucun reçu sérialisé/rechargé, aucune ouverture de scope.
Le coach utilise les paramètres existants (confiance0.75, âge20s, cooldown15s).
Budgets WHOLE inchangés :125ms,8192requêtes,1MiB.

## Journal minimisé events.jsonl

Chaque entrée comporte cycle, temps écoulé monotone, séquence et version.
Phases : ouverture, prévalidation, acquisition du cycle, KB, API, fraîcheur.
Acquisition : étape atteinte, coût WHOLE mesuré avant émission du journal,
requêtes/octets, issue, code de refus provenant exclusivement d'un vocabulaire
fermé et catégorie de garde. Les codes non inventoriés deviennent unknown_refusal,
jamais le message d'exception. Une catégorie n'est pas une preuve rétrospective.
Les motifs des familles facultatives restent indépendants du cœur valide.

Observation : temps mission et éventuellement gameplay, pseudonymes de carte,
héros et session (HMAC à sel aléatoire non persisté), slots0–9, équipe, vie/niveau,
respawn et vitaux alliés bornés issus du normaliseur. Pas de nom de joueur,
compte, match_id brut, pointeur, mémoire brute, prompt, clés ou reçu. Seules les
familles présentes sont listées ; leur absence ne signifie jamais zéro.

Fraîcheur : âge, cause age/key_changed/age_and_key/fresh, noms de familles de clé
sur liste fermée, booléen changement de session. Aucun contenu de clé ni diff de
valeurs. La clé tactique et la décision de refus restent inchangées.
Proposition puis issue sont corrélées au cycle ; seuls les conseils dont tous les
mots appartiennent au petit lexique tactique statique peuvent être journalisés.
Le reste est omis (`text_withheld=true`), y compris identité locale connue,
URL, mail, nombres, contrôles Unicode et tokens étrangers. Ce choix conservateur
limite volontairement la recette sémantique ; il ne modifie pas le conseil du
coach. Les motifs API sont bornés et leur corps n'est jamais journalisé.
Les alias sont propres à cette exécution : pas de rapprochement intersession
prétendu sans scénario opérateur et temps observé concordants.

L'écriture est synchrone et hors mesure WHOLE ; un échec IO interrompt la recette
plutôt que continuer sans traces. Les appels normaux sans journal n'écrivent rien.
Le coût de journalisation peut légitimement rendre une proposition trop âgée ;
il ne donne aucune permission de fraîcheur supplémentaire.

## Recette et limites

Avant match : précontrôle/--help réels, absence de lecteur concurrent, STOP,
restauration audio laissée à l'opérateur unique. Menu/simulation retirée doit
produire un refus explicite sans appel coach. En match privé : obtenir au moins
un cœur normalisé dans les budgets ; un silence ou confiance faible n'est pas
un défaut. Si une proposition existe : conserver son issue et, en cas de refus,
la cause de fraîcheur et les familles modifiées, sans chercher à l'accepter.
STOP pendant attente/API doit empêcher toute mémorisation/livraison ultérieure.
Le retrait/changement de partie invalide l'ancienne proposition. Aucun signal de
fin `game_over` non qualifié n'est ajouté.

Tests hors ligne : `python -m unittest discover -s tests` (créer le dossier
ignoré out nécessaire aux tests historiques de découverte). Les tests synthétiques
ne constituent jamais une acquisition réelle. Les journaux anciens ne contiennent
pas les données nécessaires pour reconstruire86 causes de refus ou21 champs
modifiés ; aucune attribution de carte ou correction de clé n'est faite ici.
