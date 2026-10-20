"""FASHN API client for Catalog generation: submit a prediction, poll it, fetch the result.

Contract (FASHN API docs, docs.fashn.ai):

* ``POST {FASHN_BASE_URL}/v1/run`` with ``Authorization: Bearer <key>`` and
  ``{"model_name": "product-to-model" | "tryon-max", "inputs": {...}}`` returns ``{"id": ...}``.
  Every parameter goes inside ``inputs``; images are URLs or data URIs (at most 30 MiB).
* ``GET {FASHN_BASE_URL}/v1/status/{id}`` returns ``{"id", "status", "output", "error"}``.
  ``starting``, ``in_queue`` and ``processing`` are still running; ``completed`` carries
  ``output`` (a list of image URLs, kept by FASHN for 3 days); ``failed``, ``canceled`` and
  ``time_out`` are final, with ``error`` = ``{"name", "message"}`` on a runtime failure.
* API-level errors are an HTTP status with ``{"error": <name>, "message": ...}`` and no
  prediction id: 400 BadRequest, 401 UnauthorizedAccess, 404 NotFound, 429 RateLimitExceeded /
  ConcurrencyLimitExceeded / OutOfCredits, 500 InternalServerError. Retrying an API-level error
  with the same payload cannot run the prediction twice (no id was issued).

Retries: 429 rate and concurrency limits, 5xx and network timeouts are retried with backoff
inside one overall deadline (``FASHN_TIMEOUT_SECONDS``); 400, 401, 404 and OutOfCredits are not.
Every failure raises ``FashnError`` whose text is a short error name, never the key, a URL or
FASHN's message, so it is safe to log.
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

RUNNING = ("starting", "in_queue", "processing")
COMPLETED = "completed"
FINAL_FAILURES = ("failed", "canceled", "time_out")
RETRYABLE_429 = ("RateLimitExceeded", "ConcurrencyLimitExceeded")
REQUEST_TIMEOUT = 30.0
FIRST_DELAY, MAX_DELAY, BACKOFF = 2.0, 10.0, 1.5

# Patched in tests: no real waiting, no network.
_sleep = asyncio.sleep
_clock = time.monotonic
_http_client = httpx.AsyncClient


class FashnError(Exception):
    """FASHN did not produce an image. ``code`` is a safe name for logs, e.g. ``http_401``,
    ``RateLimitExceeded``, ``ImageLoadError``, ``timeout``."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _api_error_name(response: httpx.Response) -> str:
    try:
        name = response.json().get("error")
    except Exception:
        name = None
    return name if isinstance(name, str) and name.isidentifier() else f"http_{response.status_code}"


class FashnClient:
    def __init__(self, api_key: str, base_url: Optional[str] = None, timeout_seconds: Optional[int] = None):
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._base = (base_url or settings.FASHN_BASE_URL).rstrip("/")
        self._timeout = timeout_seconds or settings.FASHN_TIMEOUT_SECONDS

    async def _request(self, client: httpx.AsyncClient, method: str, path: str, deadline: float,
                       json: Optional[dict] = None) -> Dict[str, Any]:
        """One API call, retried on 429 rate/concurrency limits, 5xx and timeouts until ``deadline``."""
        delay = FIRST_DELAY
        while True:
            try:
                response = await client.request(method, f"{self._base}{path}", headers=self._headers, json=json)
            except (httpx.TimeoutException, httpx.TransportError):
                code = "timeout"
            else:
                if response.status_code < 400:
                    try:
                        body = response.json()
                    except Exception:
                        raise FashnError("invalid_response")
                    if not isinstance(body, dict):
                        raise FashnError("invalid_response")
                    return body
                code = _api_error_name(response)
                retryable = (response.status_code == 429 and code in RETRYABLE_429) or response.status_code >= 500
                if not retryable:
                    raise FashnError(code)
            if _clock() + delay > deadline:
                raise FashnError(code)
            await _sleep(delay)
            delay = min(delay * BACKOFF, MAX_DELAY)

    async def generate(self, model_name: str, inputs: Dict[str, Any]) -> tuple[str, List[str]]:
        """Run a prediction and wait for it. Returns (prediction id, output image URLs)."""
        deadline = _clock() + self._timeout
        async with _http_client(timeout=REQUEST_TIMEOUT) as client:
            started = await self._request(client, "POST", "/v1/run", deadline,
                                          json={"model_name": model_name, "inputs": inputs})
            prediction_id = started.get("id")
            if not isinstance(prediction_id, str) or not prediction_id:
                raise FashnError(_runtime_error(started) or "no_prediction_id")

            delay = FIRST_DELAY
            while True:
                if _clock() + delay > deadline:
                    raise FashnError("timeout")
                await _sleep(delay)
                delay = min(delay * BACKOFF, MAX_DELAY)
                status = await self._request(client, "GET", f"/v1/status/{prediction_id}", deadline)
                state = status.get("status")
                if state in RUNNING:
                    continue
                if state == COMPLETED:
                    output = status.get("output")
                    urls = [u for u in output if isinstance(u, str) and u] if isinstance(output, list) else []
                    if not urls:
                        raise FashnError("no_output")
                    return prediction_id, urls
                if state in FINAL_FAILURES:
                    raise FashnError(_runtime_error(status) or state)
                raise FashnError("unknown_status")

    async def download(self, url: str, max_bytes: int) -> bytes:
        """The bytes of a FASHN output (https only, at most ``max_bytes``)."""
        if not url.startswith("https://"):
            raise FashnError("invalid_output_url")
        async with _http_client(timeout=REQUEST_TIMEOUT, follow_redirects=False) as client:
            try:
                async with client.stream("GET", url) as response:
                    if response.status_code != 200:
                        raise FashnError(f"download_http_{response.status_code}")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > max_bytes:
                            raise FashnError("output_too_large")
                    return bytes(data)
            except (httpx.TimeoutException, httpx.TransportError):
                raise FashnError("download_timeout")


def _runtime_error(body: Dict[str, Any]) -> Optional[str]:
    error = body.get("error")
    name = error.get("name") if isinstance(error, dict) else error
    return name if isinstance(name, str) and name.isidentifier() else None
