from fastapi import APIRouter, HTTPException, Request, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import get_db, User, CreditTransaction
from app.config import DEFAULT_STRIPE_WEBHOOK_SECRET, production_rules_apply, settings
from app.routers.billing import credits_for
from app.services.stripe_client import stripe_mock_mode
import json
import logging
from app.api_docs import NOT_CONFIGURED_RESPONSE, error_responses

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/stripe",
    tags=["Stripe Webhooks"],
)


async def _provision_credits(db: AsyncSession, user_id: int, credits: int, reference_type: str, description: str,
                             reference_id: str | None = None):
    """Add credits to user and log CreditTransaction.

    reference_id is the Stripe checkout session or invoice id; Stripe retries
    deliveries, so an id that already granted credits is skipped.
    """
    # Lock the user row so two deliveries of the same event cannot both pass the check below.
    result = await db.execute(select(User).where(User.id == user_id).with_for_update())
    user = result.scalars().first()
    if not user:
        print(f"[Stripe] User {user_id} not found for provisioning.")
        return
    if reference_id:
        already = await db.execute(select(CreditTransaction.id).where(
            CreditTransaction.reference_type == reference_type,
            CreditTransaction.reference_id == reference_id,
        ).limit(1))
        if already.first():
            # Nothing was changed; closing the request session releases the row lock.
            logger.info("Stripe %s already provisioned; skipping duplicate delivery.", reference_id)
            return

    user.credits += credits
    txn = CreditTransaction(
        user_id=user_id,
        amount=credits,
        transaction_type="top_up",
        reference_type=reference_type,
        reference_id=reference_id,
        balance_after=user.credits,
        description=description,
    )
    db.add(txn)

    from app.routers.credits import _trigger_low_credit_warning_if_needed
    await _trigger_low_credit_warning_if_needed(db, user)

    await db.commit()
    print(f"[Stripe] Provisioned {credits} credits to user {user_id}. New balance: {user.credits}")


def _invoice_metadata(invoice: dict) -> dict:
    """The subscription metadata (from checkout's subscription_data) on an invoice.

    Its location depends on the webhook endpoint's Stripe API version.
    """
    parent = (invoice.get("parent") or {}).get("subscription_details") or {}
    lines = (invoice.get("lines") or {}).get("data") or [{}]
    for metadata in (parent.get("metadata"), (invoice.get("subscription_details") or {}).get("metadata"),
                     lines[0].get("metadata"), invoice.get("metadata")):
        if metadata and metadata.get("user_id"):
            return metadata
    return {}


async def _grant_for_metadata(db: AsyncSession, metadata: dict, reference_id: str | None, what: str):
    user_id, package, frequency = metadata.get("user_id"), metadata.get("package"), metadata.get("frequency")
    if not user_id:
        logger.warning("%s without a user_id in its metadata (%s); no credits granted.", what, reference_id)
        return
    credits = credits_for(package, frequency)
    if credits is None:
        logger.error("%s with unknown package/frequency %r/%r (%s); no credits granted.",
                     what, package, frequency, reference_id)
        return
    await _provision_credits(
        db, int(user_id), credits,
        reference_type="purchase_invoice",
        reference_id=reference_id,
        description=f"{what}: {package} plan, {frequency or 'monthly'} ({credits} credits)",
    )


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

    if stripe_mock_mode():
        # Mock mode outside production: parse JSON directly without signature verification
        try:
            event = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")
    else:
        try:
            import stripe
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
        # Metadata set by POST /api/v1/billing/checkout-session.
        metadata = data.get("metadata") or {}
        if data.get("payment_status") == "unpaid":
            logger.info("Stripe checkout %s completed unpaid; no credits yet.", data.get("id"))
        else:
            await _grant_for_metadata(db, metadata, data.get("id"), "Stripe checkout completed")

    elif event_type == "invoice.payment_succeeded":
        # Recurring billing - renew credits. The first invoice of a subscription is
        # paid by the checkout above, which already granted its credits.
        if data.get("billing_reason") == "subscription_create":
            return {"status": "ok", "event_type": event_type}
        await _grant_for_metadata(db, _invoice_metadata(data), data.get("id"), "Recurring payment succeeded")

    elif event_type == "customer.subscription.deleted":
        # Handle cancellation
        metadata = data.get("metadata", {})
        user_id = metadata.get("user_id")
        if user_id:
            print(f"[Stripe] Subscription cancelled for user {user_id}")

    return {"status": "ok", "event_type": event_type}
