from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, User, SketchJob, SketchJobReference, SketchOutput, Brand, BrandMember
from app.middleware.auth import check_brand_role, get_current_user
from app.worker import process_sketch_job
from app.api_docs import error_responses
from app.services.job_refunds import refund_job
from app.services.sketch_availability import SKETCH_DISABLED_RESPONSE, require_sketch_jobs_enabled
from app.routers.body_parsing import parse_body, read_form_or_json
from app.services.input_paths import check_request_paths
from app.services.job_images import MAX_UPLOAD_BYTES, UPLOAD_TYPES, check_upload
from app.services.sketch_inputs import MAX_INPUT_IMAGES

router = APIRouter(prefix="/api/v1/sketch-jobs", tags=["Sketch Studio"])

# ========================== Credit Costs ==========================

MODE_CREDITS = {
    "fast_draft": 1,
    "studio_quality": 5,
}

# Form file fields -> reference type
UPLOAD_FIELDS = {"sketches": "sketch", "fabric_refs": "fabric", "print_refs": "print",
                 "construction_refs": "construction"}
SKETCH_REQUIRED = ("At least one sketch image is required: upload it as a `sketches` file (multipart), or "
                   "upload it with POST /api/v1/assets and send its storage_path in reference_image_paths.")

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
    reference_image_paths: Optional[List[str]] = Field(
        default_factory=list,
        description="Sketch images: `storage_path`s of image assets of the same brand (`POST /api/v1/assets`).",
    )


# ========================== Endpoints ============================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a sketch-to-image job",
    description=(
        "Create a new sketch-to-image job supporting both JSON and FormData. Without `brand_id` the caller's "
        "first brand is used. The caller must own the brand or be a member with at least the editor role "
        "(else 403); an unknown brand returns 404. Nothing is stored, queued or charged when rejected.\n"
        "\n"
        f"Images: at least one sketch, and at most {MAX_INPUT_IMAGES} images in all (sketches and references "
        "together). Multipart files (`sketches`, `fabric_refs`, `print_refs`, `construction_refs`) must each be "
        f"{UPLOAD_TYPES} (decoded, not judged by name or content type) of at most "
        f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB. JSON `reference_image_paths` must be `storage_path`s of image "
        "assets of the same brand; anything else (external URLs, other buckets, `..`, another brand's file) is "
        "reported as not found. Any bad image is a 422 naming the field and index, before anything is charged, "
        "stored, written or queued.\n"
        "\n"
        "**Disabled in production** while `SKETCH_JOBS_ENABLED` is off: answers 503 for every caller, "
        "platform admins included, before anything is stored, queued or charged."
    ),
    response_description="The created sketch job with reserved credits.",
    operation_id="create_sketch_job",
    responses={**error_responses(400, 401, 402, 403, 404, 422), **SKETCH_DISABLED_RESPONSE},
)
async def create_sketch_job(
    request: Request,
    current_user: User = Depends(require_sketch_jobs_enabled),
    db: AsyncSession = Depends(get_db),
):
    """Create a new sketch-to-image job supporting both JSON and FormData."""
    import uuid
    from app.services.storage import storage_service

    form, json_data = await read_form_or_json(request)
    uploads = []  # (label, reference type, uploaded file)
    paths = []    # storage paths of brand assets (JSON)

    if form is not None:
        brand_id_val = form.get("brand_id")
        brand_id = parse_body(SketchJobCreate, {"brand_id": brand_id_val}).brand_id if brand_id_val else None
        product_hint = form.get("product_description") or form.get("product_hint")
        material_description = form.get("material_description")
        model_brief = form.get("model_brief")
        background_brief = form.get("background_brief")
        output_mode = form.get("output_mode") or "ON_MODEL"
        resolution = form.get("resolution") or "2K"
        aspect_ratio = form.get("aspect_ratio") or "3:4"
        generation_mode = form.get("model_tier") or form.get("generation_mode") or "studio_quality"

        # Files are checked once the brand is authorized, and saved once everything is checked
        for key, ref_type in UPLOAD_FIELDS.items():
            for index, file in enumerate(form.getlist(key)):
                if isinstance(file, str) or file.filename:  # an empty file input sends a nameless part
                    uploads.append((f"{key}[{index}]", ref_type, file))
    else:
        payload = parse_body(SketchJobCreate, json_data)
        brand_id = payload.brand_id
        product_hint = payload.product_hint
        material_description = payload.material_description
        model_brief = payload.model_brief
        background_brief = payload.background_brief
        output_mode = payload.output_mode
        resolution = payload.resolution
        aspect_ratio = payload.aspect_ratio
        generation_mode = payload.generation_mode
        paths = payload.reference_image_paths or []

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
    await check_brand_role(brand_id, current_user, db, minimum_role="editor")

    # The images: counted, then each checked (ours and this brand's, or a real image upload),
    # all before any credits are charged or anything is stored, written or queued.
    count = len(uploads) + len(paths)
    if count > MAX_INPUT_IMAGES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"A sketch job takes at most {MAX_INPUT_IMAGES} images (sketches and "
                                   f"references together); this request has {count}.")
    if not paths and not any(ref_type == "sketch" for _, ref_type, _ in uploads):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=SKETCH_REQUIRED)
    await check_request_paths(db, brand_id, [(f"reference_image_paths[{i}]", p) for i, p in enumerate(paths)])
    extensions, errors = [], []
    for label, _, file in uploads:
        extension, problem = (None, "is not a file") if isinstance(file, str) else await check_upload(file)
        extensions.append(extension)
        if problem:
            errors.append(f"{label} {problem}.")
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=" ".join(errors))

    credits_needed = MODE_CREDITS.get(generation_mode, 5)

    if (current_user.credits or 0) < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {credits_needed}, have {current_user.credits or 0}."
        )

    references_to_create = [{"reference_type": "sketch", "image_path": p} for p in paths]
    for (_, ref_type, file), extension in zip(uploads, extensions):
        unique_filename = f"{uuid.uuid4()}{extension}"
        file_bytes = await file.read()
        storage_path = storage_service.save_file_bytes(unique_filename, file_bytes)
        references_to_create.append({
            "reference_type": ref_type,
            "image_path": storage_path,
        })

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


@router.get(
    "/{job_id}",
    summary="Get a sketch job",
    description="Get sketch job status, progress, and outputs.",
    response_description="Sketch job status, progress and outputs.",
    operation_id="get_sketch_job",
    responses=error_responses(401, 404, 422),
)
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


@router.post(
    "/{job_id}/cancel",
    summary="Cancel a sketch job",
    description="Cancel active/queued sketch job and refund credits.",
    response_description="The cancelled job; reserved credits are refunded.",
    operation_id="cancel_sketch_job",
    responses=error_responses(401, 404, 409, 422),
)
async def cancel_sketch_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel active/queued sketch job and refund credits."""
    # Locked: a second cancel or the worker's failure handler waits, then sees the new status.
    result = await db.execute(
        select(SketchJob).where(SketchJob.id == job_id, SketchJob.user_id == current_user.id)
        .with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sketch job not found.")
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot cancel job with status: {job.status}")

    job.status = "cancelled"
    refunded = await refund_job(db, "sketch_job", job, "cancelled")  # at most once per job
    await db.commit()

    return {"job_id": job.id, "status": "cancelled", "credits_refunded": refunded}


@router.post(
    "/{job_id}/retry",
    summary="Retry a sketch job",
    description="Retry a failed sketch job. Disabled in production (503) while `SKETCH_JOBS_ENABLED` is off.",
    response_description="The sketch job re-queued for processing.",
    operation_id="retry_sketch_job",
    responses={**error_responses(401, 404, 409, 422), **SKETCH_DISABLED_RESPONSE},
)
async def retry_sketch_job(
    job_id: int,
    current_user: User = Depends(require_sketch_jobs_enabled),
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
