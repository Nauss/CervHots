"""Guarded real entrypoint for disk-only requests; SYNTHETIC arguments only."""
import importlib.abc
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class NoBackend(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ('hotstate.reader', 'hotstate.live', 'hotstate.native_context',
                        'cerveau.native_reader_guard', 'cerveau.player_identity'):
            raise AssertionError('backend/identity import forbidden')
        return None

def main():
    from cerveau import passive_session as product
    sys.meta_path.insert(0, NoBackend())
    with patch.object(product, 'NativeSource', side_effect=AssertionError('source forbidden')), \
            patch.object(product, 'preflight', side_effect=AssertionError('preflight forbidden')), \
            patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')):
        code = product.main(sys.argv[1:])
    assert 'cerveau.native_reader_guard' not in sys.modules
    assert 'hotstate.reader' not in sys.modules
    return code


if __name__ == '__main__':
    raise SystemExit(main())
