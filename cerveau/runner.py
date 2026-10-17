"""Orchestration bornée : un seul appel en vol, pas de file de conseils périmés."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .brain import Coach, Decision

ROOT = Path(__file__).resolve().parent.parent


def knowledge_for(state: dict) -> str:
    from kb.briefing import DB, build

    meta = state["meta"]
    if not meta.get("map"):
        return "Carte inconnue : aucun conseil spécifique à une carte n'est étayé."
    if not Path(DB).is_file():
        raise ValueError("KB absente : exécuter python kb/refresh.py")
    composition = state["composition"]
    clock = meta.get("t_s")
    if meta.get("clock_kind") == "mission":
        clock = None  # La préparation compte dans le replay, pas dans les timings HUD de la KB.
    try:
        return build(meta["map"], composition["allies"], composition["enemies"],
                     None if clock is None else int(clock))
    except SystemExit as exc:
        raise ValueError(f"Contexte KB invalide : {exc}") from None


def _hero_key(hero):
    # Countdown/regeneration are continuous; keep meaningful tactical transitions.
    volatile = {"health", "health_max", "resource", "resource_max", "respawn_s"}
    result = {key: value for key, value in hero.items() if key not in volatile}
    for value, maximum in (("health", "health_max"), ("resource", "resource_max")):
        if value in hero and hero.get(maximum, 0) > 0:
            result[value + "_band"] = min(3, int(hero[value] / hero[maximum] * 4))
    if "respawn_s" in hero:
        result["respawn_band"] = 0 if hero["respawn_s"] <= 5 else 1 if hero["respawn_s"] <= 15 else 2
    return result


def tactical_key(state: dict) -> str:
    # Les globes et l'horloge murale changent sans invalider une consigne tactique.
    return json.dumps({
        "map": state["meta"].get("map"), "composition": state.get("composition"),
        "match_id": state["meta"].get("match_id"), "local_player": state.get("local_player"),
        "heroes": [_hero_key(h) for h in state["heroes"]] if "heroes" in state else None,
        "ally_team": state.get("ally_team"),
        "stats": {k: v for k, v in state.get("stats", {}).items() if k != "globes_total"},
        "events": state.get("events"), "positions": state.get("positions"),
    }, sort_keys=True, ensure_ascii=False)


class Pipeline:
    def __init__(self, coach: Coach, read_state, *, knowledge=knowledge_for,
                 synthesize=None, deliver=None, clock=time.monotonic,
                 cooldown: float = 15.0, max_age: float = 20.0):
        self.coach = coach
        self.read_state = read_state
        self.knowledge = knowledge
        self.synthesize = synthesize
        self.deliver = deliver or (lambda decision, speech, valid: valid())
        self.clock = clock
        self.cooldown = cooldown
        self.max_age = max_age
        self.last_delivery = float("-inf")

    def cycle(self) -> Decision:
        if self.clock() - self.last_delivery < self.cooldown:
            return Decision(raison="cooldown")
        started = self.clock()
        state = self.read_state()
        key = tactical_key(state)

        def fresh():
            current = self.read_state()
            return self.clock() - started <= self.max_age and tactical_key(current) == key

        decision = self.coach.decide(state, self.knowledge(state))
        if not decision.parler:
            return decision
        if not fresh():
            return Decision(raison="périmé")
        speech = self.synthesize(decision) if self.synthesize else None
        if not fresh():
            return Decision(raison="périmé")
        if not self.deliver(decision, speech, fresh):
            return Decision(raison="non_diffusé")
        self.coach.remember(decision)
        self.last_delivery = self.clock()
        return decision
