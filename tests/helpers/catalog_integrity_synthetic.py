"""SYNTHETIC interprocess barriers; real Windows file sharing/termination.

No native/live constructors. Paths are explicitly supplied by the test parent.
"""
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cerveau import passive_session as cli
from cerveau import catalog_integrity as integrity

mode, root, output, ready, release = sys.argv[1:]
root, output, ready, release = map(Path, (root, output, ready, release))


def barrier():
    ready.write_text(json.dumps(dict(kind='SYNTHETIC barrier', pid=os.getpid())))
    deadline = time.monotonic() + 20
    while not release.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError('SYNTHETIC barrier timeout')
        time.sleep(.01)


if mode == 'publish-interrupt':
    original = os.fsync
    calls = [0]
    def syncing(fd):
        calls[0] += 1
        if calls[0] == 5:  # four complete payload files, then full marker bytes
            barrier()
        return original(fd)
    with patch('os.fsync', side_effect=syncing):
        raise SystemExit(cli.main(['--catalog', '--sessions-root', str(root), '--report-dir', str(output)]))
elif mode == 'verify-held':
    original = integrity._digest
    calls = [0]
    def digest(fd, budget):
        result = original(fd, budget)
        calls[0] += 1
        if calls[0] == 4:
            barrier()
        return result
    with patch.object(integrity, '_digest', side_effect=digest):
        raise SystemExit(cli.main(['--verify-catalog', '--report-dir', str(output)]))
else:
    raise ValueError('unknown SYNTHETIC mode')
