"""Observed identity is not static KB coverage; never invent hero knowledge."""
from contextlib import closing
import copy
import gc
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cerveau.runner import knowledge_for


class KnowledgeCoverageTests(unittest.TestCase):
    def test_known_native_hero_missing_from_kb_keeps_map_facts_and_explicit_unknown(self):
        state = {'meta': {'source': 'live', 'native_status': 'valide', 'map': 'Cursed Hollow',
                          't_s': 123.5},
                 'composition': {'allies': ['jaina'], 'enemies': ['xalatath']}}
        before = copy.deepcopy(state)
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / 'kb.db'
            with closing(sqlite3.connect(database)) as connection:
                connection.execute('CREATE TABLE maps (slug TEXT, name TEXT, aliases_fr TEXT)')
                connection.execute('CREATE TABLE heroes (slug TEXT, name TEXT)')
                connection.execute("INSERT INTO maps VALUES ('cursed-hollow', 'Cursed Hollow', '[]')")
                connection.execute("INSERT INTO heroes VALUES ('jaina', 'Jaina')")
                connection.commit()
            failure = result = None
            with patch('kb.briefing.DB', str(database)), patch('kb.briefing.NOTES', str(Path(tmp) / 'no-notes')):
                try:
                    result = knowledge_for(state)
                except ValueError as exc:
                    failure = str(exc)
            gc.collect()  # legacy KB error path may retain its connection until GC
            self.assertIsNone(failure, failure)
            self.assertIn('CARTE', result)
            self.assertIn('Savoir héros indisponible : xalatath', result)
            self.assertNotIn('de jeu', result)  # mission time is not HUD time
            self.assertEqual(state, before)


if __name__ == '__main__':
    unittest.main()
