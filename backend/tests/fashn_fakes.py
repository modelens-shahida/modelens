"""A fake FASHN API for tests: no network, no real key.

``install(monkeypatch)`` routes every httpx client made by app.services.fashn_client through an
``httpx.MockTransport`` that answers like FASHN (docs.fashn.ai):

* ``POST /v1/run`` -> ``run_replies`` in order (default ``200 {"id": PREDICTION_ID}``)
* ``GET /v1/status/<id>`` -> ``status_replies`` in order, the last one repeating
  (default ``in_queue``, ``processing``, then ``completed`` with ``[OUTPUT_URL]``)
* ``GET OUTPUT_URL`` -> ``output`` bytes (default a real PNG) with ``output_status``

Polling sleeps are skipped; ``clock`` is a fake monotonic clock that advances by each sleep, so
timeouts can be tested without waiting. Every request is recorded in ``requests``.
"""
import io
import json
from typing import Any, List, Optional

import httpx
from PIL import Image

from app.services import fashn_client

PREDICTION_ID = "123a87r9-4129-4bb3-be18-9c9fb5bd7fc1-u1"
OUTPUT_URL = "https://cdn.fashn.ai/123a87r9/output_0.png"
TEST_KEY = "fa-test-only-0000000000000000"


def png(size=(32, 48), color=(180, 120, 90)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format="PNG")
    return out.getvalue()


def status(state: str, output: Optional[List[str]] = None, error: Optional[dict] = None) -> tuple:
    return 200, {"id": PREDICTION_ID, "status": state, "output": output, "error": error}


def api_error(code: int, name: str, message: str = "error") -> tuple:
    return code, {"error": name, "message": message}


class FakeFashn:
    def __init__(self):
        self.run_replies: List[Any] = []
        self.status_replies: List[Any] = [status("in_queue"), status("processing"),
                                          status("completed", [OUTPUT_URL])]
        self.output = png()
        self.output_status = 200
        self.requests: List[httpx.Request] = []
        self.now = 1000.0
        self._status_index = 0

    # ---- recorded calls -------------------------------------------------------------------
    @property
    def runs(self) -> List[httpx.Request]:
        return [r for r in self.requests if r.method == "POST" and r.url.path == "/v1/run"]

    @property
    def polls(self) -> List[httpx.Request]:
        return [r for r in self.requests if r.url.path.startswith("/v1/status/")]

    @property
    def downloads(self) -> List[httpx.Request]:
        return [r for r in self.requests if str(r.url) == OUTPUT_URL]

    @property
    def run_json(self) -> dict:
        return json.loads(self.runs[-1].content)

    @property
    def call_count(self) -> int:
        return len(self.runs)

    def assert_not_called(self):
        assert self.requests == [], [str(r.url) for r in self.requests]

    # ---- transport ------------------------------------------------------------------------
    def _reply(self, reply) -> httpx.Response:
        if isinstance(reply, Exception):
            raise reply
        code, body = reply
        return httpx.Response(code, json=body)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST" and request.url.path == "/v1/run":
            reply = self.run_replies.pop(0) if self.run_replies else (200, {"id": PREDICTION_ID, "error": None})
            return self._reply(reply)
        if request.url.path.startswith("/v1/status/"):
            index = min(self._status_index, len(self.status_replies) - 1)
            self._status_index += 1
            return self._reply(self.status_replies[index])
        if str(request.url) == OUTPUT_URL:
            return httpx.Response(self.output_status, content=self.output)
        return httpx.Response(404, json={"error": "NotFound", "message": "unknown fake route"})

    async def sleep(self, seconds: float):
        self.now += seconds

    def clock(self) -> float:
        return self.now


def install(monkeypatch, key: Optional[str] = TEST_KEY) -> FakeFashn:
    """Install the fake (and, unless ``key`` is None, a FASHN key in settings)."""
    from app.config import settings
    fake = FakeFashn()

    def client_factory(*args, **kwargs):
        return httpx.AsyncClient(*args, transport=httpx.MockTransport(fake.handler), **kwargs)

    monkeypatch.setattr(fashn_client, "_http_client", client_factory)
    monkeypatch.setattr(fashn_client, "_sleep", fake.sleep)
    monkeypatch.setattr(fashn_client, "_clock", fake.clock)
    monkeypatch.setattr(settings, "FASHN_API_KEY", key)
    return fake
