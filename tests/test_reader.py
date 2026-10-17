"""Données synthétiques explicites : aucune lecture du processus de jeu."""
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from hotstate.reader import DumpBackend, ProcessBackend, snapshot

NAME = "gt_KillLogOnHeroUnitDies_Func"
MAPPING = {"triggers": {NAME: {"field": "deaths_total", "offset_fiable": -28}}}


class Backend:
    def __init__(self, flag, count, m24, m20):
        self.data = struct.pack("<8I", flag, count, m24, m20, 0, 0, 0, 0) + NAME.encode() + b"\0"

    def regions_bytes(self):
        yield 0x1000, self.data


class ReaderTests(unittest.TestCase):
    def test_unproven_trigger_counts_are_debug_records_not_objective_facts(self):
        mapping = {"triggers": {NAME: {"field": "alterac_capture_point", "offset_fiable": -28}}}
        observed = snapshot(Backend(1, 8, 8, 0), mapping, debug=True)
        self.assertEqual(observed["stats"], {})
        self.assertTrue(observed["triggers_bruts"][NAME])

    def test_native_signature_failure_keeps_only_previous_validated_fields(self):
        from hotstate.native import NativeUnavailable

        backend, context = Backend(1, 8, 8, 0), Mock()
        backend.module_base = 0x9000
        context.finish.return_value = {"local_player": {"id": 5, "team": 1, "hero": "Ragnaros"},
                                       "players": [], "composition_complete": False}
        with patch("hotstate.native.NativeReader", side_effect=NativeUnavailable("signature_native_invalide")):
            observed = snapshot(backend, MAPPING, context=context)
        self.assertEqual(observed["stats"], {"deaths_total": 8})
        self.assertEqual(observed["meta"]["native_status"], "signature_native_invalide")
        self.assertNotIn("heroes", observed)
        self.assertNotIn("t_s", observed["meta"])

    def test_process_random_access_uses_the_existing_read_only_reader(self):
        backend = object.__new__(ProcessBackend)
        backend._read = Mock(return_value=b"native")
        self.assertEqual(backend.read_memory(0x7000, 6), b"native")
        backend._read.assert_called_once_with(0x7000, 6)

    def test_dump_random_access_reads_image_and_contiguous_regions_but_not_holes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            heap, manifest, image = root / "heap.bin", root / "heap.json", root / "image.bin"
            heap.write_bytes(b"abcdefgh")
            manifest.write_text(json.dumps({"regions": [
                {"addr": 0x1000, "size": 4, "offset": 0},
                {"addr": 0x1004, "size": 4, "offset": 4}]}))
            image.write_bytes(b"native-module")
            backend = DumpBackend(heap, manifest, image=image, module_base=0x9000)
            try:
                self.assertEqual(backend.read_memory(0x1002, 4), b"cdef")
                self.assertEqual(backend.read_memory(0x9000, 6), b"native")
                self.assertIsNone(backend.read_memory(0x1007, 2))
                self.assertIsNone(backend.read_memory(0x8000, 4))
            finally:
                backend.close()

    def test_native_enrichment_is_automatic_and_preserves_validated_counters(self):
        backend, context = Backend(1, 8, 8, 0), Mock()
        backend.module_base = 0x9000
        context.finish.return_value = {
            "meta": {"map": "Dragon Shire"},
            "local_player": {"id": 5, "team": 1, "hero": "Ragnaros"}, "players": []}
        reader = Mock()
        reader.read_state.return_value = {"meta": {"t_s": 123.5, "native_status": "valide"},
                                          "heroes": [{"hero": "ragnaros", "level": 19}]}
        with patch("hotstate.native.NativeReader", return_value=reader) as factory:
            observed = snapshot(backend, MAPPING, context=context)
        factory.assert_called_once_with(backend)
        self.assertEqual(observed["stats"], {"deaths_total": 8})
        self.assertEqual(observed["meta"]["t_s"], 123.5)
        self.assertEqual(observed["heroes"][0]["level"], 19)

    def test_context_uses_the_same_region_scan_and_does_not_replace_counters(self):
        backend = Backend(1, 8, 8, 0)
        context = Mock()
        context.finish.return_value = {"meta": {"map": "Dragon Shire"},
                                       "local_player": {"id": 5, "team": 1, "hero": "Ragnaros"},
                                       "players": [], "composition_complete": False}
        import inspect
        self.assertIn("context", inspect.signature(snapshot).parameters)
        result = snapshot(backend, MAPPING, context=context)
        context.begin.assert_called_once()
        context.feed.assert_called_once_with(0x1000, backend.data)
        self.assertEqual(result["stats"], {"deaths_total": 8})
        self.assertEqual(result["meta"]["map"], "Dragon Shire")
        self.assertEqual(result["meta"]["source"], "dump")
        self.assertEqual(result["local_player"]["team"], 1)

    def test_template_or_inconsistent_records_never_become_game_observations(self):
        for fields in ((0, 32755, 32755, 0), (1, 32755, 0, 0)):
            with self.subTest(fields=fields):
                self.assertEqual(snapshot(Backend(*fields), MAPPING)["stats"], {})

    def test_both_validated_live_record_layouts_are_accepted(self):
        for fields in ((1, 8, 8, 0), (1, 8, 0, 8)):
            with self.subTest(fields=fields):
                self.assertEqual(snapshot(Backend(*fields), MAPPING)["stats"], {"deaths_total": 8})


if __name__ == "__main__":
    unittest.main()
