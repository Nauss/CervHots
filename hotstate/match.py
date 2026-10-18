"""Initial seed/cache from the current native application, never a heap search.

Offsets follow the native replay.initData schema, not an occurrence of a seed.
observe() must run inside the caller's bracketed/rechecked read-set. It is not
itself a publishable packet and grants no tactical permission.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .native import NativeUnavailable

PROFILE = json.loads((Path(__file__).parent / 'profiles/98348-match.json').read_text(encoding='utf-8'))


class ActiveMatch:
    def __init__(self, *, profile=None):
        self.profile = PROFILE if profile is None else profile

    @staticmethod
    def _pointer(value):
        if not 0x10000 <= value < 0x800000000000 or value % 8:
            raise NativeUnavailable('racine_partie_native_invalide')
        return value

    def observe(self, n):
        p = self.profile
        pe = n.base + n.global_u32(0x3c)
        if (p.get('build') != 98348 or n.profile.get('build') != 98348
                or n.value(pe + 8) != p['pe_timestamp']
                or n.value(pe + 24 + 56) != p['image_size'] or not p.get('signatures')):
            raise NativeUnavailable('profil_partie_native_invalide')
        for signature in p['signatures']:
            code = n.read(n.base + signature['rva'], signature['size'])
            if hashlib.sha256(code).hexdigest() != signature['sha256']:
                raise NativeUnavailable('signature_partie_native_invalide')
        # GameMapPath uses this current application interface and its +e0 getter.
        app = self._pointer(n.value(n.base + 0x2f825f8, 'Q') ^ 0x50c23112)
        vtable = self._pointer(n.value(app, 'Q'))
        if (n.value(vtable + 0xe0, 'Q') != n.base + 0x1324b70
                or n.value(vtable + 0x358, 'Q') != n.base + 0x1327c00
                or n.value(app + 0x1d910) != 4):
            raise NativeUnavailable('partie_application_non_active')
        # The same source is copied by replay save132b0f0 -> db9a40 -> cf96b0
        # and serialized by1350f80. No function is invoked by this reader.
        config = app + 0x83f78
        # Schema888 -> alias889 -> struct775; lobby762 field4/tag-7:uint32.
        seed = n.read(config + 0x1d428, 4)
        # gameDescription684 field21/tag-7 -> array642, stride40, inline data+8.
        cache = config + 0xd480
        count = n.value(cache, 'Q')
        if not 1 <= count <= 32:
            raise NativeUnavailable('cache_partie_native_invalide')
        handles = n.read(cache + 8, count * 40)
        if any(handles[i:i + 4] != b's2ma' for i in range(0, len(handles), 40)):
            raise NativeUnavailable('cache_partie_native_invalide')
        return {'source': 'native_active_initdata',
                'match_id': hashlib.sha256(seed + handles).hexdigest()}
