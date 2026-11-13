"""Fast CODE-rendered warnings; arbitrary model text keeps exact-key checks."""
from __future__ import annotations

from hotstate.position_maps import SUPPORTED_MAPS
from .brain import Coach, Decision
from .macro import INTENT, TEXT, MacroCoach, MacroPolicy, facts


class ReactiveCoach(MacroCoach):
    """Use current typed facts before paying for knowledge/API preparation."""
    fact_maps = SUPPORTED_MAPS

    def prepare(self, state):
        self.observe(state)
        current = facts(state, maps=self.fact_maps)
        if current is None or INTENT not in current['allowed']:
            return None  # The ordinary Coach may abstain; its rules stay intact.
        if self.episode_delivered:
            return Decision(raison='répétition')
        return Decision(True, 2, TEXT, 1., 'calme', INTENT, 'conseil', intent=INTENT)

    def decide(self, state, knowledge=''):
        prepared = self.prepare(state)
        return prepared if prepared is not None else Coach.decide(self, state, knowledge)

    def remember(self, decision):
        Coach.remember(self, decision)
        if decision.parler and decision.intent == INTENT and decision.texte == TEXT:
            self.episode_delivered = True


class ReactivePolicy:
    def revalidate(self, original, current, decision):
        if decision.intent == INTENT:
            return MacroPolicy(maps=SUPPORTED_MAPS).revalidate(original, current, decision)
        if decision.intent is not None:
            return False
        from .runner import tactical_key
        return tactical_key(original) == tactical_key(current)
