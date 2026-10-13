"""
X-Internal-Secret check for service-to-service callbacks.

The NestJS templates backend and the FASHN webhook proxy call
/api/v1/internal/generations/* and /api/v1/fashn/webhook with the shared
INTERNAL_CALLBACK_SECRET. The repository default is public, so wherever
production rules apply (APP_ENV production, missing or unknown) these routes
answer 503 until a real secret is configured. Otherwise the header must match
the configured secret (constant-time compare) or the caller gets 403.
"""
import hmac
import logging
from typing import Optional

from fastapi import HTTPException, status

from app.config import DEFAULT_INTERNAL_CALLBACK_SECRET, production_rules_apply, settings

logger = logging.getLogger(__name__)

NOT_CONFIGURED = "Internal callbacks are not configured."


def internal_secret_usable() -> bool:
    """A secret is set, and it is not the repository default where production rules apply."""
    secret = settings.INTERNAL_CALLBACK_SECRET or ""
    if not secret:
        return False
    return not (production_rules_apply() and secret == DEFAULT_INTERNAL_CALLBACK_SECRET)


def check_internal_secret(provided: Optional[str], detail: str) -> None:
    """Raise 503 if no usable secret is configured, 403 if ``provided`` does not match it."""
    if not internal_secret_usable():
        logger.error("Rejected internal callback: INTERNAL_CALLBACK_SECRET is unset or the repository default.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=NOT_CONFIGURED)
    secret = settings.INTERNAL_CALLBACK_SECRET.encode()
    if provided is None or not hmac.compare_digest(provided.encode(), secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
