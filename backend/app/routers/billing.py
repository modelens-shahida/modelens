from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, User, CreditTransaction
from app.middleware.auth import get_current_user
from app.config import settings

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

STRIPE_PRICE_MAP = {
    ("lite", "monthly"): "STRIPE_PRICE_LITE_MONTHLY",
    ("lite", "yearly"): "STRIPE_PRICE_LITE_YEARLY",
    ("plus", "monthly"): "STRIPE_PRICE_PLUS_MONTHLY",
    ("plus", "yearly"): "STRIPE_PRICE_PLUS_YEARLY",
    ("pro", "monthly"): "STRIPE_PRICE_PRO_MONTHLY",
    ("pro", "yearly"): "STRIPE_PRICE_PRO_YEARLY",
}

def get_stripe_price_id(package: str, frequency: str) -> str:
    """Get Stripe price ID from settings based on package and frequency."""
    key = (package.lower(), frequency.lower())
    setting_name = STRIPE_PRICE_MAP.get(key)
    if not setting_name:
        raise ValueError(f"Invalid package/frequency: {package}/{frequency}")
    return getattr(settings, setting_name)

@router.post("/checkout-session")
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

    if settings.STRIPE_MOCK_MODE:
        # Return mock checkout URL for local/test environments
        return {
            "session_url": f"https://checkout.stripe.com/mock?package={payload.package}&freq={payload.frequency}&user={current_user.id}",
            "session_id": f"cs_mock_{current_user.id}_{payload.package}",
            "mock": True,
        }

    try:
        import stripe
        stripe.api_key = settings.STRIPE_API_KEY

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": f"ModeLens {payload.package.title()} Plan"},
                    "unit_amount": CREDIT_PACKAGES[payload.package][payload.frequency],
                    "recurring": {"interval": "month" if payload.frequency == "monthly" else "year"},
                },
                "quantity": 1,
            }],
            metadata={
                "user_id": str(current_user.id),
                "package": payload.package,
                "frequency": payload.frequency,
            },
            success_url=settings.STRIPE_SUCCESS_URL,
            cancel_url=settings.STRIPE_CANCEL_URL,
        )
        return {"session_url": session.url, "session_id": session.id, "mock": False}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe error: {str(e)}")


@router.post("/portal-session")
async def create_portal_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a Stripe Billing Customer Portal link."""
    if settings.STRIPE_MOCK_MODE:
        return {
            "portal_url": f"https://billing.stripe.com/mock?user={current_user.id}",
            "mock": True,
        }

    try:
        import stripe
        stripe.api_key = settings.STRIPE_API_KEY

        portal = stripe.billing_portal.Session.create(
            customer=f"cus_mock_{current_user.id}",
            return_url="https://modelens-xi.vercel.app/dashboard",
        )
        return {"portal_url": portal.url, "mock": False}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe error: {str(e)}")
