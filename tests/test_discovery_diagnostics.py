"""Hermetic bounded-discovery telemetry tests. No game, GUI or audio."""
from pathlib import Path
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_capture_visibility_pipeline as fixtures
from etudes.rea.scripts import capture_visibility_pipeline as capture
from hotstate.native import NativeUnavailable

ROOT = Path(capture.__file__).resolve().parents[3]


class DiscoveryDiagnosticsTests(unittest.TestCase):
    def test_failed_reads_and_byte_budget_reported(self):
        def query(handle, address, out, size):
            mbi = out._obj
            mbi.BaseAddress = 0x200000; mbi.RegionSize = 8192
            mbi.State = 0x1000; mbi.Type = 0x20000; mbi.Protect = 4
            return size
        backend = SimpleNamespace(k32=SimpleNamespace(VirtualQueryEx=query), handle=1,
                                  read_memory=lambda address, size: None)
        stats = {}
        self.assertEqual(list(capture.bounded_regions(backend, max_bytes=4096, diagnostics=stats)), [])
        self.assertEqual(stats['bytes_requested'], 4096)
        self.assertEqual(stats['bytes_read'], 0)
        self.assertEqual(stats['read_failures'], 1)
        self.assertEqual(stats['query_count'], 1)
        self.assertEqual(stats['stop_reason'], 'byte_limit')

    def test_query_failure_and_wall_limit_reported(self):
        backend = SimpleNamespace(k32=SimpleNamespace(VirtualQueryEx=lambda *args: 0), handle=1)
        stats = {}; list(capture.bounded_regions(backend, diagnostics=stats))
        self.assertEqual(stats['stop_reason'], 'query_failed')
        stats = {}
        with patch.object(capture, 'REAL_CLOCK', side_effect=[100., 101., 101.]):
            self.assertEqual(list(capture.bounded_regions(backend, max_seconds=.5, diagnostics=stats)), [])
        self.assertEqual(stats['stop_reason'], 'time_limit')
        self.assertEqual(stats['query_count'], 0)

    def test_discovery_only_reports_hash_comparisons_not_raw_context(self):
        fixture = fixtures.PipelineCollectorTests(); m, address, size, probe = fixture.fixture()
        a, b, c = fixture.options(m); stats = {}
        with a, b, c:
            result = capture.discover_context(fixtures.FixtureProcess(m), probe,
                regions=[(address, m.read_memory(address, size))], native_profile=m.profile, diagnostics=stats)
        self.assertEqual(stats['stop_reason'], 'selected')
        self.assertEqual(stats['active_match_id'], result['native_match_id'])
        self.assertEqual(stats['matching_contexts'], 1)
        self.assertGreater(stats['anchor_occurrences'], 0)
        for private in ('OWNER_TEST', '_match_seed', '_cache_handles'):
            self.assertNotIn(private, json.dumps(stats))

    def test_stale_context_not_selected_and_failure_diagnosed(self):
        fixture = fixtures.PipelineCollectorTests(); m, address, size, probe = fixture.fixture()
        m.pack(m.app + 0x83f78 + 0x1d428, 'I', m.seed + 1)
        a, b, c = fixture.options(m); stats = {}
        with a, b, c, self.assertRaisesRegex(NativeUnavailable, 'non_trouve'):
            capture.discover_context(fixtures.FixtureProcess(m), probe,
                regions=[(address, m.read_memory(address, size))], native_profile=m.profile, diagnostics=stats)
        self.assertEqual(stats['matching_contexts'], 0)
        self.assertEqual(stats['decoded_contexts'], 1)
        self.assertEqual(stats['stop_reason'], 'no_matching_context')
        self.assertEqual(stats['decoder_attempts'], 1)

    def test_cli_failure_sidecar_saved_and_process_closed(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'out', prefix='synthetic-discovery-') as tmp:
            directory = Path(tmp); player = directory/'player.txt'; player.write_text('OWNER_TEST')
            output = directory/'capture.jsonl'; backend = Mock()
            with patch.object(capture, 'frozen_sources', return_value=('synthetic_sha', {})), \
                 patch.object(capture, 'ContextProbe'), \
                 patch('hotstate.protocols.load_protocol', return_value=SimpleNamespace(__name__='SYNTHETIC_PROTOCOL')), \
                 patch.object(capture, 'ProcessBackend', return_value=backend), \
                 patch.object(capture, 'discover_context', side_effect=NativeUnavailable('SYNTHETIC_BOUNDED_REFUSAL')):
                with self.assertRaisesRegex(NativeUnavailable, 'SYNTHETIC_BOUNDED_REFUSAL'):
                    capture.main(['--live', '--candidate-visibility', '--expected-commit', 'synthetic_sha',
                                  '--player-file', str(player), '--out', str(output), '--discover-context'])
            backend.close.assert_called_once()
            data = json.loads(output.with_suffix('.discovery.json').read_text())
            self.assertEqual(data['status'], 'rejected')
            self.assertEqual(data['rejected'], 'SYNTHETIC_BOUNDED_REFUSAL')
            self.assertEqual(data['commit'], 'synthetic_sha')
            self.assertEqual(output.read_text(), '')

    def test_existing_discovery_report_never_overwritten_or_process_opened(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'out', prefix='synthetic-discovery-') as tmp:
            directory = Path(tmp); player = directory/'player.txt'; player.write_text('OWNER_TEST')
            output = directory/'capture.jsonl'; report = output.with_suffix('.discovery.json')
            report.write_text('preserved evidence')
            with patch.object(capture, 'frozen_sources', return_value=('synthetic_sha', {})), \
                 patch.object(capture, 'ContextProbe'), \
                 patch('hotstate.protocols.load_protocol', return_value=SimpleNamespace(__name__='SYNTHETIC_PROTOCOL')), \
                 patch.object(capture, 'ProcessBackend') as process, self.assertRaises(FileExistsError):
                capture.main(['--live', '--candidate-visibility', '--expected-commit', 'synthetic_sha',
                              '--player-file', str(player), '--out', str(output), '--discover-context'])
            process.assert_not_called()
            self.assertEqual(report.read_text(), 'preserved evidence')


if __name__ == '__main__':
    unittest.main()
