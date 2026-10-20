"""Offline dependency check; no process, credentials, network or audio."""
import unittest
from unittest.mock import patch
from pathlib import Path
import sqlite3
import tempfile
from contextlib import closing

from cerveau.diagnostic_session import preflight


class PreflightTests(unittest.TestCase):
    def test_dependency_check_uses_supported_installed_protocol_not_exact_native_build(self):
        # The live typed context does not decode a replay protocol. The project
        # uses its loader's default for recent builds (documented shim).
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / 'fixture.db'
            with closing(sqlite3.connect(database)) as connection:
                connection.execute('CREATE TABLE maps (slug TEXT)')
            with patch('hotstate.protocols.load_protocol') as load, \
                    patch('kb.briefing.DB', str(database)), \
                    patch('etudes.rea.scripts.capture_talents_pipeline.runtime_dependencies', return_value={}):
                result = preflight()
        self.assertTrue(result['ready'])
        load.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
