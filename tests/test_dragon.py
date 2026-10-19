"""Synthetic Dragon fixtures. No fixture is a live Dragon qualification."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from test_objectives import ObjectiveMemory
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.dragon import DragonObjective


class DragonMemory(ObjectiveMemory):
    def __init__(self):
        super().__init__()
        p = json.loads((Path(__file__).resolve().parents[1] / 'hotstate/profiles/98348-dragon.json').read_text())
        p['pe_timestamp'] = self.profile['pe_timestamp']
        p['signatures'] = copy.deepcopy(self.profile['signatures'])
        self.p = p
        for i, spec in enumerate(p['functions']):
            record, off = 0x300000+i*4096, 4+i*8192
            self.pack(self.table+spec['index']*8, 'Q', record)
            self.pack(record+8, 'I', off)
            self.pack(record+0x50, 'I', spec['index'])
            name = spec['name'].encode()
            self.pack(record+0x58, 'IIQ', len(name)<<2, 2, record+256)
            self.put(record+256, name)
            code = bytes([i+1])*spec['length']
            self.put(self.module_base+0x3B8C920+off, code)
            spec['sha256'] = hashlib.sha256(code).hexdigest()
        b = self.module_base
        self.pack(b+0x34F02C4, 'I', 16)
        self.pack(b+0x34F02C8, 'II', 0x900000, 0)
        self.pack(b+0x32C38B4, 'I', 0)
        self.pack(b+0x32C55D0, 'I', 0)
        self.pack(self.g+0xE2B31, 'i', 2)
        self.pack(self.g+0xE2B4A, 'i', 2)
        self.pack(self.g+0x11869, 'i', 7)
        self.pack(self.g+0xE2B36, 'III', 3<<16|5, 3<<16|5, 3<<16|6)
        self.pack(self.g+0xE2B19, 'I', self.tag(4))
        self.pack(self.g+0xE2B11, 'Ii', 0, 0)
        self.pack(self.g+0xE2B05, 'I', self.tag(0))
        self.pack(self.g+0xE2B01, 'I', self.tag(1))
        self.types = {}
        for i, name in enumerate(('DragonShireShrineSun', 'DragonShireShrineMoon',
                                  'DragonballCaptureBeacon', 'DragonballCaptureBeacon', 'VehicleDragon')):
            unit = self.unit(i)
            self.pack(unit+0x10, 'I', self.tag(i))
            self.pack(unit+0x39, 'B', 0)
            self.pack(unit+0x44, 'B', 0)
            self.pack(unit+0x160, 'Q', 0)
            self.types[unit] = name
        for i in (1, 2):
            self.pack(self.g+0xE2B4E+i*21, 'IIBiII', self.tag(i-1), 0, 1, i+5, 0, 1)
            self.capture(i)

    @staticmethod
    def tag(i):
        return i<<22|1

    @staticmethod
    def unit(i):
        return 0x900000+i*0x2F0

    def capture(self, i, *, owner=0, state=2, enabled=1, counter=0):
        cp = self.g+0x118C5+(i+5)*132
        self.pack(cp, 'BIiiiiiiii', enabled, self.tag(i+1), 0, counter, 64, 64, 1, 2, state, 0)
        self.pack(cp+37, 'i', 2)
        self.pack(self.unit(i-1)+0x44, 'B', owner)
        self.pack(self.unit(i+1)+0x44, 'B', owner)

    def reader(self):
        return DragonObjective(NativeReader(self, profile=self.profile), profile=self.p)

    def sample(self):
        r = self.reader()
        with patch.object(r.units, '_unit_type', side_effect=lambda n,u: self.types[u]):
            return r.inspect_saved()


class DragonTests(unittest.TestCase):
    def test_shrines_named_and_no_shared_percent(self):
        s = DragonMemory().sample()
        self.assertEqual(s['status'], 'offline_non_atomic')
        self.assertEqual(s['phase'], 'shrines')
        self.assertEqual([x['id'] for x in s['shrines']], ['sun', 'moon'])
        self.assertEqual([x['owner'] for x in s['shrines']], ['neutral', 'neutral'])
        self.assertNotIn('percent', json.dumps(s))

    def test_capture_loss_contestation_and_neutral_are_separate(self):
        m = DragonMemory()
        m.capture(1, owner=11, state=3, counter=64)
        m.capture(2, owner=12, state=0, counter=-20)
        s = m.sample()['shrines']
        self.assertEqual(s[0]['owner'], 0)
        self.assertEqual(s[0]['state'], 'captured')
        self.assertEqual(s[1]['owner'], 1)
        self.assertEqual(s[1]['state'], 'contested')
        m.capture(1, owner=0, state=4, counter=0)
        self.assertEqual(m.sample()['shrines'][0]['owner'], 'neutral')

    def test_disabled_record_does_not_publish_residual_contestation(self):
        m = DragonMemory()
        m.capture(1, enabled=0, state=0, counter=64)
        s = m.sample()['shrines'][0]
        self.assertEqual(s['state'], 'disabled')
        self.assertIsNone(s['capture_counter'])
        self.assertIsNone(s['contested'])

    def test_corrupt_indices_goals_flags_states_and_owners_refused(self):
        cases = [(0xE2B31, 'i', 4), (0xE2B4A, 'i', 3),
                 (0xE2B4E+21+9, 'i', 0), (0x118C5+6*132, 'B', 2),
                 (0x118D2+6*132, 'i', 63), (0x118E2+6*132, 'i', 6),
                 (0x118CE+6*132, 'i', 65)]
        for off, fmt, value in cases:
            with self.subTest(offset=off):
                m = DragonMemory(); m.pack(m.g+off, fmt, value)
                with self.assertRaises(NativeUnavailable):
                    m.sample()
        m = DragonMemory(); m.capture(1, owner=8)
        with self.assertRaises(NativeUnavailable):
            m.sample()

    def test_recycled_shrine_never_reads_replacement(self):
        m = DragonMemory(); m.pack(m.unit(0)+0x10, 'I', 2)
        original = m.read_memory
        def restricted(address,size):
            if m.unit(0)+0x18 <= address < m.unit(0)+0x2F0:
                raise AssertionError('replacement read')
            return original(address,size)
        m.read_memory = restricted
        s = m.sample()['shrines'][0]
        self.assertEqual(s['state'], 'unknown')
        self.assertIsNone(s['owner'])

    def test_wrong_type_or_beacon_alias_refused(self):
        m = DragonMemory(); m.types[m.unit(0)] = 'HeroStitches'
        with self.assertRaises(NativeUnavailable):
            m.sample()
        m = DragonMemory()
        m.pack(m.g+0xE2B4E+2*21+9, 'i', 6)
        with self.assertRaises(NativeUnavailable):
            m.sample()
        # Distinct indices are not enough: the effective beacon must differ.
        m = DragonMemory()
        m.pack(m.g+0x118C5+7*132+1, 'I', m.tag(2))
        with self.assertRaisesRegex(NativeUnavailable,'beacon_dragon_duplique'):
            m.sample()

    def test_vm_mirror_and_fingerprint_refused(self):
        m = DragonMemory(); r = m.reader(); r._verify(r.native)
        m.pack(m.module_base+0x2FA7100, 'Q', m.table+8)
        with self.assertRaises(NativeUnavailable):
            r._verify(r.native)
        m = DragonMemory(); m.put(m.module_base+0x3B8C920+4, b'!')
        with self.assertRaises(NativeUnavailable):
            m.sample()

    def test_recycled_statue_and_dragon_stay_unknown(self):
        m = DragonMemory(); m.pack(m.unit(4)+0x10, 'I', 2)
        self.assertEqual(m.sample()['statue']['state'], 'unknown')
        m.pack(m.g+0xE2B31, 'i', 3)
        m.pack(m.g+0xE2B11, 'I', m.tag(4))
        s = m.sample()
        self.assertEqual(s['phase'], 'unknown')
        self.assertEqual(s['dragon']['state'], 'unknown')
        self.assertIsNone(s['dragon']['remaining_s'])

    def test_idle_warning_and_match_reset_no_cached_history(self):
        m = DragonMemory(); m.pack(m.g+0xE2B31, 'i', 0)
        self.assertEqual(m.sample()['phase'], 'waiting')
        m.pack(m.g+0xE2B31, 'i', 1)
        self.assertEqual(m.sample()['phase'], 'warning')
        m.pack(m.g+0xE2B31, 'i', 2)
        self.assertEqual(m.sample()['dragon']['state'], 'inactive')
        self.assertEqual(m.sample()['shrines'][0]['owner'], 'neutral')

    def test_coach_gate_closed_even_on_fixture(self):
        m = DragonMemory()
        with self.assertRaisesRegex(NativeUnavailable, 'recette_dragon_absente'):
            m.reader().read({})
        m.recorded_non_atomic = True
        with self.assertRaises(NativeUnavailable):
            m.reader().diagnose(None)

    def test_named_behavior_does_not_accept_other_buff(self):
        m = ObjectiveMemory(); m.protector()
        r = m.reader()
        self.assertEqual(r._duration(r.native, 0x900000), 79.5)
        self.assertEqual(r._duration(r.native, 0x900000, 'TransformHeroVehicleBeingCapturedBehavior'), 0)

    def test_current_channel_marker_is_boolean_not_its_five_second_duration(self):
        m = DragonMemory(); m.protector()
        m.capture(1, owner=11, state=3, counter=64)
        m.capture(2, owner=11, state=3, counter=64)
        m.pack(m.unit(4)+0x44, 'B', 11)
        m.pack(m.unit(4)+0x160, 'Q', 0xA00000)
        name = b'TransformHeroVehicleBeingCapturedBehavior'
        m.pack(0xE03000+8, 'QQ', 0xE04000, len(name)); m.put(0xE04000,name)
        m.pack(0xF00000+0x28, 'i', int(2.5*65536))
        s = m.sample()['statue']
        self.assertEqual(s, {'state':'capturable','team':0,'channeling':True})
        self.assertNotIn('remaining_s',s)
        m.pack(m.unit(4)+0x160,'Q',0)
        self.assertFalse(m.sample()['statue']['channeling'])
        m.capture(2, owner=12, state=3, counter=-64)
        with self.assertRaisesRegex(NativeUnavailable,'statue_sanctuaires'):
            m.sample()

    def test_active_dragon_is_bound_to_actual_pilot_and_never_reads_health(self):
        m = DragonMemory(); m.protector()
        m.capture(1, enabled=0); m.capture(2, enabled=0)
        m.pack(m.g+0xE2B31, 'i', 3)
        m.pack(m.g+0xE2B11, 'Ii', m.tag(4), 9)
        m.pack(m.unit(4)+0x44, 'B', 9)
        m.pack(m.unit(4)+0x160, 'Q', 0xA00000)
        m.pack(0x1100000+0x1C, 'BB', 1, 2)
        original = m.read_memory
        def restricted(a,s):
            if a in (m.unit(4)+0x220,m.unit(4)+0x22C):
                raise AssertionError('unqualified vitals read')
            return original(a,s)
        m.read_memory = restricted
        with patch('hotstate.native.NativeReader.player_pointer',return_value=0x1100000):
            self.assertEqual(m.sample()['dragon'], {'state':'active','team':1,'remaining_s':79.5})
            m.pack(m.unit(4)+0x39, 'B', 2)
            self.assertEqual(m.sample()['dragon']['state'], 'ended')
            m.pack(m.unit(4)+0x39, 'B', 0)
            m.pack(m.g+0xE2B15, 'i', 8)
            with self.assertRaisesRegex(NativeUnavailable,'pilote_dragon'):
                m.sample()


if __name__ == '__main__':
    unittest.main()
