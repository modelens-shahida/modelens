"""A fake google-genai client for worker tests: no network, fake key.

install(monkeypatch) patches google.genai.Client and returns a FakeGemini whose
`generate_content` mock records each request; responses are real
google.genai.types objects, so the worker parses exactly what the SDK returns.
"""
import base64
from unittest.mock import MagicMock

from google import genai
from google.genai import types

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
