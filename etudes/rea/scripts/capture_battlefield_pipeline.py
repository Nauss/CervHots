#!/usr/bin/env python
"""Private full battlefield pipeline; no coach, GUI, audio or release approval."""
import sys
import copy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from etudes.rea.scripts import capture_visibility_pipeline as shared
from hotstate.battlefield import VolskayaBattlefield
from hotstate.native import NativeUnavailable
_BASE_SAMPLE=shared.take_sample
_BASE_REPLAY=shared.replay_sample
_BASE_FREEZE=shared.frozen_sources


def take_sample(*args,**kwargs):
    refusals=[];original=VolskayaBattlefield.read
    observations=[];observe=VolskayaBattlefield._observe
    def private_observation(reader,*args,**kwargs):
        result=observe(reader,*args,**kwargs)
        observations.append(copy.deepcopy({k:v for k,v in result.items() if k!='_acquired'}))
        return result
    def observed(reader,context,**options):
        try:return original(reader,context,**options)
        except NativeUnavailable as exc:
            refusals.append(str(exc));raise
    with patch('hotstate.battlefield.VALIDATED_MAPS',('Volskaya',)),patch.object(VolskayaBattlefield,'read',observed),patch.object(VolskayaBattlefield,'_observe',private_observation):
        row=_BASE_SAMPLE(*args,**kwargs)
    row['mode']='unreleased_full_battlefield_pipeline_diagnostic'
    row['battlefield_diagnostic_version']=2
    row['optional_battlefield_refusals']=refusals
    row['private_battlefield_observations']=observations
    if row['status']=='accepted' and 'battlefield' not in row.get('normalized',{}):
        row['status']='rejected';row['rejected']='champ_bataille_pipeline_absent'
    return row


def replay_sample(*args,**kwargs):
    with patch.object(shared,'take_sample',take_sample):
        repeated=_BASE_REPLAY(*args,**kwargs)
    original=args[0]
    for key in ('private_battlefield_observations','optional_battlefield_refusals'):
        if original.get('battlefield_diagnostic_version')==2 and key not in original:
            raise AssertionError('private battlefield diagnostic missing')
        if key in original and repeated.get(key)!=original[key]:
            raise AssertionError('private battlefield diagnostic differs')
    return repeated


def capture_frame(*args,**kwargs):
    with patch.object(shared,'take_sample',take_sample):return shared.capture_frame(*args,**kwargs)


def _freeze(commit,*,extra_paths=()):
    return _BASE_FREEZE(commit,extra_paths=(*extra_paths,Path(__file__).resolve(),ROOT/'cerveau/battlefield.py',ROOT/'cerveau/objectives.py'))


def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    if '--live' in args:
        if '--candidate-battlefield' not in args:raise SystemExit('explicit --candidate-battlefield required')
        args.remove('--candidate-battlefield');args.append('--candidate-visibility')
    with patch.object(shared,'take_sample',take_sample),patch.object(shared,'frozen_sources',_freeze),patch.object(shared,'PIPELINE_KIND','unreleased_full_native_battlefield_pipeline'):
        return shared.main(args)

if __name__=='__main__':raise SystemExit(main())
