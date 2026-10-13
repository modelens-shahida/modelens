from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, User, CreditTransaction
from app.middleware.auth import get_current_user
from app.config import settings
from app.api_docs import PAYMENTS_NOT_CONFIGURED_RESPONSE, error_responses
from app.services.stripe_client import get_stripe, provider_error, stripe_mock_mode

router = APIRouter(
    prefix="/api/v1/billing",
    tags=["Billing"],
)

# ========================== Schemas ==============================

CREDIT_PACKAGES = {
    "lite": {"monthly": 50, "annual": 600, "price_monthly": 900, "price_annual": 9000},
    "plus": {"monthly": 250, "annual": 3000, "price_monthly": 2900, "price_annual": 29000},
    "pro": {"monthly": 1000, "annual": 12000, "price_monthly": 9900, "price_annual": 99000},
}

class CheckoutRequest(BaseModel):
    package: str = Field(..., description="lite, plus, or pro")
    frequency: str = Field(..., description="monthly or annual")

class PortalRequest(BaseModel):
    customer_id: Optional[str] = None

# ========================== Endpoints ============================



# ========================== Stripe Price Mapping =================

# The API takes "annual"; the price settings are named *_YEARLY.
STRIPE_PRICE_MAP = {
    ("lite", "monthly"): "STRIPE_PRICE_LITE_MONTHLY",
    ("lite", "annual"): "STRIPE_PRICE_LITE_YEARLY",
    ("plus", "monthly"): "STRIPE_PRICE_PLUS_MONTHLY",
    ("plus", "annual"): "STRIPE_PRICE_PLUS_YEARLY",
    ("pro", "monthly"): "STRIPE_PRICE_PRO_MONTHLY",
    ("pro", "annual"): "STRIPE_PRICE_PRO_YEARLY",
}

def get_stripe_price_id(package: str, frequency: str) -> str:
    """Get Stripe price ID from settings based on package and frequency."""
    key = (package.lower(), frequency.lower())
    setting_name = STRIPE_PRICE_MAP.get(key)
    if not setting_name:
        raise ValueError(f"Invalid package/frequency: {package}/{frequency}")
    return getattr(settings, setting_name)


def credits_for(package: Optional[str], frequency: Optional[str]) -> Optional[int]:
    """Credits one paid billing period grants, or None for an unknown package/frequency.

    Used by the Stripe webhook on the metadata this module puts on the checkout
    session and subscription; sessions without a frequency count as monthly.
    """
    frequency = frequency or "monthly"
    if package not in CREDIT_PACKAGES or frequency not in ("monthly", "annual"):
        return None
    return CREDIT_PACKAGES[package][frequency]


def _find_customer_id(stripe, user: User) -> Optional[str]:
    """The newest Stripe customer created by checkout for this user's email, if any."""
    customers = stripe.Customer.list(email=user.email, limit=1)
    return customers.data[0].id if customers.data else None


@router.post(
    "/checkout-session",
    summary="Create a Stripe checkout session",
    description=(
        "Create a Stripe Checkout Session for credit package purchase.\n"
        "\n"
        "Credits are granted by the Stripe webhook once Stripe reports the payment, not by this call. "
        "Mock sessions are returned only in mock mode outside production; in production Stripe is always used."
    ),
    response_description="Stripe Checkout Session URL and ID.",
    operation_id="create_checkout_session",
    responses={**error_responses(400, 401, 422, 502), **PAYMENTS_NOT_CONFIGURED_RESPONSE},
)
async def create_checkout_session(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout Session for credit package purchase."""
    if payload.package not in CREDIT_PACKAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid package. Choose from: {list(CREDIT_PACKAGES.keys())}"
        )
    if payload.frequency not in ("monthly", "annual"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid frequency. Choose: monthly or annual"
        )

    if stripe_mock_mode():
        # Return mock checkout URL for local/test environments
        return {
            "session_url": f"https://checkout.stripe.com/mock?package={payload.package}&freq={payload.frequency}&user={current_user.id}",
            "session_id": f"cs_mock_{current_user.id}_{payload.package}",
            "mock": True,
        }

    stripe = get_stripe()
    # Read by the Stripe webhook: on the session for checkout.session.completed,
    # and on the subscription for the renewal invoices.
    metadata = {
        "user_id": str(current_user.id),
        "package": payload.package,
        "frequency": payload.frequency,
    }
    try:
        customer_id = _find_customer_id(stripe, current_user)
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{
                "price": get_stripe_price_id(payload.package, payload.frequency),
                "quantity": 1,
            }],
            client_reference_id=str(current_user.id),
            **({"customer": customer_id} if customer_id else {"customer_email": current_user.email}),
            metadata=metadata,
            subscription_data={"metadata": metadata},
            success_url=settings.STRIPE_SUCCESS_URL,
            cancel_url=settings.STRIPE_CANCEL_URL,
        )
    except stripe.error.StripeError as exc:
        raise provider_error(exc, "checkout session")
    return {"session_url": session.url, "session_id": session.id, "mock": False}


@router.post(
    "/portal-session",
    summary="Create a Stripe billing portal session",
    description=(
        "Generate a Stripe Billing Customer Portal link for the caller's own Stripe customer "
        "(the one their checkout created, found by their email). 404 if they have never checked out. "
        "Mock links are returned only in mock mode outside production."
    ),
    response_description="Stripe Billing Portal URL.",
    operation_id="create_portal_session",
    responses={**error_responses(401, 404, 502), **PAYMENTS_NOT_CONFIGURED_RESPONSE},
)
async def create_portal_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a Stripe Billing Customer Portal link."""
    if stripe_mock_mode():
        return {
            "portal_url": f"https://billing.stripe.com/mock?user={current_user.id}",
            "mock": True,
        }

    stripe = get_stripe()
    try:
        customer_id = _find_customer_id(stripe, current_user)
        if not customer_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No billing account found. Buy a plan first.")
        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url="https://modelens-xi.vercel.app/dashboard",
        )
    except stripe.error.StripeError as exc:
        raise provider_error(exc, "billing portal session")
    return {"portal_url": portal.url, "mock": False}
