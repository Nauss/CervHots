"""Public targeted STOP contract; all sessions/identities are SYNTHETIC."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cerveau import passive_session as product


class StopRequestTests(unittest.TestCase):
    def test_metadata_directory_and_output_file_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            output,stop=root/'session',root/'STOP'
            output.write_text('UNTOUCHED')
            self.assertEqual(self.invoke(output,stop)[0],1)
            self.assertEqual(output.read_text(),'UNTOUCHED')
            output.unlink()
            output.mkdir()
            (output/'control.json').mkdir()
            self.assertEqual(self.invoke(output,stop)[0],1)
            self.assertFalse(stop.exists())

    def test_windows_unsafe_names_are_rejected_without_read_or_write(self):
        import os
        if os.name!='nt':
            self.skipTest('Windows path vocabulary')
        from cerveau.control_io import absolute
        for value in ('C:/', '//server/share/STOP', '//?/C:/STOP', 'C:/x/STOP:stream', 'C:/x/STOP.', 'C:/x/STOP ', 'C:/x/CON', 'C:/x/NUL.txt', 'C:/x/LPT1', 'C:/x/COM1.txt', 'C:/x/../STOP', 'C:/'+('/x'*65)+'/STOP'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                absolute(value)

    def test_exclusive_create_race_preserves_the_other_regular_file(self):
        from contextlib import contextmanager
        from cerveau import session_control as control
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            output,stop=root/'session',root/'STOP'
            output.mkdir()
            control.record_control(output,stop)
            original=control.file_handle
            @contextmanager
            def race(path, parent_fd, *, create=False):
                if path==stop and create:
                    stop.write_bytes(b'SYNTHETIC_OTHER_WRITER')
                with original(path,parent_fd,create=create) as fd:
                    yield fd
            with patch.object(control,'file_handle',race):
                code,row=self.invoke(output,stop)
            self.assertEqual(code,0)
            self.assertEqual(row['state'],'already_present')
            self.assertEqual(stop.read_bytes(),b'SYNTHETIC_OTHER_WRITER')

    def test_sync_failure_is_uncertain_and_never_removes_the_signal(self):
        from cerveau.session_control import record_control
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            output,stop=root/'session',root/'STOP'
            output.mkdir()
            record_control(output,stop)
            with patch('cerveau.session_control.os.fsync',side_effect=OSError('PRIVATE_SECRET')):
                code,row=self.invoke(output,stop)
            self.assertEqual(code,1)
            self.assertEqual(row['state'],'refused')
            self.assertTrue(stop.is_file())
            self.assertNotIn('SECRET',json.dumps(row))

    def test_public_cli_synthetic_stop_and_restart(self):
        from tests.helpers.stop_request_synthetic import exercise
        with tempfile.TemporaryDirectory() as directory:
            report=exercise(Path(directory).resolve()/'SYNTHETIC')
        self.assertTrue(report['legacy_refused'] and report['mismatch_refused'])
        self.assertEqual([r['case'] for r in report['results']],['first','new-parent'])

    def test_real_parser_mode_and_explicit_default_matrix_is_backend_free(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            argv = ['--request-stop','--output-dir',str(root/'session'),'--stop-file',str(root/'STOP')]
            variants = [[flag] for flag in ('--live','--status','--preflight','--check-ready','--catalog','--verify-catalog','--diagnose','--summarize','--report-html','--help')]
            for option,value in (('--collection','core'),('--max-seconds','300'),('--interval','5'),('--player-file',str(root/'private.txt')),('--journal',str(root/'events.jsonl')),('--report-dir',str(root/'report')),('--sessions-root',str(root/'sessions')),('--visual-reference',str(root/'secret.bmp'))):
                variants.extend(([option,value],[option+'='+value]))
            variants += [['--stop-file',str(root/'STOP')],['--output-dir='+str(root/'session')],['--request-stop']]
            for extra in variants:
                with self.subTest(extra=extra):
                    result = subprocess.run([sys.executable,'-B','-m','cerveau.passive_session',*argv,*extra],capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,2,result.stderr)
                    self.assertEqual(result.stdout,'')
                    self.assertNotIn('Traceback',result.stderr)
                    self.assertNotIn(str(root),result.stderr)
                    self.assertEqual(list(root.iterdir()),[])
            for bad in (['--request-stop'],['--request-stop','--output-dir','relative','--stop-file',str(root/'STOP')]):
                result = subprocess.run([sys.executable,'-B','-m','cerveau.passive_session',*bad],capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,2)
                self.assertEqual(result.stdout,'')

    def test_idempotence_preserves_existing_bytes_mtime_and_other_files(self):
        from cerveau.session_control import record_control
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            output,stop=root/'session',root/'exact.STOP'
            output.mkdir()
            record_control(output,stop)
            for name in ('events.jsonl','status.json','summary.json','private.txt'):
                (output/name).write_text('PRIVATE_DO_NOT_READ')
            stop.write_bytes(b'EXISTING_SIGNAL_DO_NOT_CHANGE')
            before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
            with patch.object(Path,'open',side_effect=AssertionError('no Path.open identity/journal')):
                code,row=self.invoke(output,stop)
            self.assertEqual(code,0)
            self.assertEqual(row['state'],'already_present')
            self.assertNotIn('PRIVATE',json.dumps(row))
            self.assertNotIn(str(root),json.dumps(row))
            self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()})

    def test_missing_parent_and_lexical_escape_do_not_create_any_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            output=root/'session'
            output.mkdir()
            for stop in (root/'absent'/'new.STOP', root/'x'/'..'/'new.STOP', root/('x'*2049)):
                # Forged consistent bytes still cannot bypass path validation.
                (output/'control.json').write_text(json.dumps({'schema':'passive_stop_control_v1','output_dir':str(output),'stop_file':str(stop)})+'\n')
                before=(output/'control.json').read_bytes()
                self.assertEqual(self.invoke(output,stop)[0],1)
                self.assertEqual((output/'control.json').read_bytes(),before)
                self.assertEqual(sorted(p.name for p in root.iterdir()),['session'])

    def test_hardlinked_control_or_target_is_refused_without_write(self):
        import os
        from cerveau.session_control import record_control
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            output,stop=root/'session',root/'exact.STOP'
            output.mkdir()
            record_control(output,stop)
            other=root/'other'
            other.write_bytes(b'UNTOUCHED')
            os.link(other,stop)
            self.assertEqual(self.invoke(output,stop)[0],1)
            self.assertEqual(other.read_bytes(),b'UNTOUCHED')
            stop.unlink()
            os.link(output/'control.json',root/'control-alias')
            self.assertEqual(self.invoke(output,stop)[0],1)
            self.assertFalse(stop.exists())

    def test_io_refusal_does_not_expose_exception_or_claim_publication(self):
        from cerveau.session_control import record_control
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            (root/'session').mkdir()
            record_control(root/'session',root/'STOP')
            with patch('cerveau.session_control.file_handle',side_effect=PermissionError('PRIVATE_SECRET')) as denied:
                code,row=self.invoke(root/'session',root/'STOP')
            denied.assert_called_once()
            self.assertEqual(code,1)
            self.assertEqual(row['state'],'refused')
            self.assertIsNone(row['reader_active'])
            self.assertFalse(row['current_permission'])
            self.assertNotIn('SECRET',json.dumps(row))

    def test_duplicate_control_options_refuse_before_any_filesystem_use(self):
        from contextlib import redirect_stderr
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            out, stop = root/'session', root/'exact.STOP'
            with redirect_stderr(StringIO()), patch('cerveau.session_control.request_stop', side_effect=AssertionError('no IO')):
                code, row = self.invoke(out, stop, '--stop-file', str(stop))
            self.assertEqual(code, 2)
            self.assertIsNone(row)
            self.assertEqual(list(root.iterdir()), [])

    def invoke(self, output, stop, *extra):
        stream = StringIO()
        with redirect_stdout(stream), patch.object(product, 'preflight', side_effect=AssertionError('no preflight')), patch.object(product, 'NativeSource', side_effect=AssertionError('no source')):
            code = product.main(['--request-stop', '--output-dir', str(output), '--stop-file', str(stop), *extra])
        return code, json.loads(stream.getvalue()) if stream.getvalue() else None

    def test_unsafe_targets_are_refused_without_mutating_anything(self):
        from cerveau.session_control import record_control
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output = root/'session'
            output.mkdir()
            stop = root/'exact.STOP'
            record_control(output, stop)
            for target in (stop, output/'events.jsonl', root/'passive-session.lock'):
                if target == stop:
                    target.mkdir()
                with self.subTest(target=target.name):
                    before = {str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
                    code, row = self.invoke(output, target)
                    self.assertEqual(code, 1)
                    self.assertEqual(row['state'], 'refused')
                    self.assertEqual(before, {str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})
            stop.rmdir()
            # An apparently consistent record must not make metadata a STOP.
            control = output/'control.json'
            control.write_text(json.dumps({'schema':'passive_stop_control_v1','output_dir':str(output),'stop_file':str(control)})+'\n')
            self.assertEqual(self.invoke(output, control)[0], 1)

    def test_control_is_regular_bounded_closed_and_exact(self):
        from cerveau.session_control import record_control
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output, stop = root/'session', root/'exact.STOP'
            output.mkdir()
            code, _ = self.invoke(output, stop)
            self.assertEqual(code, 1)  # legacy: never retrofit
            record_control(output, stop)
            control = output/'control.json'
            good = control.read_bytes()
            variants = [b'{', b'null\n', b'[]\n', good.rstrip(), b'x'*16385,
                        b'['*2000+b'0'+b']'*2000+b'\n',
                        good.replace(b'passive_stop_control_v1', b'unknown'),
                        good.replace(b'"schema":', b'"schema":"wrong","schema":')]
            for raw in variants:
                with self.subTest(raw=raw[:30]):
                    control.write_bytes(raw)
                    self.assertEqual(self.invoke(output, stop)[0], 1)
                    self.assertFalse(stop.exists())
                    self.assertEqual(control.read_bytes(), raw)
            control.write_bytes(good)
            self.assertEqual(self.invoke(output, root/'different.STOP')[0], 1)
            self.assertFalse((root/'different.STOP').exists())

    def test_symlink_stop_and_control_are_refused(self):
        from cerveau.session_control import record_control
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output, stop, other = root/'session', root/'exact.STOP', root/'other'
            output.mkdir()
            other.write_text('SYNTHETIC_UNTOUCHED')
            record_control(output, stop)
            try:
                stop.symlink_to(other)
            except OSError as exc:
                if getattr(exc,'winerror',None) == 1314:
                    self.skipTest('Windows symlink privilege 1314; junction covered separately')
                raise
            self.assertEqual(self.invoke(output, stop)[0], 1)
            self.assertEqual(other.read_text(), 'SYNTHETIC_UNTOUCHED')
            stop.unlink()
            control = output/'control.json'
            control.rename(root/'control-original')
            control.symlink_to(root/'control-original')
            self.assertEqual(self.invoke(output, stop)[0], 1)
            self.assertFalse(stop.exists())

    def test_real_junction_in_ancestors_is_refused(self):
        import os
        import subprocess
        from cerveau.session_control import record_control
        if os.name != 'nt':
            self.skipTest('Windows junction')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            actual, link = root/'actual', root/'junction'
            actual.mkdir()
            result = subprocess.run(['cmd','/c','mklink','/J',str(link),str(actual)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            try:
                output, stop = actual/'session', root/'exact.STOP'
                output.mkdir()
                record_control(output,stop)
                # Match the caller spelling in forged metadata too.
                linked_output = link/'session'
                control=output/'control.json'
                control.write_text(json.dumps({'schema':'passive_stop_control_v1','output_dir':str(linked_output),'stop_file':str(stop)})+'\n')
                self.assertEqual(self.invoke(linked_output,stop)[0],1)
                self.assertFalse(stop.exists())
            finally:
                link.rmdir()

    def test_new_session_registers_exact_control_and_cooperative_request(self):
        from test_passive_session import SyntheticSource, synthetic_state, Clock
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            player = root / 'private.txt'
            player.write_text('SYNTHETIC_IDENTITY')
            output, stop = root/'new-parent'/'session', root/'exact.STOP'
            source = SyntheticSource([synthetic_state('a')])
            clock = Clock()
            original = product.run_session
            replies = []
            def run(factory, stopped, emit, **kwargs):
                def persist(row):
                    emit(row)
                    if row['event'] == 'observation':
                        for expected in ('published', 'already_present'):
                            stream = StringIO()
                            with redirect_stdout(stream):
                                code = product.main(['--request-stop', '--output-dir', str(output), '--stop-file', str(stop)])
                            self.assertEqual(code, 0)
                            reply = json.loads(stream.getvalue())
                            self.assertEqual(reply['state'], expected)
                            self.assertIsNone(reply['reader_active'])
                            self.assertFalse(reply['current_permission'])
                            replies.append(reply)
                return original(factory, stopped, persist, clock=clock, sleep=clock.sleep, **kwargs)
            with patch.object(product, 'NativeSource', return_value=source), patch.object(product, 'run_session', side_effect=run), redirect_stdout(StringIO()):
                self.assertEqual(product.main(['--live','--player-file',str(player),'--output-dir',str(output),'--stop-file',str(stop)]), 0)
            self.assertEqual(len(replies), 2)
            control = json.loads((output/'control.json').read_text())
            self.assertEqual(control, {'schema':'passive_stop_control_v1','output_dir':str(output),'stop_file':str(stop)})
            self.assertEqual(json.loads((output/'summary.json').read_text())['reason'], 'stop_file')
            self.assertTrue(source.closed)
            self.assertEqual(source.calls, 1)
            self.assertTrue((output.parent/'passive-session.lock').is_file())


if __name__ == '__main__':
    unittest.main()
