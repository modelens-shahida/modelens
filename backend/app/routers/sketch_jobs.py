from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, User, SketchJob, SketchJobReference, SketchOutput, Brand, BrandMember
from app.middleware.auth import get_current_user
from app.worker import process_sketch_job

router = APIRouter(prefix="/api/v1/sketch-jobs", tags=["Sketch Studio"])

# ========================== Credit Costs ==========================

MODE_CREDITS = {
    "fast_draft": 1,
    "studio_quality": 5,
}

# ========================== Schemas ==============================

class SketchJobCreate(BaseModel):
    brand_id: Optional[int] = None
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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new sketch-to-image job supporting both JSON and FormData."""
    import os
    import uuid
    from app.services.storage import storage_service

    content_type = request.headers.get("content-type", "")
    references_to_create = []

    if "multipart/form-data" in content_type:
        form = await request.form()
        brand_id_val = form.get("brand_id")
        brand_id = int(brand_id_val) if brand_id_val else None
        product_hint = form.get("product_description") or form.get("product_hint")
        material_description = form.get("material_description")
        model_brief = form.get("model_brief")
        background_brief = form.get("background_brief")
        output_mode = form.get("output_mode") or "ON_MODEL"
        resolution = form.get("resolution") or "2K"
        aspect_ratio = form.get("aspect_ratio") or "3:4"
        generation_mode = form.get("model_tier") or form.get("generation_mode") or "studio_quality"

        # Parse and save files
        for key in ["sketches", "fabric_refs", "print_refs", "construction_refs"]:
            # Map frontend keys to DB reference types
            ref_type = "sketch"
            if key == "fabric_refs":
                ref_type = "fabric"
            elif key == "print_refs":
                ref_type = "print"
            elif key == "construction_refs":
                ref_type = "construction"

            uploaded_files = form.getlist(key)
            for file in uploaded_files:
                if file and file.filename:
                    filename = file.filename
                    file_ext = os.path.splitext(filename)[1]
                    unique_filename = f"{uuid.uuid4()}{file_ext}"
                    file_bytes = await file.read()
                    storage_path = storage_service.save_file_bytes(unique_filename, file_bytes)
                    references_to_create.append({
                        "reference_type": ref_type,
                        "image_path": storage_path,
                    })
    else:
        json_data = await request.json()
        payload = SketchJobCreate(**json_data)
        brand_id = payload.brand_id
        product_hint = payload.product_hint
        material_description = payload.material_description
        model_brief = payload.model_brief
        background_brief = payload.background_brief
        output_mode = payload.output_mode
        resolution = payload.resolution
        aspect_ratio = payload.aspect_ratio
        generation_mode = payload.generation_mode

        for ref_path in (payload.reference_image_paths or []):
            references_to_create.append({
                "reference_type": "sketch",
                "image_path": ref_path,
            })

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

    credits_needed = MODE_CREDITS.get(generation_mode, 5)

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
        brand_id=brand_id,
        status="queued",
        product_hint=product_hint,
        material_description=material_description,
        model_brief=model_brief,
        background_brief=background_brief,
        output_mode=output_mode,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        generation_mode=generation_mode,
        credits_reserved=credits_needed,
        credits_consumed=0,
        progress=0,
    )
    db.add(job)
    await db.flush()

    # Add reference images
    for ref_data in references_to_create:
        ref = SketchJobReference(
            job_id=job.id,
            reference_type=ref_data["reference_type"],
            image_path=ref_data["image_path"],
        )
        db.add(ref)

    await db.commit()
    await db.refresh(job)

    # Dispatch Celery task
    try:
        process_sketch_job.delay(job.id)
    except Exception as e:
        print(f"[SketchJob] Celery dispatch failed: {e}")

    return {
        "job_id": job.id,
        "status": job.status,
        "generation_mode": job.generation_mode,
        "credits_reserved": credits_needed,
        "estimated_time": "~15 sec" if generation_mode == "fast_draft" else "~45 sec",
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
        process_sketch_job.delay(job.id)
    except Exception as e:
        print(f"[SketchJob] Retry dispatch failed: {e}")

    return {"job_id": job.id, "status": "queued"}
