"""Tests du cerveau ; le transport distant est remplacé par un double explicite."""
import json
import unittest

from cerveau.brain import Coach
from grocoapi import GrocoError


class Gateway:
    def __init__(self, answer=None):
        self.answer = answer or {
            "parler": True, "priorite": 2, "texte": "Regroupez-vous avant le prochain combat.",
            "confiance": 0.9, "style": "calme", "sujet": "regroupement",
        }
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if isinstance(self.answer, Exception):
            raise self.answer
        content = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return {"choices": [{"message": {"content": content}}]}


class BrainTests(unittest.TestCase):
    def test_state_and_knowledge_reach_gateway_and_return_short_decision(self):
        gateway = Gateway()
        coach = Coach(gateway, model="compte/sonnet")
        state = {"meta": {"source": "dump"}, "stats": {"deaths_total": 8}}
        result = coach.decide(state, "CARTE — ne pas engager seul.")
        self.assertTrue(result.parler)
        self.assertEqual(result.texte, "Regroupez-vous avant le prochain combat.")
        messages, options = gateway.calls[0]
        self.assertEqual(options["model"], "compte/sonnet")
        prompt = json.loads(messages[-1]["content"])
        self.assertEqual(prompt["etat"], state)
        self.assertIn("ne pas engager seul", prompt["savoir"])
        self.assertNotIn("session_id", options)

    def test_unsafe_or_malformed_decisions_fail_closed(self):
        base = Gateway().answer
        cases = [
            "pas du JSON", "[]", "null",
            {**base, "parler": "false"}, {**base, "priorite": True},
            {**base, "confiance": float("nan")}, {**base, "confiance": True},
            {**base, "confiance": 0.5}, {**base, "texte": "mot " * 26},
            {**base, "texte": ""}, {**base, "style": "colere"},
            {**base, "sujet": ""}, {**base, "parler": False},
            GrocoError(429, "quota atteint"),
        ]
        for answer in cases:
            with self.subTest(answer=answer):
                result = Coach(Gateway(answer)).decide({})
                self.assertFalse(result.parler)
                self.assertEqual(result.texte, "")

    def test_markdown_json_is_accepted_but_prose_is_not(self):
        raw = json.dumps(Gateway().answer)
        self.assertTrue(Coach(Gateway("```json\n" + raw + "\n```")).decide({}).parler)
        self.assertFalse(Coach(Gateway("Explication : " + raw)).decide({}).parler)

    def test_remember_only_delivered_advice_and_bound_history(self):
        gateway = Gateway()
        coach = Coach(gateway)
        first = coach.decide({})
        self.assertTrue(coach.decide({}).parler)  # généré mais pas diffusé
        coach.remember(first)
        self.assertFalse(coach.decide({}).parler)
        prompt = json.loads(gateway.calls[-1][0][-1]["content"])
        self.assertEqual(prompt["historique"][0]["texte"], first.texte)
        for i in range(12):
            gateway.answer = {**Gateway().answer, "sujet": f"sujet-{i}", "texte": f"Conseil numéro {i}."}
            coach.remember(coach.decide({}))
        self.assertEqual(len(coach.history), 8)


if __name__ == "__main__":
    unittest.main()
