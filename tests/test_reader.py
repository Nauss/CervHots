"""Données synthétiques explicites : aucune lecture du processus de jeu."""
import struct
import unittest

from hotstate.reader import snapshot

NAME = "gt_KillLogOnHeroUnitDies_Func"
MAPPING = {"triggers": {NAME: {"field": "deaths_total", "offset_fiable": -28}}}


class Backend:
    def __init__(self, flag, count, m24, m20):
        self.data = struct.pack("<8I", flag, count, m24, m20, 0, 0, 0, 0) + NAME.encode() + b"\0"

    def regions_bytes(self):
        yield 0x1000, self.data


class ReaderTests(unittest.TestCase):
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
