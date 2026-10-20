"""Orchestration bornée : un seul appel en vol, pas de file de conseils périmés."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .brain import Coach, Decision
from .state import validated_gameplay_clock
from .objectives import objective_key
from .battlefield import battlefield_key
from .talents import talents_key
from .cooldowns import cooldown_key

ROOT = Path(__file__).resolve().parent.parent


def knowledge_for(state: dict) -> str:
    from kb.briefing import DB, build

    meta = state["meta"]
    if not meta.get("map"):
        return "Carte inconnue : aucun conseil spécifique à une carte n'est étayé."
    if not Path(DB).is_file():
        raise ValueError("KB absente : exécuter python kb/refresh.py")
    composition = state["composition"]
    gameplay = validated_gameplay_clock(meta)
    clock = (gameplay["t_s"] if gameplay is not None and gameplay["phase"] == "playing"
             and gameplay["t_s"] >= 0 else None)
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
    gameplay = validated_gameplay_clock(state["meta"])
    positions = state.get("positions")
    if state["meta"].get("native_status") == "valide" and isinstance(positions, dict):
        # A repeated reading of the same coordinates is not a movement.
        # Any actual movement/availability change still cancels the advice.
        positions = {k: v for k, v in positions.items() if k != "t"}
    visibility = state.get('visibility')
    if isinstance(visibility, dict):
        visibility = {k: v for k, v in visibility.items() if k != 't'}
    return json.dumps({
        "map": state["meta"].get("map"), "composition": state.get("composition"),
        "match_id": state["meta"].get("match_id"), "local_player": state.get("local_player"),
        "heroes": [_hero_key(h) for h in state["heroes"]] if "heroes" in state else None,
        "ally_team": state.get("ally_team"),
        "gameplay": ((gameplay["phase"], gameplay["timer_paused"], int(gameplay["t_s"] // 30))
                     if gameplay is not None else None),
        "stats": {k: v for k, v in state.get("stats", {}).items() if k != "globes_total"},
        "events": state.get("events"), "positions": positions, 'visibility': visibility,
        'objective': objective_key(state.get('objective')),
        'battlefield': battlefield_key(state.get('battlefield')),
        'talents': talents_key(state.get('talents')),
        'local_cooldowns': cooldown_key(state.get('local_cooldowns')),
    }, sort_keys=True, ensure_ascii=False)


class Pipeline:
    def __init__(self, coach: Coach, read_state, *, knowledge=knowledge_for,
                 synthesize=None, deliver=None, clock=time.monotonic,
                 cooldown: float = 15.0, max_age: float = 20.0, journal=None, checkpoint=None):
        self.coach = coach
        self.read_state = read_state
        self.knowledge = knowledge
        self.synthesize = synthesize
        self.deliver = deliver or (lambda decision, speech, valid: valid())
        self.clock = clock
        self.cooldown = cooldown
        self.max_age = max_age
        self.last_delivery = float("-inf")
        self.journal = journal
        self.checkpoint = checkpoint

    def cycle(self) -> Decision:
        if self.clock() - self.last_delivery < self.cooldown:
            return Decision(raison="cooldown")
        started = self.clock()
        if self.journal is not None:
            self.journal.set_phase('cycle_acquisition')
        state = self.read_state()
        key = tactical_key(state)
        if self.journal is not None:
            self.journal.observation(state)

        def fresh():
            if self.journal is not None:
                self.journal.set_phase('freshness')
            current = self.read_state()
            age = self.clock() - started
            current_key = tactical_key(current)
            if self.journal is not None:
                self.journal.observation(current)
                self.journal.freshness(key, current_key, age, self.max_age)
            return age <= self.max_age and current_key == key

        if self.journal is not None:
            self.journal.set_phase('knowledge')
        knowledge = self.knowledge(state)
        if self.journal is not None:
            self.journal.set_phase('api')
        decision = self.coach.decide(state, knowledge)
        if self.checkpoint is not None:
            self.checkpoint()
        if self.journal is not None:
            self.journal.proposal(decision)
        if not decision.parler:
            return decision
        if not fresh():
            return Decision(raison="périmé")
        speech = self.synthesize(decision) if self.synthesize else None
        if not fresh():
            return Decision(raison="périmé")
        if not self.deliver(decision, speech, fresh):
            return Decision(raison="non_diffusé")
        if self.checkpoint is not None:
            self.checkpoint()
        self.coach.remember(decision)
        self.last_delivery = self.clock()
        return decision
