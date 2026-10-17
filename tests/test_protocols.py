"""Chargement des modules officiels, sans le module imp retiré de Python 3.12."""
import importlib.util
import tempfile
import unittest
from pathlib import Path


class ProtocolLoadingTests(unittest.TestCase):
    def test_numeric_latest_and_explicit_build_without_legacy_imp(self):
        self.assertIsNotNone(importlib.util.find_spec("hotstate.protocols"))
        from hotstate.protocols import load_protocol

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for build in (7, 12):
                (folder / f"protocol{build:05d}.py").write_text(
                    f"SYNTHETIC_TEST_BUILD = {build}\n", encoding="utf-8")
            self.assertEqual(load_protocol(directory=folder).SYNTHETIC_TEST_BUILD, 12)
            self.assertEqual(load_protocol(7, directory=folder).SYNTHETIC_TEST_BUILD, 7)
            with self.assertRaises(ModuleNotFoundError):
                load_protocol(8, directory=folder)
