"""Real CLI + simulated cooperative source. SYNTHETIC, never game/HUD/native.

Usage: python -B tests/helpers/stop_request_synthetic.py ABSOLUTE_NEW_PARENT
"""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))


def inventory(root):
    return {p.relative_to(root).as_posix():dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mtime_ns=p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}


def exercise(parent):
    from cerveau import passive_session as product
    from test_passive_session import SyntheticSource, synthetic_state, Clock
    assert parent.is_absolute()
    parent.mkdir(parents=True, exist_ok=False)
    assert Path(tempfile.gettempdir()) == Path(os.environ['TMPDIR'])
    assert all(Path(os.environ[k]) == Path(tempfile.gettempdir()) for k in ('TEMP','TMP'))
    identity=parent/'SYNTHETIC-identity.txt'
    identity.write_text('SYNTHETIC_IDENTITY',encoding='utf-8')
    commands=[]
    def cli(label, argv, expected=0, guarded=False):
        prefix=([str(ROOT/'tests/helpers/stop_request_guarded.py')] if guarded else ['-m','cerveau.passive_session'])
        args=[sys.executable,'-B',*prefix,*map(str,argv)]
        before=inventory(parent)
        directories={p.relative_to(parent).as_posix() for p in parent.rglob('*') if p.is_dir()}
        result=subprocess.run(args,cwd=ROOT,env=os.environ.copy(),capture_output=True,timeout=30)
        if argv[0]=='--request-stop':
            after=inventory(parent)
            target=Path(argv[argv.index('--stop-file')+1]).relative_to(parent).as_posix()
            assert all(after.get(name)==value for name,value in before.items())
            assert set(after)-set(before) <= {target}
            assert directories=={p.relative_to(parent).as_posix() for p in parent.rglob('*') if p.is_dir()}
        (parent/(label+'.stdout')).write_bytes(result.stdout)
        (parent/(label+'.stderr')).write_bytes(result.stderr)
        commands.append(dict(label=label,argv=args,exit_code=result.returncode))
        assert result.returncode==expected,(label,result.returncode,result.stderr)
        row=json.loads(result.stdout)
        assert row.get('reader_active') is None and row.get('current_permission') is False
        return row
    results=[]
    original=product.run_session
    for name in ('first','new-parent'):
        out,stop=parent/name/'session',parent/(name+'.STOP')
        source=SyntheticSource([synthetic_state(name)])
        clock=Clock()
        def loop(factory,stopped,emit,**kwargs):
            def persist(row):
                emit(row)
                if row['event']=='observation':
                    argv=['--request-stop','--output-dir',out,'--stop-file',stop]
                    # Exactly one new file and no rewritten file, excluding logs
                    # written by this harness after the subprocess returned.
                    before=inventory(out.parent)
                    elsewhere=inventory(parent/name)
                    published=cli(name+'-publish',argv)
                    assert published['state']=='published' and stop.is_file()
                    assert before==inventory(out.parent)==elsewhere
                    stable=inventory(out.parent)
                    stat_before=(stop.read_bytes(),stop.stat().st_mtime_ns)
                    present=cli(name+'-idempotent',argv)
                    assert present['state']=='already_present'
                    assert stable==inventory(out.parent)
                    assert stat_before==(stop.read_bytes(),stop.stat().st_mtime_ns)
                    guarded=cli(name+'-guarded',argv,guarded=True)
                    assert guarded==present
            return original(factory,stopped,persist,clock=clock,sleep=clock.sleep,**kwargs)
        live=['--live','--player-file',str(identity),'--output-dir',str(out),'--stop-file',str(stop)]
        stdout=io.StringIO()
        with patch.object(product,'NativeSource',return_value=source),patch.object(product,'run_session',loop),redirect_stdout(stdout):
            code=product.main(live)
        (parent/(name+'-live.stdout')).write_text(stdout.getvalue(),encoding='utf-8')
        assert code==0 and source.closed and source.calls==1
        summary=json.loads((out/'summary.json').read_text())
        assert summary['reason']=='stop_file' and summary['collection']=='core'
        status=cli(name+'-status',['--status','--output-dir',out])
        assert status['state']=='recorded_stopped'
        assert (out.parent/'passive-session.lock').is_file()
        unopened=parent/(name+'-must-not-open')/'session'
        with patch.object(product,'NativeSource',side_effect=AssertionError('STOP before open')),patch.object(product,'preflight',side_effect=AssertionError('STOP before preflight')),redirect_stdout(io.StringIO()):
            assert product.main(['--live','--player-file',str(identity),'--output-dir',str(unopened),'--stop-file',str(stop)])==0
        assert not unopened.parent.exists()
        results.append(dict(case=name,state='cooperatively_stopped',reader_closed=True,stop_before_open=True,core_default=True))
    legacy=parent/'legacy'
    legacy.mkdir()
    (legacy/'events.jsonl').write_text('UNTRUSTED_JOURNAL_NEVER_READ')
    before=inventory(legacy)
    row=cli('legacy-refusal',['--request-stop','--output-dir',legacy,'--stop-file',parent/'legacy.STOP'],1,guarded=True)
    assert row['state']=='refused' and not (parent/'legacy.STOP').exists()
    assert before==inventory(legacy)
    mismatch=parent/'mismatch.STOP'
    row=cli('mismatch-refusal',['--request-stop','--output-dir',parent/'first'/'session','--stop-file',mismatch],1,guarded=True)
    assert row['state']=='refused' and not mismatch.exists()
    # Distinct new-session control/comparison binding, old claims/STOP preserved.
    tokens=[]
    for name in ('first','new-parent'):
        rows=[json.loads(s) for s in (parent/name/'session/events.jsonl').read_text().splitlines()]
        tokens.append(next(r['comparison']['session_token'] for r in rows if r['event']=='observation'))
    assert tokens[0]!=tokens[1]
    report=dict(basis='SYNTHETIC_NOT_LIVE_NOT_HUD',results=results,commands=commands,
                legacy_refused=True,mismatch_refused=True,new_binding=True,tempfile=tempfile.gettempdir())
    (parent/'commands.json').write_text(json.dumps(commands,indent=2)+'\n',encoding='utf-8')
    (parent/'SYNTHETIC-results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    print(json.dumps(exercise(Path(sys.argv[1]))))
