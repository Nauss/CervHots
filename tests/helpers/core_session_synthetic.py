"""SYNTHETIC physical fixture through actual CLI, NativeSource, normalizer/journal.

Never opens a game. Not a product mode or live qualification. Invocation from
repository cwd: python -B tests/helpers/core_session_synthetic.py OUTPUT_PARENT
A NEW parent is mandatory. Only generated SYNTHETIC identity is consumed.
"""
from contextlib import ExitStack, contextmanager
from pathlib import Path
import json
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))
from test_core_collection_mode import CoreCollectionTests, READERS
from test_capture_visibility_pipeline import FixtureProcess
from cerveau import passive_session as product


@contextmanager
def mapped_core_source(fixture, *, stop_after_read=None, guard_optional=True):
    """Retains the real NativeSource guard/lifecycle; transport is SYNTHETIC."""
    original_source = product.NativeSource
    opened = []
    class Backend(FixtureProcess):
        closed = False
        def close(self):
            self.closed = True
    def factory(player, *, collection='all'):
        backend = Backend(fixture.memory)
        # Restore the class symbols before reading: live's provenance isinstance
        # must see the actual ProcessBackend/NativeContextProbe types.
        with patch('hotstate.reader.ProcessBackend', return_value=backend), \
                patch('hotstate.native_context.NativeContextProbe', return_value=fixture.memory.probe()):
            source = original_source(player, collection=collection)
        opened.append(source)
        read = source.read
        def take(observe):
            result = read(observe)
            if stop_after_read is not None:
                stop_after_read()
            return result
        source.read = take
        return source
    with ExitStack() as stack:
        stack.enter_context(patch('hotstate.reader.ProcessBackend.__init__',
                                  side_effect=AssertionError('OS backend forbidden SYNTHETIC')))
        stack.enter_context(patch('socket.socket', side_effect=AssertionError('network forbidden')))
        stack.enter_context(patch('cerveau.brain.Coach', side_effect=AssertionError('Coach forbidden')))
        stack.enter_context(patch.object(product, 'NativeSource', factory))
        for name in READERS if guard_optional else ():
            stack.enter_context(patch(name, side_effect=AssertionError('unselected IO SYNTHETIC')))
        yield opened


def main():
    parent = Path(sys.argv[1])
    assert parent.is_absolute()
    parent.mkdir(parents=True, exist_ok=False)
    identity = parent/'SYNTHETIC-identity.txt'
    identity.write_text('SYNTHETIC_IDENTITY', encoding='utf-8')
    stop = parent/'STOP-SYNTHETIC'
    out = parent/'session'
    test = CoreCollectionTests()
    test.setUp()
    original_loop = product.run_session
    def loop(factory, stopped, emit, **kwargs):
        def persist(row):
            emit(row)
            if row['event'] == 'observation':
                stop.touch()
        return original_loop(factory, stopped, persist, **kwargs)
    try:
        with mapped_core_source(test.fixture) as sources, patch.object(product, 'run_session', loop):
            code = product.main(['--live', '--collection', 'core', '--player-file', str(identity),
                '--output-dir', str(out), '--stop-file', str(stop), '--max-seconds', '1'])
        assert code == 0
        assert len(sources) == 1 and sources[0].backend is None and sources[0].probe is None
        assert sources[0].guard.handle is None
        summary = json.loads((out/'summary.json').read_text())
        assert summary['accepted'] == 1 and summary['collection'] == 'core'
        assert summary['reason'] == 'stop_file' and summary['reader_active'] is False
        rows = [json.loads(line) for line in (out/'events.jsonl').read_text().splitlines()]
        assert next(r for r in rows if r['event'] == 'acquisition')['collection'] == 'core'
        (parent/'SYNTHETIC-PROVENANCE.json').write_text(json.dumps(dict(
            basis='SYNTHETIC_NOT_LIVE_NOT_HUD', references_held=False,
            os_backend_opened=False, source_guard_released=True,
            callbacks='real NativeSource/read_current/snapshot/tactical_key/run_session/Journal/main',
            exit_code=code), indent=2)+'\n', encoding='utf-8')
        return code
    finally:
        test.doCleanups()


if __name__ == '__main__':
    raise SystemExit(main())
