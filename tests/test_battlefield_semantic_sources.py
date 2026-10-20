"""Hermetic consumer-selected masks and public/diagnostic graph separation.

No historical trace is reinterpreted, and none of these fixtures qualifies live.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from hotstate.battlefield import _SelectedCensusMemory, VolskayaBattlefield
from hotstate.battlefield_details import structure_details, structure_public
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.visibility import CurrentVisibility
from test_battlefield_memo import Memory
from test_native import NativeMemory


class SemanticSourcesTests(unittest.TestCase):
    def selected(self):
        raw = Memory()
        memory = _SelectedCensusMemory(raw, semantic_selection=True)
        native = SimpleNamespace(read=raw.read_memory)
        return raw, memory, native

    def test_only_consumed_visibility_bit_is_stable_not_dirty_neighbors(self):
        for before, after in ((0x80, 0x88), (0x88, 0x80)):
            with self.subTest(before=before):
                raw, memory, native = self.selected()
                raw.data[100] = before
                self.assertEqual(memory.masked_byte(100, 0x10), 0)
                raw.data[100] = after
                memory.verify_sources(native, 'torn')
                self.assertEqual(raw.calls, [(100, 1), (100, 1)])
                raw.data[100] ^= 0x10
                with self.assertRaisesRegex(NativeUnavailable, 'torn'):
                    memory.verify_sources(native, 'torn')

    def test_union_of_consumers_includes_structure_life_and_catalogue(self):
        raw, memory, native = self.selected()
        raw.data[100] = 0x20
        memory.masked_byte(100, 0x20)
        memory.masked_byte(100, 0x06)
        self.assertEqual(memory.byte_masks[100], (0x26, 0x20))
        raw.data[100] ^= 0x80
        memory.verify_sources(native, 'torn')
        for bit in (1, 2, 5):
            raw.data[100] = 0x20 ^ (1 << bit)
            with self.subTest(bit=bit), self.assertRaisesRegex(NativeUnavailable, 'torn'):
                memory.verify_sources(native, 'torn')

    def test_full_consumer_promotes_same_byte_or_different_sized_overlap(self):
        for full_first in (False, True):
            for address, size in ((100, 1), (99, 4), (96, 8)):
                with self.subTest(full_first=full_first, address=address, size=size):
                    raw, memory, native = self.selected()
                    if full_first:
                        memory.read_memory(address, size)
                    memory.masked_byte(100, 0x10)
                    if not full_first:
                        memory.read_memory(address, size)
                    raw.data[100] = 0x80
                    with self.assertRaisesRegex(NativeUnavailable, 'torn'):
                        memory.verify_sources(native, 'torn')

    def test_initial_full_and_selected_consumers_cannot_contradict(self):
        raw, memory, native = self.selected()
        memory.masked_byte(100, 0x10)
        raw.data[100] = 0x10
        memory.fresh_read(99, 4)
        # Even if the process returns to the initial bit, consumed sources
        # disagreed during acquisition; final equality cannot rescue them.
        raw.data[100] = 0
        with self.assertRaisesRegex(NativeUnavailable, 'torn'):
            memory.verify_sources(native, 'torn')

    def test_full_full_contradiction_is_not_rescued_by_a_mask(self):
        raw, memory, native = self.selected()
        memory.read_memory(100, 1)
        raw.data[100] = 0x80
        memory.fresh_read(99, 4)
        memory.masked_byte(100, 0x10)
        with self.assertRaisesRegex(NativeUnavailable, 'torn'):
            memory.verify_sources(native, 'torn')

    def test_selected_headers_share_one_physical_final_check(self):
        raw, memory, native = self.selected()
        unit = 0x900000
        memory.census_header(unit)
        memory.read_memory(unit+0x10, 4)  # Generation/tag stays full.
        memory.read_memory(unit+0x18, 8)  # Chosen catalogue pointer stays full.
        memory.masked_byte(unit+0x39, 0x20)
        memory.masked_byte(unit+0x3c, 0x10)
        raw.calls.clear()
        raw.data[unit+0x39] = 0x80
        raw.data[unit+0x3c] = 0x88
        memory.verify_sources(native, 'torn')
        self.assertEqual(raw.calls, [(unit+0x10, 0x38)])
        raw.data[unit+0x10] = 1
        with self.assertRaisesRegex(NativeUnavailable, 'torn'):
            memory.verify_sources(native, 'torn')

    def test_short_selected_read_and_short_final_check_refuse(self):
        raw, memory, native = self.selected()
        raw.read_memory = lambda address, size: b''
        with self.assertRaises(NativeUnavailable):
            memory.masked_byte(100, 0x10)
        raw, memory, native = self.selected()
        memory.masked_byte(100, 0x10)
        native.read = lambda address, size: b''
        # NativeReader normally rejects truncation before verify_sources.
        # Exercise that real boundary, not an unvalidated fake read method.
        actual = object.__new__(NativeReader)
        actual.memory = SimpleNamespace(read_memory=native.read)
        with self.assertRaisesRegex(NativeUnavailable, 'memoire_native_incomplete'):
            memory.verify_sources(actual, 'torn')

    def test_masks_are_opt_in_and_lifetime_is_one_observation(self):
        raw = Memory()
        ordinary = _SelectedCensusMemory(raw)
        ordinary.masked_byte(100, 0x10)
        self.assertEqual(ordinary.read_set, [(100, b'\0')])
        self.assertEqual(ordinary.byte_masks, {})
        selected = _SelectedCensusMemory(raw, semantic_selection=True)
        selected.masked_byte(100, 0x10)
        raw.data[100] = 0x10
        next_attempt = _SelectedCensusMemory(raw, semantic_selection=True)
        self.assertEqual(next_attempt.masked_byte(100, 0x10), 0x10)
        self.assertEqual(selected.masked_byte(100, 0x10), 0)

    def test_invalid_masks_refuse_and_fresh_reads_keep_full_guards(self):
        raw, memory, native = self.selected()
        for mask in (0, -1, 256, True, '16'):
            with self.subTest(mask=mask), self.assertRaises(NativeUnavailable):
                memory.masked_byte(100, mask)
        with memory.fresh_reads():
            memory.masked_byte(100, 0x10)
        raw.data[100] = 0x80
        with self.assertRaisesRegex(NativeUnavailable, 'torn'):
            memory.verify_sources(native, 'torn')

    def census(self, structure):
        raw = NativeMemory()
        base, table = raw.module_base, 0x900000
        raw.pack(base+0x34F02C4, 'I', 16)
        raw.pack(base+0x34F02C8, 'Q', table)
        raw.pack(base+0x32C38B4, 'I', 0)
        raw.pack(base+0x32C55D0, 'I', 0)
        for slot in range(16):
            raw.put(table+slot*0x2f0+0x10, bytes(0x38))
        raw.pack(table+0x10, 'I', 1)
        raw.pack(table+0x18, 'Q', 0xa00000)
        raw.pack(table+0x44, 'B', 11)
        selected = _SelectedCensusMemory(raw, semantic_selection=True)
        native = NativeReader(selected, profile=raw.profile)
        reader = VolskayaBattlefield(native, profile={})
        name = 'TownCannonTowerL2' if structure else 'Barbarian'
        with patch.object(reader, '_unit_type', return_value=name):
            reader._census(native)
        return raw, selected, NativeReader(raw, profile=raw.profile)

    def test_actual_census_nonstructure_consumes_selector_but_not_life(self):
        raw, selected, native = self.census(False)
        self.assertEqual(selected.byte_masks[0x900039], (0x20, 0))
        raw.pack(0x900039, 'B', 0x86)
        selected.verify_sources(native, 'torn')
        raw.pack(0x900039, 'B', 0x20)
        with self.assertRaisesRegex(NativeUnavailable, 'torn'):
            selected.verify_sources(native, 'torn')

    def test_actual_census_structure_keeps_life_and_owner_and_tag_guards(self):
        for address, fmt, value in ((0x900039, 'B', 0x02), (0x900039, 'B', 0x04),
                                    (0x900044, 'B', 12), (0x900010, 'I', 2),
                                    (0x900018, 'Q', 0xb00000)):
            raw, selected, native = self.census(True)
            self.assertEqual(selected.byte_masks[0x900039], (0x26, 0))
            raw.pack(address, fmt, value)
            with self.subTest(address=address, value=value), self.assertRaisesRegex(NativeUnavailable, 'torn'):
                selected.verify_sources(native, 'torn')

    def test_actual_visibility_predicate_registers_consumed_bit(self):
        raw, memory, native = self.selected()
        unit = 0x900000
        raw.data[unit+0x44] = 6
        reader = object.__new__(NativeReader)
        reader.memory, reader.base = memory, raw.module_base
        visibility = object.__new__(CurrentVisibility)
        self.assertTrue(visibility._current(reader, unit, 6, None))
        self.assertEqual(memory.byte_masks[unit+0x3c], (0x10, 0))
        raw.data[unit+0x3c] = 0x88
        memory.verify_sources(native, 'torn')
        raw.data[unit+0x3c] |= 0x10
        with self.assertRaisesRegex(NativeUnavailable, 'torn'):
            memory.verify_sources(native, 'torn')

    def test_diagnostic_shields_are_not_public_dependencies(self):
        spec = {'id': 'extra-01', 'kind': 'core', 'unit_type': 'KingsCore', 'x_fixed': 0, 'y_fixed': 0}
        row = {'tag': 1, 'unit_type': 'KingsCore', 'kind': 'core', 'state': 'alive', 'team': 1, 'generation': 1}
        outputs, requests = [], []
        for diagnostic in (True, False):
            calls = []
            def value(address, fmt):
                calls.append(address)
                return 10000*4096 if address == 0x900220 else 2500*4096
            native = SimpleNamespace(value=value)
            with patch('hotstate.battlefield_details.CurrentVisibility._verify'), \
                 patch('hotstate.battlefield_details.CurrentVisibility._current', return_value=True), \
                 patch('hotstate.battlefield_details.PositionMemo._xy', return_value=(0, 0)):
                result = structure_details(native, SimpleNamespace(position_profile=None),
                    {'structures': [row]}, {1: 0x900000}, 0, {'structures': [spec]}, diagnostic_vitals=diagnostic)
            outputs.append(structure_public(result[0]))
            requests.append(calls)
            self.assertEqual('visible_vitals' in result[0]['observation'], diagnostic)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(requests, [[0x900220, 0x90022c, 0x900224, 0x900230], [0x900220, 0x90022c]])

    def test_public_observe_opts_in_without_changing_diagnostic_defaults(self):
        from test_current_visibility import VisibilityMemory
        from hotstate import dragon_battlefield as module
        from hotstate.dragon_battlefield import DragonBattlefield
        raw = VisibilityMemory()
        context = raw.context
        context['meta']['map_id'] = 'DragonShire'
        local = context['local_player']
        actual = (local['id'], local['team'], local['hero'], context['players'], 'fixture-session')
        reader = DragonBattlefield(NativeReader(raw, profile=raw.profile), profile={'camp_anchors_fixed': []})
        with patch.object(reader, '_verify'), \
             patch('hotstate.dragon_battlefield.DragonObjective._verify'), \
             patch('hotstate.dragon_battlefield.ActiveMatch.observe', return_value={'match_id': context['meta']['match_id']}), \
             patch('hotstate.dragon_battlefield.AlliedPositions._identity', return_value=actual), \
             patch('hotstate.visibility.CurrentVisibility._verify'), \
             patch.object(reader, '_camps', return_value=[]), \
             patch.object(reader, '_census', return_value={'structures': []}), \
             patch.object(reader, '_camp_timers'), \
             patch.object(module, '_SelectedCensusMemory', wraps=_SelectedCensusMemory) as selected, \
             patch.object(module, 'structure_details', wraps=structure_details) as details:
            result = reader._observe(context, hero_ids={local['hero']: local['hero']})
        self.assertTrue(selected.call_args.kwargs['semantic_selection'])
        self.assertFalse(details.call_args.kwargs['diagnostic_vitals'])
        self.assertEqual(len(result['structures']), 90)

    def test_ninety_visible_structure_public_graph_saves_360_physical_reads(self):
        # Isolated real getter + final guard cost, NOT a whole/live estimate.
        from hotstate.dragon_battlefield import qualified_layout
        layout = qualified_layout()
        costs = []
        projections = []
        for diagnostic in (True, False):
            raw, memory, native = self.selected()
            n = object.__new__(NativeReader)
            n.memory = memory
            units, positions, rows = {}, {}, []
            for index, spec in enumerate(layout['structures'], 1):
                unit = 0x900000+index*0x1000
                units[index] = unit
                positions[unit] = (spec['x_fixed']/4096, spec['y_fixed']/4096)
                raw.data[unit+0x222] = 1  # A positive little-endian maximum.
                rows.append({'tag': index, 'unit_type': spec['unit_type'], 'kind': spec['kind'],
                             'state': 'alive', 'team': 1, 'generation': 1})
            with patch('hotstate.battlefield_details.CurrentVisibility._verify'), \
                 patch('hotstate.battlefield_details.CurrentVisibility._current', return_value=True), \
                 patch('hotstate.battlefield_details.PositionMemo._xy', side_effect=lambda n, unit: positions[unit]):
                result = structure_details(n, SimpleNamespace(position_profile=None), {'structures': rows},
                    units, 0, layout, diagnostic_vitals=diagnostic)
            memory.verify_sources(native, 'torn')
            costs.append((len(raw.calls), sum(size for address, size in raw.calls)))
            projections.append([structure_public(row) for row in result])
        self.assertEqual(projections[0], projections[1])
        self.assertEqual(costs, [(720, 2880), (360, 1440)])

    def test_hidden_and_unknown_structures_never_acquire_any_vitals(self):
        spec = {'id': 'extra-01', 'kind': 'core', 'unit_type': 'KingsCore', 'x_fixed': 0, 'y_fixed': 0}
        row = {'tag': 1, 'unit_type': 'KingsCore', 'kind': 'core', 'state': 'alive', 'team': 1, 'generation': 1}
        for diagnostic in (True, False):
            for visible in (False, None):
                with self.subTest(diagnostic=diagnostic, visible=visible), \
                     patch('hotstate.battlefield_details.CurrentVisibility._verify'), \
                     patch('hotstate.battlefield_details.CurrentVisibility._current', return_value=visible), \
                     patch('hotstate.battlefield_details.PositionMemo._xy', return_value=(0, 0)):
                    def forbidden(*args):
                        raise AssertionError('sensitive read before CURRENT')
                    result = structure_details(SimpleNamespace(value=forbidden), SimpleNamespace(position_profile=None),
                        {'structures': [row]}, {1: 0x900000}, 0, {'structures': [spec]}, diagnostic_vitals=diagnostic)
                    public = structure_public(result[0])
                    self.assertEqual(public['state'], 'unknown')
                    self.assertIsNone(public['health_percent'])
                    self.assertIsNone(public['generation'])


if __name__ == '__main__':
    unittest.main()
