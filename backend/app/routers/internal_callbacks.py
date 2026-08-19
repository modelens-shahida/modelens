from fastapi import APIRouter, HTTPException, Depends, Header, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import get_db, CreditTransaction, Brand
from app.config import settings

router = APIRouter(prefix="/api/v1/internal", tags=["Internal Callbacks"])

INTERNAL_SECRET = getattr(settings, "INTERNAL_CALLBACK_SECRET", "modelens-internal-secret")


def verify_internal_secret(x_internal_secret: Optional[str] = Header(None)):
    """Verify internal service secret header."""
    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized internal callback")
    return True


class GenerationCompletePayload(BaseModel):
    generation_id: str
    credits_consumed: Optional[int] = None


class GenerationFailPayload(BaseModel):
    generation_id: str
    reason: Optional[str] = None


@router.post("/generations/{generation_id}/complete")
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
    result = await db.execute(
        select(CreditTransaction).where(
            CreditTransaction.reference_id == generation_id,
            CreditTransaction.status == "pending",
        )
    )
    txn = result.scalars().first()
    if not txn:
        raise HTTPException(status_code=404, detail="Pending transaction not found")

    # Finalize deduction
    txn.status = "completed"
    txn.description = f"Template generation completed - {generation_id}"

    # If actual credits differ from reserved
    if payload.credits_consumed is not None and payload.credits_consumed != abs(txn.amount):
        diff = abs(txn.amount) - payload.credits_consumed
        if diff > 0:
            # Refund the difference
            brand_result = await db.execute(select(Brand).where(Brand.id == txn.brand_id))
            brand = brand_result.scalars().first()
            if brand:
                brand.credits = (brand.credits or 0) + diff

            refund_txn = CreditTransaction(
                user_id=txn.user_id,
                brand_id=txn.brand_id,
                transaction_type="refund",
                amount=diff,
                description=f"Partial refund for generation {generation_id}",
                reference_id=generation_id,
                status="completed",
            )
            db.add(refund_txn)

    await db.commit()
    return {"status": "completed", "generation_id": generation_id}


@router.post("/generations/{generation_id}/fail")
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
    result = await db.execute(
        select(CreditTransaction).where(
            CreditTransaction.reference_id == generation_id,
            CreditTransaction.status == "pending",
        )
    )
    txn = result.scalars().first()
    if not txn:
        raise HTTPException(status_code=404, detail="Pending transaction not found")

    # Refund credits to brand
    brand_result = await db.execute(select(Brand).where(Brand.id == txn.brand_id))
    brand = brand_result.scalars().first()
    if brand:
        brand.credits = (brand.credits or 0) + abs(txn.amount)

    # Mark transaction as refunded
    txn.status = "refunded"
    txn.description = f"Refund - generation failed: {payload.reason or 'unknown'} - {generation_id}"

    refund_txn = CreditTransaction(
        user_id=txn.user_id,
        brand_id=txn.brand_id,
        transaction_type="refund",
        amount=abs(txn.amount),
        description=f"Generation failed refund - {generation_id}",
        reference_id=generation_id,
        status="completed",
    )
    db.add(refund_txn)
    await db.commit()

    return {"status": "refunded", "generation_id": generation_id, "credits_refunded": abs(txn.amount)}
