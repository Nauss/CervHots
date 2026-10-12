"""grocoapi — client minimal pour l'API de Groco (gateway Proxified, compatible OpenAI).

Zéro dépendance (stdlib uniquement). Configuration, par ordre de priorité :
1. arguments explicites (base_url, token)
2. variables d'environnement GROCO_API_URL / GROCO_API_TOKEN
3. fichier `.env` à la racine du dépôt (jamais versionné)

Voir etudes/api/ETUDE.md pour le contexte et les limites connues.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://api.ai.ranoc.org"
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class GrocoError(RuntimeError):
    """Erreur API : status HTTP + message de la passerelle."""

    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status} : {message}")
        self.status = status
        self.message = message


def _load_env_file(path: Path = _ENV_FILE) -> dict:
    """Charge un .env minimaliste (KEY=VALUE, # commentaires)."""
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


class GrocoClient:
    def __init__(self, base_url: str | None = None, token: str | None = None,
                 timeout: float = 60.0):
        env = _load_env_file()
        self.base_url = (base_url
                         or os.environ.get("GROCO_API_URL")
                         or env.get("GROCO_API_URL")
                         or DEFAULT_URL).rstrip("/")
        self.token = (token
                      or os.environ.get("GROCO_API_TOKEN")
                      or env.get("GROCO_API_TOKEN"))
        if not self.token:
            raise GrocoError(0, "aucun token : GROCO_API_TOKEN ou .env requis")
        self.timeout = timeout

    # ------------------------------------------------------------- HTTP

    def _request(self, method: str, path: str, body: dict | None = None,
                 timeout: float | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                message = json.loads(raw).get("error", {}).get("message", raw)
            except json.JSONDecodeError:
                message = raw
            raise GrocoError(e.code, message) from None

    # ------------------------------------------------------------- info

    def health(self) -> dict:
        return self._request("GET", "/health", timeout=10)

    def me(self) -> dict:
        return self._request("GET", "/v1/me")

    def accounts(self) -> list[dict]:
        return self._request("GET", "/v1/accounts").get("data", [])

    def models(self) -> list[dict]:
        """Comptes + modèles utilisables (format OpenAI)."""
        return self._request("GET", "/v1/models").get("data", [])

    def limits(self, account_id: str) -> dict:
        return self._request("GET", f"/v1/accounts/{account_id}/limits")

    # ------------------------------------------------------------- chat

    def chat(self, messages: list[dict], model: str | None = None,
             account: str | None = None, reasoning_effort: str | None = None,
             session_id: str | None = None, timeout: float | None = None,
             **extra) -> dict:
        """Un appel /v1/chat/completions (non streamé).

        messages : [{"role": "user"|"assistant"|"system", "content": str}, ...]
        Renvoie la réponse OpenAI (choices[0].message.content).
        """
        body: dict = {"messages": messages, "stream": False}
        if model:
            body["model"] = model
        if account:
            body["account"] = account
        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort
        if session_id:
            body["session_id"] = session_id
        body.update(extra)
        return self._request("POST", "/v1/chat/completions", body, timeout=timeout)

    def ask(self, prompt: str, system: str | None = None,
            model: str | None = None, **kw) -> str:
        """Raccourci : un prompt utilisateur -> le texte de réponse."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self.chat(messages, model=model, **kw)
        return resp["choices"][0]["message"]["content"]

    # ------------------------------------------------------------- async

    def chat_async(self, messages: list[dict], **kw) -> dict:
        """Lance un job async ; renvoie l'objet call (avec id) à poller."""
        body = {"messages": messages, "stream": False, "async": True}
        body.update({k: v for k, v in kw.items() if v is not None})
        return self._request("POST", "/v1/chat/completions", body)

    def poll_call(self, call_id: str, interval: float = 2.0,
                  timeout: float = 300.0) -> dict:
        """Attend la fin d'un job async via /v1/calls/{id}."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            call = self._request("GET", f"/v1/calls/{call_id}")
            if call.get("status") in ("done", "error", "failed", "completed"):
                return call
            time.sleep(interval)
        raise GrocoError(0, f"job {call_id} toujours en cours après {timeout}s")
