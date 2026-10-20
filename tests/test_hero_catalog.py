"""Catalog roster identities, never unit-form aliases or unknown fallbacks."""
import unittest

from hotstate.native import NativeReader, NativeUnavailable
from test_native import NativeMemory


class HeroCatalogTests(unittest.TestCase):
    def test_local_xalatath_identity_does_not_enable_unqualified_talents_or_cooldowns(self):
        memory = NativeMemory()
        memory.add_roster()
        header = 0x706000 + 0x118
        memory.pack(header, 'II', len('Xalatath') << 2, 0)
        memory.put(header + 8, b'Xalatath')
        memory.context['local_player']['hero'] = 'Xalatath'
        memory.context['players'][5]['hero'] = 'Xalatath'
        raw = NativeReader(memory, profile=memory.profile).read_state(memory.context)
        self.assertEqual(raw['local_player']['hero'], 'xalatath')
        self.assertNotIn('talents', raw)
        self.assertNotIn('local_cooldowns', raw)

    def memory_with_roster_hero(self, name):
        memory = NativeMemory()
        memory.add_roster()
        header = 0x701000 + 0x118  # first fixture's opponent roster CHero string
        memory.pack(header, 'II', len(name) << 2, 0)
        memory.put(header + 8, name.encode('ascii'))
        return memory

    def test_xalatath_catalog_id_accepts_core_without_enabling_optional_scopes(self):
        memory = self.memory_with_roster_hero('Xalatath')
        raw = NativeReader(memory, profile=memory.profile).read_state(memory.context)
        self.assertEqual(raw['heroes'][0]['hero'], 'xalatath')
        self.assertEqual(raw['meta']['native_status'], 'valide')
        self.assertNotIn('health', raw['heroes'][0])
        self.assertNotIn('local_cooldowns', raw)
        self.assertNotIn('talents', raw)

    def test_unit_forms_and_unknown_roster_ids_are_still_refused(self):
        for name in ('HeroXalatath', 'HeroDVaPilot', 'DVaPilot', 'UnknownNewHero', 'xalatath'):
            with self.subTest(name=name):
                memory = self.memory_with_roster_hero(name)
                with self.assertRaisesRegex(NativeUnavailable, '^heros_natif_inconnu$'):
                    NativeReader(memory, profile=memory.profile).read_state(memory.context)


if __name__ == '__main__':
    unittest.main()
