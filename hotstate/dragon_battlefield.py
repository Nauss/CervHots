"""Unreleased RO Dragon Shire camps/structures diagnostic, build98348 only.

No public receipt or coach integration. An observed census is NOT a complete
initial catalogue; missing references never imply destruction. Recipes remain
required for capture/respawn, destruction/morph and real consumer qualification.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .battlefield import VolskayaBattlefield, _SelectedCensusMemory
from .battlefield_details import camp_details, camp_public, structure_details
from .dragon import DragonObjective
from .live import LiveBudget
from .match import ActiveMatch
from .native import NativeReader, NativeUnavailable
from .native_context import NativeContextProbe
from .positions import AlliedPositions

PROFILE = json.loads((Path(__file__).parent/'profiles/98348-dragon-battlefield.json').read_text(encoding='utf-8'))
GIANTS = ('MercDefenderSiegeGiant',)*2
KNIGHTS = ('MercDefenderMeleeKnight',)*3+('MercDefenderRangedMage',)
DEFENDERS = {1: GIANTS, 2: KNIGHTS, 3: GIANTS, 4: KNIGHTS, 5: KNIGHTS}


class DragonBattlefield(VolskayaBattlefield):
    CAMP_TYPES = (1, 2, 1, 2, 2)
    CAMP_KINDS = ('siege_giants', 'knights', 'siege_giants', 'knights', 'knights')
    CAMP_DEFENDERS = DEFENDERS
    CAMP_LANERS = {i: (('MercLanerSiegeGiant',) if i in (1, 3) else
                      ('MercLanerMeleeKnight', 'MercLanerRangedMage')) for i in range(1, 6)}
    MIN_VM_FUNCTIONS = 5979

    def __init__(self, native, *, profile=None, position_profile=None, match_profile=None):
        super().__init__(native, profile=PROFILE if profile is None else profile,
                         position_profile=position_profile, match_profile=match_profile)

    def _verify(self, n):
        if (self.profile.get('map') != 'DragonShire'
                or self.profile.get('camp_types') != list(self.CAMP_TYPES)
                or self.profile.get('camp_anchors_fixed') != PROFILE['camp_anchors_fixed']):
            raise NativeUnavailable('profil_champ_bataille_dragon_invalide')
        super()._verify(n)
        AlliedPositions(n, profile=self.position_profile)._verify(n)

    def _inventory(self, n):
        units = {}
        census = self._census(n, unit_pointers=units)
        positions = AlliedPositions(n, profile=self.position_profile)
        for row in census['structures']:
            x, y = positions._xy(n, units[row['tag']])
            row.update(x_fixed=round(x*4096), y_fixed=round(y*4096))
        return census, units

    def inspect_saved(self):
        self._verify(self.native)
        census, _ = self._inventory(self.native)
        return {'status': 'offline_non_atomic', 'map_id': 'DragonShire',
                'camps': self._camps(self.native), 'town_registry': self._towns(self.native),
                'census': census, 'catalogue_complete': False}

    def _sample(self, n, local_id):
        self._verify(n)
        camps = self._camps(n)
        positions = AlliedPositions(n, profile=self.position_profile)
        for row, expected in zip(camps, self.profile['camp_anchors_fixed']):
            unit = self._resolve(n, row['beacon_tag'])
            x, y = positions._xy(n, unit)
            if [round(x*4096), round(y*4096)] != expected:
                raise NativeUnavailable('ancre_camp_dragon_invalide')
        camp_details(n, self, camps, local_id)
        census, units = self._inventory(n)
        # Private observed-only catalogue to exercise exact identity, CURRENT
        # and vitals getters. It is never persisted as an initial map layout.
        layout = {'structures': [dict(row, id=f"observed-{index:03d}")
                                 for index, row in enumerate(census['structures'], 1)]}
        structures = structure_details(n, self, census, units, local_id, layout)
        return {'camps': camps,
                'projected_camps': [camp_public(row, kinds=self.CAMP_KINDS) for row in camps],
                'structures': structures, 'town_registry': self._towns(n),
                'unresolved_slots': census['unresolved_slots'], 'catalogue_complete': False}

    def diagnose(self, probe, *, clock=None, hero_ids=None):
        if (not isinstance(probe, NativeContextProbe)
                or getattr(self.native.memory, 'recorded_non_atomic', False)):
            raise NativeUnavailable('contexte_live_champ_bataille_dragon_requis')
        clock = time.monotonic if clock is None else clock
        budget = LiveBudget(self.native.memory, clock=clock)
        memory = _SelectedCensusMemory(budget)
        n = NativeReader(memory, profile=self.native.profile)
        before = self._clock(n, memory)
        probe.begin()
        probe.observe_native(budget, native_profile=self.native.profile, clock=clock)
        context = probe.finish()
        map_id, match_id, local, team, _ = AlliedPositions._context(context)
        if map_id != 'DragonShire':
            raise NativeUnavailable('carte_dragon_requise')
        identity = ActiveMatch(profile=self.match_profile).observe(n)
        if hero_ids is None:
            hero_ids = json.loads((Path(__file__).parent/'hero_ids.json').read_text(encoding='utf-8'))
        actual = AlliedPositions(n, profile=self.position_profile)._identity(n, hero_ids)
        expected_hero = hero_ids.get(context['local_player']['hero'], context['local_player']['hero'])
        expected_members = [(p['id'], p['team']) for p in sorted(context['players'], key=lambda p: p['id'])]
        if (identity['match_id'] != match_id or actual[:2] != (local, team)
                or actual[2] != expected_hero
                or [(p['id'], p['team']) for p in actual[3]] != expected_members):
            raise NativeUnavailable('perspective_champ_bataille_dragon_incoherente')
        # Map-specific ACTIVE initialization is independently fingerprinted;
        # this does not expand AlliedPositions' public map support.
        DragonObjective(n)._verify(n)
        sample = self._sample(n, local)
        for address, size, slices in memory.coherence_checks(self._coherence_reads(memory.read_set)):
            data = budget.read_memory(address, size)
            if data is None or len(data) != size or any(data[off:off+len(value)] != value for off, value in slices):
                raise NativeUnavailable('lecture_champ_bataille_dragon_dechiree')
        memory.verify_bits(NativeReader(budget, profile=self.native.profile))
        probe.recheck(budget)
        start = len(memory.read_set)
        with memory.fresh_reads():
            after = n.read_clock()
        memory.validate_clock_end(start, 'lecture_champ_bataille_dragon_dechiree')
        budget.check()
        if not 0 <= after-before <= 0.125:
            raise NativeUnavailable('fenetre_champ_bataille_dragon_invalide')
        return dict(sample, status='diagnostic_unreleased', map_id=map_id, match_id=match_id,
                    local_id=local, team=team, mission_interval_s=[before, after],
                    read_count=budget.reads, bytes_requested=budget.bytes_requested)

    def read(self, context, **options):
        raise NativeUnavailable('recette_champ_bataille_dragon_absente')
