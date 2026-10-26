import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from nexus_me.config import Settings
from nexus_me.providers import Ollama, OpenAI, ProviderError, request_json


class Handler(BaseHTTPRequestHandler):
    paths = []
    remote = False

    def log_message(self, *args):
        pass

    def send_json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/api/tags")
            self.end_headers()
            return
        self.send_json({"models": [{"name": "local-test"}, {"name": "remote-cloud"}]})

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).paths.append((self.path, payload))
        if self.path == "/api/show":
            self.send_json({"remote_host": "remote.example"} if self.remote else {"details": {"parameter_size": "4B"}})
        else:
            self.send_json({"message": {"content": "Resposta do servidor simulado"}, "prompt_eval_count": 25, "eval_count": 7})


class ProviderTests(unittest.TestCase):
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

    def setUp(self):
        Handler.paths = []
        Handler.remote = False

    def test_ollama_http_contract(self):
        client = Ollama(Settings(ollama_url=self.url, ollama_model="local-test"))
        self.assertEqual(client.models(), ["local-test"])
        result = client.chat([{"role": "user", "content": "Olá"}])
        self.assertEqual(result.output_tokens, 7)
        self.assertEqual(Handler.paths[-1][0], "/api/chat")
        self.assertFalse(Handler.paths[-1][1]["stream"])
        self.assertEqual(Handler.paths[-1][1]["options"]["num_ctx"], 8192)

    def test_cloud_alias_cannot_receive_local_context(self):
        Handler.remote = True
        with self.assertRaises(ProviderError):
            Ollama(Settings(ollama_url=self.url, ollama_model="innocent-alias")).chat([{"role": "user", "content": "private"}])
        self.assertEqual([p for p, _ in Handler.paths], ["/api/show"])

    def test_redirects_are_blocked(self):
        with self.assertRaises(ProviderError):
            request_json(self.url + "/redirect")

    def test_responses_api_extracts_text_after_reasoning(self):
        reply = {"status": "completed", "output": [{"type": "reasoning", "summary": []},
                 {"type": "message", "content": [{"type": "output_text", "text": "Resposta"}]}],
                 "usage": {"input_tokens": 5, "output_tokens": 9}}
        with patch("nexus_me.providers.request_json", return_value=reply) as call:
            result = OpenAI().chat({"model": "configured", "input": [], "store": False}, "test-only")
        self.assertEqual(result.text, "Resposta")
        self.assertEqual(result.input_tokens, 5)
        self.assertEqual(call.call_args.args[0], "https://api.openai.com/v1/responses")

    def test_incomplete_response_is_not_reported_as_success(self):
        with patch("nexus_me.providers.request_json", return_value={"status": "incomplete"}):
            with self.assertRaises(ProviderError):
                OpenAI().chat({"model": "configured"}, "test-only")


if __name__ == "__main__":
    unittest.main()
