"""Synthetic tracker reference only: never inject future facts into observations."""
import copy
import unittest

from etudes.rea.scripts import validate_native


def event(kind, loop, index=4, generation=2, owner=1):
    return {"_event": "NNet.Replay.Tracker." + kind, "_gameloop": loop,
            "m_unitTagIndex": index, "m_unitTagRecycle": generation,
            "m_controlPlayerId": owner, "m_unitTypeName": b"HeroSynthetic"}


class RespawnReferenceTests(unittest.TestCase):
    def setUp(self):
        self.observed = {"meta": {"t_s": 10.25}, "heroes": [
            {"id": 0, "alive": False, "respawn_s": 2.0625}]}
        self.tracker = [event("SUnitBornEvent", 0), event("SUnitDiedEvent", 100),
                        event("SUnitRevivedEvent", 197), event("SUnitDiedEvent", 220),
                        event("SUnitRevivedEvent", 300)]

    def compare(self):
        return validate_native.validate_respawn_timers(self.observed, iter(self.tracker))[0]

    def test_exact_next_revive_not_rounded_or_later_revive_and_no_mutation(self):
        before = copy.deepcopy(self.observed)
        row = self.compare()
        self.assertEqual(row["expected_respawn_s"], 197 / 16 - 10.25)
        self.assertIs(row["respawn_matches"], True)
        self.assertEqual(before, self.observed)
        self.observed["heroes"][0]["respawn_s"] = 2.06
        self.assertIs(self.compare()["respawn_matches"], False)

    def test_other_unit_and_generation_are_not_matching_revivals(self):
        self.tracker.insert(2, event("SUnitRevivedEvent", 180, generation=3))
        self.tracker.insert(3, event("SUnitRevivedEvent", 181, index=5))
        self.assertIs(self.compare()["respawn_matches"], True)

    def test_absent_timer_or_truncated_tracker_stays_unknown(self):
        del self.observed["heroes"][0]["respawn_s"]
        self.assertIsNone(self.compare()["respawn_matches"])
        self.assertNotIn("respawn_s", self.observed["heroes"][0])
        self.observed["heroes"][0]["respawn_s"] = 2.0625
        self.tracker = self.tracker[:2]
        row = self.compare()
        self.assertIsNone(row["expected_respawn_s"])
        self.assertIsNone(row["respawn_matches"])

    def test_reused_index_and_new_owner_do_not_validate_old_timer(self):
        self.tracker.insert(2, event("SUnitBornEvent", 175, generation=3, owner=2))
        self.assertIsNone(self.compare()["expected_respawn_s"])

    def test_alive_at_clock_or_birth_in_future_cannot_prove_timer(self):
        self.tracker = [event("SUnitBornEvent", 0), event("SUnitDiedEvent", 180),
                        event("SUnitRevivedEvent", 197)]
        self.assertIsNone(self.compare()["expected_respawn_s"])
        self.tracker[0]["_gameloop"] = 170
        self.assertIsNone(self.compare()["expected_respawn_s"])

    def test_at_revive_boundary_not_the_next_death_cycle(self):
        self.observed["meta"]["t_s"] = 197 / 16
        self.assertIsNone(self.compare()["expected_respawn_s"])

    def test_missing_timers_have_unknown_aggregate_not_vacuous_success(self):
        del self.observed["heroes"][0]["respawn_s"]
        rows = validate_native.validate_respawn_timers(self.observed, self.tracker)
        self.assertIsNone(validate_native.respawn_timer_status(rows))
        self.assertIsNone(validate_native.respawn_timer_status([]))

    def test_observed_timer_without_reference_fails_aggregate(self):
        self.tracker = self.tracker[:2]
        rows = validate_native.validate_respawn_timers(self.observed, self.tracker)
        self.assertIs(validate_native.respawn_timer_status(rows), False)

    def test_owner_changes_are_applied_at_capture_with_generation_guard(self):
        change = event("SUnitOwnerChangeEvent", 120)
        change["m_controlPlayerId"] = 2
        self.tracker.insert(2, change)
        self.assertIsNone(self.compare()["expected_respawn_s"])
        change["m_unitTagRecycle"] = 3
        self.assertIs(self.compare()["respawn_matches"], True)


if __name__ == "__main__":
    unittest.main()
