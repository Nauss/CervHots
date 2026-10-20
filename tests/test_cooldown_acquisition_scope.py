"""Acquisition scope regressions, mapped/synthetic only; no live qualification."""
import unittest
from unittest.mock import patch

import test_cooldown_sources as source_fixture
import test_cooldown_packet as packet_fixture
from hotstate import cooldown_sources, cooldown_costs, cooldown_qualification
from hotstate.native import NativeUnavailable


class CooldownAcquisitionScopeTests(unittest.TestCase):
    def source(self):
        helper = source_fixture.SourceTests()
        helper.setUp()
        return helper

    def packet(self):
        helper = packet_fixture.CooldownPacketTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        return helper

    def test_filter_before_cost_keeps_native_active_ordinal_and_slot(self):
        helper = self.source()
        with patch.object(cooldown_costs, 'current_cost', return_value={'status': 'fixture'}) as cost:
            rows = cooldown_sources.active_instances(helper.n, 0x10000, native_owner=6,
                                                       allowed_abilities=frozenset({'StitchesHook'}))
        self.assertEqual([(p['ordinal'], p['instance_slot'], p['ability']) for p in rows],
                         [(2, 3, 'StitchesHook')])
        cost.assert_called_once_with(helper.n, 0x31000, 6)

    def test_diagnostic_default_still_reads_every_current_instance_cost(self):
        helper = self.source()
        with patch.object(cooldown_costs, 'current_cost', return_value={'status': 'fixture'}) as cost:
            rows = cooldown_sources.active_instances(helper.n, 0x10000, native_owner=6)
        self.assertEqual([p['ability'] for p in rows], ['StitchesSlam', 'StitchesHook'])
        self.assertEqual(cost.call_count, 2)

    def test_absent_allowed_name_never_constructs_catalogue_ability(self):
        helper = self.source()
        with patch.object(cooldown_costs, 'current_cost', side_effect=AssertionError('unqualified cost read')):
            rows = cooldown_sources.active_instances(helper.n, 0x10000, native_owner=6,
                                                       allowed_abilities=frozenset({'AbsentFromCurrentBitmap'}))
        self.assertEqual(rows, [])

    def test_filter_does_not_hide_duplicate_or_missing_current_descriptor(self):
        for mutation in ('duplicate', 'descriptor'):
            helper = self.source()
            if mutation == 'duplicate':
                helper.values[0x20068 + 24] = 0x30000
            else:
                helper.values[0x30028] = 0x10
            with self.subTest(mutation=mutation), self.assertRaises(NativeUnavailable):
                cooldown_sources.active_instances(helper.n, 0x10000,
                                                   allowed_abilities=frozenset({'NotPresent'}))

    def test_filter_is_explicit_set_not_string_coercion(self):
        helper = self.source()
        for invalid in ('StitchesHook', ['StitchesHook'], {None}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                cooldown_sources.active_instances(helper.n, 0x10000, allowed_abilities=invalid)

    def test_unit_cd_only_packet_never_reads_unqualified_player_or_charge_stores(self):
        helper = self.packet()
        with helper.opened(), patch.object(cooldown_sources, 'stored_links',
                                           side_effect=AssertionError('unqualified storage read')):
            before = len(helper.calls)
            packet = helper.read()
        ability = packet['abilities'][0]
        self.assertTrue(ability['cooldown_ready'])
        self.assertEqual(ability['charges_status'], 'not_applicable_current_max_zero')
        self.assertEqual(packet['read_count'], len(helper.calls) - before)
        self.assertEqual(packet['bytes_requested'], sum(size for _, size in helper.calls[before:]))
        self.assertEqual(packet['actor_scope'], 'current_native_main_hero')
        self.assertEqual(packet['ui_control_body'], 'unknown')

    def test_current_internal_instance_never_reads_its_cost_or_becomes_hud_permission(self):
        helper = self.packet()
        name = 'UnprovenInternal'
        helper.m.pack(helper.m.name_string + 0x18, 'II', len(name) * 4, 0)
        helper.m.put(helper.m.name_string + 0x20, name.encode('ascii'))
        with helper.opened(), patch.object(cooldown_costs, 'current_cost',
                                           side_effect=AssertionError('internal current cost read')):
            self.assertEqual(helper.read()['abilities'], [])

    def test_no_qualified_instance_still_requires_actual_unit_cd_root(self):
        helper = self.packet()
        name = 'UnprovenInternal'
        helper.m.pack(helper.m.name_string + 0x18, 'II', len(name) * 4, 0)
        helper.m.put(helper.m.name_string + 0x20, name.encode('ascii'))
        helper.m.pack(helper.m.local_unit + 8, 'Q', 0)
        with helper.opened(), self.assertRaises(NativeUnavailable):
            helper.read()

    def test_changed_positive_max_stays_unknown_without_reading_unqualified_charges(self):
        helper = self.packet()
        helper.m.pack(helper.m.cost + 0x20, 'i', 2 * 4096)
        with helper.opened(), patch.object(cooldown_sources, 'stored_links',
                                           side_effect=AssertionError('unqualified charge read')):
            ability = helper.read()['abilities'][0]
        self.assertEqual(ability['charges_status'], 'unknown')
        self.assertNotIn('charges_available', ability)
        self.assertNotIn('charges_max', ability)
        self.assertTrue(ability['cooldown_ready'])
        self.assertEqual(ability['cast_legality'], 'unknown')

    def test_only_explicit_policy_storage_is_acquired_not_inferred_as_observed(self):
        for case, storage, charges in (
                ((9, 'player', 'Abil/FixtureSpell', None, None, 0), 'player', False),
                ((9, 'unit', 'Abil/FixtureSpell', 'player', 'Charge/FixtureSpell', 2), 'player', True)):
            helper = self.packet()
            with self.subTest(case=case), helper.opened(), \
                 patch.dict(cooldown_qualification.QUALIFIED_BINDINGS, {
                     (98348, 'Volskaya', 'ragnaros'): {'FixtureSpell': case}}), \
                 patch.object(cooldown_sources, 'stored_links', return_value={}) as source:
                ability = helper.read()['abilities'][0]
            source.assert_called_once()
            self.assertEqual(source.call_args.args[1], helper.m.local_player)
            self.assertEqual(source.call_args.kwargs, {'storage': storage, 'charges': charges})
            # A policy can select a source; it never replaces the CURRENT cost
            # binding/max or turns a missing native link into a known value.
            self.assertNotIn('charges_available', ability)
            if not charges:
                self.assertEqual(ability['cooldown_status'], 'unknown')
                self.assertNotIn('cooldown_ready', ability)
            helper.doCleanups()


if __name__ == '__main__':
    unittest.main()
