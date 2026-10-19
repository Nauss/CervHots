"""Synthetic CURRENT boundary for the dimmed capture BEACON, not its shrine."""
import copy
import time
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from test_dragon import DragonMemory
from test_dragon_contract import packet
from hotstate.acquisition import issue
from hotstate.native import NativeReader, NativeUnavailable
from hotstate.dragon import DragonObjective
from cerveau.dragon import project_dragon, dragon_key


def public_sample(memory, visible):
    reader = memory.reader()
    with ExitStack() as stack:
        stack.enter_context(patch.object(reader.units, '_unit_type', side_effect=lambda n,u: memory.types[u]))
        stack.enter_context(patch('hotstate.positions.AlliedPositions._verify'))
        stack.enter_context(patch('hotstate.visibility.CurrentVisibility._verify'))
        observed = stack.enter_context(patch('hotstate.visibility.CurrentVisibility._current'))
        if isinstance(visible, list):
            observed.side_effect = visible
        else:
            observed.return_value = visible
        sample = reader._sample(reader.native, local_id=0)
        return sample, list(observed.call_args_list)


def project(sample):
    raw, local = packet()
    raw['objective'].update(copy.deepcopy(sample))
    raw['objective']['status'] = 'validated'
    issue(raw['objective'], time.monotonic())
    with patch('hotstate.dragon.VALIDATED_MAPS', ('DragonShire',)):
        return project_dragon(raw, local, 0)


class DragonBeaconVisibilityTests(unittest.TestCase):
    def test_false_and_unknown_capture_sight_preserve_public_owner_not_progress(self):
        for visible in (False, None):
            with self.subTest(visible=visible):
                memory = DragonMemory()
                memory.capture(1, owner=11, state=3, counter=64)
                memory.capture(2, owner=12, state=0, counter=-20)
                sample, calls = public_sample(memory, visible)
                self.assertEqual([call.args[1] for call in calls], [memory.unit(2), memory.unit(3)])
                for row, owner in zip(sample['shrines'], (0,1)):
                    self.assertEqual(row['owner'], owner)
                    self.assertEqual(row['state'], 'unknown')
                    self.assertIsNone(row['contested'])
                    self.assertIsNone(row['capture_counter'])
                    self.assertIsNone(row['capture_goal'])
                    self.assertIs(row['capture_current_visible'], visible)
                clean = project(sample)
                self.assertIsNotNone(clean)
                self.assertEqual([row['owner'] for row in clean['shrines']], [0,1])

    def test_current_beacons_retain_observed_progress_not_private_counters_in_projection(self):
        memory = DragonMemory()
        memory.capture(1, owner=11, state=3, counter=64)
        memory.capture(2, owner=12, state=0, counter=-20)
        sample, calls = public_sample(memory, True)
        self.assertEqual(len(calls), 2)
        self.assertEqual([row['state'] for row in sample['shrines']], ['captured','contested'])
        self.assertTrue(all(row['capture_current_visible'] is True for row in sample['shrines']))
        clean = project(sample)
        self.assertIsNotNone(clean)
        self.assertIs(clean['shrines'][1]['contested'], True)
        self.assertNotIn('capture_counter', str(clean))
        self.assertNotIn('capture_current_visible', str(clean))

    def test_public_owners_with_unknown_progress_still_allow_separate_visible_channel(self):
        memory = DragonMemory()
        memory.capture(1, owner=11, state=3, counter=64)
        memory.capture(2, owner=11, state=3, counter=64)
        memory.pack(memory.unit(4)+0x44, 'B', 11)
        with patch('hotstate.objectives.VolskayaObjective._duration', return_value=2.0):
            sample, calls = public_sample(memory, [False,None,True])
        self.assertEqual([call.args[1] for call in calls], [memory.unit(2),memory.unit(3),memory.unit(4)])
        self.assertTrue(all(row['state']=='unknown' and row['owner']==0 for row in sample['shrines']))
        clean = project(sample)
        self.assertIsNotNone(clean)
        self.assertEqual(clean['statue'], {'state':'capturable','team':0,'channeling':True})

    def test_active_capture_requires_strict_current_true_not_owner_or_missing_flag(self):
        for visible in ('missing',False,None,1,'known'):
            with self.subTest(visible=visible):
                sample = DragonMemory().sample()
                for row in sample['shrines']:
                    if visible != 'missing':
                        row['capture_current_visible'] = visible
                self.assertIsNone(project(sample))
        sample = DragonMemory().sample()
        for row in sample['shrines']:
            row['capture_current_visible'] = True
        self.assertIsNotNone(project(sample))

    def test_known_owner_with_unknown_capture_requires_explicit_unestablished_sight(self):
        sample = DragonMemory().sample()
        for row in sample['shrines']:
            row.update(state='unknown', owner=1, contested=None, capture_current_visible=None)
        self.assertIsNotNone(project(sample))
        for value in ('missing',True,1,'known'):
            with self.subTest(value=value):
                changed = copy.deepcopy(sample)
                if value == 'missing':
                    changed['shrines'][0].pop('capture_current_visible')
                else:
                    changed['shrines'][0]['capture_current_visible'] = value
                self.assertIsNone(project(changed))

    def test_hidden_capture_changes_do_not_change_public_tactical_key(self):
        keys = []
        for state in (0,4,5):
            memory = DragonMemory()
            memory.capture(2, owner=12, state=state, counter=-20)
            sample, _ = public_sample(memory, False)
            clean = project(sample)
            self.assertIsNotNone(clean)
            keys.append(dragon_key(clean))
        self.assertEqual(keys[0], keys[1])
        self.assertEqual(keys[1], keys[2])

    def test_hidden_or_disabled_progress_is_not_read_at_all(self):
        for enabled in (0,1):
            for visible in (False,None):
                with self.subTest(enabled=enabled,visible=visible):
                    memory = DragonMemory()
                    memory.capture(1, enabled=enabled, state=0, counter=64)
                    original = memory.read_memory
                    spans = [(memory.g+0x118C5+index*132+offset, length)
                             for index in (6,7) for offset,length in ((9,12),(29,12))]
                    def guarded(address,size):
                        if any(address < start+length and start < address+size for start,length in spans):
                            raise AssertionError('hidden progress entered public readset')
                        return original(address,size)
                    memory.read_memory = guarded
                    sample, _ = public_sample(memory, visible)
                    self.assertEqual(sample['shrines'][0]['state'], 'unknown' if enabled else 'disabled')
                    self.assertIsNone(sample['shrines'][0]['contested'])

    def test_only_visible_capture_changes_can_invalidate_the_public_receipt(self):
        from test_capture_dragon import CaptureDragonTests
        for visible in (False,None,True):
            with self.subTest(visible=visible), CaptureDragonTests().fixture() as (memory,probe,context):
                reader = DragonObjective(NativeReader(memory,profile=memory.profile),profile=memory.p)
                original = reader._sample
                def change_after_sample(n,local_id=None):
                    result = original(n,local_id=local_id)
                    memory.pack(memory.g+0x118C5+6*132+29,'i',0)
                    return result
                with patch('hotstate.positions.AlliedPositions._verify'), \
                     patch('hotstate.visibility.CurrentVisibility._verify'), \
                     patch('hotstate.visibility.CurrentVisibility._current',return_value=visible), \
                     patch.object(reader,'_sample',side_effect=change_after_sample):
                    if visible is True:
                        with self.assertRaisesRegex(NativeUnavailable,'lecture_dragon_dechiree'):
                            reader._observe(context)
                    else:
                        result = reader._observe(context)
                        self.assertTrue(all(row['state']=='unknown' for row in result['shrines']))


if __name__ == '__main__':
    unittest.main()
