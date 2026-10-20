"""Composed consumer regressions on mapped fixtures, NEVER live qualification."""
import contextlib
import copy
import json
import unittest
from unittest.mock import patch

from test_cooldown_packet import memory_fixture
import test_talents_product as talent_fixture
import test_capture_talents as talent_collector
import test_capture_dragon_battlefield_pipeline as battlefield_fixture
from test_dragon_contract import public_fixture
from test_capture_visibility_pipeline import FixtureClock, FixtureProcess
from hotstate import live, talents, cooldown_packet, cooldown_qualification
from hotstate.acquisition import issue
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.dragon import DragonObjective
from hotstate.dragon_battlefield import DragonBattlefield
from cerveau.state import snapshot
from cerveau.runner import tactical_key


class DayCompositionTests(unittest.TestCase):
    def setUp(self):
        self.memory, profiles = memory_fixture(talent_fixture.TalentProductTests().fixture())
        # The two fixtures share the native database root, not two product
        # contexts. Add the talent table to the actual combined root.
        native = NativeReader(self.memory, profile=self.memory.profile)
        self.memory.pack(native.value(native.base + 0x3388b18, 'Q') + 0x148, 'Q', 0x50000)
        self.clock = FixtureClock()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(talent_collector.TalentCollectorTests().options(self.memory))
        for name, value in (
                ('hotstate.visibility.PROFILE', self.memory.visibility_profile),
                ('hotstate.cooldown_packet.SIGNATURES', tuple(self.memory.profile['signatures']) * 3),
                ('hotstate.cooldown_sources.PROFILE', profiles[0]),
                ('hotstate.cooldown_costs.PROFILE', profiles[1]),
                ('hotstate.talents.VALIDATED_SCOPES', (('Volskaya', 'ragnaros'),)),
                ('hotstate.talents.VALIDATED_LOCAL_SCOPES', (('Volskaya', 'ragnaros'),)),
                ('hotstate.cooldown_packet.VALIDATED_SCOPES', (('Volskaya', 'ragnaros'),))):
            self.stack.enter_context(patch(name, value))
        self.stack.enter_context(patch.dict(cooldown_qualification.QUALIFIED_BINDINGS, {
            (98348, 'Volskaya', 'ragnaros'): {'FixtureSpell': (9, 'unit', 'Abil/FixtureSpell', None, None, 0)}}))
        self.stack.enter_context(patch('time.monotonic', self.clock))
        actual = live.memory_snapshot
        def fixture_snapshot(memory, mapping, *, context):
            return actual(memory, mapping, context=context, native_profile=self.memory.profile)
        self.stack.enter_context(patch.object(live, 'memory_snapshot', fixture_snapshot))
        self.budgets = []
        budget_class = live.LiveBudget
        def budget(*args, **kwargs):
            result = budget_class(*args, **kwargs)
            self.budgets.append(result)
            return result
        self.stack.enter_context(patch.object(live, 'LiveBudget', side_effect=budget))

    def take(self, probe=None):
        seen = {}
        def project(raw):
            seen['raw'] = raw
            return snapshot(raw)
        def key(clean):
            seen['key'] = tactical_key(clean)
        clean = live.read_current(FixtureProcess(self.memory), {'triggers': {}},
                                  context=self.memory.probe() if probe is None else probe, project=project, key=key)
        return clean, seen

    def test_both_families_use_one_actual_consumer_budget_and_core_receipt(self):
        clean, seen = self.take()
        self.assertEqual(len(self.budgets), 1)
        self.assertLessEqual(self.budgets[0].reads, 8192)
        self.assertLessEqual(self.budgets[0].bytes_requested, 2**20)
        self.assertEqual(clean['talents']['players'][0]['status'], 'observed')
        self.assertTrue(clean['local_cooldowns']['abilities'][0]['cooldown_ready'])
        self.assertEqual(seen['raw']['perspective']['local_generation'], 1)
        self.assertEqual(seen['raw']['perspective']['allied_generations'], {str(i): 1 for i in range(5, 10)})
        self.assertTrue({'talents', 'local_cooldowns'}.issubset(json.loads(seen['key'])))
        for hero in clean['heroes']:
            if hero['team'] != clean['ally_team']:
                self.assertTrue({'health', 'resource', 'x', 'y', 'talents', 'cooldowns'}.isdisjoint(hero))

    def test_closed_cd_scope_does_not_drop_qualified_talents(self):
        with patch.object(cooldown_packet, 'VALIDATED_SCOPES', ()):
            clean, _ = self.take()
        self.assertNotIn('local_cooldowns', clean)
        self.assertIn('talents', clean)

    def test_closed_talent_scopes_do_not_drop_qualified_cd(self):
        with patch.object(talents, 'VALIDATED_SCOPES', ()), patch.object(talents, 'VALIDATED_LOCAL_SCOPES', ()):
            clean, _ = self.take()
        self.assertNotIn('talents', clean)
        self.assertIn('local_cooldowns', clean)

    def test_torn_cd_is_unknown_without_poisoning_current_talents(self):
        original = self.memory.read_memory
        calls = [0]
        def mutate(address, size):
            if address == self.memory.cd_node + 0x18:
                calls[0] += 1
                if calls[0] >= 2:
                    self.memory.pack(address, 'i', 65536)
            return original(address, size)
        self.memory.read_memory = mutate
        clean, _ = self.take()
        self.assertNotIn('local_cooldowns', clean)
        self.assertIn('talents', clean)

    def test_shared_whole_read_and_byte_failures_latch_even_when_optional_catches(self):
        original = self.memory.read_memory
        active = [None]
        def limit(address, size):
            data = original(address, size)
            if address == self.memory.cd_node + 0x18 and active[0] is not None:
                # Synthetic near-limit injection, NOT a physical cost claim.
                budget = self.budgets[-1]
                if active[0] == 'reads':
                    budget.reads = 8192
                else:
                    budget.bytes_requested = 2**20
            return data
        self.memory.read_memory = limit
        for kind in ('reads', 'bytes'):
            active[0] = kind
            with self.subTest(kind=kind), self.assertRaisesRegex(NativeUnavailable, 'budget_pipeline_depasse'):
                self.take()
            self.assertLessEqual(self.budgets[-1].reads, 8192)
            self.assertLessEqual(self.budgets[-1].bytes_requested, 2**20)

    def test_cd_timeout_cannot_publish_an_earlier_talent_receipt(self):
        original = self.memory.read_memory
        def late(address, size):
            data = original(address, size)
            if address == self.memory.cd_node + 0x18:
                self.clock.value += 0.126
            return data
        self.memory.read_memory = late
        with self.assertRaisesRegex(NativeUnavailable, 'globale_depassee'):
            self.take()

    def test_each_discrete_transition_changes_its_own_key_without_losing_peer(self):
        _, first = self.take()
        self.memory.pack(self.memory.cd_node + 0x18, 'i', 2 * 65536)
        _, second = self.take()
        self.memory.pack(self.memory.cd_node + 0x18, 'i', 65536)
        _, countdown = self.take()
        self.memory.pack(self.memory.module_base + 0x3677a30 + 6 * 128 + 4, 'I', 0xffffffff)
        _, third = self.take()
        keys = [json.loads(row['key']) for row in (first, second, countdown, third)]
        self.assertNotEqual(keys[0]['local_cooldowns'], keys[1]['local_cooldowns'])
        self.assertEqual(keys[0]['talents'], keys[1]['talents'])
        self.assertEqual(keys[1], keys[2])
        self.assertNotEqual(keys[2]['talents'], keys[3]['talents'])
        self.assertEqual(keys[2]['local_cooldowns'], keys[3]['local_cooldowns'])

    def test_mismatched_family_receipt_drops_only_that_family(self):
        _, seen = self.take()
        for family, peer in (('talents', 'local_cooldowns'), ('local_cooldowns', 'talents')):
            raw = copy.deepcopy(seen['raw'])
            raw[family]['match_id'] = 'f' * 64
            issue(raw[family], self.clock.value)
            clean = snapshot(raw)
            with self.subTest(family=family):
                self.assertNotIn(family, clean)
                self.assertIn(peer, clean)

    @contextlib.contextmanager
    def dragon_options(self):
        # Business observations for objective/battlefield are literal stubs;
        # both local families still traverse their real mapped native readers.
        # No fixture value or cost here qualifies a live Dragon observation.
        probe = self.memory.probe()
        probe.map_resolver = lambda _: {'map_id': 'DragonShire', 'map': 'Dragon Shire'}
        def objective(context, **options):
            local = context['local_player']
            return dict(public_fixture(), map_id='DragonShire',
                        match_id=context['meta']['match_id'], local_id=local['id'],
                        team=local['team'], local_hero='ragnaros', mission_t_s=123.5,
                        read_window_s=0.001, _acquired=self.clock.value)
        with contextlib.ExitStack() as stack:
            for name in ('hotstate.talents.VALIDATED_SCOPES',
                         'hotstate.talents.VALIDATED_LOCAL_SCOPES',
                         'hotstate.cooldown_packet.VALIDATED_SCOPES'):
                stack.enter_context(patch(name, (('DragonShire', 'ragnaros'),)))
            stack.enter_context(patch.dict(cooldown_qualification.QUALIFIED_BINDINGS, {
                (98348, 'DragonShire', 'ragnaros'): {'FixtureSpell': (9, 'unit', 'Abil/FixtureSpell', None, None, 0)}}))
            stack.enter_context(patch.object(DragonObjective, '_observe', side_effect=objective))
            stack.enter_context(patch.object(DragonBattlefield, '_observe',
                side_effect=battlefield_fixture.DragonBattlefieldPipelineTests().sample))
            yield probe

    def test_four_family_dispatch_projections_and_discrete_key_matrix(self):
        families = ('objective', 'battlefield', 'talents', 'local_cooldowns')
        with self.dragon_options() as probe:
            clean, seen = self.take(probe)
        self.assertEqual(len(self.budgets), 1)
        self.assertTrue(set(families).issubset(clean))
        self.assertEqual(len(clean['battlefield']['camps']['entries']), 5)
        self.assertEqual(len(clean['battlefield']['structures']['entries']), 90)
        before = json.loads(seen['key'])
        for family in families:
            changed = copy.deepcopy(clean)
            if family == 'objective':
                shrine = changed[family]['shrines'][0]
                shrine['owner'] = 1 if shrine['owner'] == 0 else 0
            elif family == 'battlefield':
                changed[family]['camps']['entries'][0].update(
                    current_visible=True, state='available', owner='neutral')
            elif family == 'talents':
                changed[family]['players'][0]['tiers'][0].update(
                    status='unselected', slot=None, catalog_id=None)
            else:
                changed[family]['abilities'][0].update(remaining_s=1, cooldown_ready=False)
            after = json.loads(tactical_key(changed))
            with self.subTest(family=family):
                self.assertNotEqual(before[family], after[family])
                self.assertTrue(all(before[peer] == after[peer] for peer in families if peer != family))

    def test_four_family_closed_battlefield_does_not_remove_other_three(self):
        with self.dragon_options() as probe, patch('hotstate.dragon_battlefield.VALIDATED_MAPS', ()):
            clean, _ = self.take(probe)
        self.assertNotIn('battlefield', clean)
        self.assertTrue({'objective', 'talents', 'local_cooldowns'}.issubset(clean))

    def test_four_family_stale_battlefield_receipt_drops_only_battlefield(self):
        with self.dragon_options() as probe:
            _, seen = self.take(probe)
            raw = copy.deepcopy(seen['raw'])
            issue(raw['battlefield']['structures'], self.clock.value - 2)
            clean = snapshot(raw)
        self.assertNotIn('battlefield', clean)
        self.assertTrue({'objective', 'talents', 'local_cooldowns'}.issubset(clean))


if __name__ == '__main__':
    unittest.main()
