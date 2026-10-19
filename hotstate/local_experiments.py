"""Reusable isolated LOCAL experiment, NOT a coach producer or a live CLI.

Only Stitches/Volskaya98348 and typed native InitData are supported. Historical
replay exercises decode/order, never current freshness. Owned talents are NOT
all manual choices; cooldown-ready is NOT mana/range/CC/charge/cast legality.
No images, GUI, client calls, hardcoded workspace, raw trace or public receipt.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import time
from pathlib import Path

from .native import NativeReader, NativeUnavailable
from .native_context import NativeContextProbe
from .positions import AlliedPositions, _RecordedMemory
from .match import ActiveMatch
from .reader import ProcessBackend

PROFILE = json.loads((Path(__file__).parent/'profiles/98348-local-experiments.json').read_text(encoding='utf-8'))


def supports_scope(build, map_id, hero, context_source):
    return (type(build) is int and build == 98348 and map_id == 'Volskaya'
            and hero == 'stitches' and context_source == 'initdata_native_fields')


def verify_experiment_profile(n, profile):
    if (not supports_scope(profile.get('build'),profile.get('map'),profile.get('hero'),profile.get('context_source'))
            or n.profile.get('build') != 98348
            or profile.get('cooldown_link') != 'Abil/StitchesSlam'
            or len(profile.get('signatures',())) != 5):
        raise NativeUnavailable('prototype_profile_unsupported')
    for signature in profile['signatures']:
        if hashlib.sha256(n.read(n.base+signature['rva'],signature['size'])).hexdigest() != signature['sha256']:
            raise NativeUnavailable('prototype_signature_mismatch')


class _BudgetMemory:
    """Counts physical reads including checks; stores no raw readset."""
    def __init__(self, memory, *, clock):
        self.memory, self.clock = memory, clock
        self.module_base = memory.module_base
        self.recorded_non_atomic = getattr(memory,'recorded_non_atomic',False)
        self.started = clock()
        self.read_count = self.bytes_requested = 0

    def read_memory(self, address, size):
        if not 0 <= self.clock()-self.started <= 0.125:
            raise NativeUnavailable('prototype_window_expired')
        if (type(size) is not int or size <= 0 or self.read_count >= 8192
                or self.bytes_requested+size > 1048576):
            raise NativeUnavailable('prototype_budget_exceeded')
        self.read_count += 1
        self.bytes_requested += size
        data = self.memory.read_memory(address,size)
        if not 0 <= self.clock()-self.started <= 0.125:
            raise NativeUnavailable('prototype_window_expired')
        return data


def chosen_indices(raw, count):
    """PlayerHasTalent membership only, despite the historical helper name."""
    if type(count) is not int or not 0 <= count <= 65536 or len(raw) != (count+7)//8:
        raise NativeUnavailable('talent_bitset_incomplete')
    return [i for i in range(count) if raw[i//8] & (1 << (i%8))]


def cooldown_value(value):
    if type(value) is not int or not 0 <= value <= 3600*65536:
        raise NativeUnavailable('cooldown_value_invalid')
    return value/65536


def pointer(p):
    if type(p) is not int or not 0x10000 <= p < 0x800000000000 or p%8:
        raise NativeUnavailable('prototype_bad_pointer')
    return p


def follow_link(node, read):
    seen = set()
    while node & 3:
        if node & 1:
            return 0
        address = node & ~3
        if address in seen or len(seen) >= 128:
            raise NativeUnavailable('cooldown_tagged_cycle')
        seen.add(address)
        pointer(address)
        node = read(address+8)
    if node:
        pointer(node)
    return node


def require_fresh(acquired, now):
    if not 0 <= now-acquired <= 1:
        raise NativeUnavailable('prototype_stale')


def text(n, p):
    pointer(p)
    length,flags = struct.unpack('<II',n.read(p+0x18,8))
    length >>= 2
    if not 0 < length <= 128:
        raise NativeUnavailable('prototype_bad_string_length')
    address = pointer(n.value(p+0x20,'Q')) if flags & 2 else p+0x20
    try:
        value = n.read(address,length).decode('ascii')
    except UnicodeError:
        raise NativeUnavailable('prototype_bad_string') from None
    if not re.fullmatch('[A-Za-z0-9_/.]+',value):
        raise NativeUnavailable('prototype_bad_string')
    return value


def talents(n, player):
    count = n.value(player+0x190)
    if not 0 <= count <= 65536:
        raise NativeUnavailable('talent_bit_count_invalid')
    if count == 0:
        return []
    bits = pointer(n.value(player+0x188,'Q'))
    selected = chosen_indices(n.read(bits,(count+7)//8),count)
    root = pointer(n.value(n.base+0x3388B18,'Q'))
    database = pointer(n.value(root+0x240,'Q'))
    catalog_count = n.value(database+0x90)
    table = pointer(n.value(database+0xA0,'Q'))
    if not 0 < catalog_count <= 65536 or count > catalog_count:
        raise NativeUnavailable('talent_catalog_count_invalid')
    result = []
    for i in selected:
        desc = pointer(n.value(table+i*8,'Q'))
        if n.value(desc+0x40,'H') != i:
            raise NativeUnavailable('talent_catalog_index_invalid')
        result.append(text(n,pointer(n.value(desc+0x30,'Q'))))
    return result


def cooldowns(n, unit):
    state = pointer(n.value(unit+8,'Q'))
    head = n.value(state+8,'Q')
    if not head:
        raise NativeUnavailable('cooldown_root_absent')
    pointer(head)
    node = follow_link(n.value(head+8,'Q'),lambda a:n.value(a,'Q'))
    result,seen = {},set()
    while node:
        if node in seen or len(seen) >= 128:
            raise NativeUnavailable('cooldown_list_cycle')
        seen.add(node)
        name = text(n,pointer(n.value(node+0x10,'Q')))
        if name in result:
            raise NativeUnavailable('cooldown_duplicate_link')
        result[name] = cooldown_value(n.value(node+0x18,'i'))
        node = follow_link(n.value(node+8,'Q'),lambda a:n.value(a,'Q'))
    if 'Abil/StitchesSlam' not in result:
        raise NativeUnavailable('stitches_slam_link_absent')
    remaining = result['Abil/StitchesSlam']
    return {'ability':'StitchesSlam','cooldown_link':'Abil/StitchesSlam',
            'remaining_s':remaining,'cooldown_ready':remaining == 0,
            'precision':'internal 1/65536 s, Galaxy getter truncates by16 before fixed4096',
            'readiness_scope':'cooldown only, NOT mana/range/stun/cast legality'}


def _clock(n, recorded):
    start = len(recorded.read_set)
    value = n.read_clock()
    recorded.validate_clock_end(start,'prototype_clock_root_changed')
    return value


def observe(backend, probe, *, clock=None):
    """Bounded experiment only. Caller owns backend; never opens a process.

    No JSON receipt is issued and no raw addresses/readsets leave this method.
    Live source support still does NOT authorize consumption by the coach.
    """
    clock = time.monotonic if clock is None else clock
    row = {'status':'rejected','source':'native_local_experiment_NOT_PRODUCT',
           'execution_kind':('live_diagnostic_NOT_PRODUCT' if isinstance(backend,ProcessBackend)
                             else 'historical_or_fixture_NOT_LIVE')}
    if not isinstance(probe,NativeContextProbe):
        return dict(row,reason='prototype_source_unsupported')
    budget = _BudgetMemory(backend,clock=clock)
    recorded = _RecordedMemory(budget)
    try:
        if budget.recorded_non_atomic:
            raise NativeUnavailable('prototype_non_atomic_dump')
        n = NativeReader(recorded)
        verify_experiment_profile(n,PROFILE)
        initial = ActiveMatch().observe(n)
        first = _clock(n,recorded)
        probe.begin()
        probe.observe_native(budget)
        context = probe.finish()
        map_id,match_id,local,team,_ = AlliedPositions._context(context)
        ids = json.loads((Path(__file__).parent/'hero_ids.json').read_text(encoding='utf-8'))
        actual = AlliedPositions(n)._identity(n,ids)
        if (not supports_scope(n.profile['build'],map_id,actual[2],context.get('meta',{}).get('context_source'))
                or match_id != initial['match_id'] or actual[:2] != (local,team)):
            raise NativeUnavailable('prototype_local_identity_or_scope')
        player = pointer(n.player_pointer(local+1))
        tag = n.value(player+0x58)
        unit = n.unit_pointer(tag,local+1)
        if n.value(unit+0x39,'B') & 6:
            raise NativeUnavailable('prototype_local_dead')
        owned,ability = talents(n,player),cooldowns(n,unit)
        for address,data in recorded.coherence_reads('prototype_torn'):
            if budget.read_memory(address,len(data)) != data:
                raise NativeUnavailable('prototype_torn')
        probe.recheck(budget)
        last = _clock(n,recorded)
        elapsed = clock()-budget.started
        if not 0 <= last-first <= 0.125 or not 0 <= elapsed <= 0.125:
            raise NativeUnavailable('prototype_window_expired')
        row.update(status='accepted',hero='stitches',local_id=local,team=team,
                   match_id=match_id,mission_interval_s=[first,last],
                   local_generation=tag & 0x3FFFFF,owned_talents=owned,ability=ability,
                   ownership_scope='PlayerHasTalent membership, NOT proof of manual choice',
                   cast_legality='unknown',elapsed_s=elapsed)
    except NativeUnavailable as exc:
        row['reason'] = str(exc)
    row.update(read_count=budget.read_count,bytes_requested=budget.bytes_requested)
    return row
