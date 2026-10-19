"""Synthetic tests only; never accepted as Volskaya recipe evidence."""
import unittest
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from test_native import NativeMemory
from test_objectives import ObjectiveMemory
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.battlefield import VolskayaBattlefield, structure_kind
from hotstate.positions import _RecordedMemory
from etudes.rea.scripts.capture_positions import TraceMemory

class BattlefieldTests(unittest.TestCase):
    def test_structure_catalogue_distinguishes_ruins_and_unknown(self):
        for name,kind in [('KingsCore','core'),('TownTownHallL2','fort'),
                          ('TownTownHallL3','keep'),('TownMoonwellL2','healing_fountain'),
                          ('TownCannonTowerL3Standalone','tower'),('TownCannonTowerDead','tower_ruins'),
                          ('TownGateL215BLUR','gate'),('TownWallRadial16L2','wall')]:
            self.assertEqual(structure_kind(name),kind)
        for name in ('HeroMuradin','OverwatchTurret','TownCannonTowerL99','KingsCoreExtra'):
            self.assertIsNone(structure_kind(name))

    def memory(self):
        m=NativeMemory();b=m.module_base
        m.pack(b+0x34F02C4,'I',16)
        m.pack(b+0x34F02C8,'II',0x900000,0)
        m.pack(b+0x32C38B4,'I',0);m.pack(b+0x32C55D0,'I',0)
        m.pack(0x900010,'I',1);m.pack(0x900044,'B',11)
        return m,VolskayaBattlefield(NativeReader(m,profile=m.profile),profile={})

    def test_recycled_reference_does_not_read_replacement(self):
        m,r=self.memory();m.pack(0x900010,'I',2)
        original=m.read_memory
        def restricted(address,size):
            if address==0x900044:raise AssertionError('replacement owner accessed')
            return original(address,size)
        m.read_memory=restricted
        self.assertIsNone(r._resolve(r.native,1))

    def test_reference_bounds_and_current_generation(self):
        m,r=self.memory()
        self.assertEqual(r._resolve(r.native,1),0x900000)
        for tag in (0,0xffffffff,16<<22):
            self.assertIsNone(r._resolve(r.native,tag))

    def test_public_release_closed_and_rolling_dump_rejected(self):
        m,r=self.memory()
        with self.assertRaises(NativeUnavailable):r.read({'map_id':'Volskaya'})
        m.recorded_non_atomic=True
        with self.assertRaises(NativeUnavailable):r.diagnose('Volskaya')

    def test_no_absence_to_destroyed_and_ruins_not_alive(self):
        self.assertEqual(VolskayaBattlefield._life(None,None),'unknown')
        self.assertEqual(VolskayaBattlefield._life('TownCannonTowerDead',0),'destroyed')
        self.assertEqual(VolskayaBattlefield._life('TownCannonTowerL2',2),'destroyed')
        self.assertEqual(VolskayaBattlefield._life('TownCannonTowerL2',0),'alive')

    def camp_memory(self):
        m=ObjectiveMemory();b=m.module_base
        m.pack(b+0x34F02C4,'I',16)
        m.pack(b+0x34F02C8,'II',0x900000,0)
        m.pack(b+0x32C38B4,'I',0);m.pack(b+0x32C55D0,'I',0)
        refs=[3<<16|i for i in range(5,15)]
        m.pack(b+0x2F72670,'I',10)
        m.pack(0x650000,'I'*10,*refs)
        m.pack(m.g+0xE2130,'I',5)
        for i,kind in enumerate((5,5,6,6,10),1):
            a=m.g+i*780
            m.pack(a+0xDF070,'ii',0,kind);m.pack(a+0xDF0BA,'i',kind)
            m.pack(a+0xDF337,'i',15)
            m.pack(a+0xDF33B,'BB',1,1)
            m.pack(a+0xDF352,'Bi',0,2)
            m.pack(a+0xDF367,'B',0)
            tag=((i-1)<<22)|1;unit=0x900000+(i-1)*0x2F0
            m.pack(a+0xDF363,'I',tag)
            m.pack(unit+0x10,'I',tag);m.pack(unit+0x44,'B',0)
            left,right=refs[(i-1)*2:i*2]
            m.pack(a+0xDF33E,'II',left,right)
            m.timer(left&65535,0,0,paused=1,clock=1)
            m.timer(right&65535,0,0,paused=1,clock=1)
        return m,VolskayaBattlefield(NativeReader(m,profile=m.profile),profile={})

    def test_camp_dead_before_spawn_is_not_captured_or_ready(self):
        m,r=self.camp_memory()
        with patch.object(r,'_unit_type',return_value='TownMercCampCaptureBeacon'):
            camps=r._camps(r.native)
        self.assertEqual(len(camps),5)
        self.assertEqual([c['defender_type'] for c in camps],[5,5,6,6,10])
        for c in camps:
            self.assertEqual(c['state_code'],2)
            self.assertFalse(c['spawned'])
            self.assertEqual(c['last_capture_team'],'neutral')
            self.assertIsNone(c['respawn']['remaining_s'])

    def test_camp_corruption_ambiguity_and_no_default_owner(self):
        cases=[(0xDF070,'i',1),(0xDF074,'i',7),(0xDF0BA,'i',7),
               (0xDF33B,'B',2),(0xDF352,'B',2),(0xDF353,'i',6),
               (0xDF367,'B',2),(0xDF337,'i',14),
               (0xDF342,'I',3<<16|5),(0xDF363,'I',0)]
        for off,fmt,value in cases:
            with self.subTest(off=off):
                m,r=self.camp_memory();m.pack(m.g+780+off,fmt,value)
                with patch.object(r,'_unit_type',return_value='TownMercCampCaptureBeacon'):
                    with self.assertRaises(NativeUnavailable):r._camps(r.native)

    def test_vm_active_root_and_function_fingerprints(self):
        m=NativeMemory();b=m.module_base
        p=json.loads((Path(__file__).resolve().parents[1]/'hotstate/profiles/98348-battlefield.json').read_text())
        p['pe_timestamp']=m.profile['pe_timestamp'];p['signatures']=copy.deepcopy(m.profile['signatures'])
        table=0x200000
        m.pack(b+0x3B8C5C8,'Q',table);m.pack(b+0x2FA7100,'Q',table)
        m.pack(b+0x2FA70F0,'I',6238);m.pack(b+0x3B8C904,'I',0x180000)
        for i,spec in enumerate(p['functions']):
            record=0x300000+i*4096;off=4+i*8192
            m.pack(table+spec['index']*8,'Q',record)
            m.pack(record+8,'I',off);m.pack(record+0x50,'I',spec['index'])
            name=spec['name'].encode()
            m.pack(record+0x58,'IIQ',len(name)<<2,2,record+256)
            m.put(record+256,name)
            code=bytes([i+1])*spec['length'];m.put(b+0x3B8C920+off,code)
            spec['sha256']=hashlib.sha256(code).hexdigest()
        r=VolskayaBattlefield(NativeReader(m,profile=m.profile),profile=p)
        r._verify(r.native)
        m.pack(b+0x2FA7100,'Q',table+8)
        with self.assertRaises(NativeUnavailable):r._verify(r.native)
        m.pack(b+0x2FA7100,'Q',table)
        m.put(b+0x3B8C920+4,b'!')
        with self.assertRaises(NativeUnavailable):r._verify(r.native)

    def test_census_1024_slots_fits_trace_without_xy_or_vitals(self):
        m=NativeMemory();b=m.module_base
        m.pack(b+0x34F02C4,'I',1024)
        m.pack(b+0x32C38B4,'I',0);m.pack(b+0x32C55D0,'I',0)
        for page in range(64):
            address=0x1000000+page*0x10000
            m.pack(b+0x34F02C8+page*8,'Q',address)
            for slot in range(16):
                unit=address+slot*0x2F0
                m.put(unit+0x10,bytes(0x38))
                m.pack(unit+0x10,'I',((page*16+slot)<<22)|1)
                m.pack(unit+0x18,'Q',0x2000000)
        trace=TraceMemory(m);recorded=_RecordedMemory(trace)
        n=NativeReader(recorded,profile=m.profile);r=VolskayaBattlefield(n,profile={})
        with patch.object(r,'_unit_type',return_value='HeroMuradin'):
            census=r._census(n)
        for address,data in recorded.read_set:
            self.assertEqual(trace.read_memory(address,len(data)),data)
        self.assertLess(len(trace.reads),8192)
        self.assertEqual(census['known_structure_count'],0)
        self.assertEqual(census['unresolved_slots'],[])
        self.assertEqual(census['unit_limit'],1024)

    def test_clock_keeps_root_checks_not_tick_equality(self):
        m=NativeMemory();trace=TraceMemory(m);recorded=_RecordedMemory(trace)
        n=NativeReader(recorded,profile=m.profile)
        start=len(recorded.read_set)
        first=VolskayaBattlefield._clock(n,recorded)
        self.assertEqual(len(recorded.read_set)-start,4)
        counter=trace.reads[-1]['address']
        m.pack(counter,'i',int((first+0.0625)*4096))
        second=VolskayaBattlefield._clock(n,recorded)
        self.assertEqual(second-first,0.0625)
        self.assertFalse(any(address==counter for address,data in recorded.read_set))
        for address,data in recorded.read_set:
            self.assertEqual(m.read_memory(address,len(data)),data)

if __name__=='__main__':unittest.main()
