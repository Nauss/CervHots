"""Read-only build98348 allied main-hero positions, measured on Volskaya.

Release evidence and its sparse pixel-calibration limits: P2-POSITIONS.md.
Observer/rolling dumps grant no permissions. Diagnostics never produce a
validated packet and are not consumed by the coach.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import time
from pathlib import Path

from .native import MASK, NativeReader, NativeUnavailable

MAX_WINDOW_S = 0.125
VALIDATED_MAPS = ('Volskaya',)  # Player recipe only; no Dragon/Braxis extrapolation.
PROFILE = json.loads((Path(__file__).parent / 'profiles/98348-positions.json').read_text(encoding='utf-8'))


def playable_bounds(map_id):
    """Known structural bounds; this is NOT a map validation allowlist."""
    return PROFILE.get('maps', {}).get(map_id, {}).get('bounds')


class _RecordedMemory:
    def __init__(self, memory):
        self.memory = memory
        self.module_base = memory.module_base
        self.recorded_non_atomic = getattr(memory, 'recorded_non_atomic', False)
        self.read_set = []

    def read_memory(self, address, size):
        data = self.memory.read_memory(address, size)
        if data is not None:
            self.read_set.append((address, data))
        return data


class AlliedPositions:
    def __init__(self, native, *, profile=None):
        self.native = native
        self.profile = profile if profile is not None else PROFILE

    @staticmethod
    def _pointer(pointer):
        if not 0x10000 <= pointer < 0x800000000000 or pointer % 8:
            raise NativeUnavailable('pointeur_positions_invalide')
        return pointer

    def _verify(self, n):
        p = self.profile
        pe = n.base + n.global_u32(0x3C)
        if (p.get('build') != 98348 or n.profile.get('build') != 98348
                or n.value(pe + 8) != p['pe_timestamp']
                or n.value(pe + 24 + 56) != p['image_size'] or not p.get('signatures')
                or n.value(n.base + 0x35C8CD9, 'B') != 1
                or n.global_u32(0x3366118) != 14):
            raise NativeUnavailable('profil_positions_non_pris_en_charge')
        for signature in p['signatures']:
            code = n.read(n.base + signature['rva'], signature['size'])
            if hashlib.sha256(code).hexdigest() != signature['sha256']:
                raise NativeUnavailable('signature_positions_invalide')

    def _bounds(self, n, map_id):
        spec = self.profile.get('maps', {}).get(map_id)
        if spec is None:
            raise NativeUnavailable('carte_positions_non_prise_en_charge')
        high = (n.global_u32(0x32C2130) + n.global_u32(0x34F01D4) + 0x6D6AFAFC) & MASK
        low = n.global_u32(0x34F01D0) ^ n.global_u32(0x32C4880)
        simulation = self._pointer((high << 32) | low)
        # RegionPlayableMap -> simulation region(16): (16 + 31)*16 = 0x2f0.
        bounds = struct.unpack('<iiii', n.read(simulation + 0x2F0, 16))
        if (list(bounds) != spec['bounds'] or not -256 <= bounds[0] < bounds[2] <= 512
                or not -256 <= bounds[1] < bounds[3] <= 512):
            raise NativeUnavailable('bornes_positions_incoherentes')
        return bounds

    def _xy(self, n, unit):
        a, encoded = struct.unpack('<II', n.read(unit + 0x60, 8))
        key_pointer = self._pointer(n.value(n.base + 0x3388AE0, 'Q'))
        key = n.value(key_pointer)

        def table(index):
            return n.value(n.base + 0x32C1C90 + (index & 4095) * 4)

        right = (~((encoded - table(~a - (a >> 12))) & MASK) & MASK) ^ key
        left = (table((right >> 12) + right) + a) & MASK
        exchange = (right ^ left) & 0x55555555
        x, y = left ^ exchange, right ^ exchange
        signed = lambda value: value if value < 0x80000000 else value - 0x100000000
        return signed(x) / 4096, signed(y) / 4096

    def _sample(self, n, map_id, members, hero_ids):
        self._verify(n)
        xmin, ymin, xmax, ymax = self._bounds(n, map_id)
        if hero_ids is None:
            hero_ids = json.loads((Path(__file__).parent / 'hero_ids.json').read_text(encoding='utf-8'))
        heroes = []
        for member in members:
            index = member['id']
            player = self._pointer(n.player_pointer(index + 1))
            hero = n.hero_id(player, hero_ids)
            expected = member.get('hero')
            if expected is not None and hero_ids.get(expected, expected) != hero:
                raise NativeUnavailable('identite_positions_incoherente')
            # CPlayer's main hero only. Never enumerate other owned units.
            unit = self._pointer(n.unit_pointer(n.value(player + 0x58), index + 1))
            if n.value(unit + 0x39, 'B') & 6:
                continue  # A corpse's last location is not a live ally position.
            x, y = self._xy(n, unit)
            if not xmin <= x <= xmax or not ymin <= y <= ymax:
                raise NativeUnavailable('coordonnees_positions_hors_bornes')
            heroes.append({'id': index, 'hero': hero, 'x': x, 'y': y,
                           'u': (x - xmin) / (xmax - xmin),
                           'v': 1 - (y - ymin) / (ymax - ymin)})
        return {'map_id': map_id, 'bounds': [xmin, ymin, xmax, ymax], 'heroes': heroes}

    def _identity(self, n, hero_ids):
        """Active client perspective, never the observed/spectated player branch.

        UI LocalPlayer/Teammate path: getter6579d0 -> CPlayer table -> team+1c.
        A root stamp identifies this acquisition's native objects, NOT replay
        seed/cache identity; no cached initData buffer can grant permissions.
        """
        signatures = self.profile.get('identity_signatures')
        if not signatures:
            raise NativeUnavailable('profil_identite_positions_absent')
        for s in signatures:
            if hashlib.sha256(n.read(n.base + s['rva'], s['size'])).hexdigest() != s['sha256']:
                raise NativeUnavailable('signature_identite_positions_invalide')
        low = ~(n.global_u32(0x339FEC8) - n.global_u32(0x32C51F8)) & MASK
        high = ~(n.global_u32(0x339FECC) - n.global_u32(0x32C403C)) & MASK
        client = self._pointer((high << 32) | low)
        if (n.value(client) ^ n.global_u32(0x32C3850)) & 0x30:
            raise NativeUnavailable('perspective_observateur_ou_replay')
        local = n.value(client + 0xC, 'B')
        if not 1 <= local <= 10:
            raise NativeUnavailable('identite_locale_native_absente')
        members, pointers = [], []
        for index in range(10):
            player = self._pointer(n.player_pointer(index + 1))
            team, kind = struct.unpack('<BB', n.read(player + 0x1C, 2))
            if team not in (0, 1) or kind not in (1, 2) or (index == local - 1 and kind != 1):
                raise NativeUnavailable('identite_ou_equipe_native_invalide')
            members.append({'id': index, 'team': team})
            pointers.append(player)
        if any(sum(p['team'] == t for p in members) != 5 for t in (0, 1)):
            raise NativeUnavailable('equipes_natives_non_5v5')
        hero = n.hero_id(pointers[local - 1], hero_ids)
        team = members[local - 1]['team']
        # Simulation roots are independently recorded/rechecked by read_clock/bounds.
        stamp = hashlib.sha256(struct.pack('<Q10Q', client, *pointers)).hexdigest()
        return local - 1, team, hero, members, stamp

    @staticmethod
    def _context(context):
        if not isinstance(context, dict):
            raise NativeUnavailable('identite_positions_absente')
        roster, local, meta = context.get('players'), context.get('local_player'), context.get('meta')
        if (not isinstance(roster, list) or len(roster) != 10
                or not all(isinstance(p, dict) and type(p.get('id')) is int
                           and type(p.get('team')) is int and p['team'] in (0, 1)
                           and (p.get('hero') is None or isinstance(p['hero'], str)) for p in roster)
                or {p['id'] for p in roster} != set(range(10))
                or any(sum(p['team'] == team for p in roster) != 5 for team in (0, 1))
                or not isinstance(local, dict) or type(local.get('id')) is not int
                or type(local.get('team')) is not int or local['team'] not in (0, 1)
                or local['id'] not in range(10) or not isinstance(local.get('hero'), str)
                or next(p for p in roster if p['id'] == local['id'])['team'] != local['team']
                or not isinstance(meta, dict) or meta.get('context_source') != 'initdata_memory'
                or not isinstance(meta.get('match_id'), str)
                or not re.fullmatch('[0-9a-f]{64}', meta['match_id'])
                or not isinstance(meta.get('map_id'), str)):
            raise NativeUnavailable('identite_positions_absente_ou_ambigue')
        allies = [dict(p) for p in sorted(roster, key=lambda p: p['id']) if p['team'] == local['team']]
        for member in allies:
            if member['id'] == local['id']:
                member['hero'] = local['hero']
        return meta['map_id'], meta['match_id'], local['id'], local['team'], allies

    def inspect_saved(self, map_id, *, hero_ids=None):
        """Offline structural diagnostics, all ten main units, NO player claim.

        u/v are playable-rectangle candidate coordinates, not a measured HUD
        calibration. Never pass this packet to snapshot/Coach.
        """
        n = NativeReader(self.native.memory, profile=self.native.profile)
        result = self._sample(n, map_id, [{'id': i} for i in range(10)], hero_ids)
        return dict(result, status='offline_non_atomic', mission_t_s=n.read_clock())

    def read(self, context, *, hero_ids=None):
        map_id, match_id, local_id, team, allies = self._context(context)
        if getattr(self.native.memory, 'recorded_non_atomic', False):
            raise NativeUnavailable('capture_positions_non_atomique')
        if map_id not in VALIDATED_MAPS:
            raise NativeUnavailable('recette_positions_absente')
        result = self._observe(map_id, context=context, hero_ids=hero_ids)
        from .acquisition import issue
        acquired = result.pop('_acquired')
        result.update(status='validated', match_id=match_id)
        return issue(result, acquired)

    def diagnose(self, map_id, *, hero_ids=None):
        """Same acquisition core with publication CLOSED; never a coach packet."""
        result = self._observe(map_id, hero_ids=hero_ids)
        result.pop('_acquired')
        return dict(result, status='diagnostic_unreleased')

    def _observe(self, map_id, *, context=None, hero_ids=None):
        if getattr(self.native.memory, 'recorded_non_atomic', False):
            raise NativeUnavailable('capture_positions_non_atomique')
        if hero_ids is None:
            hero_ids = json.loads((Path(__file__).parent / 'hero_ids.json').read_text(encoding='utf-8'))
        expected_context = self._context(context) if context is not None else None
        clock = getattr(self.native.memory, 'positions_clock', time.monotonic)
        wall = clock()
        memory = _RecordedMemory(self.native.memory)
        n = NativeReader(memory, profile=self.native.profile)
        before = n.read_clock()
        local_id, team, hero, members, stamp = self._identity(n, hero_ids)
        allies = [dict(p) for p in members if p['team'] == team]
        if expected_context is not None:
            _, _, expected_id, expected_team, expected_allies = expected_context
            expected_hero = hero_ids.get(context['local_player']['hero'], context['local_player']['hero'])
            if (expected_id != local_id or expected_team != team or expected_hero != hero
                    or [p['id'] for p in expected_allies] != [p['id'] for p in allies]):
                raise NativeUnavailable('identite_positions_native_incoherente')
            allies = expected_allies
        result = self._sample(n, map_id, allies, hero_ids)
        # No retry/cached fallback: keys, roots, code, owner, tag, flags and XY
        # are all reread. This is a conservative torn-read detector, not a lock.
        for address, data in memory.read_set:
            if self.native.read(address, len(data)) != data:
                raise NativeUnavailable('lecture_positions_dechiree')
        after = n.read_clock()
        window = clock() - wall
        if not 0 <= after - before <= MAX_WINDOW_S or not 0 <= window <= MAX_WINDOW_S:
            raise NativeUnavailable('fenetre_positions_trop_large')
        if context is not None and self._context(context) != expected_context:
            raise NativeUnavailable('contexte_positions_modifie')
        return dict(result, mission_t_s=after, read_window_s=window, _acquired=wall,
                    native_session=stamp, local_id=local_id, team=team)
