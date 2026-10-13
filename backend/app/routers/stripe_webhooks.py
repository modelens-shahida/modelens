from fastapi import APIRouter, HTTPException, Request, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import get_db, User, CreditTransaction
from app.config import DEFAULT_STRIPE_WEBHOOK_SECRET, production_rules_apply, settings
import json
import logging
from app.api_docs import NOT_CONFIGURED_RESPONSE, error_responses

logger = logging.getLogger(__name__)

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


@router.post(
    "/webhook",
    summary="Receive a Stripe webhook",
    description=(
        "Handle Stripe webhook events.\n"
        "Verifies signature and provisions credits on successful payments.\n"
        "\n"
        "Called by Stripe; authenticated with the `Stripe-Signature` header. The check is skipped only in "
        "mock mode outside production; in production (or when APP_ENV is missing or unknown) the signature "
        "is always verified, and the endpoint answers 503 until a real STRIPE_WEBHOOK_SECRET is set."
    ),
    response_description="Acknowledgement that the event was received.",
    operation_id="receive_stripe_webhook",
    responses={**error_responses(400), **NOT_CONFIGURED_RESPONSE},
)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle Stripe webhook events.
    Verifies signature and provisions credits on successful payments.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    production = production_rules_apply()
    if production and settings.STRIPE_MOCK_MODE:
        logger.error("STRIPE_MOCK_MODE is on but production rules apply; verifying the Stripe signature anyway.")
    if production and settings.STRIPE_WEBHOOK_SECRET in ("", DEFAULT_STRIPE_WEBHOOK_SECRET):
        logger.error("Rejected Stripe webhook: STRIPE_WEBHOOK_SECRET is unset or the repository default.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Stripe webhooks are not configured.")

    if settings.STRIPE_MOCK_MODE and not production:
        # Mock mode outside production: parse JSON directly without signature verification
        try:
            event = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")
    else:
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            # Verified; read the event as a plain dict (stripe>=7 returns an Event without .get).
            event = json.loads(payload)
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
