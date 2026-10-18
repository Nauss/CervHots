"""Synthetic memory; no real player/fog validation is claimed by these tests."""
import copy
import unittest
from unittest.mock import patch

from test_positions import PositionMemory
from test_positions_contract import raw_packet
from test_native_match import add_match
from hotstate.native import NativeReader, NativeUnavailable

from hotstate.visibility import CurrentVisibility
from cerveau.state import snapshot



class VisibilityMemory(PositionMemory):
    def __init__(self, base=0x40000000):
        super().__init__(base)
        add_match(self)
        self.visibility_profile = copy.deepcopy(self.position_profile)
        self.pack(base + 0x2fadd9c, 'I', 0xf)
        # Player6 shares CURRENT sight/detection with players6..10.
        self.pack(base + 0x35a1ee0 + 6 * 4, 'I', sum(1 << i for i in range(6, 11)))
        self.pack(base + 0x35c7980, 'II', (~0x130000) & 0xffffffff, 0xffffffff)
        self.pack(base + 0x32c5898, 'I', 0)
        self.pack(base + 0x32c2fe0, 'I', 0)
        self.pack(0x130000 + 0x10 + 6 * 4, 'I', 1)
        self.put(0x130000 + 0x200d0 + 8192, bytes(8192))
        self.put(base + 0x2f3d630 + 0x30030, bytes(8192))
        self.catalog = 0x140000
        self.pack(self.catalog + 0xe8, 'i', 2)
        self.pack(self.catalog + 0xe1, 'B', 8)  # No footprint fallback in fixture.
        for i in range(10):
            self.pack(0x900000 + i * 0x2f0 + 0x18, 'Q', self.catalog)

    def fog(self, visible):
        x, y = 21, 41
        self.pack(0x130000 + 0x200d0 + 8192 + (x // 32 + y * 8) * 4, 'I', (1 << x) if visible else 0)

    def visibility(self):
        return CurrentVisibility(NativeReader(self, profile=self.profile),
                                 profile=self.visibility_profile, position_profile=self.position_profile,
                                 match_profile=self.match_profile)

    def enemy(self):
        return self.visibility().diagnose('Volskaya', context=self.context,
                                         hero_ids=self.hero_ids)['heroes'][0]


class CurrentVisibilityTests(unittest.TestCase):
    def test_visible_fog_revealed_fog_visible_never_uses_history_or_cache(self):
        m = VisibilityMemory()
        m.fog(True)
        self.assertIs(m.enemy()['visible'], True)
        m.fog(False)
        self.assertIs(m.enemy()['visible'], False)
        m.pack(0x900000 + 0x28c, 'I', 1 << 6)
        self.assertIs(m.enemy()['visible'], True)
        m.pack(0x900000 + 0x28c, 'I', 0)
        self.assertIs(m.enemy()['visible'], False)
        m.fog(True)
        self.assertIs(m.enemy()['visible'], True)

    def test_known_or_explored_unused_and_enemy_sees_different_layer(self):
        m = VisibilityMemory()
        m.pack(0x900000 + 0x294, 'I', 0xffffffff)  # Unrelated history must not grant sight.
        self.assertIs(m.enemy()['visible'], False)
        m.fog(True)
        m.pack(0x130000 + 0x10 + 6 * 4, 'I', 0)
        m.put(0x130000 + 0x200d0, bytes(8192))
        self.assertIs(m.enemy()['visible'], False)

    def test_stealth_reveal_is_not_detection_and_hidden_state_wins(self):
        m = VisibilityMemory(); m.fog(True)
        m.pack(0x900000 + 0x30, 'I', 1 << 30)
        self.assertIs(m.enemy()['visible'], False)
        m.pack(0x900000 + 0x28c, 'I', 1 << 6)
        self.assertIs(m.enemy()['visible'], False)
        m.pack(0x900000 + 0x27c, 'I', 1 << 6)
        self.assertIs(m.enemy()['visible'], True)
        for offset, fmt, value in ((0x4c, 'b', 1), (0x3c, 'B', 0x10), (0x41, 'B', 0x10)):
            m.pack(0x900000 + offset, fmt, value)
            self.assertIs(m.enemy()['visible'], False)
            m.pack(0x900000 + offset, fmt, 0)

    def test_unresolved_behavior_or_footprint_is_unknown_not_certain_false(self):
        for change in ('shared', 'reveal', 'detection', 'footprint', 'footprint_mode1'):
            m = VisibilityMemory()
            if change == 'shared': m.pack(0x900000 + 0x156, 'B', 0x10)
            elif change == 'reveal': m.pack(0x900000 + 0x156, 'B', 4)
            elif change == 'detection':
                m.fog(True); m.pack(0x900000 + 0x30, 'I', 1 << 30)
                m.pack(0x900000 + 0x154, 'B', 0x20)
            else:
                m.pack(m.catalog + 0xe1, 'B', 0)
                if change == 'footprint_mode1': m.pack(m.catalog + 0xe8, 'i', 1)
            with self.subTest(change=change):
                sample = m.enemy()
                self.assertIsNone(sample['visible'])
                self.assertIn('reason', sample)

    def test_no_human_perspective_or_bad_build_reference_layer_fails_closed(self):
        for change in ('observer', 'bot', 'local', 'team', 'root', 'tag', 'owner', 'code', 'flags', 'layer', 'mode'):
            m = VisibilityMemory(); m.fog(True)
            if change == 'observer': m.pack(0x120000, 'I', 0x20)
            elif change == 'bot': m.pack(0x606000 + 0x1d, 'B', 2)
            elif change == 'local': m.pack(0x120000 + 0xc, 'B', 0)
            elif change == 'team': m.pack(0x606000 + 0x1c, 'B', 0)
            elif change == 'root': m.pack(m.module_base + 0x35c7980, 'I', 0)
            elif change == 'tag': m.pack(0x900000 + 0x10, 'I', 99)
            elif change == 'owner': m.pack(0x900000 + 0x44, 'B', 9)
            elif change == 'code': m.put(m.module_base + 0x200, b'CORRUPT')
            elif change == 'flags': m.pack(m.module_base + 0x2fadd9c, 'I', 0)
            elif change == 'layer': m.pack(0x130000 + 0x10 + 6 * 4, 'I', 16)
            else: m.pack(m.catalog + 0xe8, 'i', 4)
            with self.subTest(change=change), self.assertRaises(NativeUnavailable): m.enemy()

    def test_torn_fog_reference_perspective_and_clock_budget_reject(self):
        for target in ('fog', 'generation', 'local'):
            m = VisibilityMemory(); m.fog(True)
            original, fired = m.read_memory, False
            addresses = {'fog': 0x130000 + 0x200d0 + 8192 + 41 * 32,
                         'generation': 0x900000 + 0x10, 'local': 0x120000 + 0xc}
            def changing(address, size):
                nonlocal fired
                data = original(address, size)
                if not fired and address == addresses[target]:
                    fired = True; m.put(address, bytes([data[0] ^ 1]) + data[1:])
                return data
            m.read_memory = changing
            with self.subTest(target=target), self.assertRaises(NativeUnavailable): m.enemy()
        m = VisibilityMemory()
        with patch('hotstate.visibility.time.monotonic', side_effect=[0, 0.2]), self.assertRaises(NativeUnavailable):
            m.enemy()

    def test_aslr_dead_unknown_and_no_release_from_rolling_dump_or_diagnostic(self):
        for base in (0x40000000, 0x7ff500000000):
            m = VisibilityMemory(base); m.fog(True)
            self.assertIs(m.enemy()['visible'], True)
            result = m.visibility().diagnose('Volskaya', hero_ids=m.hero_ids)
            self.assertIsNone(result['heroes'][2]['visible'])
            self.assertNotIn('acquisition', result)
            self.assertNotIn('x', result['heroes'][0])
            with self.assertRaisesRegex(NativeUnavailable, 'recette_visibilite_joueur_absente'):
                m.visibility().read(m.context)
            m.recorded_non_atomic = True
            with self.assertRaisesRegex(NativeUnavailable, 'non_atomique'): m.enemy()

    def test_visible_diagnostic_grants_no_enemy_fields_or_cooldowns_to_model(self):
        raw = raw_packet(); m = VisibilityMemory(); m.fog(True)
        raw['visibility'] = m.visibility().diagnose('Volskaya', hero_ids=m.hero_ids)
        for hero in raw['heroes']:
            hero.update(x=42, y=84, health=123, health_max=456, resource=50,
                        resource_max=100, cooldowns={'R': 0}, visible=True)
        for phase in (True, False, True):
            m.fog(phase); raw['visibility'] = m.visibility().diagnose('Volskaya', hero_ids=m.hero_ids)
            state = snapshot(raw)
            self.assertNotIn('visibility', state)
            self.assertNotIn('cooldowns', str(state))
            for enemy in state['heroes'][:5]:
                for field in ('x', 'y', 'health', 'resource', 'visible'): self.assertNotIn(field, enemy)

    def test_static_triangle_refinement_and_neighbor_current_sight(self):
        m = VisibilityMemory(); v = m.visibility(); n = v.native
        x, y = 21, 41
        def static(xx, yy):
            address = m.module_base + 0x2f3d630 + 0x30030 + (xx // 32 + yy * 8) * 4
            m.pack(address, 'I', n.value(address) | (1 << (xx & 31)))
        self.assertTrue(v._triangle(n, x, y, 0, 0, 6))
        static(x, y - 1); static(x - 1, y)
        self.assertFalse(v._triangle(n, x, y, 0, 0, 6))
        m.pack(0x130000 + 0x200d0 + 8192 + ((x // 32) + (y - 1) * 8) * 4, 'I', 1 << x)
        self.assertTrue(v._triangle(n, x, y, 0, 0, 6))


if __name__ == '__main__':
    unittest.main()
