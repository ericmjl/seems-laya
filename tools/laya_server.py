"""A small HTTP server around a local Laya Router.

Speaks the same envelope the Seems runtime expects, so the app can stay
standard-library-only: POST /predict with {"state", "questions", "model"} and
GET /health. Run it (in the container or on any machine that can spare the
memory) and point LAYA_URL at it:

    python tools/laya_server.py --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from laya import Router

ROUTER: Router | None = None
PREDICT_LOCK = threading.Lock()  # one forward pass at a time: concurrent predict() races
MAX_QUESTIONS = 64              # on macOS (MPS command buffers), see seems/client.py
MAX_STATE_CHARS = 50_000


def _predict(state, questions, model):
    if not questions:
        raise ValueError("send at least one question")
    if len(questions) > MAX_QUESTIONS:
        raise ValueError(f"too many questions ({len(questions)} > {MAX_QUESTIONS})")
    size = len(state) if isinstance(state, str) else len(str(state))
    if size > MAX_STATE_CHARS:
        raise ValueError(f"state too large ({size} > {MAX_STATE_CHARS} chars)")
    name = (model or "").strip().lower() or None
    if name in ("router", "auto"):
        name = None
    with PREDICT_LOCK:
        if name:
            return ROUTER.predict(state, questions, model=name)
        return ROUTER.predict(state, questions)


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            self._json(200, {"status": "ok" if ROUTER else "loading", "server": "seems-laya/laya_server"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/predict":
            self._json(404, {"error": "not found"})
            return
        started = time.perf_counter()
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            answer = _predict(body.get("state"), body.get("questions") or {}, body.get("model"))
            answer["ms"] = round((time.perf_counter() - started) * 1000)
            self._json(200, answer)
        except Exception as err:
            self._json(400, {"error": f"{type(err).__name__}: {err}"})

    def log_message(self, fmt, *args):  # quieter default logging
        pass


def main():
    parser = argparse.ArgumentParser(description="Serve a local Laya Router over HTTP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", default=None, help="default checkpoint: english | multilingual | typed-decisions")
    parser.add_argument("--device", default=None, help="torch device, for example mps or cuda")
    args = parser.parse_args()

    global ROUTER
    print(f"loading Laya ({args.model or 'router'}) ...", flush=True)
    ROUTER = Router(default=args.model) if args.model else Router()
    print(f"ready on http://{args.host}:{args.port}", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
