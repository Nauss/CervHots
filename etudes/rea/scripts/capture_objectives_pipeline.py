#!/usr/bin/env python
"""Private current-objective FULL native pipeline, product gate stays CLOSED.

Reuses the exercised bounded context discovery, recording-only live clocks,
reader.snapshot -> NativeReader.read_state -> normalizer -> tactical_key and
PNG brackets. Only this diagnostic process enables candidate objective packets.
No game launch/GUI control, memory write, coach/API, audio or replay producer.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etudes.rea.scripts import capture_visibility_pipeline as shared
from hotstate.objectives import VolskayaObjective
from hotstate.native import NativeUnavailable

_BASE_SAMPLE = shared.take_sample
_BASE_REPLAY = shared.replay_sample
_BASE_FREEZE = shared.frozen_sources


def take_sample(*args, **kwargs):
    refusals = []
    original = VolskayaObjective.read

    def observed(reader, context, **options):
        try:
            return original(reader, context, **options)
        except NativeUnavailable as exc:
            refusals.append(str(exc))
            raise

    with patch('hotstate.objectives.VALIDATED_MAPS', ('Volskaya',)), \
            patch.object(VolskayaObjective, 'read', observed):
        row = _BASE_SAMPLE(*args, **kwargs)
    row['mode'] = 'unreleased_full_objective_pipeline_diagnostic'
    row['optional_objective_refusals'] = refusals
    if row['status'] == 'accepted' and 'objective' not in row.get('normalized', {}):
        row['status'] = 'rejected'
        row['rejected'] = 'objectif_pipeline_absent'
    return row


def replay_sample(*args, **kwargs):
    # Historical clock sequences recreate acquisition in-process, never trust
    # serialized HMAC receipts or turn an old capture into a fresh observation.
    with patch.object(shared, 'take_sample', take_sample):
        return _BASE_REPLAY(*args, **kwargs)


def capture_frame(*args, **kwargs):
    with patch.object(shared, 'take_sample', take_sample):
        return shared.capture_frame(*args, **kwargs)


def _freeze(commit, *, extra_paths=()):
    return _BASE_FREEZE(commit, extra_paths=(*extra_paths, Path(__file__).resolve(),
                                           ROOT / 'cerveau/objectives.py'))


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if '--live' in args:
        if '--candidate-objectives' not in args:
            raise SystemExit('explicit --candidate-objectives consent required')
        args.remove('--candidate-objectives')
        # The shared CLI also preserves the already delivered current visibility
        # field. Its legacy explicit flag does not enable any extra enemy data.
        args.append('--candidate-visibility')
    with patch.object(shared, 'take_sample', take_sample), \
            patch.object(shared, 'frozen_sources', _freeze), \
            patch.object(shared, 'PIPELINE_KIND', 'unreleased_full_native_objective_pipeline'):
        return shared.main(args)


if __name__ == '__main__':
    raise SystemExit(main())
