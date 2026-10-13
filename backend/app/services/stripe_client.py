"""Shared Stripe setup for the billing routes.

One place decides mock vs real Stripe and sets the API key, so the routes never
read STRIPE_MOCK_MODE or the key themselves.
"""
import logging

from fastapi import HTTPException, status

from app.config import DEFAULT_STRIPE_SECRET_KEY, production_rules_apply, settings

logger = logging.getLogger(__name__)

PAYMENTS_NOT_CONFIGURED = "Payments are not configured."
PAYMENT_PROVIDER_ERROR = "The payment provider could not complete the request. Please try again later."


def stripe_mock_mode() -> bool:
    """Mock Stripe only outside production; where production rules apply STRIPE_MOCK_MODE is ignored."""
    return settings.STRIPE_MOCK_MODE and not production_rules_apply()


def get_stripe():
    """The stripe module with its API key set from STRIPE_SECRET_KEY.

    Where production rules apply, an unset or repository-default key is refused
    with 503 instead of sending it to Stripe.
    """
    import stripe

    key = settings.STRIPE_SECRET_KEY
    if production_rules_apply() and key in ("", DEFAULT_STRIPE_SECRET_KEY):
        logger.error("Refused a Stripe call: STRIPE_SECRET_KEY is unset or the repository default.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=PAYMENTS_NOT_CONFIGURED)
    stripe.api_key = key
    return stripe


def provider_error(exc: Exception, action: str) -> HTTPException:
    """Log a Stripe failure without its message (it can echo request data) and return a safe 502."""
    logger.warning(
        "Stripe %s failed: %s (code=%s, http_status=%s, request_id=%s)",
        action, type(exc).__name__, getattr(exc, "code", None),
        getattr(exc, "http_status", None), getattr(exc, "request_id", None),
    )
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=PAYMENT_PROVIDER_ERROR)
