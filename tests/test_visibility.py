"""Hermetic visibility/privacy regressions; NEVER evidence of live validation."""
import unittest
from unittest.mock import patch

from test_positions import PositionMemory
from test_positions_contract import raw_packet
from hotstate.native import NativeReader, NativeUnavailable
from cerveau.state import snapshot


class PerspectivePrivacyTests(unittest.TestCase):
    def test_optional_torn_clock_code_omits_clock_but_preserves_core(self):
        import hashlib
        from test_gameplay_clock import ClockMemory
        from hotstate.gameplay import GameplayClock
        m = ClockMemory()
        # Relocate synthetic timers before adding synthetic CPlayers (same old
        # fixture addresses); no live offsets or evidence are derived here.
        for index in (5, 6):
            new = 0x1600000 + index * 0x1000
            m.put(new, m.read_memory(0x600000 + index * 0x1000, 40))
            m.pack(m.slots + index * 16 + 8, 'Q', new)
        m.add_roster(); m.pack(m.module_base + 0x4020970, 'Q', m.slots)
        marker = b'SYNTHETIC_CLOCK_ONLY_SIGNATURE'
        m.put(m.module_base + 0x900, marker)
        m.clock_profile['signatures'] = [dict(rva=0x900, size=len(marker),
                                             sha256=hashlib.sha256(marker).hexdigest())]
        original = m.read_memory; fired = False
        def changing(address, size):
            nonlocal fired
            data = original(address, size)
            if not fired and address == m.module_base + 0x900:
                fired = True; m.put(address, b'CORRUPT')
            return data
        m.read_memory = changing
        with patch('hotstate.gameplay.GameplayClock', side_effect=lambda n: GameplayClock(n, profile=m.clock_profile)):
            raw = NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)
        raw['meta'].update(m.context['meta'], source='live')
        self.assertTrue(fired)
        self.assertNotIn('gameplay_clock', raw['meta'])
        self.assertEqual(len(raw['heroes']), 10)
        self.assertIn('health', snapshot(raw)['heroes'][5])

    def test_optional_torn_xy_omits_only_positions_not_public_core_or_vitals(self):
        m = PositionMemory(); original = m.read_memory; fired = False
        def changing(address, size):
            nonlocal fired
            data = original(address, size)
            if not fired and address == 0x900000 + 5 * 0x2f0 + 0x60:
                fired = True; m.position(6, 70, 80)
            return data
        m.read_memory = changing
        with patch('hotstate.positions.PROFILE', m.position_profile):
            raw = NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)
        raw['meta'].update(m.context['meta'], source='live')
        self.assertTrue(fired)
        self.assertNotIn('positions', raw)
        self.assertEqual(len(raw['heroes']), 10)
        self.assertEqual(raw['heroes'][5]['level'], 19)
        self.assertIn('health', snapshot(raw)['heroes'][5])

    def test_vitals_require_untampered_same_process_receipt_and_live_source(self):
        for change in ('receipt', 'source', 'value', 'time', 'window', 'override'):
            raw = raw_packet()
            if change == 'receipt': raw.pop('perspective')
            elif change == 'source': raw['meta']['source'] = 'dump'
            elif change == 'value': raw['heroes'][5]['health'] = 1
            elif change == 'time': raw['meta']['t_s'] += 2
            elif change == 'window': raw['perspective']['read_window_s'] = 1
            state = snapshot(raw, team=0 if change == 'override' else None)
            with self.subTest(change=change):
                for hero in state['heroes']:
                    self.assertNotIn('health', hero)
                    self.assertNotIn('resource', hero)

    def test_rolling_dump_never_issues_perspective_or_positions(self):
        m = PositionMemory(); m.recorded_non_atomic = True
        raw = NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)
        self.assertNotIn('perspective', raw)
        self.assertNotIn('positions', raw)

    def test_native_vital_read_detects_torn_root_team_handle_and_context(self):
        for target in ('root', 'team', 'handle', 'context'):
            m = PositionMemory(); original = m.read_memory; fired = False
            def changing(address, size):
                nonlocal fired
                data = original(address, size)
                if not fired and address == 0x900000 + 5 * 0x2f0 + 0x220:
                    fired = True
                    if target == 'root': m.pack(m.module_base + 0x34f01d0, 'I', 0)
                    elif target == 'team': m.pack(0x606000 + 0x1c, 'B', 0)
                    elif target == 'handle': m.pack(0x606000 + 0x58, 'I', 99)
                    else: m.context['meta']['match_id'] = 'b' * 64
                return data
            m.read_memory = changing
            with self.subTest(target=target), self.assertRaises(NativeUnavailable):
                NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)

    def test_stale_roster_does_not_grant_enemy_vitals_after_native_team_change(self):
        m = PositionMemory()
        # Swap native teams (still 5v5) without updating initData/context.
        for slot in range(1, 11):
            m.pack(0x600000 + slot * 0x1000 + 0x1c, 'B', 1 - (slot - 1) // 5)
        with self.assertRaises(NativeUnavailable):
            NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)

    def test_observer_bot_missing_player_never_grants_vitals(self):
        for change in ('observer', 'bot', 'missing'):
            m = PositionMemory()
            if change == 'observer': m.pack(0x120000, 'I', 0x20)
            elif change == 'bot': m.pack(0x606000 + 0x1d, 'B', 2)
            else: m.pack(0x120000 + 0xc, 'B', 0)
            with self.subTest(change=change), self.assertRaises(NativeUnavailable):
                NativeReader(m, profile=m.profile).read_state(m.context, hero_ids=m.hero_ids)

    def test_paused_clock_never_keeps_vitals_fresh(self):
        raw = raw_packet()
        self.assertIn('health', snapshot(raw)['heroes'][5])
        import time
        with patch('hotstate.acquisition.time.monotonic', return_value=time.monotonic() + 2):
            self.assertNotIn('health', snapshot(raw)['heroes'][5])
            self.assertNotIn('resource', snapshot(raw)['heroes'][5])

    def test_packet_cannot_cross_match_team_or_local_identity(self):
        for change in ('match', 'team', 'hero'):
            raw = raw_packet()
            if change == 'match': raw['meta']['match_id'] = 'b' * 64
            elif change == 'team':
                for member in raw['players'] + raw['heroes']: member['team'] = 1 - member['team']
                raw['local_player']['team'] = 0
            else:
                raw['local_player']['hero'] = 'jaina'
                raw['players'][5]['hero'] = raw['heroes'][5]['hero'] = 'jaina'
            with self.subTest(change=change):
                self.assertNotIn('health', snapshot(raw)['heroes'][5])


if __name__ == '__main__':
    unittest.main()
