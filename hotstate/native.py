"""Read-only native simulation state; never invoke client functions.

Only the fingerprinted build profile is supported. Unknown or inconsistent
memory is rejected rather than converted into zero or a tactical observation.
"""
from __future__ import annotations

import hashlib
import json
import struct
import copy
import time
from contextlib import nullcontext
from pathlib import Path

MASK = 0xFFFFFFFF


class NativeUnavailable(ValueError):
    """A native observation cannot be established safely."""


def module_base_from_image(image):
    """Recover ASLR from the encoded native declaration; never use preferred ImageBase."""
    try:
        low, high = struct.unpack_from("<II", image, 0x4124C60)
        low_key = struct.unpack_from("<I", image, 0x32C23C8)[0]
        high_key = struct.unpack_from("<I", image, 0x32C209C)[0]
    except struct.error:
        raise NativeUnavailable("image_native_incomplete") from None
    pointer = (((high ^ high_key ^ 0xE6F631CE) & MASK) << 32) | (~(low - low_key) & MASK)
    base = pointer - 0x29A7CF8
    if not 0x10000 <= base < 0x800000000000 or base % 0x10000:
        raise NativeUnavailable("base_image_native_invalide")
    return base


class NativeReader:
    def __init__(self, memory, *, profile=None):
        self.memory = memory
        self.base = memory.module_base
        self.profile = profile if profile is not None else json.loads(
            (Path(__file__).parent / "profiles/98348.json").read_text(encoding="utf-8"))
        self.verify_profile()

    def verify_profile(self):
        if not self.profile.get("signatures") or self.read(self.base, 2) != b"MZ":
            raise NativeUnavailable("profil_natif_invalide")
        pe = self.base + self.global_u32(0x3C)
        if (self.read(pe, 4) != b"PE\0\0"
                or self.value(pe + 8) != self.profile["pe_timestamp"]
                or self.value(pe + 24 + 56) != self.profile["image_size"]):
            raise NativeUnavailable("build_natif_non_pris_en_charge")
        for signature in self.profile["signatures"]:
            code = self.read(self.base + signature["rva"], signature["size"])
            if hashlib.sha256(code).hexdigest() != signature["sha256"]:
                raise NativeUnavailable("signature_native_invalide")
        if not self.value(self.base + 0x35C8CD9, "B"):
            raise NativeUnavailable("aucune_simulation_active")

    def read(self, address, size):
        data = self.memory.read_memory(address, size)
        if data is None or len(data) != size:
            raise NativeUnavailable("memoire_native_incomplete")
        return data

    def value(self, address, fmt="I"):
        return struct.unpack("<" + fmt, self.read(address, struct.calcsize("<" + fmt)))[0]

    def global_u32(self, rva):
        return self.value(self.base + rva)

    def read_clock(self):
        # A per-acquisition source memo must NEVER freeze either the tick or
        # its encoded roots. Both boundaries still make five physical reads.
        scope = getattr(self.memory,'fresh_reads',nullcontext)
        with scope():
            high = (self.global_u32(0x32C2130) + self.global_u32(0x34F01D4) + 0x6D6AFAFC) & MASK
            low = self.global_u32(0x34F01D0) ^ self.global_u32(0x32C4880)
            seconds = self.value(((high << 32) | low) + 0x68, "i") / 4096
            if not 0 <= seconds <= 21600:
                raise NativeUnavailable("horloge_native_invalide")
            return seconds

    def player_pointer(self, native_id):
        if self.global_u32(0x3366118) != 14:
            raise NativeUnavailable("encodage_joueurs_non_pris_en_charge")
        high = (self.global_u32(0x35C8CB4) - self.global_u32(0x32C4CF4)) & MASK
        low = (self.global_u32(0x35C8CB0) - self.global_u32(0x32C1ED0)) & MASK
        table = self.value((high << 32) | low, "Q")
        encoded_a, encoded_b = struct.unpack("<II", self.read(table + native_id * 8, 8))
        key = self.value(self.value(self.base + 0x3388AE0, "Q"))
        index = ((encoded_a >> 12) + encoded_a) & 4095
        right = ((encoded_b + self.global_u32(0x32C1C90 + index * 4)) & MASK) ^ key
        index = (right - (right >> 12)) & 4095
        left = (encoded_a + self.global_u32(0x32C1C90 + index * 4)) & MASK
        exchanged = (right ^ left) & 0x55555555
        pointer = ((right ^ exchanged) << 32) | (left ^ exchanged)
        if self.value(pointer + 0x22, "B") != native_id:
            raise NativeUnavailable("identifiant_joueur_natif_incoherent")
        return pointer

    def hero_id(self, player, hero_ids):
        record = self.value(player + 0x50, "Q")
        string_object = self.value(record + 0x30, "Q")
        header = string_object + 0x18
        length = self.value(header) >> 2
        if not 0 < length <= 80:
            raise NativeUnavailable("identifiant_heros_natif_invalide")
        buffer = header + 8
        if self.value(header + 4) & 2:
            buffer = self.value(buffer, "Q")
        try:
            identifier = self.read(buffer, length).decode("ascii")
            return hero_ids[identifier]
        except (UnicodeError, KeyError):
            raise NativeUnavailable("heros_natif_inconnu") from None

    def unit_pointer(self, tag, native_id):
        index = tag >> 22
        if (tag + 1) & 0xFFFFFFFE == 0 or index >= self.global_u32(0x34F02C4):
            raise NativeUnavailable("reference_unite_native_invalide")
        page = (tag >> 26) * 8
        low = self.global_u32(0x34F02C8 + page) ^ self.global_u32(0x32C38B4)
        high = (self.global_u32(0x34F02CC + page) + self.global_u32(0x32C55D0)) & MASK
        pointer = ((high << 32) | low) + (index & 15) * 0x2F0
        if (self.value(pointer + 0x10) != tag
                or self.value(pointer + 0x44, "B") != native_id):
            raise NativeUnavailable("proprietaire_ou_generation_unite_incoherent")
        return pointer

    def unit_level(self, unit):
        head = self.value(unit + 0x160, "Q")
        node = self.value(head, "Q") & ~1 if head else 0
        visited = set()
        while node:
            if node in visited or len(visited) >= 64:
                raise NativeUnavailable("liste_composants_native_invalide")
            visited.add(node)
            count = self.value(node + 0x48, "B")
            if not 1 <= count <= 8:
                raise NativeUnavailable("nombre_composants_natif_invalide")
            for ordinal in range(count):
                component = self.value(node + 8 + ordinal * 8, "Q")
                if self.value(component + 0x78, "B") & 1:
                    continue
                vtable = self.value(component, "Q")
                getter = self.value(vtable + 0x140, "Q")
                if self.read(getter, 6) == b"\xB8\x0C\0\0\0\xC3":
                    level = self.value(component + 0xD0, "i") + 1
                    if not 1 <= level <= 30:
                        raise NativeUnavailable("niveau_natif_invalide")
                    return level
            link = self.value(node, "Q")
            node = 0 if link & 1 else link
        raise NativeUnavailable("composant_experience_absent")

    def respawn_seconds(self, player):
        reference = self.value(player + 0xF0) & 0xFFFF
        slots = self.value(self.base + 0x4020970, "Q")
        slot = slots + reference * 16
        if self.value(slot + 6, "B") != 0x13:
            return None
        timer = self.value(slot + 8, "Q")
        if not timer:
            return None
        elapsed, deadline = struct.unpack("<ii", self.read(timer + 0x18, 8))
        remaining = (deadline - elapsed) / 4096
        return remaining if deadline >= 0 and 0 <= remaining <= 600 else None

    def read_state(self, context, *, hero_ids=None):
        """Bind vitals to the ACTIVE human perspective, not a cached lobby.

        All successful core reads are repeated before issuance. This detects
        torn reads, not an atomic snapshot or an ABA change between samples.
        """
        from .positions import AlliedPositions, _RecordedMemory
        from .acquisition import issue

        expected = copy.deepcopy(context)
        _, match_id, local_id, team, _ = AlliedPositions._context(expected)
        if hero_ids is None:
            hero_ids = json.loads((Path(__file__).parent / 'hero_ids.json').read_text(encoding='utf-8'))
        acquired = time.monotonic()
        memory = _RecordedMemory(self.memory,cache=True)
        n = NativeReader(memory, profile=self.profile)
        identity = AlliedPositions(n, profile=self.profile)._identity(n, hero_ids)
        native_id, native_team, hero, members, stamp = identity
        if (native_id != local_id or native_team != team
                or hero != hero_ids.get(expected['local_player']['hero'], expected['local_player']['hero'])
                or any(p['team'] != next(m['team'] for m in members if m['id'] == p['id'])
                       for p in expected['players'])):
            raise NativeUnavailable('perspective_native_incoherente')
        # Optional enrichments own their read-sets and rejection policy. An XY
        # read already refused as torn must not poison the independent core.
        result = n._read_state(expected, hero_ids=hero_ids, optional_native=self)
        for address, data in memory.coherence_reads('lecture_native_dechiree'):
            if self.read(address, len(data)) != data:
                raise NativeUnavailable('lecture_native_dechiree')
        window = time.monotonic() - acquired
        if not 0 <= window <= 0.125 or context != expected:
            raise NativeUnavailable('perspective_native_perimee_ou_modifiee')
        if not getattr(self.memory, 'recorded_non_atomic', False):
            result['perspective'] = issue({
                'match_id': match_id, 'local_id': local_id, 'team': team,
                'native_session': stamp, 'local_hero': hero,
                'mission_t_s': result['meta']['t_s'], 'read_window_s': window,
                'heroes': copy.deepcopy(result['heroes']),
            }, acquired)
        return result

    def _read_state(self, context, *, hero_ids=None, optional_native=None):
        if not isinstance(context, dict):
            raise NativeUnavailable("contexte_natif_absent")
        local = context.get("local_player")
        roster = context.get("players")
        if (not isinstance(local, dict) or not isinstance(roster, list) or len(roster) != 10
                or not all(isinstance(p, dict) and type(p.get("id")) is int
                           and type(p.get("team")) is int and p["team"] in (0, 1) for p in roster)
                or {p["id"] for p in roster} != set(range(10))
                or any(sum(p["team"] == team for p in roster) != 5 for team in (0, 1))
                or local.get("id") not in range(10) or local.get("team") not in (0, 1)
                or not isinstance(local.get("hero"), str)
                or next(p for p in roster if p["id"] == local["id"])["team"] != local["team"]):
            raise NativeUnavailable("contexte_natif_incomplet")
        if hero_ids is None:
            hero_ids = json.loads((Path(__file__).parent / "hero_ids.json").read_text(encoding="utf-8"))
        started = self.read_clock()
        players, heroes = [], []
        for member in sorted(roster, key=lambda p: p["id"]):
            index = member["id"]
            player = self.player_pointer(index + 1)
            hero = self.hero_id(player, hero_ids)
            unit = self.unit_pointer(self.value(player + 0x58), index + 1)
            alive = self.value(unit + 0x39, "B") & 6 == 0
            observation = {"id": index, "team": member["team"], "hero": hero,
                           "alive": alive, "level": self.unit_level(unit)}
            if not alive:
                remaining = self.respawn_seconds(player)
                if remaining is not None:
                    observation["respawn_s"] = remaining
            if member["team"] == local["team"]:
                maximum = self.value(unit + 0x220, "i") / 4096
                health = maximum - self.value(unit + 0x22C, "i") / 4096
                if maximum > 0 and 0 <= health <= maximum:
                    observation.update(health=health, health_max=maximum)
                resource = self.value(unit + 0x234, "i") / 4096
                resource_max = self.value(unit + 0x228, "i") / 4096
                if resource_max > 0 and 0 <= resource <= resource_max:
                    observation.update(resource=resource, resource_max=resource_max)
            heroes.append(observation)
            players.append({key: observation[key] for key in ("id", "team", "hero")})
        local_player = next(p for p in players if p["id"] == local["id"])
        expected = hero_ids.get(local["hero"], local["hero"])
        if local_player["hero"] != expected:
            raise NativeUnavailable("identite_locale_native_incoherente")
        from .gameplay import GameplayClock
        optional_native = self if optional_native is None else optional_native
        gameplay_clock = None
        try:
            gameplay_clock = GameplayClock(optional_native).read()
        except NativeUnavailable:
            pass  # HUD unknown does not invalidate the independent P0/P1 fields.
        from .positions import AlliedPositions
        positions = None
        try:
            positions = AlliedPositions(optional_native).read(context, hero_ids=hero_ids)
        except NativeUnavailable:
            pass  # No recipe/identity/consistent read => no coordinates, not zeros.
        from .visibility import CurrentVisibility
        visibility = None
        try:
            visibility = CurrentVisibility(optional_native).read(context, hero_ids=hero_ids)
        except NativeUnavailable:
            pass  # Unknown current sight never grants enemy tactical permissions.
        from .objectives import VolskayaObjective
        objective = None
        try:
            if context.get('meta', {}).get('map_id') == 'DragonShire':
                from .dragon import DragonObjective
                objective = DragonObjective(optional_native).read(context, hero_ids=hero_ids)
            else:
                objective = VolskayaObjective(optional_native).read(context, hero_ids=hero_ids)
        except NativeUnavailable:
            pass  # Unknown objective is not a cached event or a default zero.
        from .cooldown_packet import LocalCooldowns
        local_cooldowns = None
        try:
            local_cooldowns = LocalCooldowns(optional_native).read(context, hero_ids=hero_ids)
        except NativeUnavailable:
            pass  # Unqualified/changed local source never supplies ready defaults.
        finished = self.read_clock()
        if not 0 <= finished - started <= 1:
            raise NativeUnavailable("observation_native_non_synchrone")
        meta = {"t_s": finished, "clock_kind": "mission", "native_status": "valide",
                "native_build": self.profile["build"]}
        if gameplay_clock is not None:
            meta["gameplay_clock"] = gameplay_clock
        result = {"meta": meta,
                  "players": players, "heroes": heroes, "local_player": local_player,
                  "composition_complete": len(players) == 10}
        if positions is not None:
            result["positions"] = positions
        if visibility is not None:
            result['visibility'] = visibility
        if objective is not None:
            result['objective'] = objective
        if local_cooldowns is not None:
            result['local_cooldowns'] = local_cooldowns
        return result
