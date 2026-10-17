"""Mode diagnostic : fixtures synthétiques, sans jeu, API réelle ni son."""
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class DiagnosticTests(unittest.TestCase):
    def test_observed_counters_reach_gateway_and_return_a_factual_phrase(self):
        self.assertTrue(Path("cerveau/diagnostic.py").is_file(),
                        "Le mode diagnostic live n'existe pas encore")
        from cerveau.diagnostic import diagnose

        events = []
        calls = []

        class Gateway:
            def chat(self, messages, **options):
                calls.append((messages, options))
                data = json.loads(messages[1]["content"])
                return {"choices": [{"message": {"content": json.dumps(
                    {"texte": data["phrases_autorisees"][0]}, ensure_ascii=False)}}]}

        raw = {"meta": {"source": "live", "t": "HORLOGE_SYSTEME_TEST"},
               "stats": {"deaths_total": 3, "respawns_total": 2, "globes_total": 41,
                         "game_over": 1},
               "triggers_bruts": {"ADRESSE_PRIVEE_TEST": 123}}
        text = diagnose(Gateway(), raw, lambda event, data: events.append((event, data)),
                        model="compte-test/modele-test")
        self.assertIn("3 morts", text)
        self.assertIn("2 réapparitions", text)
        self.assertIn("41 globes", text)
        self.assertEqual(len(calls), 1)
        request = json.loads(calls[0][0][1]["content"])
        self.assertEqual(request["etat"]["stats"],
                         {"deaths_total": 3, "respawns_total": 2, "globes_total": 41})
        encoded = json.dumps(calls, ensure_ascii=False)
        for secret in ("ADRESSE_PRIVEE_TEST", "HORLOGE_SYSTEME_TEST", "game_over"):
            self.assertNotIn(secret, encoded)
        self.assertEqual([event for event, _ in events],
                         ["observation", "api_requete", "api_reponse", "phrase_validee"])

    def test_expired_api_response_never_synthesizes(self):
        from cerveau import diagnostic
        self.assertTrue(callable(getattr(diagnostic, "run_session", None)),
                        "La session live bornée reste à implémenter")
        now = [0.0]
        synthesized = []
        events = []

        class Gateway:
            def chat(self, messages, **options):
                now[0] += 21
                data = json.loads(messages[1]["content"])
                return {"choices": [{"message": {"content": json.dumps(
                    {"texte": data["phrases_autorisees"][0]})}}]}

        diagnostic.run_session(
            lambda: {"stats": {"deaths_total": 4}}, Gateway(),
            lambda event, data: events.append((event, data)),
            synthesize=lambda text: synthesized.append(text),
            cycles=1, clock=lambda: now[0],
        )
        self.assertEqual(synthesized, [])
        self.assertIn("observation_perimee", [event for event, _ in events])

    def test_cli_requires_live_opt_in_before_importing_process_or_audio(self):
        result = subprocess.run([sys.executable, "-m", "cerveau.diagnostic", "--help"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--live", result.stdout)
        self.assertIn("--cycles", result.stdout)
        self.assertIn("--stop-file", result.stdout)
        self.assertIn("--player", result.stdout)
        result = subprocess.run([sys.executable, "-m", "cerveau.diagnostic"],
                                capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)

    def test_unknown_counters_and_invented_advice_never_reach_audio(self):
        from cerveau.diagnostic import run_session

        for raw, response in (
            ({"stats": {"deaths_total": True, "globes_total": -1}}, "{}"),
            ({"stats": {"deaths_total": 2}}, '{"texte":"Attaquez le boss, vous êtes cinq."}'),
        ):
            with self.subTest(raw=raw):
                gateway = Mock()
                gateway.chat.return_value = {"choices": [{"message": {"content": response}}]}
                synthesize = Mock()
                events = []
                run_session(lambda raw=raw: raw, gateway,
                            lambda event, data, events=events: events.append(event),
                            synthesize=synthesize, cycles=1)
                synthesize.assert_not_called()
                self.assertIn("cycle_rejete", events)
                if raw["stats"].get("deaths_total") != 2:
                    gateway.chat.assert_not_called()

    def test_stop_after_api_prevents_audio_and_further_cycles(self):
        from cerveau.diagnostic import run_session

        stopped = [False]
        calls = []

        class Gateway:
            def chat(self, messages, **options):
                calls.append(messages)
                stopped[0] = True
                data = json.loads(messages[1]["content"])
                return {"choices": [{"message": {"content": json.dumps(
                    {"texte": data["phrases_autorisees"][0]})}}]}

        synthesize = Mock()
        run_session(lambda: {"stats": {"globes_total": 10}}, Gateway(),
                    lambda event, data: None, synthesize=synthesize,
                    stop_requested=lambda: stopped[0], cycles=6)
        synthesize.assert_not_called()
        self.assertEqual(len(calls), 1)

    def test_session_sends_only_after_synthesis_and_stops_at_cycle_limit(self):
        from cerveau.diagnostic import run_session

        now = [0.0]
        stages = []

        class Gateway:
            def chat(self, messages, **options):
                data = json.loads(messages[1]["content"])
                return {"choices": [{"message": {"content": json.dumps(
                    {"texte": data["phrases_autorisees"][0]})}}]}

        def synthesize(text):
            stages.append("tts")
            return SimpleNamespace(duration_s=2)

        def deliver(speech, fresh):
            self.assertTrue(fresh())
            stages.append("mumble")
            return True

        def wait(seconds):
            now[0] += seconds

        events = []
        run_session(lambda: {"stats": {"deaths_total": 2}}, Gateway(),
                    lambda event, data: events.append(event), synthesize=synthesize,
                    deliver=deliver, cycles=2, interval=30, clock=lambda: now[0], wait=wait)
        self.assertEqual(stages, ["tts", "mumble", "tts", "mumble"])
        self.assertEqual(events.count("mumble_envoye"), 2)
        self.assertEqual(events.count("session_fin"), 1)
        self.assertEqual(now[0], 30)

    def test_cli_journals_a_complete_silent_cycle_and_closes_process_handle(self):
        from cerveau import diagnostic

        class Gateway:
            def chat(self, messages, **options):
                data = json.loads(messages[1]["content"])
                return {"choices": [{"message": {"content": json.dumps(
                    {"texte": data["phrases_autorisees"][0]})}}]}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "hotstate").mkdir()
            (root / "hotstate/triggers_map.json").write_text("{}", encoding="utf-8")
            backend = SimpleNamespace(pid=123, handle=456,
                                      k32=SimpleNamespace(CloseHandle=Mock(return_value=1)))
            with (patch.object(diagnostic, "__file__", str(root / "cerveau/diagnostic.py")),
                  patch("hotstate.reader.ProcessBackend", return_value=backend),
                  patch("hotstate.reader.snapshot", return_value={"stats": {"globes_total": 4}}),
                  patch("grocoapi.GrocoClient", return_value=Gateway()),
                  patch("grocoapi.client._load_env_file", return_value={}),
                  redirect_stdout(StringIO())):
                self.assertEqual(diagnostic.main(["--live", "--cycles", "1"]), 0)
            current = json.loads((root / "out/test-live/current.json").read_text(encoding="utf-8"))
            self.assertEqual(current["status"], "terminee")
            self.assertEqual(current["etapes"]["api_reponse"], 1)
            self.assertEqual(current["etapes"]["diagnostic_sans_audio"], 1)
            self.assertNotIn("mumble_envoye", current["etapes"])
            self.assertFalse((root / "out/test-live/RUNNING").exists())
            backend.k32.CloseHandle.assert_called_once_with(456)


if __name__ == "__main__":
    unittest.main()
