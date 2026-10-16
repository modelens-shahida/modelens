"""A fake google-genai client for worker tests: no network, fake key.

install(monkeypatch) patches google.genai.Client and returns a FakeGemini whose
`generate_content` mock records each request; responses are real
google.genai.types objects, so the worker parses exactly what the SDK returns.
"""
import base64
from unittest.mock import MagicMock

import httpx

from google import genai
from google.genai import errors, types

from app.config import settings

FAKE_KEY = "fake-gemini-key-for-tests-only"
OUTPUT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI6QAAAABJRU5ErkJggg==")


def image_response(data=OUTPUT_PNG, mime="image/png", text=None, response_id="resp-fake-1"):
    parts = ([types.Part(text=text)] if text else []) + \
        ([types.Part(inline_data=types.Blob(data=data, mime_type=mime))] if data else [])
    return types.GenerateContentResponse(
        response_id=response_id,
        candidates=[types.Candidate(content=types.Content(role="model", parts=parts),
                                    finish_reason=types.FinishReason.STOP)])


class FakeGemini:
    def __init__(self):
        self.client_cls = MagicMock(name="genai.Client")
        self.generate_content = self.client_cls.return_value.models.generate_content
        self.generate_content.return_value = image_response()

    def request(self, call=0):
        """(model, prompt, [{"mime_type", "data"}...], config) of one generate_content call."""
        kwargs = self.generate_content.call_args_list[call].kwargs
        prompt, *parts = kwargs["contents"]
        images = [{"mime_type": p.inline_data.mime_type, "data": p.inline_data.data} for p in parts]
        return kwargs["model"], prompt, images, kwargs.get("config")


def install(monkeypatch, key=FAKE_KEY):
    fake = FakeGemini()
    monkeypatch.setattr(genai, "Client", fake.client_cls)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", key)
    return fake


# ========================== Production failures =================
# Every way a request can fail, and the safe message the job gets. PROVIDER_BODY stands in for a
# provider error body (with a key-like string) that must never reach logs or the job.

PROVIDER_BODY = "quota exceeded for project 1234567890, key AIzaFAKEFAKEFAKE"

FAILURES = {
    "no key": (None, "Image generation is not configured."),
    "mock key": ("mock", "Image generation is not configured."),
    "server error": (errors.ServerError(500, {"error": {"message": PROVIDER_BODY}}),
                     "The image service returned an error."),
    "bad request": (errors.ClientError(400, {"error": {"message": PROVIDER_BODY}}),
                    "The image service returned an error."),
    "rate limited": (errors.ClientError(429, {"error": {"message": PROVIDER_BODY}}),
                     "The image service is busy. Please try again shortly."),
    "timeout": (httpx.ReadTimeout(PROVIDER_BODY), "The image service timed out."),
    "sdk error": (ValueError(PROVIDER_BODY), "The image service request failed."),
    "text only": (image_response(data=None, text="I can't draw that."),
                  "The image service returned no image."),
    "no candidates": (types.GenerateContentResponse(candidates=[]), "The image service returned no image."),
    "prompt blocked": (types.GenerateContentResponse(prompt_feedback=types.GenerateContentResponsePromptFeedback(
        block_reason=types.BlockedReason.SAFETY)),
        "The image request was blocked by the image service's safety filters."),
    "image safety": (types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[]), finish_reason=types.FinishReason.IMAGE_SAFETY)]),
        "The image was blocked by the image service's safety filters."),
    "non-image blob": (image_response(data=b"%PDF", mime="application/pdf"),
                       "The image service returned no image."),
}


def arrange_failure(gemini, monkeypatch, case):
    """Make the next Gemini request fail as FAILURES[case] says; returns the job's expected message."""
    outcome, message = FAILURES[case]
    if case in ("no key", "mock key"):
        monkeypatch.setattr(settings, "GEMINI_API_KEY", outcome)
    elif isinstance(outcome, BaseException):
        gemini.generate_content.side_effect = outcome
    else:
        gemini.generate_content.return_value = outcome
    return message
