"""The one Gemini client for the workers (google-genai SDK).

generate_image() sends a prompt plus inline image parts and asks for an IMAGE
response. Anything other than a returned image (missing key, API error,
timeout, safety block, text-only or empty response) raises GeminiError with a
message that is safe to store on a job and show to the customer. The key,
image bytes and provider error bodies are never logged or put in a message.

Requests time out after REQUEST_TIMEOUT_SECONDS. The SDK retries transient
failures (timeouts, connection errors, 408/429/5xx) inside one call, up to
REQUEST_ATTEMPTS times, so callers do not need to retry.
"""
import logging
from typing import List, Optional, Sequence, Tuple

from app.config import DEFAULT_GEMINI_GHOST_MODEL, settings

logger = logging.getLogger(__name__)

# Image-output models (ai.google.dev/gemini-api/docs/image-generation). Text-only
# models such as gemini-2.5-flash return no image and cannot run ghost jobs.
GEMINI_IMAGE_MODELS = (
    "gemini-3-pro-image",          # Nano Banana Pro, GA 2026-05-28: the default
    "gemini-nano-banana-2.1",      # Nano Banana 2.1, stable: the Sketch fast_draft default
    "gemini-3.1-flash-image",      # deprecated 2026-10-06, no shutdown date yet
    "gemini-3.1-flash-lite-image",
    "gemini-2.5-flash-image",      # shuts down 2027-03-15
)
DEFAULT_GHOST_MODEL = DEFAULT_GEMINI_GHOST_MODEL
REQUEST_TIMEOUT_SECONDS = 120
REQUEST_ATTEMPTS = 3

_BLOCKED_FINISH_REASONS = {"SAFETY", "IMAGE_SAFETY", "PROHIBITED_CONTENT", "IMAGE_PROHIBITED_CONTENT",
                           "BLOCKLIST", "SPII", "RECITATION", "IMAGE_RECITATION"}


class GeminiError(Exception):
    """No usable image came back. The message is safe to show the customer."""


def gemini_api_key() -> Optional[str]:
    secret = settings.GEMINI_API_KEY
    key = (secret.get_secret_value() if hasattr(secret, "get_secret_value") else secret or "").strip()
    return key if key and key.lower() != "mock" else None


def gemini_configured() -> bool:
    return gemini_api_key() is not None


def _client(api_key: str):
    from google import genai
    from google.genai import types
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(
        timeout=REQUEST_TIMEOUT_SECONDS * 1000,  # milliseconds
        retry_options=types.HttpRetryOptions(attempts=REQUEST_ATTEMPTS),
    ))


def _name(value) -> str:
    """An SDK enum (or plain string) as its name."""
    return str(getattr(value, "name", value) or "")


def generate_image(model: str, prompt: str, image_parts: Sequence[dict],
                   log_prefix: str = "[Gemini]") -> Tuple[bytes, str, Optional[str]]:
    """(image bytes, mime type, response id) generated from the prompt and the
    {"mime_type", "data"} image parts (prompt first, then the images in order)."""
    api_key = gemini_api_key()
    if not api_key:
        raise GeminiError("Image generation is not configured.")
    if model not in GEMINI_IMAGE_MODELS:
        logger.warning("%s model %r is not an image-output model", log_prefix, model)
        raise GeminiError("Image generation is not configured.")

    import httpx
    from google.genai import errors, types

    contents: List = [prompt]
    contents += [types.Part.from_bytes(data=p["data"], mime_type=p["mime_type"]) for p in image_parts]
    config = types.GenerateContentConfig(response_modalities=["IMAGE"])
    try:
        response = _client(api_key).models.generate_content(model=model, contents=contents, config=config)
    except errors.APIError as e:
        # str(e) carries the provider's response body: log the status code only.
        logger.warning("%s %s returned HTTP %s", log_prefix, model, getattr(e, "code", "?"))
        if getattr(e, "code", None) == 429:
            raise GeminiError("The image service is busy. Please try again shortly.") from None
        raise GeminiError("The image service returned an error.") from None
    except (httpx.TimeoutException, TimeoutError):
        logger.warning("%s %s timed out after %ss", log_prefix, model, REQUEST_TIMEOUT_SECONDS)
        raise GeminiError("The image service timed out.") from None
    except Exception as e:
        logger.warning("%s %s request failed: %s", log_prefix, model, type(e).__name__)
        raise GeminiError("The image service request failed.") from None

    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        logger.warning("%s %s blocked the request: %s", log_prefix, model, _name(feedback.block_reason))
        raise GeminiError("The image request was blocked by the image service's safety filters.")

    candidates = getattr(response, "candidates", None) or []
    candidate = candidates[0] if candidates else None
    finish = _name(getattr(candidate, "finish_reason", None))
    content = getattr(candidate, "content", None)
    for part in (getattr(content, "parts", None) or []):
        blob = getattr(part, "inline_data", None)
        data = getattr(blob, "data", None)
        mime = getattr(blob, "mime_type", None) or ""
        if data and mime.startswith("image/"):
            return data, mime, getattr(response, "response_id", None)

    if finish in _BLOCKED_FINISH_REASONS:
        logger.warning("%s %s returned no image: %s", log_prefix, model, finish)
        raise GeminiError("The image was blocked by the image service's safety filters.")
    logger.warning("%s %s returned no image (finish reason %s)", log_prefix, model, finish or "none")
    raise GeminiError("The image service returned no image.")
