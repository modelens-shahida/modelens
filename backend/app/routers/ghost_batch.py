from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from app.models.db import get_db, User, GhostJob
from app.middleware.auth import get_current_user
from app.services.credits_sync_service import credits_sync_service, estimate_credits

router = APIRouter(prefix="/api/v1/ghost", tags=["Ghost Studio Batch"])


# ========================== Credit Rates =========================

GHOST_CREDIT_RATES = {
    "1K": 2,
    "2K": 4,
    "4K": 7,
    "8K": 10,
    "default": 4,
}

GHOST_VOLUMETRIC_RATES = {
    "FRONT": 2,
    "BACK": 2,
    "INNER_COLLAR": 3,
    "TURNTABLE": 8,
}


# ========================== Schemas ==============================

class GhostViewRequest(BaseModel):
    view: str = Field(..., description="FRONT, BACK, INNER_COLLAR, TURNTABLE")
    resolution: str = "2K"


class GhostBatchItem(BaseModel):
    sku: str
    product_name: Optional[str] = None
    garment_type: Optional[str] = None
    views: List[GhostViewRequest] = [GhostViewRequest(view="FRONT")]


class GhostBatchRequest(BaseModel):
    items: List[GhostBatchItem]
    quality_mode: str = "STUDIO_QUALITY"
    preserve_print: bool = True
    preserve_construction: bool = True
    output_format: str = "PNG"
    transparent_background: bool = True
    project_name: Optional[str] = None


class GhostCreditEstimateRequest(BaseModel):
    items: List[GhostBatchItem]
    quality_mode: str = "STUDIO_QUALITY"


# ========================== Credit Estimation ====================

def estimate_ghost_batch_credits(
    items: List[GhostBatchItem],
    quality_mode: str = "STUDIO_QUALITY",
) -> Dict[str, Any]:
    """Estimate credits for ghost batch job."""
    total = 0
    breakdown = []

    for item in items:
        item_credits = 0
        for view in item.views:
            base = GHOST_CREDIT_RATES.get(view.resolution.upper(), GHOST_CREDIT_RATES["default"])
            volumetric_multiplier = 2 if view.view == "TURNTABLE" else 1
            view_credits = base * volumetric_multiplier
            item_credits += view_credits

        breakdown.append({
            "sku": item.sku,
            "views": len(item.views),
            "credits": item_credits,
        })
        total += item_credits

    return {
        "total_credits": total,
        "total_items": len(items),
        "breakdown": breakdown,
        "quality_mode": quality_mode,
    }


# ========================== Endpoints ============================

@router.post("/batch/estimate")
async def estimate_ghost_batch(
    payload: GhostCreditEstimateRequest,
    current_user: User = Depends(get_current_user),
):
    """Estimate credits for ghost batch job."""
    estimate = estimate_ghost_batch_credits(payload.items, payload.quality_mode)
    return estimate


@router.post("/batch/check")
async def check_ghost_batch_credits(
    payload: GhostCreditEstimateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pre-flight credit check for ghost batch job."""
    brand_id = getattr(current_user, 'brand_id', None)
    if not brand_id:
        raise HTTPException(status_code=400, detail="No brand associated with user.")

    estimate = estimate_ghost_batch_credits(payload.items, payload.quality_mode)
    required = estimate["total_credits"]

    check = await credits_sync_service.check_sufficient_credits(brand_id, required, db)
    return {
        "sufficient": check["sufficient"],
        "balance": check["balance"],
        "required": required,
        "shortfall": check["shortfall"],
        "breakdown": estimate["breakdown"],
    }


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def create_ghost_batch(
    payload: GhostBatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multi-garment ghost batch job with credit reservation."""
    brand_id = getattr(current_user, 'brand_id', None)
    if not brand_id:
        raise HTTPException(status_code=400, detail="No brand associated with user.")

    # Estimate credits
    estimate = estimate_ghost_batch_credits(payload.items, payload.quality_mode)
    total_credits = estimate["total_credits"]

    # Pre-flight credit check
    check = await credits_sync_service.check_sufficient_credits(brand_id, total_credits, db)
    if not check["sufficient"]:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_credits",
                "message": f"Insufficient credits. Required: {total_credits}, Available: {check['balance']}",
                "balance": check["balance"],
                "required": total_credits,
                "shortfall": check["shortfall"],
            }
        )

    job_id = str(uuid.uuid4())

    # Reserve credits
    await credits_sync_service.reserve_credits(
        brand_id=brand_id,
        user_id=current_user.id,
        amount=total_credits,
        generation_id=job_id,
        description=f"Ghost batch: {len(payload.items)} garments",
        db=db,
    )

    # Create ghost job
    ghost_job = GhostJob(
        job_id=job_id,
        user_id=current_user.id,
        brand_id=brand_id,
        status="queued",
        total_skus=len(payload.items),
        quality_mode=payload.quality_mode,
        meta={
            "batch_mode": True,
            "project_name": payload.project_name,
            "preserve_print": payload.preserve_print,
            "preserve_construction": payload.preserve_construction,
            "output_format": payload.output_format,
            "transparent_background": payload.transparent_background,
            "items": [item.dict() for item in payload.items],
            "credit_estimate": estimate,
        }
    )
    db.add(ghost_job)
    await db.commit()

    return {
        "job_id": job_id,
        "status": "queued",
        "total_items": len(payload.items),
        "total_credits_reserved": total_credits,
        "quality_mode": payload.quality_mode,
        "websocket_url": f"/api/v1/ws/ghost/{job_id}",
        "created_at": str(datetime.utcnow()),
    }


@router.get("/batch/{job_id}")
async def get_ghost_batch(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ghost batch job status."""
    result = await db.execute(
        select(GhostJob).where(GhostJob.job_id == job_id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Ghost job not found.")

    return {
        "job_id": job_id,
        "status": job.status,
        "total_items": job.total_skus,
        "completed": job.completed_skus or 0,
        "failed": job.failed_skus or 0,
        "quality_mode": job.quality_mode,
        "meta": job.meta,
        "created_at": str(job.created_at),
    }


@router.post("/batch/{job_id}/complete")
async def complete_ghost_batch(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Finalize credits on ghost batch completion."""
    result = await credits_sync_service.finalize_credits(job_id, db)
    return result


@router.post("/batch/{job_id}/fail")
async def fail_ghost_batch(
    job_id: str,
    reason: str = "Ghost generation failed",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Refund credits on ghost batch failure."""
    result = await credits_sync_service.refund_credits(
        generation_id=job_id,
        reason=reason,
        db=db,
    )
    return result


@router.get("/rates")
async def get_ghost_rates(
    current_user: User = Depends(get_current_user),
):
    """Get ghost studio credit rates."""
    return {
        "ghost_rates": GHOST_CREDIT_RATES,
        "volumetric_rates": GHOST_VOLUMETRIC_RATES,
        "note": "TURNTABLE = 2x base rate",
    }
