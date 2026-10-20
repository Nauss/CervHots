"""Hermetic tests; never evidence of a live talent choice."""
import unittest
import struct
from types import SimpleNamespace

from hotstate import talents
from hotstate.native import NativeUnavailable


class TalentSelectionTests(unittest.TestCase):
    def tree_fixture(self):
        data = {}
        def put(address, fmt, value):
            for i, byte in enumerate(struct.pack('<'+fmt, value)):
                data[address+i] = byte
        def read(address, size):
            try:
                return bytes(data[address+i] for i in range(size))
            except KeyError:
                raise NativeUnavailable('fixture_missing') from None
        n = SimpleNamespace(base=0x10000000, read=read, data=data,
            value=lambda a, f='I': struct.unpack('<'+f, read(a, struct.calcsize('<'+f)))[0])
        put(0x20050, 'Q', 0x30000)
        put(0x30040, 'H', 4)
        put(n.base+0x3388b18, 'Q', 0x40000)
        put(0x40148, 'Q', 0x50000)
        put(0x50038, 'I', 5)
        put(0x50048, 'Q', 0x60000)
        put(0x60020, 'Q', 0x70000)
        put(0x70000, 'B', 0)
        put(0x70500, 'I', 1)
        put(0x70510, 'Q', 0x80000)
        put(0x80000, 'Q', 0x90000)
        put(0x80008, 'I', 1)
        put(0x8000c, 'I', 2)
        put(0x90030, 'Q', 0xa0000)
        name = b'StitchesPatchworkCreation'
        put(0xa0018, 'I', len(name)<<2)
        put(0xa001c, 'I', 0)
        for i, byte in enumerate(name):
            data[0xa0020+i] = byte
        for tier in range(32):
            put(n.base+0x3677a30+128+tier*4, 'I', 0xffffffff)
        return n, put

    def test_reads_current_native_selection_without_baseline(self):
        n, put = self.tree_fixture()
        self.assertEqual(talents.read_tree(n, 0x20000, 1)['selected'], [])
        put(n.base+0x3677a30+128+4, 'I', 0)
        row = talents.read_tree(n, 0x20000, 1)
        self.assertEqual(row['selected'], [{'index': 0, 'tier': 1, 'slot': 2,
            'catalog_id': 'StitchesPatchworkCreation'}])

    def test_required_level_comes_from_native_catalog_not_fixed_hero_schedule(self):
        n, put = self.tree_fixture()
        put(0x70518, 'I', 1)
        put(0x70528, 'Q', 0xc0000)
        put(0xc0000, 'I', 1)
        put(0xc0004, 'I', 2)
        put(0xc0008, 'I', 0)
        self.assertEqual(talents.read_tier_levels(n, 0x70000), {1: 2})
        put(0xc0004, 'I', 0)
        with self.assertRaises(NativeUnavailable):
            talents.read_tier_levels(n, 0x70000)

    def test_unbound_probe_cannot_read_any_memory(self):
        row = talents.diagnose(None, object())
        self.assertEqual(row['status'], 'rejected')
        self.assertEqual(row['reason'], 'talent_context_source_unsupported')

    def test_missing_tree_lazy_and_bad_slot_refuse(self):
        for address, fmt, value in ((0x70500, 'I', 0), (0x70000, 'B', 1),
                                    (0x8000c, 'I', 0), (0x80008, 'I', 32)):
            n, put = self.tree_fixture()
            put(address, fmt, value)
            with self.subTest(address=address), self.assertRaises(NativeUnavailable):
                talents.read_tree(n, 0x20000, 1)

    def test_persisted_selection_not_possessions_or_offered_catalog(self):
        offered = [
            {'index': 0, 'tier': 1, 'slot': 1, 'catalog_id': 'StitchesPatchworkCreation'},
            {'index': 1, 'tier': 1, 'slot': 2, 'catalog_id': 'StitchesHungryForMore'},
            {'index': 2, 'tier': 2, 'slot': 1, 'catalog_id': 'StitchesPlaytime'},
        ]
        raw = [0xffffffff] * 32
        self.assertEqual(talents.resolve_selections(raw, offered), [])
        raw[1] = 0
        self.assertEqual(talents.resolve_selections(raw, offered), [offered[0]])
        raw[1] = 1
        self.assertEqual(talents.resolve_selections(raw, offered), [offered[1]])
        raw[1] = 0xffffffff
        self.assertEqual(talents.resolve_selections(raw, offered), [])


    def test_unresolved_or_wrong_tier_does_not_become_empty(self):
        raw = [0xffffffff] * 32
        raw[1] = 3
        with self.assertRaises(NativeUnavailable):
            talents.resolve_selections(raw, [])
        with self.assertRaises(NativeUnavailable):
            talents.resolve_selections(raw, [{'index': 3, 'tier': 2}])

    def test_duplicate_catalog_index_is_ambiguous(self):
        with self.assertRaises(NativeUnavailable):
            talents.resolve_selections([0xffffffff]*32, [
                {'index': 0, 'tier': 1}, {'index': 0, 'tier': 2}])


if __name__ == '__main__':
    unittest.main()
