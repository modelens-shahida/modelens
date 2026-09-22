from fastapi import APIRouter, HTTPException, Depends, Header, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, User, Brand, CreditTransaction
from app.middleware.auth import get_current_user
from app.services.credits_sync_service import (
    credits_sync_service,
    estimate_credits,
    estimate_batch_credits,
    CREDIT_RATES,
)
from app.config import settings

router = APIRouter(prefix="/api/v1", tags=["Generation Credits Sync"])

INTERNAL_SECRET = getattr(settings, "INTERNAL_CALLBACK_SECRET", "modelens-internal-secret")


def verify_internal_secret(x_internal_secret: Optional[str] = Header(None)):
    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Invalid internal secret.")
    return x_internal_secret


# ========================== Schemas ==============================

class CreditEstimateRequest(BaseModel):
    quality_mode: str = "STUDIO_QUALITY"
    resolution: str = "2K"
    output_count: int = 1
    angle_count: Optional[int] = None


class ReserveCreditsRequest(BaseModel):
    brand_id: int
    amount: int
    generation_id: str
    description: str = "Generation credit reservation"


class CompleteCallbackRequest(BaseModel):
    generation_id: str
    metadata: Optional[Dict[str, Any]] = None


class FailCallbackRequest(BaseModel):
    generation_id: str
    reason: str = "Generation failed"
    metadata: Optional[Dict[str, Any]] = None


# ========================== Credit Balance =======================

@router.get("/credits/balance")
async def get_credit_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current credit balance for the user's brand."""
    brand_id = getattr(current_user, 'brand_id', None)
    if not brand_id:
        raise HTTPException(status_code=400, detail="No brand associated with user.")

    balance = await credits_sync_service.get_brand_credits(brand_id, db)
    return {
        "brand_id": brand_id,
        "balance": balance,
        "currency": "credits",
    }


@router.get("/credits/rates")
async def get_credit_rates(
    current_user: User = Depends(get_current_user),
):
    """Get credit rates for all quality modes and resolutions."""
    return {
        "rates": CREDIT_RATES,
        "ghost_studio": {
            "1K": 2,
            "2K": 4,
            "4K": 7,
        },
        "batch_discount": "No discount — per angle rate applies",
    }


# ========================== Credit Estimation ====================

@router.post("/credits/estimate")
async def estimate_generation_credits(
    payload: CreditEstimateRequest,
    current_user: User = Depends(get_current_user),
):
    """Estimate credits before generation."""
    if payload.angle_count:
        total = estimate_batch_credits(
            angle_count=payload.angle_count,
            quality_mode=payload.quality_mode,
            resolution=payload.resolution,
        )
    else:
        total = estimate_credits({
            "quality_mode": payload.quality_mode,
            "resolution": payload.resolution,
            "outputCount": payload.output_count,
        })

    return {
        "estimated_credits": total,
        "quality_mode": payload.quality_mode,
        "resolution": payload.resolution,
        "output_count": payload.output_count,
        "angle_count": payload.angle_count,
        "breakdown": {
            "per_output": total // (payload.angle_count or payload.output_count),
            "total": total,
        }
    }


# ========================== Credit Check =========================

@router.post("/credits/check")
async def check_credits(
    payload: CreditEstimateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if brand has sufficient credits before generation."""
    brand_id = getattr(current_user, 'brand_id', None)
    if not brand_id:
        raise HTTPException(status_code=400, detail="No brand associated with user.")

    if payload.angle_count:
        required = estimate_batch_credits(
            angle_count=payload.angle_count,
            quality_mode=payload.quality_mode,
            resolution=payload.resolution,
        )
    else:
        required = estimate_credits({
            "quality_mode": payload.quality_mode,
            "resolution": payload.resolution,
            "outputCount": payload.output_count,
        })

    check = await credits_sync_service.check_sufficient_credits(brand_id, required, db)
    return {
        "sufficient": check["sufficient"],
        "balance": check["balance"],
        "required": required,
        "shortfall": check["shortfall"],
    }


# ========================== Internal Callbacks ===================

@router.post("/internal/generations/{generation_id}/complete")
async def complete_generation_callback(
    generation_id: str,
    payload: CompleteCallbackRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_internal_secret),
):
    """Internal callback: finalize credits on generation success."""
    result = await credits_sync_service.finalize_credits(generation_id, db)
    return result


@router.post("/internal/generations/{generation_id}/fail")
async def fail_generation_callback(
    generation_id: str,
    payload: FailCallbackRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_internal_secret),
):
    """Internal callback: refund credits on generation failure."""
    result = await credits_sync_service.refund_credits(
        generation_id=generation_id,
        reason=payload.reason,
        db=db,
    )
    return result


# ========================== Billing Layout Fix ===================

@router.get("/billing/summary")
async def get_billing_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get billing summary for dashboard TopBar."""
    brand_id = getattr(current_user, 'brand_id', None)
    if not brand_id:
        return {"balance": 0, "pending": 0, "this_month": 0}

    balance = await credits_sync_service.get_brand_credits(brand_id, db)

    # Pending transactions
    pending = await db.execute(
        select(CreditTransaction).where(
            CreditTransaction.brand_id == brand_id,
            CreditTransaction.status == "pending",
        )
    )
    pending_txns = pending.scalars().all()
    pending_amount = sum(abs(t.amount) for t in pending_txns)

    # This month usage
    from sqlalchemy import func, extract
    now = datetime.utcnow()
    monthly = await db.execute(
        select(CreditTransaction).where(
            CreditTransaction.brand_id == brand_id,
            CreditTransaction.status == "completed",
            CreditTransaction.amount < 0,
            extract('month', CreditTransaction.created_at) == now.month,
            extract('year', CreditTransaction.created_at) == now.year,
        )
    )
    monthly_txns = monthly.scalars().all()
    monthly_used = sum(abs(t.amount) for t in monthly_txns)

    return {
        "balance": balance,
        "pending": pending_amount,
        "this_month_used": monthly_used,
        "currency": "credits",
    }
