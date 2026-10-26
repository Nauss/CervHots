"""SYNTHETIC exact-process barriers, real Windows handles; test-only."""
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cerveau import offline_demo, demo_integrity

mode, output, ready, release = sys.argv[1:]
output, ready, release = map(Path, (output, ready, release))


def barrier():
    ready.write_text(json.dumps(dict(pid=os.getpid(), kind='SYNTHETIC')))
    deadline = time.monotonic()+20
    while not release.exists():
        if time.monotonic() > deadline:
            raise RuntimeError('SYNTHETIC timeout')
        time.sleep(.01)


if mode == 'publish-interrupt':
    original_commit = demo_integrity.integrity._commit_marker
    original_sync = os.fsync
    def commit(path, text):
        if path.name != demo_integrity.MARKER:
            return original_commit(path, text)
        def sync(fd):
            barrier()  # complete buffered bytes flushed, disposition still pending
            return original_sync(fd)
        with patch('os.fsync', side_effect=sync):
            return original_commit(path, text)
    with patch.object(demo_integrity.integrity, '_commit_marker', side_effect=commit):
        raise SystemExit(offline_demo.main(['--destination', str(output)]))
elif mode == 'verify-held':
    original = demo_integrity._inventory
    def inventory(guards, target):
        value = original(guards, target)
        barrier()  # every bounded payload and directory pinned
        return value
    with patch.object(demo_integrity, '_inventory', side_effect=inventory):
        raise SystemExit(offline_demo.main(['--verify', str(output)]))
else:
    raise ValueError('unknown SYNTHETIC mode')
