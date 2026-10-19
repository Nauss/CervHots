"""Dragon Shire build98348 native diagnostic; NOT released to the coach.

No event counters/cache, replay state or screen data. The existing rolling
Dragon capture proves decoding only, not live transitions or freshness. Until
an independent Dragon recipe qualifies this path, read() always refuses.
"""
from __future__ import annotations

import hashlib
import copy
import json
import struct
import time
from pathlib import Path

from .battlefield import VolskayaBattlefield
from .match import ActiveMatch
from .native import NativeReader, NativeUnavailable
from .native_context import NativeContextProbe
from .objectives import GLOBAL_DATA, VolskayaObjective
from .positions import AlliedPositions, _RecordedMemory
from .live import LiveBudget

PROFILE = json.loads((Path(__file__).parent/'profiles/98348-dragon.json').read_text(encoding='utf-8'))
VALIDATED_MAPS = ()
PHASES = ('waiting', 'warning', 'shrines', 'dragon')
CAPTURE_STATES = ('contested', 'paused', 'neutral', 'captured', 'reverting', 'capturing')


class DragonObjective:
    def __init__(self, native, *, profile=None, match_profile=None, position_profile=None):
        self.native = native
        self.profile = PROFILE if profile is None else profile
        self.match_profile, self.position_profile = match_profile, position_profile
        # Reuse native mechanics, NOT Volskaya state layout or map permission.
        self.units = VolskayaBattlefield(native)
        self.mechanics = VolskayaObjective(native)

    def _verify(self, n):
        p = self.profile
        pe = n.base+n.global_u32(0x3C)
        if (p.get('build') != 98348 or p.get('map') != 'DragonShire'
                or n.profile.get('build') != 98348 or not p.get('signatures')
                or len(p.get('functions', ())) != 30
                or n.value(pe+8) != p['pe_timestamp']
                or n.value(pe+80) != p['image_size']
                or n.value(n.base+0x35C8CD9, 'B') != 1):
            raise NativeUnavailable('profil_dragon_invalide')
        for s in p['signatures']:
            if hashlib.sha256(n.read(n.base+s['rva'], s['size'])).hexdigest() != s['sha256']:
                raise NativeUnavailable('signature_dragon_invalide')
        count, size = n.global_u32(0x2FA70F0), n.global_u32(0x3B8C904)
        table = self.units._pointer(n.value(n.base+0x3B8C5C8, 'Q'))
        if (not 1971 < count <= 65536 or not 4 <= size <= 0x180000
                or n.value(n.base+0x2FA7100, 'Q') != table):
            raise NativeUnavailable('racine_vm_dragon_invalide')
        for f in p['functions']:
            if not 0 <= f['index'] < count:
                raise NativeUnavailable('index_vm_dragon_invalide')
            record = self.units._pointer(n.value(table+f['index']*8, 'Q'))
            off = n.value(record+8)
            if (n.value(record+0x50) != f['index'] or off < 4
                    or not 0 < f['length'] <= 8192 or off+f['length'] > size):
                raise NativeUnavailable('borne_vm_dragon_invalide')
            ln, flags = struct.unpack('<II', n.read(record+0x58, 8))
            if ln>>2 != len(f['name']):
                raise NativeUnavailable('nom_vm_dragon_invalide')
            string = self.units._pointer(n.value(record+0x60, 'Q')) if flags & 2 else record+0x60
            if n.read(string, ln>>2) != f['name'].encode('ascii'):
                raise NativeUnavailable('nom_vm_dragon_invalide')
            if hashlib.sha256(n.read(n.base+0x3B8C920+off, f['length'])).hexdigest() != f['sha256']:
                raise NativeUnavailable('code_vm_dragon_invalide')

    def _unit(self, n, tag, expected):
        unit = self.units._resolve(n, tag)
        if unit is None:
            return None
        if self.units._unit_type(n, unit) != expected:
            raise NativeUnavailable('type_unite_dragon_invalide')
        owner = n.value(unit+0x44, 'B')
        if n.unit_pointer(tag, owner) != unit:
            raise NativeUnavailable('proprietaire_unite_dragon_invalide')
        return unit

    @staticmethod
    def _owner(owner):
        if owner == 0:
            return 'neutral'
        if owner in (11, 12):
            return owner-11
        raise NativeUnavailable('proprietaire_sanctuaire_dragon_invalide')

    def _shrines(self, n):
        g = n.base+GLOBAL_DATA
        count = n.value(g+0x11869, 'i')
        if n.value(g+0xE2B4A, 'i') != 2 or not 2 <= count <= 15:
            raise NativeUnavailable('nombre_sanctuaires_dragon_invalide')
        result, indices, tags, beacons = [], set(), set(), set()
        for i, name, global_offset in ((1, 'sun', 0xE2B05), (2, 'moon', 0xE2B01)):
            a = g+0xE2B4E+i*21
            tag, index = n.value(a), n.value(a+9, 'i')
            if (tag != n.value(g+global_offset) or not 1 <= index <= count
                    or index in indices or tag in tags):
                raise NativeUnavailable('liaison_sanctuaire_dragon_invalide')
            indices.add(index); tags.add(tag)
            row = {'id': name, 'owner': None, 'state': 'unknown', 'contested': None,
                   'capture_counter': None, 'capture_goal': None}
            unit = self._unit(n, tag, 'DragonShireShrine'+name.title())
            if unit is None:
                result.append(row)
                continue
            cp = g+0x118C5+index*132
            enabled = n.value(cp, 'B')
            counter, goal, maximum = struct.unpack('<iii', n.read(cp+9, 12))
            state, empty_decay, contested_decay = struct.unpack('<iii', n.read(cp+29, 12))
            if (enabled not in (0, 1) or goal != 64 or maximum != goal
                    or not -maximum <= counter <= maximum or not 0 <= state < len(CAPTURE_STATES)
                    or empty_decay != 0 or contested_decay != 2):
                raise NativeUnavailable('etat_capture_dragon_invalide')
            beacon_tag = n.value(cp+1)
            if beacon_tag in beacons:
                raise NativeUnavailable('beacon_dragon_duplique')
            beacons.add(beacon_tag)
            beacon = self._unit(n, beacon_tag, 'DragonballCaptureBeacon')
            if beacon is None:
                result.append(row)
                continue
            owner = self._owner(n.value(unit+0x44, 'B'))
            # Disable waits three seconds before neutralizing the beacon. Its
            # residual owner/state/counter are NOT current shrine activity.
            if enabled and self._owner(n.value(beacon+0x44, 'B')) != owner:
                raise NativeUnavailable('proprietaires_capture_dragon_incoherents')
            row.update(owner=owner, state=CAPTURE_STATES[state] if enabled else 'disabled',
                       contested=state == 0 if enabled else None,
                       capture_counter=counter if enabled else None,
                       capture_goal=goal if enabled else None)
            result.append(row)
        return result

    def _statue(self, n, phase, shrines, local_id=None):
        result = {'state': 'unknown', 'team': None, 'channeling': None}
        if phase != 'shrines':
            return result
        unit = self._unit(n, n.value(n.base+GLOBAL_DATA+0xE2B19), 'VehicleDragon')
        if unit is None or n.value(unit+0x39, 'B') & 6:
            return result
        owner = self._owner(n.value(unit+0x44, 'B'))
        if owner == 'neutral':
            return dict(result, state='inactive')
        if any(s['owner'] != owner or s['state'] in ('unknown', 'disabled') for s in shrines):
            raise NativeUnavailable('statue_sanctuaires_dragon_incoherents')
        if local_id is not None:
            from .visibility import CurrentVisibility, _UnknownVisibility
            helper = AlliedPositions(n, profile=self.position_profile)
            helper._verify(n)
            visibility = CurrentVisibility(n)
            visibility._verify(n)
            try:
                visible = visibility._current(n, unit, local_id+1, helper)
            except _UnknownVisibility:
                visible = None
            # Team ownership is not permission to disclose an unseen channel.
            # Do not even read the marker when CURRENT sight is unestablished.
            if visible is not True:
                return {'state': 'capturable', 'team': owner,
                        'channeling': None, 'current_visible': visible}
        # The 5s marker is applied by the channeled persistent's InitialEffect
        # and removed in FinalEffect. It is NOT the 3s channel's countdown.
        # Private diagnostic only: no permission to reveal an unseen channel.
        marker = self.mechanics._duration(n, unit, 'TransformHeroVehicleBeingCapturedBehavior')
        if not 0 <= marker <= 5:
            raise NativeUnavailable('marqueur_canalisation_dragon_invalide')
        result = {'state': 'capturable', 'team': owner, 'channeling': marker > 0}
        if local_id is not None:
            result['current_visible'] = True
        return result

    def _dragon(self, n, phase):
        result = {'state': 'inactive', 'team': None, 'remaining_s': None}
        if phase != 'dragon':
            return result
        result['state'] = 'unknown'
        g = n.base+GLOBAL_DATA
        unit = self._unit(n, n.value(g+0xE2B11), 'VehicleDragon')
        if unit is None:
            return result
        owner, pilot = n.value(unit+0x44, 'B'), n.value(g+0xE2B15, 'i')
        if not 1 <= owner <= 10 or owner != pilot:
            raise NativeUnavailable('pilote_dragon_invalide')
        player = self.units._pointer(n.player_pointer(owner))
        team, kind = struct.unpack('<BB', n.read(player+0x1C, 2))
        if team not in (0, 1) or kind not in (1, 2):
            raise NativeUnavailable('equipe_pilote_dragon_invalide')
        if n.value(unit+0x39, 'B') & 6:
            return dict(result, state='ended', team=team)
        remaining = self.mechanics._duration(n, unit)
        if not 0 < remaining <= 600:
            return result  # Zero/missing behavior is NOT an active ready unit.
        return {'state': 'active', 'team': team, 'remaining_s': remaining}

    def _sample(self, n, *, local_id=None):
        self._verify(n)
        code = n.value(n.base+GLOBAL_DATA+0xE2B31, 'i')
        if not 0 <= code < len(PHASES):
            raise NativeUnavailable('phase_dragon_invalide')
        phase = PHASES[code]
        shrines = self._shrines(n)
        registry = self.mechanics._timer_registry(n)
        timers = {name: self.mechanics._timer(n, offset, registry) for name, offset in
                  (('start', 0xE2B36), ('respawn', 0xE2B3A), ('warning', 0xE2B3E))}
        dragon = self._dragon(n, phase)
        return {'phase': 'unknown' if phase == 'dragon' and dragon['state'] == 'unknown' else phase,
                'script_phase': phase, 'shrines': shrines, 'dragon': dragon,
                'statue': self._statue(n, phase, shrines, local_id), **timers}

    def inspect_saved(self):
        return dict(self._sample(self.native), status='offline_non_atomic')

    def diagnose(self, probe, *, clock=None):
        """Whole-attempt budget including native context, checks and identity.

        Caller owns the backend; this does NOT open a process or issue a receipt.
        No sample is fed to the coach, even if it passes this diagnostic.
        """
        if (not isinstance(probe, NativeContextProbe)
                or getattr(self.native.memory, 'recorded_non_atomic', False)):
            raise NativeUnavailable('contexte_live_dragon_requis')
        clock = time.monotonic if clock is None else clock
        budget = LiveBudget(self.native.memory, clock=clock)
        memory = _RecordedMemory(budget, cache=True)
        n = NativeReader(memory, profile=self.native.profile)
        before = n.read_clock()
        probe.begin()
        probe.observe_native(budget, native_profile=self.native.profile, clock=clock)
        context = probe.finish()
        map_id, match_id, local, team, _ = AlliedPositions._context(context)
        if map_id != 'DragonShire':
            raise NativeUnavailable('carte_dragon_requise')
        identity = ActiveMatch(profile=self.match_profile).observe(n)
        ids = json.loads((Path(__file__).parent/'hero_ids.json').read_text(encoding='utf-8'))
        actual = AlliedPositions(n, profile=self.position_profile)._identity(n, ids)
        expected_hero = ids.get(context['local_player']['hero'], context['local_player']['hero'])
        expected_members = [(p['id'], p['team']) for p in sorted(context['players'], key=lambda p: p['id'])]
        if (identity['match_id'] != match_id or actual[:2] != (local, team)
                or actual[2] != expected_hero
                or [(p['id'], p['team']) for p in actual[3]] != expected_members):
            raise NativeUnavailable('perspective_dragon_incoherente')
        sample = self._sample(n)
        for address, data in memory.coherence_reads('lecture_dragon_dechiree'):
            if budget.read_memory(address, len(data)) != data:
                raise NativeUnavailable('lecture_dragon_dechiree')
        probe.recheck(budget)
        start = len(memory.read_set)
        after = n.read_clock()
        memory.validate_clock_end(start, 'lecture_dragon_dechiree')
        budget.check()
        if not 0 <= after-before <= 0.125:
            raise NativeUnavailable('fenetre_dragon_invalide')
        return dict(sample, status='diagnostic_unreleased', map_id=map_id,
                    match_id=match_id, local_id=local, team=team,
                    mission_interval_s=[before, after], read_count=budget.reads,
                    bytes_requested=budget.bytes_requested)

    def _observe(self, context, *, hero_ids=None):
        expected = copy.deepcopy(context)
        map_id, match_id, local, team, _ = AlliedPositions._context(expected)
        if map_id != 'DragonShire' or getattr(self.native.memory, 'recorded_non_atomic', False):
            raise NativeUnavailable('carte_ou_capture_dragon_non_prise_en_charge')
        clock = getattr(self.native.memory, 'positions_clock', time.monotonic)
        budget = LiveBudget(self.native.memory, clock=clock)
        memory = _RecordedMemory(budget, cache=True)
        n = NativeReader(memory, profile=self.native.profile)
        before = n.read_clock()
        identity = ActiveMatch(profile=self.match_profile).observe(n)
        if hero_ids is None:
            hero_ids = json.loads((Path(__file__).parent/'hero_ids.json').read_text(encoding='utf-8'))
        actual = AlliedPositions(n, profile=self.position_profile)._identity(n, hero_ids)
        members = [(p['id'], p['team']) for p in sorted(expected['players'], key=lambda p: p['id'])]
        expected_hero = hero_ids.get(expected['local_player']['hero'], expected['local_player']['hero'])
        if (identity['match_id'] != match_id or actual[:2] != (local, team)
                or actual[2] != expected_hero
                or [(p['id'], p['team']) for p in actual[3]] != members):
            raise NativeUnavailable('perspective_dragon_incoherente')
        sample = self._sample(n, local_id=local)
        for address, data in memory.coherence_reads('lecture_dragon_dechiree'):
            if budget.read_memory(address, len(data)) != data:
                raise NativeUnavailable('lecture_dragon_dechiree')
        start = len(memory.read_set)
        after = n.read_clock()
        memory.validate_clock_end(start, 'lecture_dragon_dechiree')
        budget.check()
        window = clock()-budget.started
        if not 0 <= after-before <= 0.125 or not 0 <= window <= 0.125 or context != expected:
            raise NativeUnavailable('fenetre_dragon_invalide')
        return dict(sample, map_id=map_id, match_id=match_id, local_id=local, team=team,
                    local_hero=actual[2], native_session=actual[4], mission_t_s=after,
                    read_window_s=window, _acquired=budget.started)

    def read(self, context, *, hero_ids=None):
        if not VALIDATED_MAPS:
            raise NativeUnavailable('recette_dragon_absente')
        map_id, _, _, _, _ = AlliedPositions._context(context)
        if map_id not in VALIDATED_MAPS:
            raise NativeUnavailable('recette_dragon_absente')
        from .acquisition import issue
        sample = self._observe(context, hero_ids=hero_ids)
        acquired = sample.pop('_acquired')
        return issue(dict(sample, status='validated'), acquired)
