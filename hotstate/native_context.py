"""Current typed native InitData, not a search for a serialized replay buffer.

Schema775 is the CURRENT GameMapPath application's config, also consumed by the
native InitData serializer. No client function is invoked, no bytes fabricated.
Names stay in-process; only an actually observed owner is matched to the label.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .context import context_from_initdata, map_from_cache
from .match import ActiveMatch
from .native import NativeReader, NativeUnavailable
from .positions import _RecordedMemory

PROFILE_PATH = Path(__file__).parent / 'profiles/98348-context.json'
SOURCE = 'initdata_native_fields'


class NativeContextProbe:
    def __init__(self, player_name, *, map_resolver=map_from_cache, profile=None):
        if not isinstance(player_name, str) or not 2 <= len(player_name) <= 64:
            raise ValueError('private player label required')
        self.player_name = player_name
        self.map_resolver = map_resolver
        self.profile = json.loads(PROFILE_PATH.read_text()) if profile is None else profile
        self.map_cache = {}
        self.begin()

    def begin(self):
        self.result = {}
        self.read_set = []
        self.reason = 'contexte_natif_absent'

    @staticmethod
    def _optional_byte(n, address):
        present = n.value(address, 'B')
        if present not in (0, 1):
            raise NativeUnavailable('option_contexte_natif_invalide')
        return n.value(address + 1, 'B') if present else None

    @staticmethod
    def _string(n, address, limit):
        count, extent = n.value(address, 'Q'), n.value(address + 8, 'Q')
        # Only the exact bounded inline representation is supported. Unequal
        # extents / unknown encodings fail closed; no pointer/SSO fallback.
        if count > limit or count != extent:
            raise NativeUnavailable('chaine_contexte_native_invalide')
        if not count:
            return ''
        try:
            value = n.read(address + 16, count).decode('utf-8')
        except UnicodeError:
            raise NativeUnavailable('chaine_contexte_native_invalide') from None
        if '\0' in value:
            raise NativeUnavailable('chaine_contexte_native_invalide')
        return value

    def observe_native(self, backend, *, native_profile=None, clock=None):
        if getattr(backend, 'recorded_non_atomic', False):
            raise NativeUnavailable('contexte_natif_capture_non_atomique')
        clock = time.monotonic if clock is None else clock
        started = clock()
        recorded = _RecordedMemory(backend)
        n = NativeReader(recorded, profile=native_profile)
        initial = ActiveMatch().observe(n)
        p = self.profile
        if p.get('build') != n.profile.get('build') or not p.get('signatures'):
            raise NativeUnavailable('profil_contexte_natif_invalide')
        for signature in p['signatures']:
            if hashlib.sha256(n.read(n.base + signature['rva'], signature['size'])).hexdigest() != signature['sha256']:
                raise NativeUnavailable('signature_contexte_native_invalide')
        app = n.value(n.base + 0x2f825f8, 'Q') ^ 0x50c23112
        config = app + 0x83f78
        users_count = n.value(config, 'Q')
        slots = config + 0xe198 + 8
        slots_count = n.value(slots, 'Q')
        if not 1 <= users_count <= 16 or not 1 <= slots_count <= 16:
            raise NativeUnavailable('effectif_contexte_natif_invalide')
        users = [{'m_name': self._string(n, config + 8 + i * 3120, 32)} for i in range(users_count)]
        members = []
        for i in range(slots_count):
            slot = slots + 8 + i * 3880
            members.append({'m_control': n.value(slot, 'B'),
                'm_userId': self._optional_byte(n, slot + 1),
                'm_teamId': n.value(slot + 3, 'B'),
                'm_observe': n.value(slot + 12),
                'm_hero': self._string(n, slot + 24, 127),
                'm_workingSetSlotId': self._optional_byte(n, slot + 1608)})
        cache = config + 0xd480
        count = n.value(cache, 'Q')
        if not 1 <= count <= 32:
            raise NativeUnavailable('cache_partie_native_invalide')
        handles = [n.read(cache + 8 + i * 40, 40) for i in range(count)]
        # This dictionary represents the observed C++ fields. It is NOT an
        # invented binary InitData buffer or a call to the replay decoder.
        try:
            result = context_from_initdata({'m_syncLobbyState': {
                'm_userInitialData': users, 'm_lobbyState': {
                    'm_slots': members, 'm_randomSeed': n.value(config + 0x1d428)},
                'm_gameDescription': {'m_cacheHandles': handles}}}, self.player_name)
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise NativeUnavailable('contexte_natif_invalide_ou_ambigu') from None
        if hashlib.sha256(result['_match_seed'].to_bytes(4, 'little') + b''.join(handles)).hexdigest() != initial['match_id']:
            raise NativeUnavailable('contexte_natif_partie_changee')
        self.read_set = list(recorded.read_set)
        key = tuple(handles)
        if not self.map_cache.get(key, {}).get('map_id'):
            self.map_cache[key] = self.map_resolver(key)
        self.recheck(backend)
        if not 0 <= clock() - started <= 0.125:
            raise NativeUnavailable('contexte_natif_perime')
        self.result = {k: v for k, v in result.items() if not k.startswith('_')}
        self.result['meta'] = {**self.map_cache[key], 'context_source': SOURCE,
                               'match_id': initial['match_id']}
        self.reason = 'contexte_natif_valide'

    def recheck(self, backend):
        if not self.read_set or any(backend.read_memory(a, len(data)) != data for a, data in self.read_set):
            raise NativeUnavailable('contexte_natif_dechire')

    def finish(self):
        return self.result
