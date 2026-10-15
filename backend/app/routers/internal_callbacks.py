from fastapi import APIRouter, HTTPException, Depends, Header, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db import get_db
from app.api_docs import NOT_CONFIGURED_RESPONSE, error_responses
from app.services.internal_auth import check_internal_secret
from app.services.job_refunds import lock_reservation, refund_reservation

router = APIRouter(prefix="/api/v1/internal", tags=["Internal Callbacks"])

def verify_internal_secret(x_internal_secret: Optional[str] = Header(None)):
    """Verify internal service secret header."""
    check_internal_secret(x_internal_secret, "Unauthorized internal callback")
    return True


class GenerationCompletePayload(BaseModel):
    generation_id: str
    credits_consumed: Optional[int] = None


class GenerationFailPayload(BaseModel):
    generation_id: str
    reason: Optional[str] = None


@router.post(
    "/generations/{generation_id}/complete",
    summary="Generation completed callback (internal)",
    description=(
        "Called by NestJS when generation completes.\n"
        "Finalizes credit deduction.\n"
        "\n"
        "Internal endpoint: requires the `X-Internal-Secret` header."
    ),
    response_description="Confirmation that the credit deduction was finalized.",
    operation_id="internal_generation_complete",
    responses={**error_responses(403, 404, 422), **NOT_CONFIGURED_RESPONSE},
)
async def generation_complete_callback(
    generation_id: str,
    payload: GenerationCompletePayload,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_internal_secret),
):
    """
    Called by NestJS when generation completes.
    Finalizes credit deduction.
    """
    # Locked: a concurrent complete/fail callback for this generation waits, then finds it settled.
    txn = await lock_reservation(db, generation_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Pending transaction not found")

    # Finalize deduction
    txn.status = "completed"
    txn.description = f"Template generation completed - {generation_id}"

    # If fewer credits were used than reserved, refund the difference (once, at most the reservation)
    if payload.credits_consumed is not None and payload.credits_consumed != abs(txn.amount):
        diff = abs(txn.amount) - payload.credits_consumed
        if diff > 0:
            await refund_reservation(db, txn, "partial", partial=diff,
                                     description=f"Partial refund for generation {generation_id}")

    await db.commit()
    return {"status": "completed", "generation_id": generation_id}


@router.post(
    "/generations/{generation_id}/fail",
    summary="Generation failed callback (internal)",
    description=(
        "Called by NestJS when generation fails.\n"
        "Refunds reserved credits.\n"
        "\n"
        "Internal endpoint: requires the `X-Internal-Secret` header."
    ),
    response_description="Confirmation that reserved credits were refunded.",
    operation_id="internal_generation_fail",
    responses={**error_responses(403, 404, 422), **NOT_CONFIGURED_RESPONSE},
)
async def generation_fail_callback(
    generation_id: str,
    payload: GenerationFailPayload,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_internal_secret),
):
    """
    Called by NestJS when generation fails.
    Refunds reserved credits.
    """
    txn = await lock_reservation(db, generation_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Pending transaction not found")

    # Refund credits to brand, once (app/services/job_refunds.py); marks the reservation refunded
    refunded = await refund_reservation(db, txn, payload.reason or "unknown", reference_id=generation_id,
                                        description=f"Generation failed refund - {generation_id}")
    txn.description = f"Refund - generation failed: {payload.reason or 'unknown'} - {generation_id}"
    await db.commit()

    return {"status": "refunded", "generation_id": generation_id, "credits_refunded": refunded}
