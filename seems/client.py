"""Client for Laya, the open-source System One decision model.

Derived from kavehmz/seems-lang (seems/client.py), which talked to TypeSafe's
hosted Jev API. This version answers judgments with Laya instead
(https://github.com/NandhaKishorM/laya, Apache 2.0 by Convai Innovations):
same state + typed-questions contract (choice / score / noul), but the model
is open-weight and runs on your own machine, so there is no API key and no
per-token bill.

Two ways to reach the model, chosen by the environment:

* ``LAYA_URL`` set   -> HTTP mode. Plain urllib against a Laya server
  (``python tools/laya_server.py``, or any endpoint speaking the same
  ``{"state", "questions", "model"}`` envelope). The language itself still
  needs only the Python standard library in this mode.
* ``LAYA_URL`` unset -> local mode. The ``laya`` package is imported in-process
  (``pip install laya``) and the checkpoint is loaded here.
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8000"
# Names Router.predict understands; anything else is treated as a Hub id.
ROUTER_MODELS = {"english", "multilingual", "typed-decisions"}
RETRY_STATUSES = {408, 409, 429, 500, 502, 503, 504}


class LayaError(RuntimeError):
    """Laya could not answer."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def model_from_env():
    """Checkpoint name: english | multilingual | typed-decisions | router, or a Hub id."""
    return (os.environ.get("LAYA_MODEL") or "english").strip().lower()


def mode():
    """How judgments are answered right now: 'http' (LAYA_URL) or 'local' (in-process)."""
    return "http" if (os.environ.get("LAYA_URL") or "").strip() else "local"


class LayaClient:
    def __init__(self, url=None, timeout=120.0, attempts=3):
        self.url = (url or os.environ.get("LAYA_URL") or "").strip() or None
        self.timeout = timeout
        self.attempts = attempts

    # ---- one request: one state, many typed questions --------------------- #

    def ask(self, state, questions: dict, model: str) -> dict:
        if self.url:
            return self._ask_http(state, questions, model)
        return self._ask_local(state, questions, model)

    def _ask_http(self, state, questions, model):
        body = json.dumps({"state": state, "model": _laya_model(model), "questions": questions},
                          ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(self.url.rstrip("/") + "/predict", data=body, method="POST", headers={
            "Content-Type": "application/json",
            "User-Agent": "seems-laya/0.1",
        })
        last = None
        for attempt in range(self.attempts):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return _checked(json.loads(response.read().decode("utf-8")))
            except urllib.error.HTTPError as err:
                detail = err.read().decode("utf-8", "replace")[:400]
                last = LayaError(f"Laya server answered HTTP {err.code}: {detail}", err.code)
                if err.code not in RETRY_STATUSES:
                    raise last from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
                last = LayaError(f"Could not reach the Laya server at {self.url}: {getattr(err, 'reason', err)}")
            if attempt < self.attempts - 1:
                time.sleep(min(8.0, 0.5 * 2 ** attempt) + random.random() * 0.25)
        raise last

    def _ask_local(self, state, questions, model):
        try:
            local, router_model = _local_model(model_from_env())
        except ImportError as err:
            raise LayaError(
                "LAYA_URL is not set, so judgments run in-process, but the laya package "
                "is not installed. Run: pip install laya   (or point LAYA_URL at a Laya server)"
            ) from err
        try:
            # One forward pass at a time. The runtime groups same-state questions into a
            # single request, so a request is already one batched pass; parallel passes
            # would only fight over the model. Laya 0.3.20 crashes under concurrent
            # predict() on macOS (MPS command-buffer race), and a GPU is not helped by
            # thread contention anyway.
            with _LOCAL_LOCK:
                if router_model:
                    answer = local.predict(state, questions, model=router_model)
                else:
                    answer = local.predict(state, questions)
        except Exception as err:
            raise LayaError(f"{type(err).__name__}: {err}") from err
        return _checked(answer)


_LOCAL = {}  # (checkpoint name) -> (Router or Agent, explicit router model or None)
_LOCAL_LOCK = threading.Lock()  # held while the model answers, see _ask_local


def _local_model(name):
    """The process-wide loaded model. Loading is expensive (seconds), and the runtime
    builds a fresh client per request, so the checkpoint is shared across clients."""
    if name not in _LOCAL:
        import laya
        if name in ROUTER_MODELS:
            _LOCAL[name] = (laya.Router(), name)
        elif name in ("router", "auto", ""):
            _LOCAL[name] = (laya.Router(), None)  # the router picks a checkpoint per request
        else:  # a Hub id such as convaiinnovations/laya-typed-decisions
            _LOCAL[name] = (laya.load(name), None)
    return _LOCAL[name]


def _laya_model(model):
    """Map the Seems model name onto what a Laya server expects (None = auto-route)."""
    name = (model or "").strip().lower()
    if not name or name in ("router", "auto"):
        return None
    return name


def _checked(answer):
    """Laya's envelope is already model/answers/usage; make the required keys explicit."""
    if not isinstance(answer, dict) or "answers" not in answer:
        raise LayaError(f"Laya returned something unexpected: {str(answer)[:200]}")
    answer.setdefault("model", "laya")
    usage = answer.setdefault("usage", {})
    usage.setdefault("input_tokens", 0)
    usage.setdefault("output_tokens", 0)
    return answer
