"""Tiny Ollama-compatible backend for Kubernetes smoke tests."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/tags":
            self._send({"models": [{"name": "mock"}]})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        if request.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            for content in ("kind ", "smoke ", "passed"):
                self.wfile.write(json.dumps({"message": {"role": "assistant", "content": content}, "done": False}).encode() + b"\n")
            self.wfile.write(json.dumps({"message": {"role": "assistant", "content": ""}, "done": True, "eval_count": 3}).encode() + b"\n")
        else:
            self._send({"message": {"role": "assistant", "content": "kind smoke passed"}, "done": True, "eval_count": 3})

    def _send(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


ThreadingHTTPServer(("0.0.0.0", 11434), Handler).serve_forever()
