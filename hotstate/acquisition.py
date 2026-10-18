"""Short-lived in-process acquisition provenance, independent of mission time.

Not a credential or an interprocess authentication protocol: this random key is
never persisted. JSON from a different run/process cannot establish provenance.
The supported positions/vitals path is direct --live -> normalizer in the same process.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time

_KEY = secrets.token_bytes(32)
MAX_AGE_S = 1.0


def _seal(packet, acquired):
    payload = {k: v for k, v in packet.items() if k != 'acquisition'}
    return hmac.new(_KEY, json.dumps([acquired, payload], sort_keys=True,
                    allow_nan=False, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()


def issue(packet, acquired):
    packet['acquisition'] = {'monotonic_s': acquired, 'seal': _seal(packet, acquired)}
    return packet


def fresh(packet):
    try:
        receipt = packet['acquisition']
        acquired, seal = receipt['monotonic_s'], receipt['seal']
        return (type(acquired) in (int, float) and isinstance(seal, str)
                and 0 <= time.monotonic() - acquired <= MAX_AGE_S
                and hmac.compare_digest(seal, _seal(packet, acquired)))
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError):
        return False
