"""RO camps/structures, fingerprinted build98348 Volskaya ONLY.

Public support is bounded to qualified behavior classes on this map/build.
Raw camp activity and structure vitals must never cross a public boundary merely
because a minimap icon is visible. Missing/recycled slots are unknown, not dead.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import struct
import time
from bisect import bisect_right, insort
from pathlib import Path

from .native import NativeReader, NativeUnavailable
from .objectives import VolskayaObjective, GLOBAL_DATA
from .positions import AlliedPositions, _RecordedMemory

PROFILE = json.loads((Path(__file__).parent / 'profiles/98348-battlefield.json').read_text(encoding='utf-8'))
STRUCTURE_LAYOUT = json.loads((Path(__file__).parent / 'profiles/98348-volskaya-structures.json').read_text(encoding='utf-8'))
VALIDATED_MAPS = ('Volskaya',)


class _SelectedCensusMemory(_RecordedMemory):
    """One private bulk I/O, equality checks only for consumed CUnit fields.

    TraceMemory still records every raw requested byte. The transient header
    excludes XY/vitals; unused dirty flags are not mistaken for source fields.
    """
    def __init__(self, memory, *, semantic_selection=False):
        super().__init__(memory)
        self.semantic_selection = semantic_selection
        self.byte_masks = {}
        self.memo = {}
        self.full_keys = set()
        self.bits = {}
        self.headers = set()
        self.header_addresses = []
        self.timers = set()
        self.header_data = {}
        self.fresh = False

    def fresh_read(self, address, size):
        return super().read_memory(address, size)

    def read_memory(self, address, size):
        # Only this _observe owns this memo. Final checks bypass it entirely.
        # A cache hit is not an extra process read and is not logged as one.
        if self.fresh:
            return self.fresh_read(address, size)
        key = address, size
        if key not in self.memo:
            index = bisect_right(self.header_addresses,address)-1
            if index>=0:
                header = self.header_addresses[index]
                raw = self.header_data[header]
                offset = address-header
                if 0 <= offset and offset+size <= len(raw):
                    data = raw[offset:offset+size]
                    # A formerly unused header byte is now consumed: include
                    # its exact selection in the final physical read check.
                    self.read_set.append((address, data))
                    self.full_keys.add(key)
                    self.memo[key] = data
                    return data
            data = self.fresh_read(address, size)
            if data is not None and len(data) == size:
                self.memo[key] = data
                self.full_keys.add(key)
            return data
        if key not in self.full_keys:
            # A fog bit read may have fetched the word without consuming all
            # its bits. A later full-word consumer must retain a FULL guard.
            self.read_set.append((address,self.memo[key]))
            self.full_keys.add(key)
        return self.memo[key]

    def masked_byte(self, address, mask):
        if type(mask) is not int or not 0 < mask <= 255:
            raise NativeUnavailable('masque_octet_natif_invalide')
        if not self.semantic_selection or self.fresh:
            return self.read_memory(address, 1)[0] & mask
        key = address, 1
        if key not in self.memo:
            index = bisect_right(self.header_addresses, address)-1
            header = self.header_addresses[index] if index >= 0 else None
            if header is not None and address < header+0x38:
                data = self.header_data[header][address-header:address-header+1]
            else:
                data = self.memory.read_memory(address, 1)
            if data is None or len(data) != 1:
                raise NativeUnavailable('memoire_native_incomplete')
            self.memo[key] = data
        value = self.memo[key][0]
        previous, expected = self.byte_masks.get(address, (0, 0))
        if (value ^ expected) & previous & mask:
            raise NativeUnavailable('lecture_champ_bataille_dechiree')
        self.byte_masks[address] = previous | mask, expected | (value & mask)
        return value & mask

    def verify_sources(self, native, reason):
        """One physical final plan, union masks and promotion by full overlaps.

        Group only already authorized header/timer regions. No mask is ever
        inferred from a field address, name or unit type.
        """
        reads = self.coherence_reads(reason)
        full = {address+i: value for address, data in reads for i, value in enumerate(data)}
        masks = {}
        for address, (mask, expected) in self.byte_masks.items():
            if address in full:
                if (full[address] ^ expected) & mask:
                    raise NativeUnavailable(reason)
            else:
                masks[address] = mask
                reads.append((address, bytes([expected])))
        for address, size, slices in self.coherence_checks(reads):
            data = native.read(address, size)
            for offset, expected in slices:
                mask = masks.get(address+offset) if len(expected) == 1 else None
                if (data[offset] & mask != expected[0] if mask is not None
                        else data[offset:offset+len(expected)] != expected):
                    raise NativeUnavailable(reason)
        self.verify_bits(native)

    def bit_test(self, address, bit):
        if type(bit) is not int or not 0 <= bit < 32:
            raise NativeUnavailable('bit_visibilite_invalide')
        key = address,4
        if key not in self.memo:
            data = self.memory.read_memory(address,4)
            if data is None or len(data)!=4:
                raise NativeUnavailable('mot_visibilite_incomplet')
            self.memo[key] = data
        word = int.from_bytes(self.memo[key],'little')
        mask,expected = self.bits.get(address,(0,0))
        mask |= 1<<bit
        self.bits[address] = mask,word & mask
        return bool(word & (1<<bit))

    def verify_bits(self, native):
        # Keys/root/layer are ordinary full-field guards. Only actual cell
        # bits consumed by the native fog/static predicates are masked.
        for address,(mask,expected) in self.bits.items():
            word = int.from_bytes(native.read(address,4),'little')
            if word & mask != expected:
                raise NativeUnavailable('lecture_champ_bataille_dechiree')

    def census_header(self, unit):
        data = self.memory.read_memory(unit+0x10,0x38)
        if data is None or len(data)!=0x38:
            raise NativeUnavailable('entete_recensement_incomplete')
        if unit+0x10 not in self.headers:
            self.headers.add(unit+0x10)
            insort(self.header_addresses,unit+0x10)
        self.header_data[unit+0x10] = data
        return data

    def timer_object(self, address):
        # Native timer properties use vtable/owner, flags, clock, elapsed and
        # deadline. +12..15 and +32..39 are not consumed by this getter.
        data = self.memory.read_memory(address,40)
        if data is None or len(data)!=40:
            raise NativeUnavailable('objet_timer_incomplet')
        self.read_set.extend(((address,data[:12]),(address+16,data[16:32])))
        self.timers.add(address)
        return data

    def coherence_checks(self, reads):
        # Group only explicitly acquired census/timer objects. Binary lookup
        # avoids scanning every unit header for every selected field.
        headers,timers = sorted(self.headers),sorted(self.timers)
        def enclosing(regions,address,end,size):
            index = bisect_right(regions,address)-1
            return regions[index] if index>=0 and end<=regions[index]+size else None
        groups = {}
        for address, data in reads:
            timer = enclosing(timers,address,address+len(data),40)
            header = enclosing(headers,address,address+len(data),0x38)
            key = (timer,40) if timer is not None else (address,len(data)) if header is None else (header,0x38)
            groups.setdefault(key, []).append((address-key[0], data))
        # Sampled last, checked first. Elapsed is STILL compared exactly;
        # it is never advanced, extrapolated or omitted as an unused field.
        return sorted(((a,size,slices) for (a,size),slices in groups.items()),
                      key=lambda check: check[0] not in self.timers)


def structure_kind(name):
    if name == 'KingsCore':
        return 'core'
    if name == 'TownCannonTowerDead':
        return 'tower_ruins'
    if name in ('TownTownHallL2', 'TownTownHallL3'):
        return 'fort' if name.endswith('L2') else 'keep'
    if name in ('TownMoonwellL2', 'TownMoonwellL3'):
        return 'healing_fountain'
    if name in ('TownCannonTowerL2', 'TownCannonTowerL3', 'TownCannonTowerL3Standalone'):
        return 'tower'
    if isinstance(name, str) and re.fullmatch(r'TownWallRadial(?:[1-9]|1[0-9]|2[01])L[23]', name):
        return 'wall'
    if name in ('TownGateL215BLUR', 'TownGateL215BRUL',
                'TownGateL3BLURBRVisionBlocked', 'TownGateL3BLURTLVisionBlocked',
                'TownGateL3BRULBLVisionBlocked', 'TownGateL3BRULTRVisionBlocked',
                'TownGateL3VerticalLeftVisionBlocked', 'TownGateL3VerticalRightVisionBlocked'):
        return 'gate'
    return None


class VolskayaBattlefield:
    CAMP_TYPES = (5, 5, 6, 6, 10)
    MIN_VM_FUNCTIONS = 6236

    def __init__(self, native, *, profile=None, position_profile=None, match_profile=None):
        self.native = native
        self.profile = PROFILE if profile is None else profile
        self.position_profile = position_profile
        self.match_profile = match_profile

    _pointer = staticmethod(VolskayaObjective._pointer)

    def _verify(self, n):
        p = self.profile
        if (p.get('build') != 98348 or n.profile.get('build') != 98348
                or len(p.get('functions', ())) != 15 or not p.get('signatures')
                or n.value(n.base + 0x35C8CD9, 'B') != 1):
            raise NativeUnavailable('profil_champ_bataille_invalide')
        pe = n.base + n.global_u32(0x3C)
        if n.value(pe+8) != p['pe_timestamp'] or n.value(pe+80) != p['image_size']:
            raise NativeUnavailable('build_champ_bataille_invalide')
        for s in p['signatures']:
            if hashlib.sha256(n.read(n.base+s['rva'], s['size'])).hexdigest() != s['sha256']:
                raise NativeUnavailable('signature_champ_bataille_invalide')
        count, size = n.global_u32(0x2FA70F0), n.global_u32(0x3B8C904)
        table = self._pointer(n.value(n.base+0x3B8C5C8, 'Q'))
        if (not self.MIN_VM_FUNCTIONS <= count <= 65536 or not 4 <= size <= 0x180000
                or n.value(n.base+0x2FA7100, 'Q') != table):
            raise NativeUnavailable('racine_vm_champ_bataille_invalide')
        for f in p['functions']:
            if not 0 <= f['index'] < count:
                raise NativeUnavailable('index_vm_champ_bataille_invalide')
            record = self._pointer(n.value(table+f['index']*8, 'Q'))
            off = n.value(record+8)
            if (n.value(record+0x50) != f['index'] or not 4 <= off
                    or not 0 < f['length'] <= 8192 or off+f['length'] > size):
                raise NativeUnavailable('borne_vm_champ_bataille_invalide')
            ln, flags = struct.unpack('<II', n.read(record+0x58, 8))
            if ln >> 2 != len(f['name']):
                raise NativeUnavailable('nom_vm_champ_bataille_invalide')
            string = self._pointer(n.value(record+0x60, 'Q')) if flags & 2 else record+0x60
            if n.read(string, ln>>2) != f['name'].encode('ascii'):
                raise NativeUnavailable('nom_vm_champ_bataille_invalide')
            if hashlib.sha256(n.read(n.base+0x3B8C920+off, f['length'])).hexdigest() != f['sha256']:
                raise NativeUnavailable('code_vm_champ_bataille_invalide')

    def _resolve(self, n, tag):
        if type(tag) is not int or not 0 <= tag <= 0xFFFFFFFF or (tag+1) & 0xFFFFFFFE == 0:
            return None
        index = tag >> 22
        limit = n.global_u32(0x34F02C4)
        if not 1 <= limit <= 65536 or index >= limit:
            return None
        page = (tag >> 26)*8
        low = n.global_u32(0x34F02C8+page) ^ n.global_u32(0x32C38B4)
        high = (n.global_u32(0x34F02CC+page)+n.global_u32(0x32C55D0)) & 0xFFFFFFFF
        unit = self._pointer(((high << 32) | low)+(index & 15)*0x2F0)
        # No owner, type, position or vitals read on a recycled reference.
        return unit if n.value(unit+0x10) == tag else None

    def _unit_type(self, n, unit):
        flags = n.masked_byte(unit+0x39, 0x20)
        packed = n.value(unit+(0x20 if flags & 0x20 else 0x18), 'Q')
        catalog = self._pointer(packed & ~31)
        index = n.value(catalog+2, 'H')
        root = self._pointer(n.value(n.base+0x3388B18, 'Q'))
        database = self._pointer(n.value(root+0x2A0, 'Q'))
        count = n.value(database+0x90)
        if not 0 < count <= 65536 or index >= count:
            raise NativeUnavailable('borne_catalogue_unite_invalide')
        table = self._pointer(n.value(database+0xA0, 'Q'))
        descriptor = self._pointer(n.value(table+index*8, 'Q'))
        if n.value(descriptor+0x40, 'H') != index:
            raise NativeUnavailable('index_catalogue_unite_invalide')
        string = self._pointer(n.value(descriptor+0x30, 'Q'))
        header = string+0x18
        length, string_flags = struct.unpack('<II', n.read(header, 8))
        length >>= 2
        if not 0 < length <= 128:
            raise NativeUnavailable('longueur_type_unite_invalide')
        buffer = self._pointer(n.value(header+8, 'Q'), alignment=1) if string_flags & 2 else header+8
        try:
            name = n.read(buffer, length).decode('ascii')
        except UnicodeError:
            raise NativeUnavailable('type_unite_non_ascii') from None
        if not re.fullmatch('[A-Za-z0-9_]+', name):
            raise NativeUnavailable('type_unite_invalide')
        return name

    def _team(self, n, owner):
        if owner in (11, 12):
            return owner-11
        if owner in (0,15):
            return 'neutral'
        if 1 <= owner <= 10:
            player = self._pointer(n.player_pointer(owner))
            team, kind = struct.unpack('<BB', n.read(player+0x1C, 2))
            if team in (0, 1) and kind in (1, 2):
                return team
        raise NativeUnavailable('proprietaire_champ_bataille_invalide')

    @staticmethod
    def _life(name, flags):
        if name is None or flags is None:
            return 'unknown'
        if name == 'TownCannonTowerDead' or flags & 6:
            return 'destroyed'
        return 'alive'

    def _camps(self, n, *, include_timers=True):
        g = n.base+GLOBAL_DATA
        if n.value(g+0xE2130) != 5:
            raise NativeUnavailable('nombre_camps_volskaya_invalide')
        camps, seen_tags, seen_timers = [], set(), set()
        for index, expected_type in enumerate(self.CAMP_TYPES, 1):
            a = g+index*780
            kind, defender = struct.unpack('<ii', n.read(a+0xDF070, 8))
            merc = n.value(a+0xDF0BA, 'i')
            enabled, hibernation = struct.unpack('<BB', n.read(a+0xDF33B, 2))
            spawned = n.value(a+0xDF352, 'B')
            state = n.value(a+0xDF353, 'i')
            capture = n.value(a+0xDF367, 'B')
            if (kind != 0 or defender != expected_type or merc != expected_type
                    or any(v not in (0, 1) for v in (enabled, hibernation, spawned, capture))
                    or state not in range(6)):
                raise NativeUnavailable('etat_camp_volskaya_invalide')
            tag = n.value(a+0xDF363)
            refs = (n.value(a+0xDF33E), n.value(a+0xDF342))
            if tag in seen_tags or refs[0] == refs[1] or any(ref in seen_timers for ref in refs):
                raise NativeUnavailable('references_camps_ambigues')
            seen_tags.add(tag)
            seen_timers.update(refs)
            unit = self._resolve(n, tag)
            if unit is None or self._unit_type(n, unit) != 'TownMercCampCaptureBeacon':
                raise NativeUnavailable('reference_balise_camp_invalide')
            owner = n.value(unit+0x44, 'B')
            n.unit_pointer(tag, owner)
            last_player = n.value(a+0xDF337, 'i')
            camps.append({'index': index, 'defender_type': defender, 'merc_type': merc,
                'beacon_tag': tag, 'beacon_generation': tag & 0x3FFFFF,
                'beacon_owner': owner, 'last_capture_team': self._team(n, last_player),
                'enabled': bool(enabled), 'spawned': bool(spawned), 'state_code': state,
                'capture_enabled': bool(capture), 'personal_hibernation': bool(hibernation)})
        if include_timers:
            self._camp_timers(n,camps)
        return camps

    def _camp_timers(self,n,camps):
        if not camps:
            return
        helper = VolskayaObjective(n)
        registry = helper._timer_registry(n)
        for row in camps:
            index = row['index']
            row['birth'] = helper._timer(n,index*780+0xDF33E,registry)
            row['respawn'] = helper._timer(n,index*780+0xDF342,registry)

    def _towns(self, n):
        g = n.base+GLOBAL_DATA
        if n.value(g+0xD4F8D) != 12:
            raise NativeUnavailable('nombre_villes_volskaya_invalide')
        result, seen = [], set()
        for town in range(1, 13):
            a = g+town*1065
            lane, owner = struct.unpack('<ii', n.read(a+0xD4F91, 8))
            count = n.value(a+0xD4FA2)
            if lane not in (1, 2, 3) or owner not in (11, 12) or not 1 <= count <= 63:
                raise NativeUnavailable('ville_volskaya_invalide')
            for index in range(1, count+1):
                kind = n.value(a+0xD4FA6+index*4)
                tag = n.value(a+0xD50A6+index*4)
                if kind not in range(1, 7) or tag in seen:
                    raise NativeUnavailable('registre_structure_ambigu')
                seen.add(tag)
                unit = self._resolve(n, tag)
                row = dict(town=town, index=index, lane=lane, town_team=owner-11,
                           preset=kind, tag=tag, generation=tag & 0x3FFFFF)
                if unit is None:
                    row.update(state='unknown', reason='reference_absente_ou_recyclee')
                else:
                    current_owner = n.value(unit+0x44, 'B')
                    n.unit_pointer(tag, current_owner)
                    name = self._unit_type(n, unit)
                    flags = n.value(unit+0x39, 'B')
                    row.update(unit_type=name, kind=structure_kind(name),
                        team=self._team(n, current_owner), state=self._life(name, flags))
                    if row['kind'] is None:
                        row.update(state='unknown', reason='type_structure_non_couvert')
                result.append(row)
        return result

    def _census(self, n, *, unit_pointers=None):
        """Bounded ACTIVE unit table; not a heap/name occurrence scan.

        Raw diagnostics only. Non-structure names, owners, XY and vitals are
        not returned. A table slot is checked against its full current tag.
        """
        limit = n.global_u32(0x34F02C4)
        if not 1 <= limit <= 1024:
            raise NativeUnavailable('borne_recensement_unites_invalide')
        rows, unknown, names = [], [], {}
        for page_index in range((limit+15)//16):
            off = page_index*8
            low = n.global_u32(0x34F02C8+off)^n.global_u32(0x32C38B4)
            high = (n.global_u32(0x34F02CC+off)+n.global_u32(0x32C55D0)) & 0xFFFFFFFF
            page = (high << 32) | low
            if not page:
                continue
            self._pointer(page)
            for index in range(page_index*16, min(limit, (page_index+1)*16)):
                unit = page+(index & 15)*0x2F0
                # Only consumed fields: unused +0x14 and +0x42 bytes change
                # continuously and are not an identity/type/owner source.
                # Never read XY (+0x60), vitals (+0x220) or hero components.
                bulk = getattr(n.memory,'census_header',None)
                header = bulk(unit) if callable(bulk) else None
                tag = struct.unpack_from('<I',header)[0] if header is not None else n.value(unit+0x10)
                if (tag+1) & 0xFFFFFFFE == 0 or tag >> 22 != index:
                    # This is no active reference and produces no row. Its
                    # allocator churn is not a structure generation source;
                    # missing layout entries remain unknown, never destroyed.
                    continue
                if header is not None:
                    n.memory.read_set.append((unit+0x10,header[:4]))
                if header is None:
                    flags = n.masked_byte(unit+0x39, 0x20)
                    packed = n.value(unit+(0x20 if flags & 0x20 else 0x18),'Q')
                else:
                    flags = n.masked_byte(unit+0x39, 0x20)
                    off = 0x10 if flags & 0x20 else 8
                    packed = struct.unpack_from('<Q',header,off)[0]
                    n.memory.read_set.append((unit+0x10+off,header[off:off+8]))
                catalog = self._pointer(packed & ~31)
                if catalog not in names:
                    try:
                        names[catalog] = self._unit_type(n, unit)
                    except NativeUnavailable:
                        unknown.append(index)
                        continue
                name = names[catalog]
                kind = structure_kind(name)
                if kind is None:
                    continue
                # Actual structure rows also consume the life bits.
                flags = n.masked_byte(unit+0x39, 0x26)
                if header is None:
                    owner = n.value(unit+0x44,'B')
                else:
                    owner = header[0x34]
                    n.memory.read_set.append((unit+0x44,header[0x34:0x35]))
                if unit_pointers is not None:
                    unit_pointers[tag] = unit
                rows.append(dict(tag=tag, generation=tag & 0x3FFFFF,
                    unit_type=name, kind=kind, team=self._team(n, owner),
                    state=self._life(name, flags)))
        return {'structures': rows, 'unresolved_slots': unknown,
                'unit_limit': limit, 'known_structure_count': len(rows)}

    def inspect_saved(self):
        self._verify(self.native)
        return {'status': 'offline_non_atomic', 'camps': self._camps(self.native),
                'structures': self._towns(self.native), 'catalogue_complete': False,
                'census': self._census(self.native)}

    def _observe(self, map_id, *, section='inventory', context=None, hero_ids=None):
        if map_id != 'Volskaya' or getattr(self.native.memory, 'recorded_non_atomic', False):
            raise NativeUnavailable('carte_ou_capture_champ_bataille_non_prise_en_charge')
        expected = copy.deepcopy(context)
        clock = getattr(self.native.memory, 'positions_clock', time.monotonic)
        start = clock()
        memory = _SelectedCensusMemory(self.native.memory)
        n = NativeReader(memory, profile=self.native.profile)
        before = self._clock(n, memory)
        self._verify(n)
        identity = VolskayaObjective(n, position_profile=self.position_profile,
            match_profile=self.match_profile)._perspective(n, map_id, hero_ids)
        if expected is not None:
            cm, match, local, team, _ = AlliedPositions._context(expected)
            if (cm != map_id or identity['native_match_id'] != match
                    or identity['local_id'] != local or identity['team'] != team):
                raise NativeUnavailable('perspective_champ_bataille_incoherente')
        if section == 'inventory':
            result = {'camps':self._camps(n),'structures':self._towns(n),'census':self._census(n),'catalogue_complete':False}
        elif section == 'camps':
            from .battlefield_details import camp_details
            result = {'camps':camp_details(n,self,self._camps(n),identity['local_id'])}
        elif section == 'structures':
            from .battlefield_details import structure_details
            units = {}
            census = self._census(n,unit_pointers=units)
            result = {'structures':structure_details(n,self,census,units,identity['local_id'],STRUCTURE_LAYOUT),
                      'unresolved_slots':census['unresolved_slots']}
        elif section == 'combined':
            from .visibility import CurrentVisibility
            from .battlefield_details import camp_details,structure_details
            # One bounded observation verifies visibility once and rechecks
            # every consumed camp AND structure source before issuing either.
            CurrentVisibility(n)._verify(n)
            camps = camp_details(n,self,self._camps(n,include_timers=False),identity['local_id'],verify_visibility=False)
            units = {}
            census = self._census(n,unit_pointers=units)
            result = {'camps':camps,
                      'structures':structure_details(n,self,census,units,identity['local_id'],STRUCTURE_LAYOUT,verify_visibility=False),
                      'unresolved_slots':census['unresolved_slots']}
            self._camp_timers(n,camps)
        else:
            raise NativeUnavailable('section_champ_bataille_invalide')
        after = self._clock(n, memory)
        for address, size, slices in memory.coherence_checks(self._coherence_reads(memory.read_set)):
            data = self.native.read(address, size)
            if any(data[offset:offset+len(expected)] != expected for offset, expected in slices):
                raise NativeUnavailable('lecture_champ_bataille_dechiree')
        memory.verify_bits(self.native)
        window = clock()-start
        if not 0 <= after-before <= 0.125 or not 0 <= window <= 0.125 or context != expected:
            raise NativeUnavailable('lecture_champ_bataille_perimee')
        return dict(result, **identity, status='diagnostic_unreleased', map_id=map_id,
                    mission_t_s=after, read_window_s=window,section=section,_acquired=start)

    def diagnose(self, map_id, *, section='inventory', context=None, hero_ids=None):
        result = self._observe(map_id,section=section,context=context,hero_ids=hero_ids)
        result.pop('_acquired')
        return result

    @staticmethod
    def _coherence_reads(read_set):
        # Initial reads remain fully recorded, including repetitions. Never
        # coalesce a contradiction; only identical address/size/bytes can use
        # one final equality check. Overlapping different sizes stay separate.
        unique = {}
        observed_bytes = {}
        for address, data in read_set:
            for offset, value in enumerate(data):
                at = address+offset
                if at in observed_bytes and observed_bytes[at] != value:
                    raise NativeUnavailable('lecture_champ_bataille_dechiree')
                observed_bytes[at] = value
            key = address, len(data)
            if key in unique and unique[key] != data:
                raise NativeUnavailable('lecture_champ_bataille_dechiree')
            unique[key] = data
        return [(address, data) for (address, size), data in unique.items()]

    @staticmethod
    def _clock(n, memory):
        # The tick counter is a bounded interval, NOT a stable business field.
        # Retain all four reads of its encoded root in the equality read-set;
        # omit only the final four-byte counter from that equality comparison.
        # TraceMemory still records it for exact ordered playback.
        start = len(memory.read_set)
        # Both boundary clocks (including roots) must be actual fresh reads.
        memory.fresh = True
        try:
            value = n.read_clock()
        finally:
            memory.fresh = False
        if len(memory.read_set) != start+5 or len(memory.read_set[-1][1]) != 4:
            raise NativeUnavailable('trace_horloge_champ_bataille_invalide')
        memory.read_set.pop()
        return value

    def read(self, context, **options):
        from .acquisition import issue
        from .battlefield_details import camp_public,structure_public
        map_id, match_id, _, _, _ = AlliedPositions._context(context)
        if map_id not in VALIDATED_MAPS:
            raise NativeUnavailable('champ_bataille_non_valide_en_recette')
        packets = {}
        raw = self._observe(map_id,section='combined',context=context,**options)
        acquired = raw.pop('_acquired')
        for section,project in (('camps',camp_public),('structures',structure_public)):
            packet = {k:raw[k] for k in ('map_id','local_id','team','local_hero','native_session',
                       'mission_t_s','read_window_s','section')}
            packet.update(status='validated',match_id=match_id)
            packet['section'] = section
            packet[section] = [project(row) for row in raw[section]]
            packets[section] = issue(packet,acquired)
        return packets
