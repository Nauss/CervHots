"""Synthetic bytecode/timer/state fixtures, never game evidence."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from test_native import NativeMemory
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.objectives import VolskayaObjective


class ObjectiveMemory(NativeMemory):
    def __init__(self):
        super().__init__()
        self.p = json.loads((Path(__file__).resolve().parents[1] / 'hotstate/profiles/98348-objectives.json').read_text())
        self.p['pe_timestamp'] = self.profile['pe_timestamp']
        self.p['signatures'] = copy.deepcopy(self.profile['signatures'])
        self.table = 0x200000
        b = self.module_base
        self.pack(b + 0x3B8C5C8, 'Q', self.table)
        self.pack(b + 0x2FA7100, 'Q', self.table)
        self.pack(b + 0x2FA70F0, 'I', 6238)
        self.pack(b + 0x3B8C904, 'I', 0x180000)
        for ordinal, spec in enumerate(self.p['functions']):
            record = 0x300000 + ordinal * 4096
            off = ordinal * 2048 + 4
            self.pack(self.table + spec['index'] * 8, 'Q', record)
            self.pack(record + 8, 'I', off)
            self.pack(record + 0x50, 'I', spec['index'])
            name = spec['name'].encode('ascii')
            self.pack(record + 0x58, 'IIQ', len(name) << 2, 2, record + 256)
            self.put(record + 256, name)
            data = bytes([ordinal + 1]) * spec['length']
            self.put(b + 0x3B8C920 + off, data)
            spec['sha256'] = hashlib.sha256(data).hexdigest()
        self.g = b + 0x3D0C920
        self.put(self.g + 0x1975B0, bytes(0x380))
        self.pack(self.g + 0x1975B0, 'ii', 3 * 4096, 45 * 4096)
        self.pack(self.g + 0x197784, 'ii', 3, 1)
        self.pack(b + 0x4020970, 'Q', b + 0x4020980)
        self.pack(b + 0x2F72670, 'I', 2)
        self.pack(b + 0x2F72680, 'Q', 0x650000)
        self.pack(0x650000, 'II', (3 << 16) | 5, (3 << 16) | 6)
        self.timer(5, 10, 150)
        self.timer(6, 0, 0, paused=1, clock=1)
        self.pack(self.g + 0x19778C, 'II', (3 << 16) | 5, (3 << 16) | 6)
        for i in range(1,4):
            self.point(i, state=2)

    def timer(self, idx, elapsed, deadline, paused=0, expired=0, clock=0):
        ptr = 0x600000 + idx * 4096
        ref = (3 << 16) | idx
        self.pack(self.module_base + 0x4020980 + idx * 16, 'HHHBBQ', 3, 0, 1, 19, 0, ptr)
        self.pack(ptr, 'QII4BIiiiI', self.module_base + 0x26B4F18, ref, 0, 0, paused, expired, 0,
                  clock, int(elapsed*4096), int(deadline*4096), 0, 0)

    def point(self, i, active=0, owner=0, state=2, progress=(0,0), contest=(0,0)):
        self.pack(self.g + 0x1975DC + i*113, 'BiB', active, owner, int(state == 1))
        self.pack(self.g + 0x1975E6 + i*113, 'ii', *(int(x*4096) for x in contest))
        self.pack(self.g + 0x1975F2 + i*113, 'ii', *(int(x*4096) for x in progress))
        self.pack(self.g + 0x19761B + i*113, 'i', state)

    def reader(self):
        return VolskayaObjective(NativeReader(self, profile=self.profile), profile=self.p)

    def protector(self, owner=11, team=None):
        b = self.module_base
        team = (0 if owner==11 else 1) if team is None else team
        self.point(1,owner=team+1,state=2)
        self.pack(b+0x34F02C4,'I',16)
        self.pack(b+0x34F02C8,'II',0x900000,0)
        self.pack(b+0x32C38B4,'I',0)
        self.pack(b+0x32C55D0,'I',0)
        self.pack(self.g+0x19779D,'I',1)
        self.pack(0x900000+0x10,'I',1)
        self.pack(0x900000+0x39,'B',0)
        self.pack(0x900000+0x44,'B',owner)
        self.pack(0x900000+0x220,'i',10000*4096)
        self.pack(0x900000+0x22C,'i',2500*4096)
        self.pack(0x900000+0x160,'Q',0xA00000)
        self.pack(0xA00000,'Q',0xA00100)
        self.pack(0xA00100,'QQ',1,0xB00000)
        self.pack(0xA00100+0x48,'B',1)
        self.pack(0xB00000,'Q',0xC00000)
        self.pack(0xB00000+0x78,'B',0)
        self.pack(0xC00000+0x140,'Q',b+0x800)
        self.put(b+0x800,b'\xB8\x03\0\0\0\xC3')
        self.pack(0xB00000+0x70,'Q',0xD00001)
        self.pack(0xD00000,'HH',6,5)
        self.pack(b+0x3388B18,'Q',0xE00000)
        self.pack(0xE00000+0x70,'Q',0xE01000)
        self.pack(0xE01000+0x90,'I',10)
        self.pack(0xE01000+0xA0,'Q',0xE02000)
        self.pack(0xE02000+5*8,'Q',0xE03000)
        self.pack(0xE03000+0x40,'H',5)
        name=b'VehicleDragonTimedLife'
        self.pack(0xE03000+8,'QQ',0xE04000,len(name))
        self.put(0xE04000,name)
        self.pack(0xB00000+0xC0,'Q',0xF00000)
        self.pack(0xB00000+0xF2,'H',1)
        self.pack(0xF00000,'Q',0xB00000+0xC0)
        self.pack(0xF00000+0x10,'i',1)
        self.pack(0xF00000+0x28,'i',int(79.5*65536)+15)
        self.pack(0xF00000+0x3E,'B',0)


class ObjectiveTests(unittest.TestCase):
    def test_completed_inactive_point_retains_at_most_one_source_step_overshoot(self):
        m=ObjectiveMemory()
        # Synthetic regression for the real game10 terminal184396/4096 value.
        # Old trace remains replayed under its original commit, never rewritten.
        m.point(1,owner=2,state=2,progress=(0,184396/4096))
        self.assertEqual(m.reader()._sample()['phase'],'waiting')
        m.point(1,owner=2,state=2,progress=(0,45.0625))
        self.assertEqual(m.reader()._sample()['points'][0]['victory_percent'],[0,100])
        m.point(1,owner=2,state=2,progress=(0,45.0625+1/4096))
        with self.assertRaises(NativeUnavailable):m.reader()._sample()
        m.point(1,active=1,owner=2,state=0,progress=(0,184396/4096))
        with self.assertRaises(NativeUnavailable):m.reader()._sample()

    def test_protector_life_and_behavior_duration_are_not_point_progress(self):
        for owner in (11,12):
            m=ObjectiveMemory();m.protector(owner)
            s=m.reader()._sample()
            self.assertEqual(s['phase'],'protector')
            self.assertIsNone(s['point'])
            self.assertEqual(s['protector'],{'state':'active','team':owner-11,'health_percent':75.0,'remaining_s':79.5})
            m.pack(0x900000+0x39,'B',2)
            self.assertEqual(m.reader()._sample()['protector']['state'],'destroyed')

    def test_protector_corrupt_recycled_or_untyped_references_refused(self):
        for kind in ('owner','health','component_cycle','entry_cycle','infinite','catalog_count','catalog_index','entry_flag'):
            with self.subTest(kind=kind):
                m=ObjectiveMemory();m.protector()
                if kind=='owner':m.pack(0x900000+0x44,'B',5)
                elif kind=='health':m.pack(0x900000+0x22C,'i',20000*4096)
                elif kind=='component_cycle':
                    m.pack(0xA00100,'Q',0xA00100);m.pack(0xB00000+0x78,'B',1)
                elif kind=='entry_cycle':m.pack(0xF00000,'Q',0xF00000)
                elif kind=='infinite':m.pack(0xF00000+0x10,'i',0)
                elif kind=='catalog_count':m.pack(0xE01000+0x90,'I',0)
                elif kind=='catalog_index':m.pack(0xE03000+0x40,'H',9)
                else:m.pack(0xF00000+0x3E,'B',2)
                with self.assertRaises(NativeUnavailable):m.reader()._sample()

    def test_recycled_protector_is_unknown_never_replacement_vitals_or_destroyed(self):
        m=ObjectiveMemory();m.protector()
        m.pack(0x900000+0x10,'I',2)
        original=m.read_memory
        def forbidden_vitals(address,size):
            if address in (0x900000+0x44,0x900000+0x39,0x900000+0x220,0x900000+0x22C,0x900000+0x160):
                raise AssertionError('replacement unit accessed')
            return original(address,size)
        m.read_memory=forbidden_vitals
        m.point(2,active=1,state=2)
        m.pack(m.g+0x197788,'i',2)
        sample=m.reader()._sample()
        self.assertEqual(sample['phase'],'active')
        self.assertEqual(sample['point']['owner'],'neutral')
        self.assertEqual(sample['protector']['state'],'unknown')
        self.assertIsNone(sample['protector']['health_percent'])
        self.assertIsNone(sample['protector']['remaining_s'])

    def test_actual_pilot_owner_is_bound_to_current_cplayer_and_winning_team(self):
        from unittest.mock import patch
        for team in (0,1):
            m=ObjectiveMemory();m.protector(owner=9,team=team)
            m.pack(0x1100000+0x1C,'BB',team,2)
            r=m.reader()
            with patch.object(r.native,'player_pointer',return_value=0x1100000) as resolve:
                result=r._sample()
                self.assertEqual(result['protector']['team'],team)
                resolve.assert_called_once_with(9)
                # A pilot of the other team is NOT accepted by broadening owner IDs.
                m.pack(0x1100000+0x1C,'B',1-team)
                with self.assertRaisesRegex(NativeUnavailable,'equipe_protecteur'):r._sample()
                m.pack(0x1100000+0x1C,'BB',team,3)
                with self.assertRaisesRegex(NativeUnavailable,'pilote_protecteur'):r._sample()

    def test_waiting_warning_active_contested_loss_recapture_and_reset(self):
        m = ObjectiveMemory(); r = m.reader()
        self.assertEqual(r._sample()['phase'], 'waiting')
        m.timer(6, 5, 30)
        self.assertEqual(r._sample()['phase'], 'warning')
        m.timer(6,30,30,expired=1)
        m.point(1,active=1,owner=0,state=2)
        s = r._sample(); self.assertEqual(s['phase'],'active'); self.assertEqual(s['point']['owner'],'neutral')
        m.point(1,active=1,owner=1,state=1,progress=(22.5,0),contest=(3,0))
        s = r._sample(); self.assertTrue(s['point']['contested']); self.assertEqual(s['point']['victory_percent'],[50,0])
        m.point(1,active=1,owner=2,state=0,progress=(22.5,9),contest=(0,3))
        # Galaxy fixed12 division truncates 9/45 before multiplication by100.
        s = r._sample(); self.assertEqual(s['point']['owner'],1); self.assertEqual(s['point']['victory_percent'],[50,19])
        m.point(1,state=2)
        m.timer(6,0,0,paused=1,clock=1)
        self.assertEqual(r._sample()['phase'],'waiting')

    def test_unknown_corrupt_state_never_becomes_neutral_or_zero(self):
        for change in ('owner','state','active','progress','goal','current','count','double_active'):
            with self.subTest(change=change):
                m = ObjectiveMemory();m.point(1,active=1,owner=1,state=0)
                a = m.g+113
                if change=='owner':m.pack(a+0x1975DD,'i',3)
                elif change=='state':m.pack(a+0x19761B,'i',99)
                elif change=='active':m.pack(a+0x1975DC,'B',2)
                elif change=='progress':m.pack(a+0x1975F2,'i',-1)
                elif change=='goal':m.pack(m.g+0x1975B4,'i',0)
                elif change=='current':m.pack(m.g+0x197788,'i',4)
                elif change=='count':m.pack(m.g+0x197784,'i',0)
                else:m.point(2,active=1)
                with self.assertRaises(NativeUnavailable):m.reader()._sample()

    def test_vm_build_root_script_index_and_timer_recycling_refused(self):
        for change in ('build','root','alias','script','index','generation','owner','type','unregistered'):
            with self.subTest(change=change):
                m=ObjectiveMemory();b=m.module_base
                if change=='build':m.p['build']=999
                elif change=='root':m.pack(b+0x3B8C5C8,'Q',0)
                elif change=='alias':m.pack(b+0x2FA7100,'Q',m.table+8)
                elif change=='script':m.put(b+0x3B8C920+4,b'BAD')
                elif change=='index':m.pack(0x300000+0x50,'I',0)
                elif change=='generation':m.pack(b+0x4020980+80,'H',4)
                elif change=='owner':m.pack(0x605000+8,'I',1)
                elif change=='type':m.pack(b+0x4020980+86,'B',18)
                else:m.pack(0x650000,'I',0)
                with self.assertRaises(NativeUnavailable):m.reader()._sample()

    def test_saved_captures_and_release_gate_cannot_publish(self):
        m=ObjectiveMemory();m.recorded_non_atomic=True
        self.assertEqual(m.reader().inspect_saved()['status'],'offline_non_atomic')
        with self.assertRaises(NativeUnavailable):m.reader().diagnose('Volskaya')
        with self.assertRaises(NativeUnavailable):m.reader().read({})

    def test_synthetic_stability_and_mission_wall_limits(self):
        m=ObjectiveMemory();r=m.reader()
        # Perspective/match guards are tested by the inherited modules; this fixture
        # bypasses them ONLY to exercise the core's readset/time guards.
        with patch.object(r,'_perspective',return_value={'local_id':0,'team':0,'native_match_id':'a'*64}):
            result=r.diagnose('Volskaya')
            self.assertEqual(result['status'],'diagnostic_unreleased')
            self.assertNotIn('acquisition',result)
        with patch.object(r,'_perspective',return_value={}),patch('hotstate.objectives.time.monotonic',side_effect=[1,1.126]):
            with self.assertRaises(NativeUnavailable):r.diagnose('Volskaya')
        original=m.read_memory
        def changing(address,size):
            data=original(address,size)
            if address==m.g+0x19761B+3*113:m.pack(m.g+0x197788,'i',2)
            return data
        m.read_memory=changing
        with patch.object(r,'_perspective',return_value={}):
            with self.assertRaisesRegex(NativeUnavailable,'dechiree'):r.diagnose('Volskaya')


if __name__=='__main__':unittest.main()
