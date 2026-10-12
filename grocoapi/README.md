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
    model="claude-sonnet-4-5", reasoning_effort="low", timeout=30,
)
texte = rep["choices"][0]["message"]["content"]

# gros job hors boucle temps réel
call = c.chat_async(messages, model="…")
résultat = c.poll_call(call["id"])
```

## Test

```bash
python grocoapi/smoke.py            # health → me → models → accounts → chat
```

## Limites connues (12/10/2026)

- **Pas de vision** : `messages[].content` est typé `string` côté gateway —
  les images ne passent pas (à demander à Groco).
- **Aucun compte LLM rattaché** à l'utilisateur tant que Groco n'a pas fait le
  login SSO : tout appel modèle renvoie 404 « Aucun compte LLM correspondant ».
