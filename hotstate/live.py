"""Bounded direct live acquisition through the consumer boundary.

Only the typed native context path is supported here. Raw reader.snapshot and
historical instrumentation are low-level diagnostics, not a Full acceptance.
No trace, process open, cache, GUI, coach call or audio lives in this module.
"""
from __future__ import annotations

import time

from .native import NativeUnavailable
from .native_context import NativeContextProbe
from .reader import ProcessBackend, snapshot as memory_snapshot


class LiveBudget(ProcessBackend):
    """One attempt's physical budget, shared by all readers and final checks.

    A ProcessBackend proxy preserves the reader's live provenance check without
    opening a second process handle. Refusals latch, even if an optional family
    catches NativeUnavailable. There is no reuse between attempts.
    """
    def __init__(self, backend, *, clock=None):
        self.backend = backend
        self.module_base = backend.module_base
        self.recorded_non_atomic = getattr(backend, 'recorded_non_atomic', False)
        self.clock = time.monotonic if clock is None else clock
        self.started = self.clock()
        self.reads = 0
        self.bytes_requested = 0
        self.failure = None

    def check(self):
        if self.failure is None and not 0 <= self.clock() - self.started <= 0.125:
            self.failure = 'fenetre_pipeline_globale_depassee'
        if self.failure is not None:
            raise NativeUnavailable(self.failure)

    def read_memory(self, address, size):
        self.check()
        if (type(size) is not int or not 0 < size <= 65536
                or self.reads >= 8192 or self.bytes_requested + size > 2**20):
            self.failure = 'budget_pipeline_depasse'
            raise NativeUnavailable(self.failure)
        # Count failed physical requests as well; never read past the limit.
        self.reads += 1
        self.bytes_requested += size
        return self.backend.read_memory(address, size)

    def positions_clock(self):
        return getattr(self.backend, 'positions_clock', time.monotonic)()

    def regions_bytes(self):
        # A legacy whole-heap scan could bypass read_memory and its budget.
        raise NativeUnavailable('scan_pipeline_natif_interdit')


def read_current(backend, mapping, *, context, project=None, key=None, clock=None):
    """Acquire, recheck context, normalize and build the key inside 125ms.

    Projection/key callbacks are the real consumer functions, not mocks in the
    product. Returning raw data is for the standalone reader CLI only; serialized
    receipts cannot grant cross-process tactical permissions.
    """
    if not isinstance(context, NativeContextProbe) or getattr(backend, 'recorded_non_atomic', False):
        raise NativeUnavailable('pipeline_live_contexte_natif_requis')
    memory = LiveBudget(backend, clock=clock)
    raw = memory_snapshot(memory, mapping, context=context)
    memory.check()
    if raw['meta'].get('native_status') != 'valide':
        raise NativeUnavailable(raw['meta'].get('native_status', 'coeur_pipeline_absent'))
    context.recheck(memory)
    result = raw if project is None else project(raw)
    if key is not None:
        key(result)
    memory.check()
    return result
