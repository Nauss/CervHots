"""SYNTHETIC NOT_LIVE: native four-family WHOLE regression, not qualification.

Only the objective business observation is a literal stub. Battlefield getters,
selection unions, fingerprints, physical rechecks, talents/CD, final native
context recheck and both consumer functions run unchanged on mapped bytes.
"""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import test_day_composition as composition_fixture
from test_dragon_contract import public_fixture
from test_objectives import ObjectiveMemory
from hotstate import dragon, dragon_battlefield, live
from hotstate.dragon import DragonObjective
from hotstate.dragon_battlefield import qualified_layout
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.native_context import NativeContextProbe
from cerveau.state import snapshot
from cerveau.runner import tactical_key


FAMILIES = ('objective', 'battlefield', 'talents', 'local_cooldowns')


def reads_overlap(reads, field_start, field_end):
    """Detect physical requests intersecting a forbidden half-open interval."""
    return any(a < field_end and field_start < a+size for a, size in reads)


class ForbiddenReadIntervalTests(unittest.TestCase):
    """SYNTHETIC NOT_LIVE requests only, not acquired bytes or live costs."""

    def test_forbidden_overlapping_requests_are_detected(self):
        address = 0x900000
        for start, end in ((0x224, 0x228), (0x230, 0x234), (0x220, 0x234)):
            field_start, field_end = address+start, address+end
            requests = (
                (field_start, end-start),  # Exact field.
                (field_start+1, 1),  # Strictly inside.
                (field_start-8, 9),  # Starts before, includes first byte.
                (field_start-8, end-start+16),  # Contains the whole field.
                (field_end-1, 8),  # Includes last byte, ends after.
            )
            for request in requests:
                with self.subTest(field=(start, end), request=request):
                    self.assertTrue(reads_overlap([request], field_start, field_end))
                    # The same non-reading assertion used below must reject
                    # even a grouped request starting before the field.
                    with self.assertRaises(AssertionError):
                        self.assertFalse(reads_overlap([request], field_start, field_end))

    def test_adjacent_and_disjoint_requests_are_allowed(self):
        address = 0x900000
        for start, end in ((0x224, 0x228), (0x230, 0x234), (0x220, 0x234)):
            field_start, field_end = address+start, address+end
            requests = [(field_start-8, 8), (field_end, 8),
                        (field_start-16, 4), (field_end+16, 4)]
            with self.subTest(field=(start, end)):
                self.assertFalse(reads_overlap(requests, field_start, field_end))
                self.assertFalse(reads_overlap([], field_start, field_end))


def map_battlefield(m):
    """Explicit fixture profiles/signatures; no production signature bypass."""
    b = m.module_base
    profiles = [copy.deepcopy(p) for p in (dragon.PROFILE, dragon_battlefield.PROFILE)]
    table = 0x4000000
    m.pack(b+0x3B8C5C8, 'Q', table)
    m.pack(b+0x2FA7100, 'Q', table)
    m.pack(b+0x2FA70F0, 'I', 6238)
    m.pack(b+0x3B8C904, 'I', 0x180000)
    for p in profiles:
        p['pe_timestamp'] = m.profile['pe_timestamp']
        p['signatures'] = copy.deepcopy(m.profile['signatures'])
        for f in p['functions']:
            record = 0x5000000+f['index']*256
            off = 4+f['index']*128
            code = ('SYNTHETIC_NOT_LIVE_'+f['name']).encode()
            f.update(length=len(code), sha256=hashlib.sha256(code).hexdigest())
            m.pack(table+f['index']*8, 'Q', record)
            m.pack(record+8, 'I', off)
            m.pack(record+0x50, 'I', f['index'])
            name = f['name'].encode()
            m.pack(record+0x58, 'IIQ', len(name)*4, 2, record+128)
            m.put(record+128, name)
            m.put(b+0x3B8C920+off, code)
    # Keep the existing hero/CD/talent database, adding the unit catalogue.
    n = NativeReader(m, profile=m.profile)
    root = n.value(b+0x3388b18, 'Q')
    database, names = 0x7000000, {}
    m.pack(root+0x2a0, 'Q', database)
    m.pack(database+0x90, 'I', 256)
    m.pack(database+0xa0, 'Q', database+0x1000)
    def catalogue(name):
        if name not in names:
            i = len(names)+1
            cat, desc, string = (database+0x10000+i*0x1000,
                                 database+0x200000+i*0x1000,
                                 database+0x400000+i*0x1000)
            m.pack(cat+2, 'H', i)
            m.pack(cat+0xe8, 'i', 2)
            m.pack(cat+0xe1, 'B', 8)
            m.pack(database+0x1000+i*8, 'Q', desc)
            m.pack(desc+0x40, 'H', i)
            m.pack(desc+0x30, 'Q', string)
            m.pack(string+0x18, 'II', len(name)*4, 0)
            m.put(string+0x20, name.encode())
            names[name] = cat
        return names[name]
    def unit(index, name, x, y, owner):
        page = index//16
        address = 0x900000+index*0x2f0
        m.pack(b+0x34f02c8+page*8, 'Q', 0x900000+page*16*0x2f0)
        m.put(address+0x10, bytes(0x38))
        m.pack(address+0x10, 'I', (index<<22)|1)
        m.pack(address+0x18, 'Q', catalogue(name))
        m.pack(address+0x44, 'B', owner)
        m.position(index+1, x, y)
        return address
    # Existing ten main hero bodies remain intact, but census needs real types.
    for i in range(10):
        m.pack(0x900000+i*0x2f0+0x18, 'Q', catalogue('FixtureHero'))
    m.structures = []
    for i, spec in enumerate(qualified_layout()['structures'], 16):
        address = unit(i, spec['unit_type'], spec['x_fixed']/4096,
                       spec['y_fixed']/4096, 11)
        m.pack(address+0x220, 'i', 10000*4096)
        m.pack(address+0x22c, 'i', 2500*4096)
        m.structures.append(address)
    # Real groups and timer registry, deliberately empty groups (not ready).
    g = b+0x3d0c920
    m.pack(g+0xe2130, 'I', 5)
    m.pack(b+0x4020970, 'Q', b+0x4020980)
    refs = [(3<<16)|i for i in range(50, 60)]
    m.pack(b+0x2f72670, 'I', 10)
    m.pack(b+0x2f72680, 'Q', 0x650000)
    m.pack(0x650000, 'I'*10, *refs)
    for i, kind in enumerate((1, 2, 1, 2, 2), 1):
        a = g+i*780
        unit(10+i-1, 'TownMercCampCaptureBeacon',
             profiles[1]['camp_anchors_fixed'][i-1][0]/4096,
             profiles[1]['camp_anchors_fixed'][i-1][1]/4096, 0)
        m.pack(a+0xdf070, 'ii', 0, kind)
        m.pack(a+0xdf0ba, 'i', kind)
        m.pack(a+0xdf337, 'i', 15)
        m.pack(a+0xdf33b, 'BB', 1, 1)
        m.pack(a+0xdf352, 'Bi', 0, 2)
        m.pack(a+0xdf367, 'B', 0)
        m.pack(a+0xdf363, 'I', ((9+i)<<22)|1)
        m.pack(a+0xdf33e, 'II', *refs[(i-1)*2:i*2])
        for ref in refs[(i-1)*2:i*2]:
            ObjectiveMemory.timer(m, ref&65535, 0, 0, paused=1, clock=1)
        ref, ptr = (3<<16)|(70+i), 0x8000000+i*0x1000
        m.pack(a+0xdf21e, 'I', ref)
        m.pack(b+0x4020980+(70+i)*16, 'HHHBBQ', 3, 0, 1, 22, 0, ptr)
        m.pack(ptr, 'QI', b+0x26b4d70, ref)
        m.pack(ptr+0x18, 'i', 0)
    m.pack(b+0x34f02c4, 'I', 106)
    # All Dragon fixed points CURRENT through the real fog predicate.
    m.put(0x130000+0x200d0+8192, b'\xff'*8192)
    return profiles


class NativeDragonWholeTests(unittest.TestCase):
    setUp = composition_fixture.DayCompositionTests.setUp
    take = composition_fixture.DayCompositionTests.take

    def prepare(self):
        objective_profile, battlefield_profile = map_battlefield(self.memory)
        self.probe = self.memory.probe()
        self.probe.map_resolver = lambda _: {'map_id': 'DragonShire', 'map': 'Dragon Shire'}
        self.objective_literal = public_fixture()
        def objective(context, **options):
            local = context['local_player']
            return dict(copy.deepcopy(self.objective_literal), map_id='DragonShire',
                        match_id=context['meta']['match_id'], local_id=local['id'],
                        team=local['team'], local_hero='ragnaros', mission_t_s=123.5,
                        read_window_s=0.001, _acquired=self.clock.value)
        for target, value in (
                ('hotstate.dragon.PROFILE', objective_profile),
                ('hotstate.dragon_battlefield.PROFILE', battlefield_profile),
                ('hotstate.talents.VALIDATED_SCOPES', (('DragonShire', 'ragnaros'),)),
                ('hotstate.talents.VALIDATED_LOCAL_SCOPES', (('DragonShire', 'ragnaros'),)),
                ('hotstate.cooldown_packet.VALIDATED_SCOPES', (('DragonShire', 'ragnaros'),))):
            self.stack.enter_context(patch(target, value))
        from hotstate import cooldown_qualification
        self.stack.enter_context(patch.dict(cooldown_qualification.QUALIFIED_BINDINGS, {
            (98348, 'DragonShire', 'ragnaros'): {'FixtureSpell': (9, 'unit', 'Abil/FixtureSpell', None, None, 0)}}))
        self.stack.enter_context(patch.object(DragonObjective, '_observe', side_effect=objective))
        self.physical = []
        original = self.memory.read_memory
        def traced(a, s):
            self.physical.append((a, s))
            return original(a, s)
        self.memory.read_memory = traced
        self.rechecks = []
        actual = NativeContextProbe.recheck
        def recheck(probe, memory):
            start = len(self.physical)
            result = actual(probe, memory)
            self.rechecks.append((memory, start, len(self.physical)))
            return result
        self.stack.enter_context(patch.object(NativeContextProbe, 'recheck', recheck))

    def full(self):
        start = len(self.physical)
        budget_count = len(self.budgets)
        clean, seen = self.take(self.probe)
        self.assertEqual(len(self.budgets), budget_count+1)
        reads = self.physical[start:]
        budget = self.budgets[-1]
        self.assertEqual((budget.reads, budget.bytes_requested),
                         (len(reads), sum(s for a, s in reads)))
        self.assertIs(self.rechecks[-1][0], budget)
        self.assertEqual(self.rechecks[-1][2], len(self.physical))
        self.assertGreater(self.rechecks[-1][2], self.rechecks[-1][1])
        self.assertTrue(set(FAMILIES).issubset(clean))
        self.assertTrue(set(FAMILIES).issubset(seen['raw']))
        self.assertTrue(set(FAMILIES).issubset(json.loads(seen['key'])))
        self.assertEqual(len(clean['battlefield']['camps']['entries']), 5)
        self.assertEqual(len(clean['battlefield']['structures']['entries']), 90)
        self.assertLessEqual(budget.reads, 8192)
        self.assertLessEqual(budget.bytes_requested, 2**20)
        self.assertLessEqual(budget.clock()-budget.started, .125)
        return clean, seen

    def test_native_whole_visible_and_fog_unknown_physical_cost(self):
        self.prepare()
        clean, _ = self.full()
        self.assertEqual(len(self.budgets), 1)
        entries = clean['battlefield']['structures']['entries']
        self.assertTrue(all(e['state'] == 'alive' and e['health_percent'] == 75 for e in entries))
        costs = [(self.budgets[-1].reads, self.budgets[-1].bytes_requested)]
        for address in self.memory.structures:
            self.assertIn((address+0x220, 4), self.physical)
            self.assertIn((address+0x22c, 4), self.physical)
            self.assertFalse(reads_overlap(self.physical, address+0x224, address+0x228))
            self.assertFalse(reads_overlap(self.physical, address+0x230, address+0x234))
        self.physical.clear()
        self.memory.put(0x130000+0x200d0+8192, bytes(8192))
        clean, _ = self.full()
        costs.append((self.budgets[-1].reads, self.budgets[-1].bytes_requested))
        for e in clean['battlefield']['structures']['entries']:
            self.assertEqual(e['state'], 'unknown')
            self.assertIsNone(e['health_percent'])
            self.assertIsNone(e['generation'])
        for address in self.memory.structures:
            self.assertFalse(reads_overlap(self.physical, address+0x220, address+0x234))
        print('SYNTHETIC NOT_LIVE WHOLE visible/fog reads,bytes:', costs)

    def test_native_discrete_mutations_change_only_their_family_key(self):
        self.prepare()
        _, seen = self.full()
        before = json.loads(seen['key'])
        def objective_transition():
            shrine = self.objective_literal['shrines'][0]
            shrine['owner'] = 1 if shrine['owner'] == 0 else 0
        mutations = (
            ('objective', objective_transition),
            ('battlefield', lambda: self.memory.pack(self.memory.structures[0]+0x39, 'B', 2)),
            ('talents', lambda: self.memory.pack(self.memory.module_base+0x3677a30+6*128+4, 'I', 0xffffffff)),
            ('local_cooldowns', lambda: self.memory.pack(self.memory.cd_node+0x18, 'i', 65536)),
        )
        for family, mutate in mutations:
            mutate()
            _, seen = self.full()
            after = json.loads(seen['key'])
            with self.subTest(family=family):
                self.assertNotEqual(before[family], after[family])
                for peer in FAMILIES:
                    if peer != family:
                        self.assertEqual(before[peer], after[peer])
            before = after

    def test_native_header_recheck_refuses_tag_and_consumed_flags(self):
        self.prepare()
        original = self.memory.read_memory
        address = self.memory.structures[0]
        for offset, bits in ((0x10, (16<<22)|2), (0x39, 2), (0x39, 4), (0x39, 0x20), (0x3c, 0x10)):
            hits = [0]
            def mutate(a, s):
                if a == address+0x10 and s == 0x38:
                    hits[0] += 1
                    if hits[0] == 2:
                        self.memory.pack(address+offset, 'I' if offset == 0x10 else 'B', bits)
                return original(a, s)
            self.memory.read_memory = mutate
            with self.subTest(offset=offset, bits=bits):
                clean, _ = self.take(self.probe)
                self.assertEqual(hits[0], 2)
                self.assertNotIn('battlefield', clean)
                self.assertTrue({'objective', 'talents', 'local_cooldowns'}.issubset(clean))
            self.memory.pack(address+offset, 'I' if offset == 0x10 else 'B', (16<<22)|1 if offset == 0x10 else 0)
        self.memory.read_memory = original

    def test_nonconsumed_header_neighbors_preserve_whole_key(self):
        self.prepare()
        _, seen = self.full()
        before = seen['key']
        original = self.memory.read_memory
        address = self.memory.structures[0]
        hits = [0]
        def dirty(a, s):
            if a == address+0x10 and s == 0x38:
                hits[0] += 1
                if hits[0] == 2:
                    self.memory.pack(address+0x39, 'B', 0x80)
                    self.memory.pack(address+0x3c, 'B', 0x88)
            return original(a, s)
        self.memory.read_memory = dirty
        _, after = self.full()
        self.assertEqual(hits[0], 2)
        self.assertEqual(before, after['key'])

    def test_final_context_mutation_and_expired_key_cannot_publish(self):
        self.prepare()
        self.full()  # Establish that the very same fixture really is Full.
        actual = NativeContextProbe.recheck
        acquired = []
        memory_snapshot = live.memory_snapshot
        def acquired_snapshot(*args, **kwargs):
            raw = memory_snapshot(*args, **kwargs)
            self.assertTrue(set(FAMILIES).issubset(raw))
            acquired.append(raw)
            return raw
        changed_source = []
        def changed(probe, budget):
            # observe_native also rechecks during initialization. Only arm
            # after this attempt's complete four-family acquisition returns.
            if acquired:
                address, data = probe.read_set[-1]
                changed_source.append((address, data))
                self.memory.put(address, bytes([data[0] ^ 1])+data[1:])
            return actual(probe, budget)
        with patch.object(live, 'memory_snapshot', acquired_snapshot), \
             patch.object(NativeContextProbe, 'recheck', changed), \
             self.assertRaisesRegex(NativeUnavailable, '^contexte_natif_dechire$'):
            self.take(self.probe)
        self.assertEqual(len(acquired), 1)
        self.assertEqual(len(changed_source), 1)
        self.memory.put(*changed_source[0])
        from test_capture_visibility_pipeline import FixtureProcess
        def expired(clean):
            self.assertTrue(set(FAMILIES).issubset(clean))
            tactical_key(clean)
            self.clock.value += .126
        with self.assertRaisesRegex(NativeUnavailable, 'globale_depassee'):
            live.read_current(FixtureProcess(self.memory), {'triggers': {}},
                              context=self.probe, project=snapshot, key=expired)

    def test_physical_budget_exhaustion_during_final_native_context_recheck(self):
        self.prepare()
        self.full()
        # Additional real mapped requests through the ONE outer budget; never
        # edit counters/limits or invent successful bytes/read costs.
        actual = NativeContextProbe.recheck
        memory_snapshot = live.memory_snapshot
        acquired = []
        def acquired_snapshot(*args, **kwargs):
            raw = memory_snapshot(*args, **kwargs)
            self.assertTrue(set(FAMILIES).issubset(raw))
            acquired.append(raw)
            return raw
        for kind in ('reads', 'bytes'):
            acquired.clear()
            start = len(self.physical)
            def exhaust(probe, budget):
                if not acquired:
                    return actual(probe, budget)
                while (budget.reads < 8192 if kind == 'reads' else budget.bytes_requested+65536 <= 2**20):
                    budget.read_memory(self.memory.module_base+0x200, 1 if kind == 'reads' else 65536)
                if kind == 'bytes':
                    remaining = 2**20-budget.bytes_requested
                    if remaining:
                        budget.read_memory(self.memory.module_base+0x200, remaining)
                return actual(probe, budget)
            with self.subTest(kind=kind), \
                 patch.object(live, 'memory_snapshot', acquired_snapshot), \
                 patch.object(NativeContextProbe, 'recheck', exhaust):
                with self.assertRaisesRegex(NativeUnavailable, 'budget_pipeline_depasse'):
                    self.take(self.probe)
            self.assertEqual(len(acquired), 1)
            budget = self.budgets[-1]
            requests = self.physical[start:]
            self.assertEqual((budget.reads, budget.bytes_requested),
                             (len(requests), sum(s for a, s in requests)))
            self.assertEqual(budget.reads if kind == 'reads' else budget.bytes_requested,
                             8192 if kind == 'reads' else 2**20)
            with self.assertRaisesRegex(NativeUnavailable, 'budget_pipeline_depasse'):
                budget.check()


if __name__ == '__main__':
    unittest.main()
