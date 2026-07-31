from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, User, SketchJob, SketchJobReference, SketchOutput
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/sketch-jobs", tags=["Sketch Studio"])

# ========================== Credit Costs ==========================

MODE_CREDITS = {
    "fast_draft": 1,
    "studio_quality": 5,
}

# ========================== Schemas ==============================

class SketchJobCreate(BaseModel):
    brand_id: int
    product_hint: Optional[str] = None
    material_description: Optional[str] = None
    model_brief: Optional[str] = None
    background_brief: Optional[str] = None
    output_mode: Optional[str] = "ON_MODEL"
    resolution: Optional[str] = "2K"
    aspect_ratio: Optional[str] = "3:4"
    generation_mode: Optional[str] = "studio_quality"
    reference_image_paths: Optional[List[str]] = []


# ========================== Endpoints ============================

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_sketch_job(
    payload: SketchJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new sketch-to-image job."""
    credits_needed = MODE_CREDITS.get(payload.generation_mode, 5)

    if (current_user.credits or 0) < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {credits_needed}, have {current_user.credits or 0}."
        )

    # Deduct credits
    current_user.credits = (current_user.credits or 0) - credits_needed

    # Create job
    job = SketchJob(
        user_id=current_user.id,
        brand_id=payload.brand_id,
        status="queued",
        product_hint=payload.product_hint,
        material_description=payload.material_description,
        model_brief=payload.model_brief,
        background_brief=payload.background_brief,
        output_mode=payload.output_mode,
        resolution=payload.resolution,
        aspect_ratio=payload.aspect_ratio,
        generation_mode=payload.generation_mode,
        credits_reserved=credits_needed,
        credits_consumed=0,
        progress=0,
    )
    db.add(job)
    await db.flush()

    # Add reference images
    for ref_path in (payload.reference_image_paths or []):
        ref = SketchJobReference(
            job_id=job.id,
            reference_type="sketch",
            image_path=ref_path,
        )
        db.add(ref)

    await db.commit()
    await db.refresh(job)

    # Dispatch Celery task
    try:
        from app.worker import process_sketch_job
        process_sketch_job.delay(job.id)
    except Exception as e:
        print(f"[SketchJob] Celery dispatch failed: {e}")

    return {
        "job_id": job.id,
        "status": job.status,
        "generation_mode": job.generation_mode,
        "credits_reserved": credits_needed,
        "estimated_time": "~15 sec" if payload.generation_mode == "fast_draft" else "~45 sec",
    }


@router.get("/{job_id}")
async def get_sketch_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get sketch job status, progress, and outputs."""
    result = await db.execute(
        select(SketchJob).where(SketchJob.id == job_id, SketchJob.user_id == current_user.id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sketch job not found.")

    refs_result = await db.execute(select(SketchJobReference).where(SketchJobReference.job_id == job_id))
    refs = refs_result.scalars().all()

    outputs_result = await db.execute(select(SketchOutput).where(SketchOutput.job_id == job_id))
    outputs = outputs_result.scalars().all()

    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "generation_mode": job.generation_mode,
        "output_mode": job.output_mode,
        "resolution": job.resolution,
        "error_message": job.error_message,
        "references": [{"id": r.id, "image_path": r.image_path, "reference_type": r.reference_type} for r in refs],
        "outputs": [{"id": o.id, "output_url": o.output_url, "quality_score": o.quality_score} for o in outputs],
        "created_at": job.created_at.isoformat(),
    }


@router.post("/{job_id}/cancel")
async def cancel_sketch_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel active/queued sketch job and refund credits."""
    result = await db.execute(
        select(SketchJob).where(SketchJob.id == job_id, SketchJob.user_id == current_user.id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sketch job not found.")
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot cancel job with status: {job.status}")

    job.status = "cancelled"
    current_user.credits = (current_user.credits or 0) + job.credits_reserved
    await db.commit()

    return {"job_id": job.id, "status": "cancelled", "credits_refunded": job.credits_reserved}


@router.post("/{job_id}/retry")
async def retry_sketch_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed sketch job."""
    result = await db.execute(
        select(SketchJob).where(SketchJob.id == job_id, SketchJob.user_id == current_user.id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sketch job not found.")
    if job.status != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot retry job with status: {job.status}")

    job.status = "queued"
    job.progress = 0
    job.error_message = None
    await db.commit()

    try:
        from app.worker import process_sketch_job
        process_sketch_job.delay(job.id)
    except Exception as e:
        print(f"[SketchJob] Retry dispatch failed: {e}")

    return {"job_id": job.id, "status": "queued"}
