"""Contexte statique observé dans les buffers initData, jamais des valeurs tactiques.

Le protocole Blizzard décode le buffer ; les noms/comptes ne sortent pas du
résolveur. Les héros IA choisis après le lobby peuvent rester inconnus.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path


def _text(value):
    return value.decode("utf-8") if isinstance(value, bytes) else value


def context_from_initdata(data: dict, player_name: str) -> dict:
    """Valider un contexte 5v5 complet et identifier l'équipe par userId, pas par couleur."""
    sync = data["m_syncLobbyState"]
    users = sync["m_userInitialData"]
    lobby = sync["m_lobbyState"]
    seed = lobby["m_randomSeed"]
    if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
        raise ValueError("seed initData invalide")
    slots = [s for s in lobby["m_slots"] if s["m_control"] in (2, 3)
             and s["m_observe"] == 0]
    if len(slots) != 10:
        raise ValueError("contexte autre que dix joueurs actifs")
    players, owners, ids = [], [], set()
    for slot in slots:
        index, team = slot["m_workingSetSlotId"], slot["m_teamId"]
        if (type(index) is not int or not 0 <= index < 16 or index in ids
                or type(team) is not int or team not in (0, 1)):
            raise ValueError("slot ou équipe initData invalide")
        ids.add(index)
        hero = _text(slot.get("m_hero", b"")) or None
        if hero is not None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", hero):
            raise ValueError("identifiant héros invalide")
        member = {"id": index, "team": team, "hero": hero}
        players.append(member)
        uid = slot.get("m_userId")
        if uid is not None:
            if type(uid) is not int or not 0 <= uid < len(users):
                raise ValueError("userId initData invalide")
            if _text(users[uid]["m_name"]) == player_name:
                owners.append(member)
    if (len(owners) != 1 or owners[0]["hero"] is None
            or any(sum(p["team"] == t for p in players) != 5 for t in (0, 1))):
        raise ValueError("joueur ambigu ou équipes autres que 5v5")
    handles = sync["m_gameDescription"]["m_cacheHandles"]
    if not handles or any(not isinstance(h, bytes) or len(h) != 40
                          or h[:4] != b"s2ma" for h in handles):
        raise ValueError("cache de carte initData invalide")
    return {"players": players, "local_player": owners[0],
            "composition_complete": all(p["hero"] is not None for p in players),
            "_match_seed": seed, "_cache_handles": handles}


def map_from_cache(handles, *, cache_root=None):
    """L'identifiant vient du MapScript de l'archive désignée par son hash."""
    import json
    import os

    import mpyq

    cache = Path(cache_root) if cache_root else Path(os.environ.get(
        "PROGRAMDATA", "C:/ProgramData")) / "Blizzard Entertainment/Battle.net/Cache"
    for handle in reversed(handles):
        digest = handle[8:].hex()
        path = cache / digest[:2] / digest[2:4] / f"{digest}.s2ma"
        if not path.is_file():
            continue
        try:
            script = mpyq.MPQArchive(str(path)).read_file("MapScript.galaxy")
        except (OSError, ValueError, KeyError):
            continue
        match = re.search(rb'\bmAPMapStringID\s*=\s*"([A-Za-z0-9_]+)"', script or b"")
        # Le nom du champ est précédé de libCore_gv_ : le mot complet a ce suffixe.
        if match is None:
            match = re.search(rb'_mAPMapStringID\s*=\s*"([A-Za-z0-9_]+)"', script or b"")
        if match:
            map_id = match[1].decode("ascii")
            result = {"map_id": map_id}
            names = json.loads((Path(__file__).resolve().parents[1]
                                / "kb/data/map_timings.json").read_text(encoding="utf-8"))["maps"]
            norm = lambda value: re.sub(r"[^a-z0-9]", "", value.casefold())
            canonical = {"Volskaya": "Volskaya Foundry"}.get(map_id, map_id)
            matches = [name for name in names if norm(name) == norm(canonical)]
            if len(matches) == 1:
                result["map"] = matches[0]
            return result
    return {}


class ContextProbe:
    """Recherche bornée d'initData ; plusieurs parties candidates => aucune donnée."""
    def __init__(self, player_name, *, decoder=None, map_resolver=map_from_cache,
                 active_lobby=None):
        if not isinstance(player_name, str) or not 2 <= len(player_name) <= 64:
            raise ValueError("nom du joueur attendu (2–64 caractères)")
        self.player_name = player_name
        self.anchor = player_name.encode("utf-8")
        self.decode_errors = (ValueError, KeyError, IndexError, TypeError, AttributeError)
        if decoder is None:
            from heroprotocol.decoders import CorruptedError, TruncatedError

            from .protocols import load_protocol

            decoder = load_protocol().decode_replay_initdata
            self.decode_errors += (CorruptedError, TruncatedError)
        self.decode = decoder
        self.map_resolver = map_resolver
        self.active_lobby = active_lobby
        self.map_cache = {}
        self.begin()

    def begin(self):
        self.contexts = {}
        self.candidate_addresses = {}  # Private diagnostic only, never finish() output.
        self.attempts = 0
        self.rejected = 0
        self.reason = "contexte_absent"

    def feed(self, base, data):
        offset = 0
        while self.attempts < 128:
            position = data.find(self.anchor, offset)
            if position < 0:
                return
            offset = position + len(self.anchor)
            if position < 2:
                continue
            first, second = data[position - 2:position]
            if (not 1 <= (first & 31) <= 16 or second != (len(self.anchor) & 31)
                    or first >> 5 != len(self.anchor) >> 5):
                continue
            self.attempts += 1
            try:
                # Le premier nom utilisateur est aligné après count(5)+length(8).
                raw = self.decode(data[position - 2:position - 2 + 65536])
                first = raw["m_syncLobbyState"]["m_userInitialData"][0]
                if _text(first["m_name"]) != self.player_name:
                    continue
                context = context_from_initdata(raw, self.player_name)
                key = (context["_match_seed"], tuple(context["_cache_handles"]))
                if key in self.contexts and self.contexts[key] != context:
                    self.reason = "contexte_ambigu"
                    self.attempts = 128
                    return
                self.contexts[key] = context
                addresses = self.candidate_addresses.setdefault(key, [])
                address = base + position - 2
                if address not in addresses:
                    addresses.append(address)
            except self.decode_errors:
                # Le tas contient aussi du texte et des copies partielles : ce ne
                # sont pas des contextes. Ne jamais publier un décodage incomplet.
                self.rejected += 1

    def finish(self):
        if self.active_lobby is not None and not self.active_lobby():
            self.reason = "aucun_lobby_actif"
            return {}
        if len(self.contexts) != 1 or self.attempts >= 128:
            self.reason = "contexte_ambigu" if self.contexts else "contexte_absent"
            return {}
        context = next(iter(self.contexts.values()))
        handles = tuple(context["_cache_handles"])
        if not self.map_cache.get(handles, {}).get("map"):
            try:
                self.map_cache[handles] = self.map_resolver(handles)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError, AssertionError):
                self.map_cache[handles] = {}
        result = {k: v for k, v in context.items() if not k.startswith("_")}
        result["meta"] = {**self.map_cache[handles], "context_source": "initdata_memory"}
        result["meta"]["match_id"] = hashlib.sha256(
            context["_match_seed"].to_bytes(4, "little") + b"".join(handles)).hexdigest()
        self.reason = "contexte_valide"
        return result


def make_probe(player_name, *, live=False):
    """Activation explicite ; pas d'import du décodeur quand aucun joueur n'est donné."""
    if player_name is None:
        return None
    active = None
    if live:
        import os

        root = Path(os.environ["LOCALAPPDATA"]) / "Temp/Heroes of the Storm"
        active = lambda: any(root.glob("TempWriteReplay*/replay.server.battlelobby"))
    return ContextProbe(player_name, active_lobby=active)
