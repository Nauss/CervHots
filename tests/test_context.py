"""Contexte mémoire : fixtures synthétiques, jamais de lecture du jeu."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


def synthetic_initdata(seed=1234):
    return {"m_syncLobbyState": {
        "m_userInitialData": [{"m_name": b"OWNER_TEST"}],
        "m_gameDescription": {"m_cacheHandles": [b"s2ma\x00\x00EU" + bytes(range(32))]},
        "m_lobbyState": {"m_randomSeed": seed, "m_slots": [
            {"m_workingSetSlotId": i, "m_teamId": i // 5, "m_observe": 0,
             "m_control": 2 if i == 5 else 3, "m_userId": 0 if i == 5 else None,
             "m_hero": b"Ragnaros" if i == 5 else b""} for i in range(10)]}}}


class ContextTests(unittest.TestCase):
    def test_map_lookup_skips_invalid_cache_entries_and_resolves_observed_volskaya_id(self):
        from hotstate.context import map_from_cache

        good, bad = b"s2ma\0\0EU" + bytes([1]) * 32, b"s2ma\0\0EU" + bytes([2]) * 32
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for handle in (good, bad):
                digest = handle[8:].hex()
                path = root / digest[:2] / digest[2:4] / (digest + ".s2ma")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"SYNTHETIC_CACHE_FIXTURE")
            archive = Mock()
            archive.read_file.return_value = b'const string libCore_gv_mAPMapStringID = "Volskaya";'
            fake = SimpleNamespace(MPQArchive=Mock(side_effect=[ValueError("Invalid file header"), archive]))
            with patch.dict(sys.modules, {"mpyq": fake}):
                observed = map_from_cache([good, bad], cache_root=root)
        self.assertEqual(observed, {"map_id": "Volskaya", "map": "Volskaya Foundry"})

    def test_a_temporarily_missing_map_cache_is_retried_not_cached_forever(self):
        from hotstate.context import ContextProbe

        resolver = Mock(side_effect=[{}, {"map": "Dragon Shire"}])
        probe = ContextProbe("OWNER_TEST", decoder=lambda payload: synthetic_initdata(),
                             map_resolver=resolver)
        probe.feed(0x1000, b"\x10\x0aOWNER_TEST\0SYNTHETIC_BUFFER")
        self.assertNotIn("map", probe.finish()["meta"])
        self.assertEqual(probe.finish()["meta"]["map"], "Dragon Shire")

    def test_invalid_identity_or_team_never_becomes_context(self):
        from hotstate.context import context_from_initdata

        for kind in ("seed_bool", "team_bool", "duplicate_slot", "missing_owner"):
            with self.subTest(kind=kind):
                data = synthetic_initdata()
                lobby = data["m_syncLobbyState"]["m_lobbyState"]
                if kind == "seed_bool":
                    lobby["m_randomSeed"] = True
                elif kind == "team_bool":
                    lobby["m_slots"][0]["m_teamId"] = False
                elif kind == "duplicate_slot":
                    lobby["m_slots"][0]["m_workingSetSlotId"] = 1
                else:
                    data["m_syncLobbyState"]["m_userInitialData"][0]["m_name"] = b"OTHER_TEST"
                with self.assertRaises(ValueError):
                    context_from_initdata(data, "OWNER_TEST")

    def test_plain_text_names_do_not_exhaust_probe_and_inactive_lobby_blocks_output(self):
        from hotstate.context import ContextProbe

        probe = ContextProbe("OWNER_TEST", decoder=lambda payload: synthetic_initdata(),
                             map_resolver=lambda handles: {})
        probe.feed(0x1000, b"TEXT_OWNER_TEST " * 200 + b"\x10\x0aOWNER_TEST\x00SYNTHETIC_BUFFER")
        self.assertEqual(probe.attempts, 1)
        self.assertEqual(probe.finish()["local_player"]["team"], 1)
        probe.active_lobby = lambda: False
        self.assertEqual(probe.finish(), {})
        self.assertEqual(probe.reason, "aucun_lobby_actif")

    def test_context_has_local_team_without_turning_ai_lobby_levels_into_game_levels(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec("hotstate.context"))
        from hotstate.context import context_from_initdata

        users = [{"m_name": b"OWNER_TEST"}]
        slots = [{"m_workingSetSlotId": i, "m_control": 2 if i == 5 else 3,
                  "m_observe": 0, "m_teamId": i // 5,
                  "m_userId": 0 if i == 5 else None,
                  "m_hero": b"Ragnaros" if i == 5 else b"",
                  "m_toonHandle": b"PRIVATE_ACCOUNT_TEST"} for i in range(10)]
        data = {"m_syncLobbyState": {"m_userInitialData": users,
                "m_gameDescription": {"m_cacheHandles": [b"s2ma\x00\x00EU" + bytes(range(32))]},
                "m_lobbyState": {"m_slots": slots, "m_randomSeed": 1234,
                                 "m_gameDuration": 0}}}
        result = context_from_initdata(data, "OWNER_TEST")
        self.assertEqual(result["local_player"], {"id": 5, "team": 1, "hero": "Ragnaros"})
        self.assertEqual(len(result["players"]), 10)
        self.assertFalse(result["composition_complete"])
        self.assertNotIn("PRIVATE_ACCOUNT_TEST", str(result))
        self.assertNotIn("OWNER_TEST", str(result))
        self.assertNotIn("level", str(result))
        self.assertNotIn("t_s", str(result))

    def test_region_probe_rejects_ambiguous_matches_and_never_reuses_previous_match(self):
        from hotstate import context
        self.assertTrue(callable(getattr(context, "ContextProbe", None)))
        probe = context.ContextProbe(
            "OWNER_TEST", decoder=lambda payload: synthetic_initdata(2 if b"SECOND" in payload else 1),
            map_resolver=lambda handles: {"map": "Dragon Shire", "map_id": "DragonShire"})
        probe.begin()
        probe.feed(0x1000, b"PREFIX\x10\x0aOWNER_TEST\x00SYNTHETIC_FIRST")
        first = probe.finish()
        self.assertEqual(first["local_player"]["team"], 1)
        self.assertEqual(first["meta"]["map"], "Dragon Shire")
        self.assertFalse(any(k.startswith("_") for k in first))
        probe.feed(0x2000, b"PREFIX\x10\x0aOWNER_TEST\x00SYNTHETIC_SECOND")
        self.assertEqual(probe.finish(), {})
        probe.begin()
        probe.feed(0x3000, b"SYNTHETIC_NO_CONTEXT_HERE")
        self.assertEqual(probe.finish(), {})
