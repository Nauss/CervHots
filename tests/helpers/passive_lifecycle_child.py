"""Test-only SYNTHETIC transport. No game, capture, API or live qualification.

Not a product entrypoint: the parent test supplies a fresh absolute directory.
File acknowledgments are exclusive, flushed and fsynced before publication.
"""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))


def publish(path, row):
    pending = path.with_name(path.name + '.pending')
    with pending.open('x', encoding='utf-8') as stream:
        json.dump(row, stream, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    pending.rename(path)


def await_file(path):
    deadline = time.perf_counter() + 20
    while not path.is_file():
        if time.perf_counter() >= deadline:
            raise TimeoutError('SYNTHETIC handshake deadline')
        time.sleep(.02)


def receipt_check(parent, old):
    from test_positions_contract import raw_packet
    from hotstate.acquisition import fresh
    from cerveau.state import snapshot
    raw = raw_packet()
    with patch('hotstate.positions.VALIDATED_MAPS', ('Volskaya',)):
        assert fresh(raw['positions']) and 'positions' in snapshot(raw)
        if old:
            foreign = json.loads(Path(old).read_text(encoding='utf-8'))
            # Force a legal age: rejection must be cross-process provenance,
            # not accidental scheduling/expiry. No key is copied or reissued.
            acquired = foreign['positions']['acquisition']['monotonic_s']
            with patch('hotstate.acquisition.time.monotonic', return_value=acquired):
                foreign_fresh = fresh(foreign['positions'])
                foreign_projected = 'positions' in snapshot(foreign)
            publish(parent / 'foreign-receipt.json', dict(
                same_process_fresh=True, foreign_fresh=foreign_fresh,
                foreign_projected=foreign_projected, age_forced_s=0))
    publish(parent / 'SYNTHETIC-receipt.json', raw)


def main():
    from core_session_synthetic import mapped_core_source
    from test_core_collection_mode import CoreCollectionTests
    from cerveau import passive_session as product

    parent, mode = Path(sys.argv[1]), sys.argv[2]
    old = sys.argv[3] if len(sys.argv) > 3 else None
    assert parent.is_absolute() and parent.is_dir()
    publish(parent / 'runtime.json', dict(pid=os.getpid(), executable=sys.executable,
        version=sys.version, basis='SYNTHETIC_NOT_LIVE_NOT_HUD',
        effective_temp=tempfile.gettempdir(),
        env_temp={k: os.environ.get(k) for k in ('TMPDIR', 'TEMP', 'TMP')}))
    identity = parent / 'SYNTHETIC-identity.txt'
    identity.write_text('SYNTHETIC_IDENTITY', encoding='utf-8')
    output, stop = parent / 'session', parent / 'STOP-SYNTHETIC'
    argv = ['--live', '--collection', 'core', '--player-file', str(identity),
            '--output-dir', str(output), '--stop-file', str(stop),
            '--max-seconds', '30', '--interval', '1']
    if mode.startswith('interrupt-'):
        def interrupt(out, target):
            if mode == 'interrupt-partial-control':
                (out / 'control.json').write_bytes(b'{')
            publish(parent / 'before-control.json', dict(source_opened=False))
            await_file(parent / 'interrupt')
            raise KeyboardInterrupt
        with patch('cerveau.session_control.record_control', interrupt), \
                patch.object(product, 'NativeSource', side_effect=AssertionError('no source before control')):
            code = product.main(argv)
        publish(parent / 'terminal.json', dict(code=code, source_opened=False))
        return code

    receipt_check(parent, old)
    test = CoreCollectionTests()
    test.setUp()
    if old:
        # New invocation, independently constructed source/probe and native
        # synthetic match identity, even with the same roster and addresses.
        memory = test.fixture.memory
        memory.seed += 1
        memory.pack(memory.config + 0x1d428, 'I', memory.seed)
        memory.context['meta']['match_id'] = hashlib.sha256(
            memory.seed.to_bytes(4, 'little') + b''.join(memory.handles)).hexdigest()
    try:
        with ExitStack() as stack:
            sources = stack.enter_context(mapped_core_source(test.fixture))
            factory = product.NativeSource
            def source(*args, **kwargs):
                result = factory(*args, **kwargs)
                close_backend = result.backend.close
                def backend_close():
                    publish(parent / 'backend-close-attempt.json', dict(attempted=True))
                    if mode == 'close-error':
                        raise OSError('SYNTHETIC uncertain closure')
                    close_backend()
                    publish(parent / 'backend-closed.json', dict(closed=True))
                result.backend.close = backend_close
                close_source = result.close
                def close():
                    close_source()
                    publish(parent / 'source-closed.json', dict(
                        backend_none=result.backend is None, probe_none=result.probe is None,
                        guard_released=result.guard.handle is None))
                result.close = close
                actual_read = result.read
                def read(observe):
                    state = actual_read(observe)
                    context_file = parent / 'first-read-context.json'
                    if not context_file.exists():
                        publish(context_file, dict(synthetic_match_id=state['meta']['match_id']))
                    return state
                result.read = read
                publish(parent / 'source-opened.json', dict(opened=True))
                return result
            stack.enter_context(patch.object(product, 'NativeSource', source))
            loop = product.run_session
            def observed(factory, stopped, emit, **kwargs):
                sequence = [0]
                def persist(row):
                    emit(row)
                    if row['event'] == 'observation':
                        sequence[0] += 1
                        publish(parent / ('observation-%d.json' % sequence[0]), dict(
                            persisted=True, session=row['session'], comparison=row['comparison']))
                return loop(factory, stopped, persist, **kwargs)
            stack.enter_context(patch.object(product, 'run_session', observed))
            code = product.main(argv)
            publish(parent / 'terminal.json', dict(code=code, sources=len(sources),
                backend_none=not sources or sources[0].backend is None,
                probe_none=not sources or sources[0].probe is None,
                guard_released=not sources or sources[0].guard.handle is None))
            if mode == 'close-error' and sources:
                # Deliberately remain alive with the uncertain source/guard.
                # Another real CLI invocation must refuse before backend open.
                await_file(parent / 'release-uncertain-process')
            return code
    finally:
        test.doCleanups()


if __name__ == '__main__':
    raise SystemExit(main())
