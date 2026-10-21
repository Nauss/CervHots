"""HUD/mission separation and freshness; fixtures are explicitly synthetic."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cerveau.state import snapshot
from cerveau.runner import knowledge_for, tactical_key
from hotstate.native import NativeReader
from test_native import NativeMemory


def clock(seconds=12.5, phase="playing"):
    return {"status": "validated", "t_s": seconds, "phase": phase,
            "timer_paused": False, "read_window_s": 0.001, "mission_t_s": 123.5}


def raw_state():
    memory = NativeMemory()
    memory.add_roster()
    result = NativeReader(memory, profile=memory.profile).read_state(
        memory.context, hero_ids=memory.hero_ids)
    result["meta"]["source"] = "live"
    result["meta"]["map"] = "Volskaya Foundry"
    return result


class GameplayContractTests(unittest.TestCase):
    def test_native_reader_adds_independent_clock_without_changing_mission(self):
        memory = NativeMemory()
        memory.add_roster()
        with patch("hotstate.gameplay.GameplayClock.read", return_value=clock()):
            result = NativeReader(memory, profile=memory.profile).read_state(
                memory.context, hero_ids=memory.hero_ids)
        self.assertEqual(result["meta"]["t_s"], 123.5)
        self.assertEqual(result["meta"]["clock_kind"], "mission")
        self.assertEqual(result["meta"]["gameplay_clock"], clock())

    def test_normalizer_keeps_only_typed_validated_clock_no_debug_identifiers(self):
        raw = raw_state()
        for seconds, phase in ((12.5, "playing"), (-28, "preparation"), (0, "playing")):
            raw["meta"]["gameplay_clock"] = dict(clock(seconds, phase), pointer="PRIVATE", name="PRIVATE")
            observed = snapshot(raw)
            self.assertEqual(observed["meta"]["gameplay_clock"], clock(seconds, phase))
            self.assertNotIn("PRIVATE", str(observed))
            self.assertEqual(observed["meta"]["t_s"], 123.5)

    def test_unproven_malformed_stale_or_replay_clock_is_omitted(self):
        for field, value in (("status", "offline_non_atomic"), ("phase", "unknown"),
                             ("t_s", float("nan")), ("t_s", True), ("t_s", 50000),
                             ("timer_paused", 1), ("read_window_s", 1),
                             ("read_window_s", -1), ("mission_t_s", 120),
                             ("mission_t_s", 124)):
            with self.subTest(field=field, value=value):
                raw = raw_state()
                raw["meta"]["gameplay_clock"] = dict(clock(), **{field: value})
                self.assertNotIn("gameplay_clock", snapshot(raw)["meta"])
        raw = {"meta": {"source": "replay", "gameplay_clock": clock()}, "timeline": {}}
        self.assertNotIn("gameplay_clock", snapshot(raw, at=123.5, team=0)["meta"])

    def test_kb_only_uses_validated_gameplay_never_mission_or_untyped_t_s(self):
        for candidate, expected in ((None, None), (clock(12.5), 12),
                                    (clock(-28, "preparation"), None),
                                    (dict(clock(), status="offline_non_atomic"), None),
                                    (dict(clock(), read_window_s=99), None)):
            with self.subTest(candidate=candidate), tempfile.TemporaryDirectory() as directory:
                database = Path(directory) / "synthetic.sqlite"
                database.touch()
                state = {"meta": {"map": "Volskaya Foundry", "t_s": 123.5},
                         "composition": {"allies": [], "enemies": []}}
                if candidate is not None: state["meta"]["gameplay_clock"] = candidate
                with (patch("kb.briefing.DB", database),
                      patch("kb.briefing.build", return_value="SYNTHETIC_KB") as build):
                    knowledge_for(state)
                build.assert_called_once_with("Volskaya Foundry", [], [], expected)

    def test_oversized_json_integers_do_not_crash_the_optional_clock(self):
        for field in ("t_s", "read_window_s", "mission_t_s"):
            raw = raw_state()
            raw["meta"]["gameplay_clock"] = dict(clock(), **{field: 10 ** 400})
            with self.subTest(field=field):
                self.assertNotIn("gameplay_clock", snapshot(raw)["meta"])

    def test_phase_pause_availability_and_large_time_shift_invalidate_advice_not_ticks(self):
        state = {"meta": {"t_s": 123.5, "gameplay_clock": clock(12.5)}, "stats": {}}
        initial = tactical_key(state)
        state["meta"]["gameplay_clock"] = clock(12.5625)
        self.assertEqual(initial, tactical_key(state))
        for candidate in (clock(-1, "preparation"), dict(clock(), timer_paused=True), clock(120), None):
            changed = copy.deepcopy(state)
            changed["meta"]["gameplay_clock"] = candidate
            self.assertNotEqual(initial, tactical_key(changed))

    def test_clock_transition_cancels_an_in_flight_advice(self):
        from cerveau.brain import Coach
        from cerveau.runner import Pipeline
        from test_cerveau import Gateway
        for candidate in (clock(-1, "preparation"), dict(clock(), timer_paused=True), None):
            state = {"meta": {"t_s": 123.5, "gameplay_clock": clock()},
                     "stats": {"deaths_total": 8},
                     "composition": {"allies": [], "enemies": []}}
            delivered = []
            def synthesize(decision):
                state["meta"]["gameplay_clock"] = candidate
            pipeline = Pipeline(Coach(Gateway()), lambda: copy.deepcopy(state),
                                knowledge=lambda s: "SYNTHETIC_KB", synthesize=synthesize,
                                deliver=lambda *args: delivered.append(args), clock=lambda: 100)
            with self.subTest(candidate=candidate):
                self.assertEqual(pipeline.cycle().raison, "périmé")
                self.assertFalse(delivered)


if __name__ == "__main__":
    unittest.main()
