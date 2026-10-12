# Étude — accès à l'API de Groco : faut-il un wrapper ?

**Date :** 12/10/2026 · **Statut :** étude close, wrapper livré (`grocoapi/`)

## 1. Ce qu'est l'API

`https://api.ai.ranoc.org` — **« Proxified API » v0.2.0** (Groco), doc interactive
en `/docs/` (Scalar), schéma exploitable en `/openapi.json` (22 Ko, OpenAPI 3.1).
Concept : une **gateway compatible OpenAI** qui expose les abonnements LLM de
Groco (comptes **Claude**, **ChatGPT/Codex**, **Cursor**, connectés par SSO
Google) derrière un token `gw_…` par utilisateur. Autrement dit : pas de clé
API marchande à acheter, c'est l'abonnement de Groco qui est mutualisé.

### Surface utile (30 routes)

| route | rôle |
|---|---|
| `POST /v1/chat/completions` | **le cœur** — compatible OpenAI (model, messages, stream) + extensions : `account`, `reasoning_effort`, `session_id`, `async` |
| `GET /v1/models` | comptes + modèles utilisables (format OpenAI) |
| `GET /v1/accounts` | comptes LLM rattachés, usage du jour, limites |
| `GET /v1/accounts/{id}/limits` | quota gateway + limite d'abonnement |
| `POST /v1/accounts/{id}/test` | test d'un compte avec un petit prompt |
| `POST /v1/sessions` + `GET /v1/sessions/{id}/files/*` | sessions d'agent et fichiers produits |
| `GET /v1/calls`, `/v1/calls/stats`, `/v1/calls/{id}` | historique, stats 30 j, polling des jobs async |
| `…/login`, `…/import` | rattachement SSO / import de session CLI (côté Groco) |
| `/admin/*` | gestion utilisateurs/tokens (Groco) |

Auth : `Authorization: Bearer gw_…`.

### Vérifications faites (12/10/2026)

- **Token** : la bonne variante est celle **sans `a` final** (testée : `GET /v1/me`
  → 200, `{"name":"Nauss","role":"user","scopes":["chat"]}`). La variante avec
  `a` renvoie 401 « Token invalide, expiré ou révoqué » → **oublier la typo**.
- **Santé** : `/health` → `{"ok":true}`.
- **Comptes** : `GET /v1/accounts` → `[]` ; `/v1/models` → `data: []` ;
  `POST /v1/chat/completions` → 404 « Aucun compte LLM correspondant ».
  **Tant que Groco n'a pas rattaché un compte LLM (SSO), aucun appel modèle ne
  passera.** Le token, lui, fonctionne déjà.

## 2. Faut-il un wrapper ? OUI — mais fin

L'API étant compatible OpenAI, on *pourrait* l'attaquer avec le SDK officiel
(`openai` + `base_url`). Ce qu'un wrapper fin apporte mal tout ça :

1. **Centralisation de la config** — une seule source (`.env` racine, jamais
   versionné) pour URL + token, partagée par tous les sous-projets. C'était une
   exigence : pas de clés éparpillées.
2. **Les extensions maison** — `account` (choisir le compte), `reasoning_effort`,
   `async` + polling `/v1/calls/{id}`, `session_id` : absentes du SDK officiel,
   passées en `extra_body` sinon. Un wrapper les rend explicites et typées.
3. **La politique d'appel du coach** — timeouts courts, retries bornés, erreurs
   lisibles, format de messages normalisé (c'est la boucle temps réel qui
   appelle, pas un humain).
4. **Zéro dépendance** — stdlib uniquement (`urllib`), ~200 lignes. Le jour où il
   faut du streaming SSE ou du vision, on étend — pas de dette.

**Ce qu'on ne fait PAS** : réécrire un SDK. Le wrapper est une façade ; si un
jour un composant veut le SDK officiel, il peut brancher `base_url` dessus sans
nous.

## 3. Limites découvertes — état (mis à jour 12/10/2026)

1. **Pas de vision dans le schéma** : `messages[].content` est typé `string`,
   `additionalProperties: false`. **Sans objet pour l'instant** : la couche
   stats passe par la lecture mémoire (triggers `gt_*`, voir
   `etudes/rea/ETUDE.md` §13) — valeurs exactes, sans capture d'écran. Le
   sujet ne reposerait que si l'on voulait des infos visuelles non couvertes
   par la mémoire (positions/HP/ults instantanés) sans décoder les structures
   `CUnitStatusHealth` / `CUnitPositionData` — or c'est la suite prévue de la
   descente mémoire, prioritaire.
2. **Aucun compte rattaché** : il faut que Groco connecte au moins un compte
   (login SSO ou import de session CLI) et active des modèles. Ensuite
   `GET /v1/models` affichera la sélection réelle.

## 4. Livrable

`grocoapi/` — client minimal (zéro dépendance) :
- config : arguments > variables d'env > `.env` racine ;
- `me()`, `health()`, `accounts()`, `models()`, `limits(account_id)`,
  `chat(messages, model=…, account=…, reasoning_effort=…, timeout=…)` ;
- `chat_async(...)` + `poll_call(id)` pour les grosses analyses (hors boucle
  temps réel) ;
- `smoke.py` : test de bout en bout (health → me → models → chat si dispo).

**Verdict : le wrapper est une bonne idée, à condition de rester une façade
mince.** Il est livré et vérifié sur l'API réelle ; le seul blocage pour le
premier appel modèle est le rattachement d'un compte, côté Groco.
