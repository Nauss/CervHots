"""SYNTHETIC real CLI persistence and migration compatibility; no game/HUD.

Invoke from checkout: python -B tests/helpers/default_collection_synthetic.py NEW_PARENT
"""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))


def exercise(parent):
    # Imports follow checkout bootstrap for direct helper subprocess invocation.
    import test_day_composition as composition
    from tests.helpers.core_session_synthetic import mapped_core_source
    from cerveau import passive_session as product
    from cerveau.native_history import summarize
    from cerveau.session_diagnosis import diagnose

    parent.mkdir(parents=True, exist_ok=False)
    identity = parent/'SYNTHETIC-identity.txt'
    identity.write_text('SYNTHETIC_IDENTITY', encoding='utf-8')
    results = []
    original_loop = product.run_session
    for selection in (None, 'core', 'all', 'talents'):
        name = selection or 'omitted'
        test = composition.DayCompositionTests()
        test.setUp()
        out, stop = parent/name/'session', parent/(name+'.STOP')
        def loop(factory, stopped, emit, **kwargs):
            def persisted(row):
                emit(row)
                if row['event'] == 'observation':
                    stop.touch(exist_ok=False)
            return original_loop(factory, stopped, persisted, **kwargs)
        argv = ['--live', '--player-file', str(identity), '--output-dir', str(out),
                '--stop-file', str(stop), '--max-seconds', '1']
        if selection is not None:
            argv += ['--collection', selection]
        try:
            with mapped_core_source(test, guard_optional=name in ('omitted', 'core')) as sources, \
                    patch.object(product, 'run_session', loop), redirect_stdout(io.StringIO()):
                code = product.main(argv)
            assert code == 0
            assert len(sources) == 1 and sources[0].backend is None and sources[0].guard.handle is None
            assert sources[0].collection == (selection or 'core')
            rows = [json.loads(line) for line in (out/'events.jsonl').read_text().splitlines()]
            acquisition = next(row for row in rows if row['event'] == 'acquisition')
            effective = selection or 'core'
            assert acquisition['collection'] == effective
            expected = product.measured_acquisition({'collection':effective})['not_selected']
            assert acquisition['not_selected'] == expected
            summary = json.loads((out/'summary.json').read_text())
            assert summary['collection'] == effective and summary['accepted'] == 1
            assert summary['reason'] == 'stop_file' and summary['reader_active'] is False
            history = summarize(out/'events.jsonl')
            diagnosis = diagnose(out/'events.jsonl')
            if effective == 'core':
                assert acquisition['optional_refusals'] == {}
                for family in expected:
                    assert diagnosis['families'][family] == {'not_selected':1}
                for family in ('talents', 'objective'):
                    assert history[family]['status'] == 'not_selected'
                    assert history[family]['original_age_s'] is None
            # Existing STOP prevents re-open and any new path creation.
            stopped_out = parent/(name+'-stopped')/'session'
            with patch.object(product, 'NativeSource', side_effect=AssertionError('STOP before source')), redirect_stdout(io.StringIO()):
                blocked = product.main(['--live', '--player-file', str(identity), '--output-dir', str(stopped_out), '--stop-file', str(stop)])
            assert blocked == 0 and not stopped_out.parent.exists()
            # A fresh STOP does not permit reusing a claimed parent or existing output.
            with patch.object(product, 'NativeSource', side_effect=AssertionError('claim before source')), redirect_stdout(io.StringIO()):
                refused = product.main(['--live', '--player-file', str(identity), '--output-dir', str(out.parent/'other'), '--stop-file', str(parent/(name+'-new.STOP'))])
            assert refused == 1 and not (out.parent/'other').exists()
            results.append(dict(case=name,collection=effective,exit_code=code,
                acquisition=acquisition,stop_before_open_code=blocked,claimed_parent_code=refused,
                closed=True,basis='SYNTHETIC_NOT_LIVE_NOT_HUD'))
        finally:
            test.doCleanups()
    # Identical core acquisition, physical costs and exclusions for omission/explicit core.
    first, second = results[0]['acquisition'], results[1]['acquisition']
    for key in ('collection', 'not_selected', 'reads', 'bytes_requested', 'optional_refusals', 'outcome'):
        assert first.get(key) == second.get(key), (key, first, second)
    (parent/'SYNTHETIC-results.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    return results


if __name__ == '__main__':
    print(json.dumps(exercise(Path(sys.argv[1]))))
