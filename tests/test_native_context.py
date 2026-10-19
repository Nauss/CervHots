"""SYNTHETIC native InitData C++ fixtures; never a serialized/live fake blob."""
import hashlib
import json
import unittest
from unittest.mock import patch

from test_current_visibility import VisibilityMemory
from test_capture_visibility_pipeline import FixtureProcess, FixtureClock
import test_capture_visibility_pipeline as fixtures
from hotstate.native_context import NativeContextProbe
from hotstate.native import NativeUnavailable
from etudes.rea.scripts import capture_visibility_pipeline as capture


class TypedContextMemory(VisibilityMemory):
    def __init__(self):
        super().__init__()
        self.fog(True)
        marker = b'TYPED_CONTEXT_SCHEMA_FIXTURE'
        self.put(self.module_base + 0x777700, marker)
        self.context_profile = {'build':98348, 'signatures':[{'rva':0x777700,
            'size':len(marker),'sha256':hashlib.sha256(marker).hexdigest()}]}
        self.config = self.app + 0x83f78

        self.pack(self.config, 'Q', 16)
        for i in range(16):
            self.native_string(self.config + 8 + i * 3120, 'OWNER_TEST' if i == 0 else '')
        self.slots = self.config + 0xe198 + 8
        self.pack(self.slots, 'Q', 16)
        for i in range(16):
            slot = self.slots + 8 + i * 3880
            self.pack(slot, 'BBBB', 2 if i == 5 else 3 if i < 10 else 0,
                      1 if i == 5 else 0, 0, i // 5 if i < 10 else 0)
            self.pack(slot + 12, 'I', 0 if i < 10 else 1)
            self.native_string(slot + 24, 'Ragnaros' if i == 5 else '')
            self.pack(slot + 1608, 'BB', 1, i)
    def native_string(self, address, text):
        data = text.encode('utf-8')
        self.pack(address, 'QQ', len(data), len(data))
        self.put(address + 16, data + b'\0')
    def probe(self, label='OWNER_TEST'):
        return NativeContextProbe(label, profile=self.context_profile,
            map_resolver=lambda handles: {'map_id':'Volskaya','map':'Volskaya Foundry'})


class NativeContextTests(unittest.TestCase):
    def options(self, m):
        return patch('hotstate.match.PROFILE',m.match_profile)
    def test_observed_fields_inactive_slots_missing_ai_and_private_names(self):
        m=TypedContextMemory();probe=m.probe()
        with self.options(m):probe.observe_native(m,native_profile=m.profile)
        data=probe.finish()
        self.assertEqual(data['local_player'],{'id':5,'team':1,'hero':'Ragnaros'})
        self.assertEqual(len(data['players']),10)
        self.assertFalse(data['composition_complete'])
        self.assertEqual(data['meta']['context_source'],'initdata_native_fields')
        self.assertNotIn('OWNER_TEST',json.dumps(data))
        self.assertNotIn('pointer',json.dumps(data))
    def test_fail_closed_wrong_label_counts_options_string_and_signature(self):
        for change in ('label','count','option','string','signature'):
            m=TypedContextMemory();probe=m.probe('NOT_OWNER' if change=='label' else 'OWNER_TEST')
            if change=='count':m.pack(m.config,'Q',17)
            if change=='option':m.pack(m.slots+8+5*3880+1,'B',2)
            if change=='string':m.pack(m.config+8,'Q',33)
            if change=='signature':m.put(m.module_base+0x777700,b'BAD')
            with self.subTest(change=change),self.options(m),self.assertRaises(NativeUnavailable):probe.observe_native(m,native_profile=m.profile)
            self.assertEqual(probe.finish(),{})
    def test_context_recheck_rejects_mutation_and_non_atomic_input(self):
        m=TypedContextMemory();probe=m.probe()
        with self.options(m):probe.observe_native(m,native_profile=m.profile)
        m.pack(m.config+0x1d428,'I',m.seed+1)
        with self.assertRaisesRegex(NativeUnavailable,'dechire'):probe.recheck(m)
        probe.begin();self.assertEqual(probe.finish(),{})
        m.recorded_non_atomic=True
        with self.assertRaisesRegex(NativeUnavailable,'non_atomique'):probe.observe_native(m,native_profile=m.profile)
    def test_snapshot_normalizer_key_and_strict_ordered_replay_no_heap_scan(self):
        m=TypedContextMemory();probe=m.probe();helper=fixtures.PipelineCollectorTests();a,b,c=helper.options(m)
        with a,b,c,patch('cerveau.brain.Coach.decide',side_effect=AssertionError('no coach')):
            row=capture.take_sample(FixtureProcess(m),probe,None,native_profile=m.profile,clock=FixtureClock())
            self.assertEqual(row['status'],'accepted',row.get('rejected'))
            self.assertEqual(row['normalized']['local_player']['id'],5)
            self.assertEqual(row['normalized']['meta']['context_source'],'initdata_native_fields')
            self.assertIn('tactical_key',row)
            for enemy in row['normalized']['heroes'][:5]:
                self.assertTrue({'health','x','y','resource','cooldowns','talents'}.isdisjoint(enemy))
            repeated=capture.replay_sample(row,m.module_base,probe,None,native_profile=m.profile)
            self.assertEqual(repeated['normalized'],row['normalized'])
            self.assertEqual(repeated['tactical_key'],row['tactical_key'])
    def test_observer_never_gets_full_pipeline_accept(self):
        m=TypedContextMemory();m.pack(0x120000,'I',0x20);helper=fixtures.PipelineCollectorTests();a,b,c=helper.options(m)
        with a,b,c:
            row=capture.take_sample(FixtureProcess(m),m.probe(),None,native_profile=m.profile,clock=FixtureClock())
        self.assertEqual(row['status'],'rejected')
    def test_elapsed_wall_age_not_static_mission_time(self):
        m=TypedContextMemory();probe=m.probe()
        with self.options(m),patch('time.monotonic',side_effect=[100,101]),self.assertRaisesRegex(NativeUnavailable,'perime'):probe.observe_native(m,native_profile=m.profile)

    def test_typed_snapshot_never_scans_legacy_trigger_heap(self):
        from hotstate.reader import snapshot
        m=TypedContextMemory();helper=fixtures.PipelineCollectorTests();a,b,c=helper.options(m)
        backend=FixtureProcess(m)
        with a,b,c,patch.object(backend,'regions_bytes',side_effect=AssertionError('heap scan forbidden')):
            raw=snapshot(backend,{'triggers':{'legacy':{'field':'deaths_total'}}},
                         context=m.probe(),native_profile=m.profile)
        self.assertEqual(raw['meta']['native_status'],'valide')
        self.assertEqual(raw['stats'],{})

    def test_map_resolver_mutation_is_inside_read_bracket(self):
        m=TypedContextMemory();probe=m.probe()
        def resolver(handles):
            m.pack(m.config+0x1d428,'I',m.seed+1)
            return {'map_id':'Volskaya','map':'Volskaya Foundry'}
        probe.map_resolver=resolver
        with self.options(m),self.assertRaisesRegex(NativeUnavailable,'dechire'):
            probe.observe_native(m,native_profile=m.profile)
        self.assertEqual(probe.finish(),{})

    def test_map_resolver_latency_cannot_publish_expired_context(self):
        m=TypedContextMemory();probe=m.probe();now=[100.0]
        def resolver(handles):
            now[0]+=1
            return {'map_id':'Volskaya','map':'Volskaya Foundry'}
        probe.map_resolver=resolver
        with self.options(m),patch('time.monotonic',side_effect=lambda:now[0]),self.assertRaisesRegex(NativeUnavailable,'perime'):
            probe.observe_native(m,native_profile=m.profile)
        self.assertEqual(probe.finish(),{})

if __name__=='__main__':unittest.main()
