"""Conservative build98348 CURRENT player visibility, Volskaya only.

The source path is Galaxy's visible UnitFilter, NOT known/explored memory.
Unsupported behavior callbacks/footprint fallback yield None, never False.
No map is released without a real human-perspective fog-transition recipe.
A visible hero grants NO cooldown, talent, position or vital permission here.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path

from .native import MASK, NativeReader, NativeUnavailable
from .positions import AlliedPositions, _RecordedMemory

PROFILE = json.loads((Path(__file__).parent / 'profiles/98348-visibility.json').read_text(encoding='utf-8'))
# Two player-perspective fog cycles, independently checked against replay8.
# Other maps remain closed; visibility never grants other enemy fields.
VALIDATED_MAPS = ('Volskaya',)
MAX_WINDOW_S = 0.125


class _UnknownVisibility(NativeUnavailable):
    pass


class CurrentVisibility:
    def __init__(self, native, *, profile=None, position_profile=None, match_profile=None):
        self.native = native
        self.profile = PROFILE if profile is None else profile
        self.position_profile = position_profile
        self.match_profile = match_profile

    def _verify(self, n):
        p = self.profile
        pe = n.base + n.global_u32(0x3c)
        if (p.get('build') != 98348 or n.profile.get('build') != 98348
                or n.value(pe + 8) != p['pe_timestamp']
                or n.value(pe + 24 + 56) != p['image_size']
                or n.value(n.base + 0x35c8cd9, 'B') != 1
                or n.global_u32(0x3366118) != 14 or not p.get('signatures')
                or n.global_u32(0x2fadd9c) != 0xf):
            raise NativeUnavailable('profil_visibilite_non_pris_en_charge')
        for s in p['signatures']:
            if hashlib.sha256(n.read(n.base + s['rva'], s['size'])).hexdigest() != s['sha256']:
                raise NativeUnavailable('signature_visibilite_invalide')

    @staticmethod
    def _fog(n, x, y, player):
        if not 0 <= x < 256 or not 0 <= y < 256:
            return False  # Native unsigned bounds; NOT remembered/explored cells.
        low = (~n.global_u32(0x35c7980) + n.global_u32(0x32c5898)) & MASK
        high = ~(n.global_u32(0x35c7984) - n.global_u32(0x32c2fe0)) & MASK
        root = AlliedPositions._pointer((high << 32) | low)
        layer = n.value(root + 0x10 + player * 4)
        if not 0 <= layer < 16:
            raise NativeUnavailable('couche_brouillard_invalide')
        address = root + 0x200d0 + (x // 32 + (layer * 256 + y) * 8) * 4
        bit_test = getattr(n.memory,'bit_test',None)
        if callable(bit_test):
            return bit_test(address,x & 31)
        word = n.value(address)
        return bool((word >> (x & 31)) & 1)

    @staticmethod
    def _static(n, x, y):
        bit_test = getattr(n.memory,'bit_test',None)
        if callable(bit_test):
            return (0 <= x < 256 and 0 <= y < 256
                    and bit_test(n.base+0x2f3d630+0x30030+(x//32+y*8)*4,x & 31))
        return (0 <= x < 256 and 0 <= y < 256
                and bool((n.value(n.base + 0x2f3d630 + 0x30030 + (x // 32 + y * 8) * 4)
                          >> (x & 31)) & 1))

    def _triangle(self, n, x, y, fx, fy, player):
        # Native 640020: diagonal/subcell refinement after CURRENT fog bit.
        if self._static(n, x, y):
            return True
        if fx < fy:
            dx, dy = (-1, 0) if fx + fy < 4096 else (0, 1)
        else:
            dx, dy = (0, -1) if fx + fy < 4096 else (1, 0)
        tx, ty = x + dx, y + dy
        if not (0 <= tx < 256 and 0 <= ty < 256) or not self._static(n, tx, ty):
            return True
        if dx:
            if not self._static(n, x, y - 1) and not self._static(n, x, y + 1):
                return True
            return (self._fog(n, tx, y, player)
                    or (self._fog(n, x, y - 1, player) and self._fog(n, x, y + 1, player)))
        if not self._static(n, x - 1, y) and not self._static(n, x + 1, y):
            return True
        return (self._fog(n, x, ty, player)
                or (self._fog(n, x - 1, y, player) and self._fog(n, x + 1, y, player)))

    def _point(self, n, unit, player, helper, catalog):
        x, y = helper._xy(n, unit)
        if not 0 <= x < 256 or not 0 <= y < 256:
            raise NativeUnavailable('point_visibilite_hors_bornes')
        ix, iy = int(x), int(y)
        if self._fog(n, ix, iy, player) and self._triangle(
                n, ix, iy, int(x * 4096) & 4095, int(y * 4096) & 4095, player):
            return True
        if n.value(catalog + 0xe1, 'B') & 8:
            return False  # Native skips the large-footprint fallback in this case.
        # Do not replace the unimplemented footprint/shape test with point-fog=False.
        raise _UnknownVisibility('empreinte_visibilite_non_resolue')

    def _current(self, n, unit, player, helper):
        # Native visibility status4 is the visible filter. Flags are exactly 0xf.
        if (n.value(unit + 0x4c, 'b') > 0 or n.value(unit + 0x3c, 'B') & 0x10
                or n.value(unit + 0x41, 'B') & 0x10):
            return False
        owner = n.value(unit + 0x44, 'B')
        shared = n.value(n.base + 0x35a1ee0 + player * 4)
        if player == owner or shared & (1 << owner):
            return True
        if n.value(unit + 0x156, 'B') & 0x10:
            raise _UnknownVisibility('comportement_partage_vision_non_resolu')
        packed = n.value(unit + (0x20 if n.value(unit + 0x3a, 'B') & 4 else 0x18), 'Q')
        catalog = AlliedPositions._pointer(packed & ~31)
        mode = n.value(catalog + 0xe8, 'i')
        if mode not in (0, 1, 2, 3):
            raise NativeUnavailable('mode_vision_catalogue_invalide')
        visible, unknown = True, None
        if mode < 3:
            try:
                visible = self._point(n, unit, player, helper, catalog)
            except _UnknownVisibility as exc:
                visible, unknown = None, exc
            if visible is not True:
                if n.value(unit + 0x156, 'B') & 4:
                    raise _UnknownVisibility('comportement_revelation_non_resolu')
                if shared & (n.value(unit + 0x290) | n.value(unit + 0x28c)):
                    visible, unknown = True, None
                elif mode < 2 and visible is False:
                    return False  # Native status2 is not visible even if detected.
        if n.value(unit + 0x30) & (1 << 30):
            if n.value(unit + 0x154, 'B') & 0x20:
                raise _UnknownVisibility('comportement_detection_non_resolu')
            if not shared & (n.value(unit + 0x280) | n.value(unit + 0x27c)):
                return False  # Status1, not visible, including revealed stealth.
        if unknown is not None:
            raise unknown
        return visible

    def _sample(self, n, helper, hero_ids):
        self._verify(n)
        local_id, team, hero, members, stamp = helper._identity(n, hero_ids)
        states = []
        for member in members:
            index = member['id']
            pointer = AlliedPositions._pointer(n.player_pointer(index + 1))
            unit = AlliedPositions._pointer(n.unit_pointer(n.value(pointer + 0x58), index + 1))
            unit_hero = n.hero_id(pointer, hero_ids)
            if n.value(unit + 0x39, 'B') & 6:
                states.append(dict(id=index, hero=unit_hero, visible=None, reason='heros_mort_hors_perimetre'))
                continue
            try:
                visible = self._current(n, unit, local_id + 1, helper)
                states.append(dict(id=index, hero=unit_hero, visible=visible))
            except _UnknownVisibility as exc:
                states.append(dict(id=index, hero=unit_hero, visible=None, reason=str(exc)))
        return dict(local_id=local_id, team=team, local_hero=hero, native_session=stamp,
                    members=members, heroes=states)

    def diagnose(self, map_id, *, context=None, hero_ids=None):
        """Fresh RO acquisition, no tactical payload, NEVER a validated packet."""
        result = self._observe(map_id, context=context, hero_ids=hero_ids)
        result.pop('_acquired')
        return dict(result, status='diagnostic_unreleased')

    def _observe(self, map_id, *, context=None, hero_ids=None):
        if getattr(self.native.memory, 'recorded_non_atomic', False):
            raise NativeUnavailable('capture_visibilite_non_atomique')
        expected = copy.deepcopy(context)
        if hero_ids is None:
            hero_ids = json.loads((Path(__file__).parent / 'hero_ids.json').read_text(encoding='utf-8'))
        clock = getattr(self.native.memory, 'positions_clock', time.monotonic)
        start = clock()
        memory = _RecordedMemory(self.native.memory,cache=True)
        n = NativeReader(memory, profile=self.native.profile)
        before = n.read_clock()
        helper = AlliedPositions(n, profile=self.position_profile)
        helper._verify(n)
        helper._bounds(n, map_id)
        from .match import ActiveMatch
        active_match = ActiveMatch(profile=self.match_profile).observe(n)
        result = self._sample(n, helper, hero_ids)
        result['native_match_id'] = active_match['match_id']
        if expected is not None:
            expected_map, _, local_id, team, _ = helper._context(expected)
            if (expected_map != map_id or active_match['match_id'] != expected['meta']['match_id']
                    or result['local_id'] != local_id or result['team'] != team
                    or result['local_hero'] != hero_ids.get(expected['local_player']['hero'], expected['local_player']['hero'])
                    or any(p['team'] != result['members'][p['id']]['team'] for p in expected['players'])):
                raise NativeUnavailable('perspective_visibilite_incoherente')
        for address, data in memory.coherence_reads('lecture_visibilite_dechiree'):
            if self.native.read(address, len(data)) != data:
                raise NativeUnavailable('lecture_visibilite_dechiree')
        clock_start = len(memory.read_set)
        after = n.read_clock()
        memory.validate_clock_end(clock_start,'lecture_visibilite_dechiree')
        window = clock()-start
        if not 0 <= after - before <= MAX_WINDOW_S or not 0 <= window <= MAX_WINDOW_S or context != expected:
            raise NativeUnavailable('fenetre_ou_contexte_visibilite_invalide')
        return dict(result, map_id=map_id, mission_t_s=after, read_window_s=window,
                    _acquired=start)

    def read(self, context, *, hero_ids=None):
        map_id, _, _, _, _ = AlliedPositions._context(context)
        if map_id not in VALIDATED_MAPS:
            raise NativeUnavailable('recette_visibilite_joueur_absente')
        result = self._observe(map_id, context=context, hero_ids=hero_ids)
        acquired = result.pop('_acquired')
        result['match_id'] = result.pop('native_match_id')
        result['status'] = 'validated'
        from .acquisition import issue
        return issue(result, acquired)
