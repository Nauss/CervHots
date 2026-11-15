"""Fast CODE-rendered warnings; arbitrary model text keeps exact-key checks."""
from __future__ import annotations

from hotstate.position_maps import SUPPORTED_MAPS
from .brain import Coach, Decision
from .macro import INTENT, TEXT, MacroCoach, MacroPolicy, facts, _identity

LEVEL_INTENT = 'level_disadvantage'
LEVEL_TEXT = "L'équipe adverse a au moins deux niveaux d'avance. Évitez les combats et récupérez de l'expérience."


def level_facts(state):
    """Known complete shared team levels, not proof of selected talents."""
    if facts(state, maps=SUPPORTED_MAPS) is None:
        return None
    levels = []
    for team in (state['ally_team'], 1 - state['ally_team']):
        values = [h.get('level') for h in state['heroes'] if h['team'] == team]
        if any(type(v) is not int or not 1 <= v <= 30 for v in values) or len(set(values)) != 1:
            return None
        levels.append(values[0])
    return dict(allies=levels[0], enemies=levels[1], disadvantaged=levels[1] - levels[0] >= 2)


class ReactiveCoach(MacroCoach):
    """Use current typed facts before paying for knowledge/API preparation."""
    fact_maps = SUPPORTED_MAPS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.level_episode_delivered = False

    def observe(self, state):
        rearmed = super().observe(state)
        levels = level_facts(state)
        if levels is not None and not levels['disadvantaged'] and self.level_episode_delivered:
            self.level_episode_delivered = False
            rearmed = True
        return rearmed

    def prepare(self, state):
        self.observe(state)
        current = facts(state, maps=self.fact_maps)
        if current is None:
            return None  # The ordinary Coach may abstain; its rules stay intact.
        if INTENT in current['allowed']:
            if self.episode_delivered:
                return Decision(raison='répétition')
            return Decision(True, 2, TEXT, 1., 'calme', INTENT, 'conseil', intent=INTENT)
        levels = level_facts(state)
        if levels is not None and levels['disadvantaged']:
            if self.level_episode_delivered:
                return Decision(raison='répétition')
            return Decision(True, 2, LEVEL_TEXT, 1., 'calme', LEVEL_INTENT,
                            'conseil', intent=LEVEL_INTENT)
        return None

    def decide(self, state, knowledge=''):
        prepared = self.prepare(state)
        return prepared if prepared is not None else Coach.decide(self, state, knowledge)

    def remember(self, decision):
        Coach.remember(self, decision)
        if decision.parler and decision.intent == INTENT and decision.texte == TEXT:
            self.episode_delivered = True
        if decision.parler and decision.intent == LEVEL_INTENT and decision.texte == LEVEL_TEXT:
            self.level_episode_delivered = True


class ReactivePolicy:
    def revalidate(self, original, current, decision):
        if decision.intent == INTENT:
            return MacroPolicy(maps=SUPPORTED_MAPS).revalidate(original, current, decision)
        if decision.intent == LEVEL_INTENT:
            before, after = level_facts(original), level_facts(current)
            return bool(before is not None and after is not None
                and before['disadvantaged'] and before == after
                and decision.parler and decision.texte == LEVEL_TEXT
                and decision.sujet == LEVEL_INTENT and decision.priorite == 2
                and decision.style == 'calme' and type(decision.confiance) in (int, float)
                and .75 <= decision.confiance <= 1
                and _identity(original) == _identity(current)
                and facts(original, maps=SUPPORTED_MAPS)['life'] == facts(current, maps=SUPPORTED_MAPS)['life']
                and current['meta']['t_s'] >= original['meta']['t_s'])
        if decision.intent is not None:
            return False
        from .runner import tactical_key
        return tactical_key(original) == tactical_key(current)
