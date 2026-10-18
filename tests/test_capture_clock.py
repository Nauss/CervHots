"""Exercise the targeted recorder without opening any process or GUI."""
import contextlib
import io

import unittest
from unittest.mock import patch

from etudes.rea.scripts.capture_clock import RecordingBackend, capture_one, main
from hotstate.gameplay import GameplayClock
from hotstate.native import NativeReader
from test_gameplay_clock import ClockMemory


class TargetedClockCaptureTests(unittest.TestCase):
    def test_packet_records_only_requested_reads_and_production_result(self):
        memory = ClockMemory()
        recording = RecordingBackend(memory)
        reader = GameplayClock(NativeReader(recording, profile=memory.profile),
                               profile=memory.clock_profile)
        packet = capture_one(reader)
        self.assertEqual(packet["clock"]["t_s"], 12.5)
        self.assertEqual(packet["clock"]["status"], "validated")
        self.assertLess(packet["monotonic_after"] - packet["monotonic_before"], 0.125)
        self.assertGreater(len(packet["reads"]), 20)
        for read in packet["reads"]:
            self.assertEqual(bytes.fromhex(read["hex"]), memory.read_memory(read["address"], read["size"]))
            self.assertLessEqual(read["before"], read["after"])
        self.assertFalse(recording.recorded_non_atomic)
        self.assertNotIn("image", packet)

    def test_failure_is_recorded_without_default_time(self):
        memory = ClockMemory()
        recording = RecordingBackend(memory)
        reader = GameplayClock(NativeReader(recording, profile=memory.profile),
                               profile=memory.clock_profile)
        memory.pack(memory.module_base + 0x3B8C5C8, "Q", 0)
        packet = capture_one(reader)
        self.assertIn("rejected", packet)
        self.assertNotIn("clock", packet)
        self.assertTrue(packet["reads"])

    def test_cli_refuses_implicit_access_bad_bounds_and_nonprivate_output(self):
        for args in ([], ["--live", "--out", "bad.jsonl"],
                     ["--live", "--out", "out/test.jsonl", "--duration", "121"],
                     ["--live", "--out", "out/test.jsonl", "--interval", "0"]):
            with (self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()),
                  patch("etudes.rea.scripts.capture_clock.ProcessBackend") as backend):
                with self.assertRaises(SystemExit): main(args)
                backend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
