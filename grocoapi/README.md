# grocoapi — client de l'API de Groco

Façade mince (zéro dépendance, stdlib uniquement) vers la gateway **Proxified
API** de Groco (`https://api.ai.ranoc.org`, compatible OpenAI). Étude et
contexte : `etudes/api/ETUDE.md`.

## Configuration

Une seule source de clés, à la racine du dépôt (`.env`, jamais versionné) :

```dotenv
GROCO_API_URL=https://api.ai.ranoc.org
GROCO_API_TOKEN=gw_…            # le token de l'utilisateur
```

Priorité : arguments explicites > variables d'environnement > `.env` racine.

## Usage

```python
from grocoapi import GrocoClient

c = GrocoClient()
c.me()                       # identité
c.models()                   # modèles dispo (format OpenAI)
c.accounts()                 # comptes LLM rattachés + usage

# appel simple
réponse = c.ask("Résume cette partie en une phrase.")

# appel complet (messages, modèle, compte, effort de raisonnement)
rep = c.chat(
    [{"role": "system", "content": "Tu es un coach HotS."},
     {"role": "user", "content": "Que faire maintenant ?"}],
    model="claude-azqc/sonnet", timeout=30,
)
texte = rep["choices"][0]["message"]["content"]

# gros job hors boucle temps réel
call = c.chat_async(messages, model="…")
résultat = c.poll_call(call["call_id"])
# status final « ok » ; réponse sous résultat["result"]
```

## Test

```bash
python grocoapi/smoke.py            # health → me → models → accounts → chat
```

## État vérifié (15/10/2026)

- **Pas de vision** : `messages[].content` est typé `string` côté gateway.
  Sans objet pour l'instant : la couche stats passe par la lecture mémoire
  (pas de captures d'écran) — voir `etudes/api/ETUDE.md` §3.
- **Comptes désormais disponibles** : les appels réels synchrones et async
  passent. Les identifiants sont au format `compte/modèle` ; utiliser la liste
  actuelle de `c.models()` plutôt qu'inventer un nom de modèle nu.
- **Pas de JSON garanti côté API** : `response_format` et les autres propriétés
  non listées par le schéma sont interdits. `cerveau/` valide la sortie du modèle.
- **Async** : acceptation `{call_id, session_id, status}`, polling terminal
  `status: ok`, réponse dans `result`.
