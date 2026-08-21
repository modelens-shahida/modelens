from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, User, GhostJob, GhostJobAsset, GhostOutput, CreditTransaction, Brand, BrandMember
from app.middleware.auth import get_current_user
from app.worker import process_ghost_job

router = APIRouter(prefix="/api/v1/ghost-jobs", tags=["Ghost Studio"])

# ========================== Credit Costs ==========================

RESOLUTION_CREDITS = {
    "1K": 2,
    "2K": 4,
    "4K": 7,
}

# ========================== Schemas ==============================

class GhostJobCreate(BaseModel):
    brand_id: Optional[int] = None
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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new ghost mannequin generation job supporting both JSON and FormData."""
    import os
    import uuid
    from app.services.storage import storage_service

    content_type = request.headers.get("content-type", "")
    image_path = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        brand_id_val = form.get("brand_id")
        brand_id = int(brand_id_val) if brand_id_val else None
        product_hint = form.get("product_hint")
        garment_type = form.get("garment_type", "dress")
        view = form.get("view", "front")
        aspect_ratio = form.get("aspect_ratio", "3:4")
        resolution = form.get("resolution", "2K")
        preserve_print = form.get("preserve_print") != "false"
        preserve_seams = form.get("preserve_seams") != "false"
        generation_mode = form.get("generation_mode", "studio")

        file = form.get("image")
        if file:
            filename = file.filename or "file.png"
            file_ext = os.path.splitext(filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_bytes = await file.read()
            image_path = storage_service.save_file_bytes(unique_filename, file_bytes)
    else:
        json_data = await request.json()
        payload = GhostJobCreate(**json_data)
        brand_id = payload.brand_id
        product_hint = payload.product_hint
        garment_type = payload.garment_type
        view = payload.view
        aspect_ratio = payload.aspect_ratio
        resolution = payload.resolution
        preserve_print = payload.preserve_print
        preserve_seams = payload.preserve_seams
        generation_mode = payload.generation_mode

    # Fallback to user's first brand if brand_id is missing or None
    if not brand_id:
        brand_query = select(Brand.id).where(Brand.owner_id == current_user.id).limit(1)
        brand_res = await db.execute(brand_query)
        brand_id = brand_res.scalar()
        if not brand_id:
            member_query = select(BrandMember.brand_id).where(BrandMember.user_id == current_user.id).limit(1)
            member_res = await db.execute(member_query)
            brand_id = member_res.scalar()
        if not brand_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active brand found for the user. Please create a brand first."
            )

    # Check credits
    credits_needed = RESOLUTION_CREDITS.get(resolution, 4)
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
        brand_id=brand_id,
        status="queued",
        product_hint=product_hint,
        garment_type=garment_type,
        view=view,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        preserve_print=preserve_print,
        preserve_seams=preserve_seams,
        generation_mode=generation_mode,
        credits_reserved=credits_needed,
        credits_consumed=0,
        progress=0,
    )
    db.add(job)
    await db.flush()

    if image_path:
        # Create GhostJobAsset record for the uploaded image
        job_asset = GhostJobAsset(
            job_id=job.id,
            image_path=image_path,
        )
        db.add(job_asset)

    await db.commit()
    await db.refresh(job)

    # Dispatch Celery task
    try:
        process_ghost_job.delay(job.id)
    except Exception as e:
        print(f"[GhostJob] Celery dispatch failed: {e}")

    return {
        "job_id": job.id,
        "status": job.status,
        "credits_reserved": credits_needed,
        "estimated_time": "~45 sec" if generation_mode == "studio" else "~15 sec",
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

# ========================== Batch Schema =========================

class GhostJobBatchItem(BaseModel):
    product_hint: Optional[str] = None
    garment_type: Optional[str] = "dress"
    view: Optional[str] = "front"
    aspect_ratio: Optional[str] = "3:4"
    resolution: Optional[str] = "2K"
    preserve_print: bool = True
    preserve_seams: bool = True
    generation_mode: Optional[str] = "studio"
    image_key: Optional[str] = None


class GhostJobBatchCreate(BaseModel):
    brand_id: int
    jobs: List[GhostJobBatchItem] = Field(..., min_length=1, max_length=50)


# ========================== Batch Endpoint =======================

@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def create_ghost_job_batch(
    payload: GhostJobBatchCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a batch of ghost mannequin generation jobs atomically."""
    if not payload.jobs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one job is required.")

    # Calculate total credits needed
    total_credits = sum(RESOLUTION_CREDITS.get(job.resolution, 4) for job in payload.jobs)

    # Single atomic credit check
    if (current_user.credits or 0) < total_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {total_credits}, have {current_user.credits or 0}."
        )

    # Deduct credits atomically
    current_user.credits = (current_user.credits or 0) - total_credits

    # Create all GhostJob records
    created_jobs = []
    for job_config in payload.jobs:
        credits_for_job = RESOLUTION_CREDITS.get(job_config.resolution, 4)
        job = GhostJob(
            user_id=current_user.id,
            brand_id=payload.brand_id,
            status="queued",
            product_hint=job_config.product_hint,
            garment_type=job_config.garment_type,
            view=job_config.view,
            aspect_ratio=job_config.aspect_ratio,
            resolution=job_config.resolution,
            preserve_print=job_config.preserve_print,
            preserve_seams=job_config.preserve_seams,
            generation_mode=job_config.generation_mode,
            credits_reserved=credits_for_job,
            credits_consumed=0,
            progress=0,
        )
        db.add(job)
        created_jobs.append((job, credits_for_job))

    await db.commit()

    # Dispatch Celery tasks in parallel
    queued_job_ids = []
    for job, _ in created_jobs:
        await db.refresh(job)
        queued_job_ids.append(job.id)
        try:
            from app.worker import process_ghost_job
            process_ghost_job.delay(job.id)
        except Exception as e:
            print(f"[GhostBatch] Celery dispatch failed for job {job.id}: {e}")

    return {
        "batch_size": len(queued_job_ids),
        "job_ids": queued_job_ids,
        "total_credits_reserved": total_credits,
        "status": "queued",
    }
