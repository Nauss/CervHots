"""Contrat HTTP local : aucune clé ni requête fournisseur dans les tests."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from grocoapi import GrocoClient, GrocoError


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/v1/calls/job":
            body, status = {"status": "ok", "result": {"choices": []}}, 200
        elif self.path == "/bad-error":
            body, status = {"error": "service indisponible"}, 502
        elif self.path == "/bad-json":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"not json")
            return
        else:
            body, status = {"ok": True}, 200
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def client(self):
        return GrocoClient(self.url, token="test-not-a-secret", timeout=0.2)

    def test_async_ok_is_terminal_status(self):
        result = self.client().poll_call("job", interval=0.001, timeout=0.05)
        self.assertEqual(result["status"], "ok")

    def test_nonstandard_error_is_still_structured(self):
        with self.assertRaises(GrocoError) as caught:
            self.client()._request("GET", "/bad-error")
        self.assertEqual(caught.exception.status, 502)
        self.assertIn("service indisponible", caught.exception.message)

    def test_invalid_success_json_is_structured(self):
        with self.assertRaises(GrocoError):
            self.client()._request("GET", "/bad-json")


if __name__ == "__main__":
    unittest.main()
