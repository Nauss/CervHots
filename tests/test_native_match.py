"""Synthetic active initial seed/cache guards, not live evidence."""
import copy
import hashlib
import unittest
from test_positions import PositionMemory
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.match import ActiveMatch


def add_match(m):
    m.match_profile = copy.deepcopy(m.profile)
    m.app = 0x160000
    m.vtable = 0x170000
    m.pack(m.module_base + 0x2f825f8, 'Q', m.app ^ 0x50c23112)
    m.pack(m.app, 'Q', m.vtable)
    m.pack(m.vtable + 0xe0, 'Q', m.module_base + 0x1324b70)
    m.pack(m.vtable + 0x358, 'Q', m.module_base + 0x1327c00)
    m.pack(m.app + 0x1d910, 'I', 4)
    m.seed = 123456
    m.handles = [b's2maEU  ' + bytes([7]) * 32]
    config = m.app + 0x83f78
    m.pack(config + 0x1d428, 'I', m.seed)
    m.pack(config + 0xd480, 'Q', len(m.handles))
    m.put(config + 0xd488, b''.join(m.handles))
    m.context['meta']['match_id'] = hashlib.sha256(m.seed.to_bytes(4, 'little') + b''.join(m.handles)).hexdigest()
    return m


class ActiveMatchTests(unittest.TestCase):
    def observe(self, m):
        return ActiveMatch(profile=m.match_profile).observe(NativeReader(m, profile=m.profile))

    def test_initial_seed_ordered_handles_hash_and_aslr(self):
        for base in (0x40000000, 0x7ff500000000):
            m = add_match(PositionMemory(base))
            result = self.observe(m)
            self.assertEqual(result['match_id'], m.context['meta']['match_id'])
            self.assertEqual(result['source'], 'native_active_initdata')
            self.assertNotIn('seed', result)
            self.assertNotIn('handles', result)

    def test_active_state_root_vtable_count_handle_and_build_fail_closed(self):
        for change in ('state', 'root', 'getter', 'state_getter', 'empty', 'oversize', 'handle', 'build'):
            m = add_match(PositionMemory())
            if change == 'state': m.pack(m.app + 0x1d910, 'I', 3)
            elif change == 'root': m.pack(m.module_base + 0x2f825f8, 'Q', 0x50c23112)
            elif change == 'getter': m.pack(m.vtable + 0xe0, 'Q', m.module_base + 0x1324b78)
            elif change == 'state_getter': m.pack(m.vtable + 0x358, 'Q', m.module_base + 0x1327c08)
            elif change == 'empty': m.pack(m.app + 0x83f78 + 0xd480, 'Q', 0)
            elif change == 'oversize': m.pack(m.app + 0x83f78 + 0xd480, 'Q', 33)
            elif change == 'handle': m.put(m.app + 0x83f78 + 0xd488, b'BAD!')
            else: m.match_profile['build'] = 999
            with self.subTest(change=change), self.assertRaises(NativeUnavailable):
                self.observe(m)

    def test_new_initial_seed_changes_identity_even_same_roster_and_addresses(self):
        m = add_match(PositionMemory())
        old = self.observe(m)['match_id']
        m.pack(m.app + 0x83f78 + 0x1d428, 'I', m.seed + 1)
        self.assertNotEqual(old, self.observe(m)['match_id'])


if __name__ == '__main__':
    unittest.main()
