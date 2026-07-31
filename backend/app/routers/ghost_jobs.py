from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, User, GhostJob, GhostJobAsset, GhostOutput, CreditTransaction
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/ghost-jobs", tags=["Ghost Studio"])

# ========================== Credit Costs ==========================

RESOLUTION_CREDITS = {
    "1K": 2,
    "2K": 4,
    "4K": 7,
}

# ========================== Schemas ==============================

class GhostJobCreate(BaseModel):
    brand_id: int
    product_hint: Optional[str] = None
    garment_type: Optional[str] = "dress"
    view: Optional[str] = "front"
    aspect_ratio: Optional[str] = "3:4"
    resolution: Optional[str] = "2K"
    preserve_print: bool = True
    preserve_seams: bool = True
    generation_mode: Optional[str] = "studio"


# ========================== Endpoints ============================

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ghost_job(
    payload: GhostJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new ghost mannequin generation job."""
    # Check credits
    credits_needed = RESOLUTION_CREDITS.get(payload.resolution, 4)
    if (current_user.credits or 0) < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {credits_needed}, have {current_user.credits or 0}."
        )

    # Deduct credits
    current_user.credits = (current_user.credits or 0) - credits_needed

    # Create job
    job = GhostJob(
        user_id=current_user.id,
        brand_id=payload.brand_id,
        status="queued",
        product_hint=payload.product_hint,
        garment_type=payload.garment_type,
        view=payload.view,
        aspect_ratio=payload.aspect_ratio,
        resolution=payload.resolution,
        preserve_print=payload.preserve_print,
        preserve_seams=payload.preserve_seams,
        generation_mode=payload.generation_mode,
        credits_reserved=credits_needed,
        credits_consumed=0,
        progress=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Dispatch Celery task
    try:
        from app.worker import process_ghost_job
        process_ghost_job.delay(job.id)
    except Exception as e:
        print(f"[GhostJob] Celery dispatch failed: {e}")

    return {
        "job_id": job.id,
        "status": job.status,
        "credits_reserved": credits_needed,
        "estimated_time": "~45 sec" if payload.generation_mode == "studio" else "~15 sec",
    }


@router.get("/{job_id}")
async def get_ghost_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ghost job status and progress."""
    result = await db.execute(select(GhostJob).where(GhostJob.id == job_id, GhostJob.user_id == current_user.id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ghost job not found.")

    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "garment_type": job.garment_type,
        "resolution": job.resolution,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
    }


@router.post("/{job_id}/retry")
async def retry_ghost_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed ghost job."""
    result = await db.execute(select(GhostJob).where(GhostJob.id == job_id, GhostJob.user_id == current_user.id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ghost job not found.")
    if job.status not in ("failed",):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot retry job with status: {job.status}")

    job.status = "queued"
    job.progress = 0
    job.error_message = None
    await db.commit()

    try:
        from app.worker import process_ghost_job
        process_ghost_job.delay(job.id)
    except Exception as e:
        print(f"[GhostJob] Retry dispatch failed: {e}")

    return {"job_id": job.id, "status": "queued"}


@router.post("/{job_id}/cancel")
async def cancel_ghost_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an active ghost job."""
    result = await db.execute(select(GhostJob).where(GhostJob.id == job_id, GhostJob.user_id == current_user.id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ghost job not found.")
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot cancel job with status: {job.status}")

    job.status = "cancelled"
    # Refund credits
    current_user.credits = (current_user.credits or 0) + job.credits_reserved
    await db.commit()

    return {"job_id": job.id, "status": "cancelled", "credits_refunded": job.credits_reserved}


@router.get("/{job_id}/outputs")
async def get_ghost_job_outputs(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get completed ghost job outputs."""
    result = await db.execute(select(GhostJob).where(GhostJob.id == job_id, GhostJob.user_id == current_user.id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ghost job not found.")

    outputs_result = await db.execute(select(GhostOutput).where(GhostOutput.job_id == job_id))
    outputs = outputs_result.scalars().all()

    return {
        "job_id": job.id,
        "status": job.status,
        "outputs": [
            {
                "id": o.id,
                "output_url": o.output_url,
                "quality_score": o.quality_score,
                "fidelity_status": o.fidelity_status,
            }
            for o in outputs
        ]
    }
