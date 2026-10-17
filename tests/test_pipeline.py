import copy
import unittest
from unittest.mock import patch

from test_cerveau import Gateway

from cerveau.brain import Coach
from cerveau.runner import Pipeline, knowledge_for, tactical_key


class PipelineTests(unittest.TestCase):
    def test_mission_time_including_preparation_is_not_used_as_hud_time_for_map_timings(self):
        state = {"meta": {"map": "Dragon Shire", "t_s": 291.875, "clock_kind": "mission"},
                 "composition": {"allies": [], "enemies": []}}
        with patch("kb.briefing.build", return_value="SYNTHETIC_KB") as build:
            knowledge_for(state)
        build.assert_called_once_with("Dragon Shire", [], [], None)

    def test_small_vital_changes_and_respawn_countdown_do_not_starve_native_coaching(self):
        self.state["heroes"] = [
            {"hero": "ragnaros", "team": 1, "alive": True, "level": 19,
             "health": 2990, "health_max": 3000, "resource": 590, "resource_max": 600},
            {"hero": "jaina", "team": 1, "alive": False, "level": 19, "respawn_s": 40}]

        def synthesize(decision):
            self.state["heroes"][0]["health"] -= 10
            self.state["heroes"][0]["resource"] -= 10
            self.state["heroes"][1]["respawn_s"] -= 8

        self.assertTrue(self.pipeline(synthesize=synthesize).cycle().parler)

    def test_native_critical_health_level_and_respawn_changes_still_cancel_old_advice(self):
        for change in ("health", "level", "alive"):
            with self.subTest(change=change):
                self.setUp()
                self.state["heroes"] = [{"hero": "ragnaros", "team": 1, "alive": True,
                                          "level": 19, "health": 2900, "health_max": 3000}]

                def synthesize(decision, change=change):
                    self.state["heroes"][0][change] = {"health": 300, "level": 20, "alive": False}[change]

                self.assertEqual(self.pipeline(synthesize=synthesize).cycle().raison, "périmé")

    def test_match_change_invalidates_otherwise_identical_observations(self):
        left = {"meta": {"source": "live", "match_id": "SYNTHETIC_A"}, "stats": {}}
        right = copy.deepcopy(left)
        right["meta"]["match_id"] = "SYNTHETIC_B"
        self.assertNotEqual(tactical_key(left), tactical_key(right))

    def setUp(self):
        self.now = 100.0
        self.state = {"meta": {"source": "live"}, "stats": {"deaths_total": 8},
                      "composition": {"allies": [], "enemies": []}}
        self.gateway = Gateway()
        self.coach = Coach(self.gateway)
        self.sent = []

    def pipeline(self, **kwargs):
        return Pipeline(self.coach, lambda: copy.deepcopy(self.state),
                        knowledge=lambda state: "test KB", clock=lambda: self.now,
                        deliver=lambda decision, speech, valid: self.sent.append(decision) or valid(),
                        **kwargs)

    def test_delivery_memory_and_cooldown(self):
        pipeline = self.pipeline()
        self.assertTrue(pipeline.cycle().parler)
        self.assertEqual(len(self.coach.history), 1)
        self.assertEqual(pipeline.cycle().raison, "cooldown")
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(len(self.sent), 1)

    def test_slow_answer_expires_before_synthesis(self):
        def slow(messages, **kwargs):
            self.now += 21
            return Gateway().chat(messages, **kwargs)
        self.gateway.chat = slow
        synthesized = []
        pipeline = self.pipeline(synthesize=lambda d: synthesized.append(d))
        self.assertEqual(pipeline.cycle().raison, "périmé")
        self.assertEqual(synthesized, [])
        self.assertEqual(self.sent, [])
        self.assertEqual(len(self.coach.history), 0)

    def test_changed_state_drops_answer_after_synthesis(self):
        def synthesize(decision):
            self.state["stats"]["deaths_total"] += 1
            return object()
        self.assertEqual(self.pipeline(synthesize=synthesize).cycle().raison, "périmé")
        self.assertEqual(self.sent, [])

    def test_globes_and_wall_clock_do_not_starve_the_coach(self):
        def synthesize(decision):
            self.state["stats"]["globes_total"] = 23
            self.state["meta"]["t"] = "un autre instant"
        self.assertTrue(self.pipeline(synthesize=synthesize).cycle().parler)

    def test_failed_delivery_is_not_remembered(self):
        pipeline = self.pipeline()
        pipeline.deliver = lambda decision, speech, valid: False
        self.assertFalse(pipeline.cycle().parler)
        self.assertEqual(len(self.coach.history), 0)

    def test_knowledge_failure_is_visible_and_does_not_call_gateway(self):
        pipeline = self.pipeline()
        def missing(state):
            raise ValueError("KB manquante")
        pipeline.knowledge = missing
        with self.assertRaisesRegex(ValueError, "KB manquante"):
            pipeline.cycle()
        self.assertEqual(self.gateway.calls, [])


if __name__ == "__main__":
    unittest.main()
