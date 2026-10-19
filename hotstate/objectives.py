"""Current Volskaya state from active build98348 Galaxy globals, read-only.

Diagnostic candidate ONLY: release stays closed until synchronized HUD recipe
and independent review. No trigger counters, event cache or replay producer.
"""
from __future__ import annotations

import hashlib
import json
import struct
import time
from pathlib import Path

from .native import NativeReader, NativeUnavailable
from .positions import AlliedPositions, _RecordedMemory

PROFILE = json.loads((Path(__file__).parent / 'profiles/98348-objectives.json').read_text(encoding='utf-8'))
GLOBAL_DATA = 0x3D0C920
MAX_WINDOW_S = 0.125
VALIDATED_MAPS = ()


class VolskayaObjective:
    def __init__(self, native, *, profile=None, position_profile=None, match_profile=None):
        self.native = native
        self.profile = profile if profile is not None else PROFILE
        self.position_profile = position_profile
        self.match_profile = match_profile

    @staticmethod
    def _pointer(value, *, alignment=8):
        if not 0x10000 <= value < 0x800000000000 or value % alignment:
            raise NativeUnavailable('pointeur_objectif_invalide')
        return value

    def _verify_vm(self, n):
        p = self.profile
        pe = n.base + n.global_u32(0x3C)
        if (p.get('build') != 98348 or n.profile.get('build') != 98348
                or n.value(pe + 8) != p['pe_timestamp']
                or n.value(pe + 24 + 56) != p['image_size']
                or not p.get('signatures') or len(p.get('functions', ())) != 28
                or n.value(n.base + 0x35C8CD9, 'B') != 1):
            raise NativeUnavailable('profil_objectif_non_pris_en_charge')
        for s in p['signatures']:
            if hashlib.sha256(n.read(n.base+s['rva'], s['size'])).hexdigest() != s['sha256']:
                raise NativeUnavailable('signature_objectif_invalide')
        count = n.global_u32(0x2FA70F0)
        table = self._pointer(n.value(n.base+0x3B8C5C8, 'Q'))
        size = n.global_u32(0x3B8C904)
        if (not 6204 < count <= 65536 or not 4 <= size <= 0x180000
                or n.value(n.base+0x2FA7100, 'Q') != table):
            raise NativeUnavailable('racine_vm_objectif_invalide')
        for f in p['functions']:
            index = f['index']
            if not 0 <= index < count:
                raise NativeUnavailable('index_vm_objectif_invalide')
            record = self._pointer(n.value(table+index*8, 'Q'))
            off = n.value(record+8)
            if (n.value(record+0x50) != index or off < 4
                    or not 0 < f['length'] <= 8192 or off+f['length'] > size):
                raise NativeUnavailable('borne_vm_objectif_invalide')
            ln, flags = struct.unpack('<II', n.read(record+0x58,8))
            if ln >> 2 != len(f['name']):
                raise NativeUnavailable('nom_vm_objectif_invalide')
            string = self._pointer(n.value(record+0x60,'Q')) if flags & 2 else record+0x60
            if n.read(string,ln>>2) != f['name'].encode('ascii'):
                raise NativeUnavailable('nom_vm_objectif_invalide')
            code = n.read(n.base+0x3B8C920+off,f['length'])
            if hashlib.sha256(code).hexdigest() != f['sha256']:
                raise NativeUnavailable('script_vm_objectif_invalide')

    def _timer_registry(self, n):
        slots = n.value(n.base+0x4020970,'Q')
        count = n.global_u32(0x2F72670)
        if slots != n.base+0x4020980 or not 2 <= count <= 8192:
            raise NativeUnavailable('registre_timer_objectif_invalide')
        table = self._pointer(n.value(n.base+0x2F72680,'Q'))
        registered = struct.unpack('<'+'I'*count, n.read(table,count*4))
        return slots, registered

    def _timer(self, n, global_offset, registry):
        slots, registered = registry
        ref = n.value(n.base+GLOBAL_DATA+global_offset)
        index, generation = ref & 65535, ref >> 16
        if index <= 1 or generation == 0 or registered.count(ref) != 1:
            raise NativeUnavailable('reference_timer_objectif_invalide')
        gen, _, refs, kind, _, pointer = struct.unpack('<HHHBBQ',n.read(slots+index*16,16))
        if gen != generation or not refs or kind != 19:
            raise NativeUnavailable('generation_type_timer_objectif_invalide')
        data = n.read(self._pointer(pointer),40)
        vt, owner = struct.unpack_from('<QI',data)
        repeat, paused, expired, reserved = data[16:20]
        clock, elapsed, deadline = struct.unpack_from('<Iii',data,20)
        if (vt != n.base+0x26B4F18 or owner != ref or repeat or reserved
                or paused not in (0,1) or expired not in (0,1) or clock not in (0,1)
                or not 0 <= elapsed <= 21600*4096 or not 0 <= deadline <= 600*4096
                or (deadline > 0 and clock != 0)):
            raise NativeUnavailable('objet_timer_objectif_invalide')
        if deadline == 0:
            if elapsed != 0 or expired:
                raise NativeUnavailable('timer_objectif_non_initialise')
            remaining = None
        else:
            if expired and not deadline <= elapsed <= deadline+4096:
                raise NativeUnavailable('expiration_timer_objectif_incoherente')
            if not expired and elapsed > deadline+4096:
                raise NativeUnavailable('expiration_timer_objectif_incoherente')
            remaining = max(0,deadline-elapsed)/4096
        return {'remaining_s':remaining,'paused':bool(paused)}

    def _point(self, n, index, contest_goal, victory_goal):
        g = n.base+GLOBAL_DATA+index*113
        active = n.value(g+0x1975DC,'B')
        owner = n.value(g+0x1975DD,'i')
        callout = n.value(g+0x1975E1,'B')
        state = n.value(g+0x19761B,'i')
        overtime = n.value(g+0x1975FA,'B')
        remaining = n.value(g+0x1975FB,'i')
        contest = struct.unpack('<ii',n.read(g+0x1975E6,8))
        victory = struct.unpack('<ii',n.read(g+0x1975F2,8))
        if (active not in (0,1) or owner not in (0,1,2) or callout not in (0,1)
                or state not in (0,1,2,3) or overtime not in (0,1)
                or not -256 <= remaining <= 5*4096
                or any(not 0 <= x <= contest_goal for x in contest)
                # AdvanceVictory adds one 0.0625s step BEFORE awarding and
                # disabling the point. That terminal value is retained on the
                # inactive record; unlike the live progress it is not clamped.
                or any(not 0 <= x <= victory_goal + (0 if active else 256) for x in victory)):
            raise NativeUnavailable('etat_point_objectif_invalide')
        # state is authoritative; isContested is a separate UI callout flag.
        # Empty is NOT necessarily neutral: victory can progress while empty.
        return {'index':index,'active':bool(active),'owner':'neutral' if owner==0 else owner-1,
                'state':('capturing','contested','empty','resetting')[state],
                'contested':state==1,'contest_seconds':[x/4096 for x in contest],
                'victory_seconds':[x/4096 for x in victory],
                'victory_percent':[(x*4096//victory_goal)*100//4096 for x in victory],
                'overtime':bool(overtime),'overtime_remaining_s':max(0,remaining)/4096 if overtime else None}

    def _behavior_name(self, n, catalog):
        # Native behavior lookup: CDataBehavior's ushort index -> active catalog.
        index = n.value(catalog+2,'H')
        root = self._pointer(n.value(n.base+0x3388B18,'Q'))
        database = self._pointer(n.value(root+0x70,'Q'))
        count = n.value(database+0x90)
        table = self._pointer(n.value(database+0xA0,'Q'))
        if not 0 < count <= 65536 or index >= count:
            raise NativeUnavailable('index_catalogue_objectif_invalide')
        descriptor = self._pointer(n.value(table+index*8,'Q'))
        length = n.value(descriptor+0x10,'Q')
        if n.value(descriptor+0x40,'H') != index or not 0 < length <= 128:
            raise NativeUnavailable('descripteur_comportement_objectif_invalide')
        string = self._pointer(n.value(descriptor+8,'Q'),alignment=1)
        try:
            return n.read(string,length).decode('ascii')
        except UnicodeError:
            raise NativeUnavailable('nom_comportement_objectif_invalide') from None

    def _duration(self, n, unit):
        # Follow the SAME first active component selection as UnitBehaviorDuration.
        # Bounded traversal; no generic private-memory search or cached pointer.
        head = n.value(unit+0x160,'Q')
        node = n.value(self._pointer(head),'Q') & ~1 if head else 0
        visited = set()
        while node:
            self._pointer(node)
            if node in visited or len(visited) >= 64:
                raise NativeUnavailable('liste_composants_objectif_invalide')
            visited.add(node)
            count = n.value(node+0x48,'B')
            if not 1 <= count <= 8:
                raise NativeUnavailable('compte_composants_objectif_invalide')
            for i in range(count):
                component = self._pointer(n.value(node+8+i*8,'Q'),alignment=4)
                if n.value(component+0x78,'B') & 1:
                    continue
                vt = self._pointer(n.value(component,'Q'))
                getter = self._pointer(n.value(vt+0x140,'Q'),alignment=1)
                if n.read(getter,6) != b'\xB8\x03\0\0\0\xC3':
                    continue
                catalog = self._pointer(n.value(component+0x70,'Q') & ~31)
                if self._behavior_name(n,catalog) != 'VehicleDragonTimedLife':
                    continue
                sentinel = component+0xC0
                entry = n.value(sentinel,'Q')
                count = n.value(component+0xF2,'H') if entry != sentinel else 0
                if not 0 <= count <= 64:
                    raise NativeUnavailable('compte_durees_objectif_invalide')
                seen, maximum = set(), 0
                for _ in range(count):
                    self._pointer(entry)
                    if entry == sentinel or entry in seen:
                        raise NativeUnavailable('liste_durees_objectif_invalide')
                    seen.add(entry)
                    enabled = n.value(entry+0x3E,'B')
                    if enabled not in (0,1):
                        raise NativeUnavailable('flag_duree_objectif_invalide')
                    if enabled == 0:
                        if n.value(entry+0x10,'i') < 1:
                            raise NativeUnavailable('duree_objectif_infinie')
                        remaining = n.value(entry+0x28,'i')
                        if not 0 <= remaining <= 600*65536:
                            raise NativeUnavailable('duree_objectif_hors_bornes')
                        maximum = max(maximum,remaining)
                    entry = n.value(entry,'Q')
                if entry != sentinel:
                    raise NativeUnavailable('fin_liste_durees_objectif_invalide')
                # Native fixed16 -> Galaxy fixed12 (truncation by four bits).
                return (maximum >> 4)/4096
            link = n.value(node,'Q')
            node = 0 if link & 1 else link
        return 0.0  # Native UnitBehaviorDuration returns zero for absent behavior.

    def _protector(self,n):
        tag = n.value(n.base+GLOBAL_DATA+0x19779D)
        if (tag+1) & 0xFFFFFFFE == 0:
            return {'state':'absent','team':None,'health_percent':None,'remaining_s':None}
        index = tag >> 22
        if index >= n.global_u32(0x34F02C4):
            raise NativeUnavailable('reference_protecteur_objectif_invalide')
        page = (tag >> 26)*8
        low = n.global_u32(0x34F02C8+page)^n.global_u32(0x32C38B4)
        high = (n.global_u32(0x34F02CC+page)+n.global_u32(0x32C55D0)) & 0xFFFFFFFF
        unit = self._pointer(((high<<32)|low)+(index&15)*0x2F0)
        owner = n.value(unit+0x44,'B')
        if owner not in (11,12) or n.unit_pointer(tag,owner) != unit:
            raise NativeUnavailable('proprietaire_protecteur_objectif_invalide')
        if n.value(unit+0x39,'B') & 6:
            return {'state':'destroyed','team':owner-11,'health_percent':None,'remaining_s':None}
        maximum, damage = n.value(unit+0x220,'i'),n.value(unit+0x22C,'i')
        if not 0 < maximum <= 1000000*4096 or not 0 <= damage <= maximum:
            raise NativeUnavailable('vie_protecteur_objectif_invalide')
        return {'state':'active','team':owner-11,'health_percent':100*(maximum-damage)/maximum,
                'remaining_s':self._duration(n,unit)}

    def _sample(self, n=None):
        n = self.native if n is None else n
        self._verify_vm(n)
        g = n.base+GLOBAL_DATA
        contest_goal, victory_goal = struct.unpack('<ii',n.read(g+0x1975B0,8))
        count,current = struct.unpack('<ii',n.read(g+0x197784,8))
        if count != 3 or not 0 <= current <= count or contest_goal != 3*4096 or victory_goal != 45*4096:
            raise NativeUnavailable('bornes_objectif_incoherentes')
        registry = self._timer_registry(n)
        cooldown = self._timer(n,0x19778C,registry)
        warning = self._timer(n,0x197790,registry)
        points = [self._point(n,i,contest_goal,victory_goal) for i in range(1,count+1)]
        active = [p for p in points if p['active']]
        if len(active)>1 or (active and active[0]['index']!=current):
            raise NativeUnavailable('points_actifs_objectif_ambigus')
        protector = self._protector(n)
        if active and protector['state']=='active':
            raise NativeUnavailable('point_et_protecteur_objectif_incoherents')
        phase = 'active' if active else 'protector' if protector['state']=='active' else 'warning' if (warning['remaining_s'] or 0)>0 else 'waiting'
        return {'phase':phase,'current_point':current or None,'point':active[0] if active else None,
                'points':points,'protector':protector,'cooldown':cooldown,'warning':warning,
                'contest_goal_s':contest_goal/4096,'victory_goal_s':victory_goal/4096}

    def _perspective(self,n,map_id):
        from .match import ActiveMatch
        helper = AlliedPositions(n,profile=self.position_profile)
        helper._verify(n)
        helper._bounds(n,map_id)
        active = ActiveMatch(profile=self.match_profile).observe(n)
        hero_ids = json.loads((Path(__file__).parent/'hero_ids.json').read_text(encoding='utf-8'))
        local,team,hero,_,stamp = helper._identity(n,hero_ids)
        return {'local_id':local,'team':team,'local_hero':hero,
                'native_match_id':active['match_id'],'native_session':stamp}

    def inspect_saved(self):
        return dict(self._sample(),status='offline_non_atomic')

    def diagnose(self,map_id):
        if map_id != 'Volskaya' or getattr(self.native.memory,'recorded_non_atomic',False):
            raise NativeUnavailable('carte_ou_capture_objectif_non_prise_en_charge')
        clock = getattr(self.native.memory,'positions_clock',time.monotonic)
        start = clock()
        memory = _RecordedMemory(self.native.memory)
        n = NativeReader(memory,profile=self.native.profile)
        before = n.read_clock()
        identity = self._perspective(n,map_id)
        sample = self._sample(n)
        for address,data in memory.read_set:
            if self.native.read(address,len(data)) != data:
                raise NativeUnavailable('lecture_objectif_dechiree')
        after,window = n.read_clock(),clock()-start
        if not 0 <= after-before <= MAX_WINDOW_S or not 0 <= window <= MAX_WINDOW_S:
            raise NativeUnavailable('fenetre_objectif_invalide')
        return dict(sample,**identity,status='diagnostic_unreleased',map_id=map_id,
                    mission_t_s=after,read_window_s=window)

    def read(self,context):
        raise NativeUnavailable('recette_objectifs_absente')
