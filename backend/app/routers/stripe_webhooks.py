from fastapi import APIRouter, HTTPException, Request, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import get_db, User, CreditTransaction
from app.config import settings
import json

router = APIRouter(
    prefix="/api/v1/stripe",
    tags=["Stripe Webhooks"],
)

PACKAGE_CREDITS = {
    "lite": 50,
    "plus": 250,
    "pro": 1000,
}


async def _provision_credits(db: AsyncSession, user_id: int, credits: int, reference_type: str, description: str):
    """Add credits to user and log CreditTransaction."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        print(f"[Stripe] User {user_id} not found for provisioning.")
        return

    user.credits += credits
    txn = CreditTransaction(
        user_id=user_id,
        amount=credits,
        transaction_type="top_up",
        reference_type=reference_type,
        balance_after=user.credits,
        description=description,
    )
    db.add(txn)

    from app.routers.credits import _trigger_low_credit_warning_if_needed
    await _trigger_low_credit_warning_if_needed(db, user)

    await db.commit()
    print(f"[Stripe] Provisioned {credits} credits to user {user_id}. New balance: {user.credits}")


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle Stripe webhook events.
    Verifies signature and provisions credits on successful payments.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if settings.STRIPE_MOCK_MODE:
        # In mock mode, parse JSON directly without signature verification
        try:
            event = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")
    else:
        try:
            import stripe
            stripe.api_key = settings.STRIPE_API_KEY
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Webhook signature verification failed: {str(e)}")

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        metadata = data.get("metadata", {})
        user_id = metadata.get("user_id")
        package = metadata.get("package", "lite")

        if user_id:
            credits = PACKAGE_CREDITS.get(package, 50)
            await _provision_credits(
                db,
                int(user_id), credits,
                reference_type="purchase_invoice",
                description=f"Stripe checkout completed: {package} plan ({credits} credits)"
            )

    elif event_type == "invoice.payment_succeeded":
        # Recurring billing - renew credits
        subscription = data.get("subscription", "")
        metadata = data.get("lines", {}).get("data", [{}])[0].get("metadata", {})
        user_id = metadata.get("user_id") or data.get("metadata", {}).get("user_id")
        package = metadata.get("package", "lite")

        if user_id:
            credits = PACKAGE_CREDITS.get(package, 50)
            await _provision_credits(
                db,
                int(user_id), credits,
                reference_type="purchase_invoice",
                description=f"Recurring payment succeeded: {package} plan ({credits} credits renewed)"
            )

    elif event_type == "customer.subscription.deleted":
        # Handle cancellation
        metadata = data.get("metadata", {})
        user_id = metadata.get("user_id")
        if user_id:
            print(f"[Stripe] Subscription cancelled for user {user_id}")

    return {"status": "ok", "event_type": event_type}
