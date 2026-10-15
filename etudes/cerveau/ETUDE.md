# Étude — cerveau Groco et orchestration

**Date :** 15/10/2026 · **Statut :** branchement livré, parcours réel validé jusqu'au WAV sans lecture sonore.

## 1. API relue sur le service réel

Schéma actuel consulté sur `/openapi.json` : `POST /v1/chat/completions` accepte
`messages` (contenus string), `model`/`account`, `reasoning_effort`, `session_id`,
`stream`, `async`. Les propriétés supplémentaires sont interdites : pas de
`response_format` ou de `max_tokens` à envoyer. Le format de sélection est
`compte` ou `compte/modèle`, pas un nom de modèle nu.

Santé et authentification vérifiées, listes de comptes/modèles désormais non
vides : l'ancien blocage du 12 octobre a disparu. URL et token sont centralisés
dans le `.env` racine, exclu de Git. Le modèle local choisi et vérifié est
`claude-azqc/sonnet`, remplaçable par configuration.

Un chat réel simple a renvoyé « Bonjour » en 11,77 s. Le chemin d'erreur avec un
compte inexistant a renvoyé HTTP 404, correctement encapsulé en `GrocoError`.
Les erreurs réseau et JSON sont également structurées.

L'asynchrone a été vérifié sur le service : l'acceptation contient `call_id`
(et non `id`), le polling atteint `status: ok`, et le résultat se trouve sous
`result`. Ce mode n'est pas utilisé dans la boucle de coaching.

## 2. Assemblage

`cerveau/` normalise les deux sorties existantes de hotstate, construit le
briefing via `kb.briefing.build`, appelle Groco sans session persistante et
valide la décision localement. La mémoire bornée contient seulement les
conseils livrés. Le mode console est silencieux ; WAV et Mumble sont explicites.

Pour le replay : coupure temporelle avant le prompt, suppression du score final,
état de vie/niveaux observés, compositions, 24 derniers événements, positions
anonymisées et mises à la même échelle que les événements héros.

Pour la mémoire : seuls les trois compteurs validés sont retenus. Correction
associée dans `reader.py` : ne plus reprendre les records de gabarit lorsque
aucun record vivant n'est trouvé. Une sentinelle comme 32755 doit rester une
absence de donnée, jamais devenir un nombre de morts.

La boucle n'a qu'un appel en vol et rejette les réponses trop vieilles ou
invalidées par une modification tactique. Le PCM est préparé avant l'attente
du silence et avant la dernière vérification de fraîcheur ; il n'est pas
resynthétisé au moment de l'envoi.

## 3. Essai réel effectué

Source : replay du compte, **3 septembre 2026 à 23:09:05, Le val maudit**,
build 97771, durée extraite 1195,06 s. Aucune lecture du processus du jeu.

Observation à **73,5 s**, équipe 0 : Kael'thas et Ragnaros morts, Varian mort
côté adverse. Le modèle a produit, avec auto-évaluation 0,8 :

> Vous êtes 3 contre 4 : ne forcez pas le combat, reculez sous votre fort et attendez le retour de Ragnaros et Kael'thas.

Le parcours CLI complet, avec le seuil par défaut de 0,75, a synthétisé ce conseil
avec Piper. WAV relu : **PCM signé 16 bits, 48 000 Hz, mono, 7,72 s**, contenu
non silencieux (RMS normalisé 0,1545). Aucun son joué et aucune connexion Mumble.

Contrôle négatif réel : seulement les trois compteurs globaux → le modèle s'est
tu. Compte LLM inexistant → `erreur_api_404`, sortie CLI non nulle. Les premiers
conseils génériques à faible confiance ont également été bloqués, sans fichier
WAV ; ce comportement est intentionnel.

## 4. Ce qui n'a pas été vérifié

- Diffusion de ce nouveau parcours dans un vrai canal Mumble : pas d'autorisation
  de lecture sonore donnée pour cet essai ; adaptateur couvert par tests sans son.
- Coaching sur processus HotS vivant : pas lancé sans décision explicite.
- Le lecteur mémoire ne fournit pas encore les informations tactiques détaillées
  présentes dans les replays ; l'API du cerveau ne pallie pas cette lacune.

## Sources et commandes

- Contrat fournisseur relu sur `https://api.ai.ranoc.org/openapi.json`.
- Contrats du dépôt : `hotstate/schema/game_state.schema.json`,
  `hotstate/triggers_map.json`, `tts.Speech`, `mumblebot.MumbleBot`.
- Tests : `python -m unittest discover -s tests -v`.
- Vérification du service : `python -m cerveau --check`.
- Usage et paramètres reproductibles : `cerveau/README.md`.
