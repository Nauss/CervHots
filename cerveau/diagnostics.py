"""Minimised, session-pseudonymous journal; never an input to the normalizer.

Only bounded scalar selections leave the process. Keys are compared internally;
only reviewed top-level field names leave it, never key strings or receipts.
Free-form advice is withheld unless every word belongs to a fixed tactical
vocabulary. This intentionally loses text rather than risk exporting secrets.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import re
import secrets

FIELDS = frozenset(('map', 'composition', 'local_player', 'heroes', 'ally_team',
                    'gameplay', 'stats', 'events', 'positions', 'visibility',
                    'objective', 'battlefield', 'talents', 'local_cooldowns'))
WORDS = frozenset('''regroupez vous avant le prochain combat restez ensemble
    ne pas engagez engager seul seule reculez attendez les alliés allié alliée
    équipe évitez évite un une la l de du des et à au aux pour sur sous sans
    avec en près loin est sont votre vos notre nos leur leurs ce cette ces
    soyez prudent prudents prudente prudemment protégez protéger soignez
    défendez défendre poussez pousser prenez prendre capturez capturer objectif
    objectif camp camps boss structure structures tour tours fort forts
    niveau niveaux avantage désavantage numérique talent talents supérieur
    inférieur manque manquez préparez préparez-vous prochain prochaine
    vague vagues voie voies ennemi ennemis ennemie ennemies héros héros
    mort morts vivant vivants santé ressources faible faibles bas basse
    attendez attendez-vous retour renforts renfort position positions vision
    visibilité caché cachés visible visibles inconnu inconnus retraite
    combat combats maintenant plutôt puis si tant que trop plus moins
    groupe regroupement regroupés reste restez-vous rentrez revenez recule
    allez gardez gardez-vous surveillez surveiller flanc flancs front arrière
    pression urgence soin soins mana pv gagner perdre risque risques
    inutile nécessaire disponible disponibles absent absents cinq quatre
    trois deux contre tous toutes toute tout attention laissez laissez-vous
    approchez approchez-vous cessez quittez n ni mais donc car besoin
    sécurité menace menaces priorité protégez-vous couvert défensive offensive
    rotate rotation reculer rejoindre rejoignez nettoyage nettoyez'''.split())


def number(value, low=0, high=21600):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


class Journal:
    def __init__(self, emit, *, salt=None, private_labels=()):
        self.emit = emit
        self.salt = secrets.token_bytes(32) if salt is None else salt
        self.private_labels = tuple(s.casefold() for s in private_labels if type(s) is str and s)
        self.sequence = 0
        self.phase = 'prepare'

    def set_phase(self, phase):
        self.phase = phase
        self.record('phase', phase=phase)

    def alias(self, kind, value):
        if type(value) is not str or not 0 < len(value) <= 256:
            return 'unknown'
        return kind + '_' + hmac.new(self.salt, value.encode('utf-8'), hashlib.sha256).hexdigest()[:12]

    def record(self, event, **fields):
        self.sequence += 1
        self.emit(dict(schema_version=1, sequence=self.sequence, event=event, **fields))

    def observation(self, state):
        meta = state.get('meta', {})
        summary = {'map': self.alias('map', meta.get('map')),
                   'session': self.alias('session', meta.get('match_id')), 'heroes': []}
        if number(meta.get('t_s')):
            summary['mission_t_s'] = meta['t_s']
        gameplay = meta.get('gameplay_clock', {})
        if number(gameplay.get('t_s'), -600) and gameplay.get('phase') in ('preparation', 'playing'):
            summary['gameplay'] = {'t_s': gameplay['t_s'], 'phase': gameplay['phase']}
        for h in state.get('heroes', [])[:10]:
            if type(h) is not dict or type(h.get('id')) is not int or not 0 <= h['id'] < 10:
                continue
            row = {'slot': h['id'], 'hero': self.alias('hero', h.get('hero'))}
            for key, low, high in (('team', 0, 1), ('level', 1, 30), ('health', 0, 100000),
                                   ('health_max', 0, 100000), ('resource', 0, 100000),
                                   ('resource_max', 0, 100000), ('respawn_s', 0, 600)):
                if key in ('health', 'health_max', 'resource', 'resource_max') and (
                        type(state.get('ally_team')) is not int or h.get('team') != state['ally_team']):
                    continue
                if number(h.get(key), low, high):
                    row[key] = h[key]
            if type(h.get('alive')) is bool:
                row['alive'] = h['alive']
            summary['heroes'].append(row)
        summary['available_fields'] = sorted(k for k in FIELDS if k in state)
        self.record('observation', **summary)

    def advice(self, text):
        if type(text) is not str or not 0 < len(text) <= 240 or len(text.split()) > 25:
            return ''
        folded = text.casefold()
        if any(label in folded for label in self.private_labels):
            return ''
        if not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ '\-.,!?;:]+", text):
            return ''
        words = re.findall(r'[a-zà-öø-ÿ]+', folded)
        return text if words and all(w in WORDS for w in words) else ''

    def proposal(self, decision):
        self.record('proposal', advice=self.advice(decision.texte),
                    text_withheld=bool(decision.texte) and not bool(self.advice(decision.texte)),
                    speaking=decision.parler, confidence=decision.confiance,
                    priority=decision.priorite, reason=decision_reason(decision.raison))

    def freshness(self, original, current, age, max_age):
        import json
        left, right = json.loads(original), json.loads(current)
        changed = sorted(k for k in FIELDS if left.get(k) != right.get(k))
        # match_id participates in rejection but is never exported, even as a field.
        identity = left.get('match_id') != right.get('match_id')
        expired = not 0 <= age <= max_age
        changed_key = original != current
        cause = ('age_and_key' if expired and changed_key else 'age' if expired
                 else 'key_changed' if changed_key else 'fresh')
        self.record('freshness', cause=cause, age_s=round(age, 6),
                    changed_fields=changed, session_changed=identity)

    def outcome(self, decision):
        self.record('outcome', speaking=decision.parler, reason=decision_reason(decision.raison))


def decision_reason(reason):
    known = {'cooldown', 'périmé', 'non_diffusé', 'conseil', 'silence',
             'réponse_invalide', 'confiance_insuffisante', 'répétition'}
    if type(reason) is str and reason in known:
        return reason
    if type(reason) is str and re.fullmatch(r'erreur_api_(?:[1-5][0-9]{2}|None)', reason):
        return reason
    return 'unknown_decision'
