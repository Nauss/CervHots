import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from cerveau.__main__ import main, make_source


class CliTests(unittest.TestCase):
    def test_reader_help_exposes_native_capture_options_without_opening_the_game(self):
        result = subprocess.run([sys.executable, "-m", "hotstate.reader", "--help"],
                                check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--image", result.stdout)
        self.assertIn("--player", result.stdout)

    def test_file_source_age_policy(self):
        for source in (None, "memory", "current", "unknown", "live", "dump", "replay"):
            for watch in (False, True):
                for stale in (False, True):
                    with (self.subTest(source=source, watch=watch, stale=stale),
                          tempfile.TemporaryDirectory() as directory):
                        path = Path(directory) / "state.json"
                        raw = {"deaths_total": 2}
                        if source is not None:
                            raw["meta"] = {"source": source}
                        if source == "replay":
                            raw["timeline"] = {"hero_events": []}  # observed empty, not unknown
                        path.write_text(json.dumps(raw), encoding="utf-8")
                        if stale:
                            os.utime(path, (1, 1))
                        args = SimpleNamespace(
                            state=path, at=0 if source == "replay" else None,
                            team=0, map=None, allies=None, enemies=None,
                            max_age=60, watch=watch,
                        )
                        read_state, backend = make_source(args)
                        self.assertIsNone(backend)
                        exempt = source == "replay" or (source == "dump" and not watch)
                        if stale and not exempt:
                            with self.assertRaises(ValueError):
                                read_state()
                        else:
                            state = read_state()
                            self.assertEqual(state["stats"]["deaths_total"],
                                             0 if source == "replay" else 2)

    def test_help_works_without_audio_dependencies(self):
        result = subprocess.run([sys.executable, "-m", "cerveau", "--help"],
                                check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--mumble", result.stdout)
        self.assertIn("--state", result.stdout)
        self.assertIn("--player", result.stdout)
        self.assertIn("--image", result.stdout)

    def test_no_source_or_negative_timing_is_rejected(self):
        for argv in ([], ["--state", "x.json", "--interval", "-1"],
                     ["--state", "x.json", "--timeout", "nan"],
                     ["--dump", "x.bin", "x.json", "--watch"],
                     ["--state", "x.json", "--image", "module.bin"]):
            with (self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()),
                  self.assertRaises(SystemExit)):
                main(argv)

    def test_missing_source_is_an_error_not_silent_success(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--state", "missing-cervhots-state.json"]), 1)

    def test_dry_run_does_not_import_voice_or_process_reader(self):
        code = "import cerveau.__main__, sys, json; print(json.dumps(list(sys.modules)))"
        result = subprocess.run([sys.executable, "-c", code], check=False,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        modules = json.loads(result.stdout)
        for module in ("tts", "mumblebot", "hotstate.reader"):
            self.assertNotIn(module, modules)

    def test_malformed_state_is_rejected_without_traceback(self):
        for raw in ([], {"meta": None}, {"players": [None]}, {"stats": []}):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "bad.json"
                path.write_text(json.dumps(raw), encoding="utf-8")
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["--state", str(path)]), 1)


if __name__ == "__main__":
    unittest.main()
