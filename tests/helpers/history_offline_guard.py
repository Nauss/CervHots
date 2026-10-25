"""Real passive_session CLI with forbidden live side effects (offline only)."""
from contextlib import ExitStack
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def forbidden(*args, **kwargs):
    raise AssertionError('offline_side_effect_forbidden')


with ExitStack() as stack:
    for target in ('socket.socket', 'hotstate.reader.ProcessBackend.__init__',
                   'hotstate.acquisition.issue', 'cerveau.brain.Coach.__init__',
                   'cerveau.cooldowns.project_local_cooldowns'):
        stack.enter_context(patch(target, forbidden))
    sys.argv = ['cerveau.passive_session'] + sys.argv[1:]
    runpy.run_module('cerveau.passive_session', run_name='__main__')
