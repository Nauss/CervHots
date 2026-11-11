"""SYNTHETIC only: selected physical IO and real consumer normalization."""
from contextlib import ExitStack
import copy
import unittest
from unittest.mock import patch

import test_day_composition as composition
from test_core_collection_mode import READERS
from test_capture_visibility_pipeline import FixtureProcess
from cerveau.state import snapshot
from cerveau.runner import tactical_key
from hotstate.live import read_current


class PositionsCollectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = composition.DayCompositionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def take(self, project=snapshot, observe=None):
        return read_current(FixtureProcess(self.fixture.memory),
            {'triggers': {}, 'collection': 'positions'}, context=self.fixture.memory.probe(),
            project=project, key=tactical_key, observe=observe)

    def test_only_positions_reader_and_projector_entered(self):
        from cerveau.passive_session import measured_acquisition
        rows = []
        with ExitStack() as stack:
            for name in READERS:
                if name != 'hotstate.positions.AlliedPositions.read':
                    stack.enter_context(patch(name, side_effect=AssertionError('unselected IO')))
            for name in ('cerveau.state._native_visibility', 'cerveau.objectives.project_objective',
                         'cerveau.battlefield.project_battlefield', 'cerveau.talents.project_talents',
                         'cerveau.cooldowns.project_local_cooldowns', 'cerveau.state.validated_gameplay_clock'):
                stack.enter_context(patch(name, side_effect=AssertionError('unselected projection')))
            state = self.take(observe=rows.append)
        self.assertEqual(len(state['positions']['heroes']), 5)
        self.assertEqual(state['positions_qualification']['status'], 'normalized')
        self.assertEqual(state['meta']['map_id'], 'Volskaya')
        self.assertEqual(measured_acquisition(rows[0])['not_selected'],
            ['gameplay_clock', 'visibility', 'objective', 'talents', 'local_cooldowns', 'battlefield'])

    def test_unsupported_map_is_unknown_with_explicit_reason(self):
        self.fixture.memory.context['meta']['map_id'] = 'DragonShire'
        # The native context fixture publishes Volskaya: change its bound result,
        # not the physical identity/read guards.
        from hotstate.positions import AlliedPositions
        original = AlliedPositions.read
        def unsupported(reader, context, **kwargs):
            other = copy.deepcopy(context)
            other['meta']['map_id'] = 'DragonShire'
            return original(reader, other, **kwargs)
        with patch.object(AlliedPositions, 'read', unsupported):
            state = self.take()
        self.assertNotIn('positions', state)
        q = state['positions_qualification']
        self.assertEqual(q['status'], 'refused')
        self.assertEqual(q['reason']['code'], 'recette_positions_absente')
        self.assertIsNone(q['age_s'])

    def test_disk_packet_cannot_become_current(self):
        import json
        captured = {}
        def project(raw):
            captured.update(copy.deepcopy(raw))
            return snapshot(raw)
        state = self.take(project=project)
        self.assertIn('positions', state)
        disk = json.loads(json.dumps(captured))
        # Authentication alone also rejects tampering; expiry isn't the test.
        disk['positions']['heroes'][0]['x'] += 1
        self.assertNotIn('positions', snapshot(disk))

    def test_normalized_journal_positions_have_no_current_receipt(self):
        captured = {}
        def project(raw):
            captured.update(copy.deepcopy(raw))
            return snapshot(raw)
        state = self.take(project=project)
        from cerveau.diagnostics import Journal
        rows = []
        Journal(rows.append).coach_input(state)
        recorded = rows[0]['coverage']['positions']
        self.assertNotIn('acquisition', recorded)
        # A recorded normalized value is not an authenticated producer packet.
        captured['positions'] = recorded
        state = snapshot(captured)
        self.assertNotIn('positions', state)
        self.assertEqual(state['positions_qualification']['status'], 'rejected')

    def test_readiness_accepts_selected_positions_without_backend(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from cerveau.passive_session import parser
        from cerveau.session_readiness import run
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = root/'SYNTHETIC-private.txt'
            identity.write_text('SYNTHETIC_PRIVATE_IDENTITY', encoding='utf-8')
            args = parser().parse_args(['--check-ready', '--collection', 'positions',
                '--player-file', str(identity), '--output-dir', str(root/'new/session'),
                '--stop-file', str(root/'STOP')])
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                code = run(args, lambda **kwargs: dict(ready=True))
            result = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result['collection'], 'positions')
        self.assertFalse(result['memory_opened'])
        self.assertFalse(result['current_permission'])

    def test_passive_positions_journal_preserves_the_bound_map(self):
        from cerveau.passive_session import run_session
        owner = self
        class Source:
            def read(self, observe):
                return owner.take(observe=observe)
            def close(self):
                pass
        rows = []
        result = run_session(Source, lambda: any(r['event'] == 'observation' for r in rows),
            rows.append, duration=1, interval=1, clock=self.fixture.clock)
        self.assertEqual(result['accepted'], 1)
        observation = next(r for r in rows if r['event'] == 'observation')
        self.assertEqual(observation['comparison']['map_id'], 'Volskaya')


if __name__ == '__main__':
    unittest.main()
