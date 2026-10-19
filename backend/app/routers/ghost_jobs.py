from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from datetime import datetime

from app.models.db import get_db, Asset, User, GhostJob, GhostJobAsset, GhostOutput
from app.middleware.auth import check_brand_asset, check_brand_role, get_current_user
from app.worker import process_ghost_job
from app.api_docs import error_responses
from app.services.job_access import require_readable
from app.services.job_images import is_image
from app.services.job_refunds import refund_job
from app.routers.body_parsing import parse_body, read_form_or_json

router = APIRouter(prefix="/api/v1/ghost-jobs", tags=["Ghost Studio"])

# ========================== Credit Costs ==========================

RESOLUTION_CREDITS = {
    "1K": 2,
    "2K": 4,
    "4K": 7,
}

# Creating ghost jobs spends credits for a brand: owner, or member with editor+.
GHOST_ROLE = "editor"

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
    image_key: Optional[str] = Field(
        None, description="`storage_path` of the garment image, as returned by `POST /api/v1/assets`."
    )
    asset_id: Optional[int] = Field(
        None, description="Id of the garment image asset (`POST /api/v1/assets`); used instead of `image_key` if set."
    )


SINGLE_IMAGE_REQUIRED = (
    "A garment image is required: upload it as the `image` file (multipart), or upload it with "
    "POST /api/v1/assets and send its storage_path as image_key (or its asset_id)."
)
SINGLE_IMAGE_INVALID = "The `image` file is not a JPEG, PNG, WebP or HEIC image."


async def _single_job_image(db: AsyncSession, brand_id: int, file, image_key: Optional[str],
                            asset_id: Optional[int]):
    """(uploaded bytes, uploaded filename, brand asset): the single job's garment image, validated
    before anything is charged or written. 422 when there is none or it is not a usable image;
    an `image_key`/`asset_id` follows the batch route's rules (an image asset of this brand)."""
    if file is not None and not isinstance(file, str):
        filename = file.filename or ""
        data = await file.read()
        if not filename.lower().endswith(BATCH_IMAGE_EXTENSIONS) or not data or not is_image(data):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=SINGLE_IMAGE_INVALID)
        return data, filename, None
    if file is not None or (asset_id is None and not image_key):  # a text field named image is not a file
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=SINGLE_IMAGE_REQUIRED)
    item = GhostJobBatchItem(image_key=image_key, asset_id=asset_id)
    [asset] = await _batch_item_assets(db, brand_id, [item], label=lambda index: "")
    return None, None, asset


@router.get(
    "/views",
    summary="Get ghost mannequin views",
    description=(
        "Get available ghost mannequin views.\n"
        "\n"
        "No authentication required."
    ),
    response_description="Available ghost mannequin views.",
    operation_id="get_ghost_views",
)
async def get_ghost_views():
    """Get available ghost mannequin views."""
    return {"views": ["front", "back", "side", "flatlay"]}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a ghost mannequin job",
    description=(
        "Create a new ghost mannequin generation job supporting both JSON and FormData. `brand_id` is required "
        "(else 422); the caller must own the brand or be a member with at least the editor role (else 403), "
        "and an unknown brand returns 404. Nothing is stored, queued or charged when the request is rejected.\n"
        "\n"
        "The garment image is required: the `image` file (multipart; JPEG, PNG, WebP or HEIC), or an image "
        "asset of the same brand uploaded first with `POST /api/v1/assets` and referenced by `image_key` (its "
        "`storage_path`) or `asset_id`, as in the batch route. No image, or one that is not such an image, is a "
        "422 before any credits are charged or anything is written."
    ),
    response_description="The created ghost job with reserved credits.",
    operation_id="create_ghost_job",
    responses=error_responses(401, 402, 403, 404, 422),
)
async def create_ghost_job(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new ghost mannequin generation job supporting both JSON and FormData."""
    import os
    import uuid
    from app.services.storage import storage_service

    image_path = None
    file = None

    form, json_data = await read_form_or_json(request)
    if form is not None:
        brand_field = form.get("brand_id")
        payload = parse_body(GhostJobCreate, {"brand_id": brand_field} if brand_field not in (None, "") else {})
        brand_id = payload.brand_id
        product_hint = form.get("product_hint")
        garment_type = form.get("garment_type", "dress")
        view = form.get("view", "front")
        aspect_ratio = form.get("aspect_ratio", "3:4")
        resolution = form.get("resolution", "2K")
        preserve_print = form.get("preserve_print") != "false"
        preserve_seams = form.get("preserve_seams") != "false"
        generation_mode = form.get("generation_mode", "studio")

        file = form.get("image")
        image_key = form.get("image_key") or None
        asset_field = form.get("asset_id")
        asset_id = parse_body(GhostJobCreate, {"brand_id": brand_id, "asset_id": asset_field}).asset_id \
            if asset_field not in (None, "") else None
    else:
        payload = parse_body(GhostJobCreate, json_data)
        brand_id = payload.brand_id
        product_hint = payload.product_hint
        garment_type = payload.garment_type
        view = payload.view
        aspect_ratio = payload.aspect_ratio
        resolution = payload.resolution
        preserve_print = payload.preserve_print
        preserve_seams = payload.preserve_seams
        generation_mode = payload.generation_mode
        image_key, asset_id = payload.image_key, payload.asset_id

    await check_brand_role(brand_id, current_user, db, minimum_role=GHOST_ROLE)

    # The garment image: required and validated before any charge or write (422 otherwise).
    file_bytes, filename, image_asset = await _single_job_image(db, brand_id, file, image_key, asset_id)

    # Check credits
    credits_needed = RESOLUTION_CREDITS.get(resolution, 4)
    if (current_user.credits or 0) < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {credits_needed}, have {current_user.credits or 0}."
        )

    if file_bytes is not None:
        file_ext = os.path.splitext(filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        image_path = storage_service.save_file_bytes(unique_filename, file_bytes)
    else:
        image_path = image_asset.storage_path

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

    # The garment image: the upload, or the brand asset it references (linked like a batch item's)
    db.add(GhostJobAsset(job_id=job.id, asset_id=image_asset.id if image_asset else None, image_path=image_path))

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


@router.get(
    "/{job_id}",
    summary="Get a ghost mannequin job",
    description="Get ghost job status and progress. Members of the job's brand (any role) and platform admins "
                "only; anyone else gets the same 404 as an unknown id.",
    response_description="Ghost job status and progress.",
    operation_id="get_ghost_job",
    responses=error_responses(401, 404, 422),
)
async def get_ghost_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ghost job status and progress."""
    result = await db.execute(select(GhostJob).where(GhostJob.id == job_id))
    job = await require_readable(db, current_user, result.scalars().first(), "Ghost job not found.")

    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "garment_type": job.garment_type,
        "resolution": job.resolution,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
    }


@router.post(
    "/{job_id}/retry",
    summary="Retry a ghost mannequin job",
    description="Retry a failed ghost job.",
    response_description="The ghost job re-queued for processing.",
    operation_id="retry_ghost_job",
    responses=error_responses(401, 404, 409, 422),
)
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


@router.post(
    "/{job_id}/cancel",
    summary="Cancel a ghost mannequin job",
    description="Cancel an active ghost job.",
    response_description="The cancelled ghost job.",
    operation_id="cancel_ghost_job",
    responses=error_responses(401, 404, 409, 422),
)
async def cancel_ghost_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an active ghost job."""
    # Locked: a second cancel or the worker's failure handler waits, then sees the new status.
    result = await db.execute(select(GhostJob).where(GhostJob.id == job_id, GhostJob.user_id == current_user.id)
                              .with_for_update().execution_options(populate_existing=True))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ghost job not found.")
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot cancel job with status: {job.status}")

    job.status = "cancelled"
    refunded = await refund_job(db, "ghost_job", job, "cancelled")  # at most once per job
    await db.commit()

    return {"job_id": job.id, "status": "cancelled", "credits_refunded": refunded}


@router.get(
    "/{job_id}/outputs",
    summary="Get ghost mannequin job outputs",
    description="Get completed ghost job outputs. Members of the job's brand (any role) and platform admins "
                "only; anyone else gets the same 404 as an unknown id.",
    response_description="Output assets of the completed ghost job.",
    operation_id="get_ghost_job_outputs",
    responses=error_responses(401, 404, 422),
)
async def get_ghost_job_outputs(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get completed ghost job outputs."""
    result = await db.execute(select(GhostJob).where(GhostJob.id == job_id))
    job = await require_readable(db, current_user, result.scalars().first(), "Ghost job not found.")

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
    image_key: Optional[str] = Field(
        None, description="`storage_path` of the item's image, as returned by `POST /api/v1/assets`."
    )
    asset_id: Optional[int] = Field(
        None, description="Id of the item's image asset (`POST /api/v1/assets`); used instead of `image_key` if set."
    )


# Same formats the Ghost Studio uploader accepts.
BATCH_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")


async def _batch_item_assets(db: AsyncSession, brand_id: int, items,
                             label=lambda index: f"jobs[{index}]: ") -> List[Asset]:
    """The uploaded image asset of every batch item, in order; 422 naming every bad item.

    Each item must reference an image asset of ``brand_id`` (not deleted) by
    ``asset_id`` or ``image_key``. Assets of other brands are reported as not
    found, so the response never says whether they exist. Read-only.
    """
    ids = {item.asset_id for item in items if item.asset_id is not None}
    keys = {item.image_key for item in items if item.asset_id is None and item.image_key}
    by_id, by_key = {}, {}
    if ids or keys:
        conditions = []
        if ids:
            conditions.append(Asset.id.in_(ids))
        if keys:
            conditions.append(Asset.storage_path.in_(keys))
        rows = (await db.execute(
            select(Asset).where(Asset.brand_id == brand_id, Asset.deleted_at.is_(None), or_(*conditions))
            .order_by(Asset.id)
        )).scalars().all()
        by_id = {a.id: a for a in rows}
        for a in rows:
            by_key.setdefault(a.storage_path, a)

    assets, errors = [], []
    for index, item in enumerate(items):
        if item.asset_id is not None:
            asset, ref = by_id.get(item.asset_id), f"asset {item.asset_id}"
        elif item.image_key:
            asset, ref = by_key.get(item.image_key), "image_key"
        else:
            errors.append(label(index) + f"an image is required (upload it with POST /api/v1/assets and send "
                          "its storage_path as image_key).")
            continue
        if asset is None:
            errors.append(label(index) + f"{ref} was not found in this brand.")
            continue
        name = (asset.filename or asset.storage_path or "").lower()
        if (asset.asset_type or "").lower() != "image" or not name.endswith(BATCH_IMAGE_EXTENSIONS):
            errors.append(label(index) + f"{ref} is not a JPEG, PNG, WebP or HEIC image.")
            continue
        assets.append(asset)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=" ".join(errors))
    return assets


class GhostJobBatchCreate(BaseModel):
    brand_id: int
    jobs: List[GhostJobBatchItem] = Field(..., min_length=1, max_length=50)


# ========================== Batch Endpoint =======================

@router.post(
    "/batch",
    status_code=status.HTTP_201_CREATED,
    summary="Create a batch of ghost mannequin jobs",
    description=(
        "Create a batch of ghost mannequin generation jobs atomically. The caller must own `brand_id` or be a "
        "member with at least the editor role (else 403); an unknown brand returns 404.\n"
        "\n"
        "Every item needs its garment image, uploaded first with `POST /api/v1/assets` to the same brand and "
        "referenced by `image_key` (the returned `storage_path`) or `asset_id`. It is linked to that item's job "
        "as a `GhostJobAsset`, like the image of a single ghost job. If any item has no image, or one that is "
        "not a JPEG/PNG/WebP/HEIC image asset of this brand, the whole request is rejected with 422 naming "
        "each item, before any credits are charged or jobs created."
    ),
    response_description="The created ghost jobs.",
    operation_id="create_ghost_job_batch",
    responses=error_responses(400, 401, 402, 403, 404, 422),
)
async def create_ghost_job_batch(
    payload: GhostJobBatchCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a batch of ghost mannequin generation jobs atomically."""
    await check_brand_role(payload.brand_id, current_user, db, minimum_role=GHOST_ROLE)
    if not payload.jobs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one job is required.")

    # Validate every item's image before charging or writing anything.
    item_assets = await _batch_item_assets(db, payload.brand_id, payload.jobs)

    # Calculate total credits needed
    total_credits = sum(RESOLUTION_CREDITS.get(job.resolution, 4) for job in payload.jobs)

    # Single atomic credit check
    if (current_user.credits or 0) < total_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {total_credits}, have {current_user.credits or 0}."
        )

    try:
        # Deduct credits atomically
        current_user.credits = (current_user.credits or 0) - total_credits

        # Create all GhostJob records, each with its image linked as on a single job.
        # One commit: if anything fails, no credits are deducted and no rows remain.
        created_jobs = []
        for job_config, asset in zip(payload.jobs, item_assets):
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
            await db.flush()
            db.add(GhostJobAsset(job_id=job.id, asset_id=asset.id, image_path=asset.storage_path))
            created_jobs.append((job, credits_for_job))

        await db.commit()
    except Exception:
        # Nothing is charged and no job or image link is left if any step fails.
        await db.rollback()
        raise

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

# ========================== Volumetric Ghost Endpoint ===========

class GhostVolumetricRequest(BaseModel):
    brand_id: int
    source_asset_id: Optional[int] = None
    garment_type: Optional[str] = "dress"
    neckline_type: Optional[str] = "round"
    views: Optional[List[str]] = ["FRONT", "BACK", "INNER_COLLAR"]
    resolution: Optional[str] = "2K"
    preserve_print: bool = True
    preserve_seams: bool = True
    alpha_mask: bool = True
    ambient_occlusion: bool = True
    generation_mode: Optional[str] = "studio_quality"


@router.post(
    "/volumetric",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a volumetric ghost mannequin job",
    description=(
        "Submit a 3D volumetric ghost mannequin job. The caller must own `brand_id` or be a member with at "
        "least the editor role (else 403); an unknown brand returns 404. `source_asset_id` must be an asset "
        "of that brand (else 404)."
    ),
    response_description="The volumetric ghost job was accepted and queued.",
    operation_id="create_volumetric_ghost_job",
    responses=error_responses(400, 401, 402, 403, 404, 422),
)
async def create_volumetric_ghost_job(
    payload: GhostVolumetricRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a 3D volumetric ghost mannequin job."""
    from app.services.ghost_volumetric_service import ghost_volumetric_service

    await check_brand_role(payload.brand_id, current_user, db, minimum_role=GHOST_ROLE)
    if payload.source_asset_id is not None:
        await check_brand_asset(payload.source_asset_id, payload.brand_id, db)

    try:
        workflow_params = ghost_volumetric_service.build_workflow_params(
            views=payload.views,
            resolution=payload.resolution,
            garment_type=payload.garment_type,
            neckline_type=payload.neckline_type,
            preserve_print=payload.preserve_print,
            preserve_seams=payload.preserve_seams,
            alpha_mask=payload.alpha_mask,
            ambient_occlusion=payload.ambient_occlusion,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Credit check
    credits_needed = RESOLUTION_CREDITS.get(payload.resolution, 4) * len(payload.views)
    if (current_user.credits or 0) < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {credits_needed}, have {current_user.credits or 0}."
        )
    current_user.credits = (current_user.credits or 0) - credits_needed

    try:
        from app.worker import run_volumetric_ghost_job
        task = run_volumetric_ghost_job.delay(
            brand_id=payload.brand_id,
            user_id=current_user.id,
            source_asset_id=payload.source_asset_id,
            workflow_params=workflow_params,
            generation_mode=payload.generation_mode,
        )
        task_id = task.id if task else f"mock_ghost3d_{payload.brand_id}"
    except Exception as e:
        print(f"[Ghost3D] Celery dispatch failed: {e}")
        task_id = f"mock_ghost3d_{payload.brand_id}"

    await db.commit()

    return {
        "task_id": task_id,
        "status": "queued",
        "views": payload.views,
        "resolution": payload.resolution,
        "credits_reserved": credits_needed,
        "workflow_id": "WF-GHOST-001",
    }


@router.get(
    "/views",
    summary="List ghost mannequin views",
    description=(
        "List available ghost mannequin views.\n"
        "\n"
        "**Note:** the same method and path is registered earlier as `get_ghost_views`, which handles every request. This handler is unreachable, so it is hidden from the schema."
    ),
    response_description="Available ghost mannequin views.",
    operation_id="list_ghost_views",
    responses=error_responses(401),
    include_in_schema=False,
)
async def list_ghost_views(
    current_user: User = Depends(get_current_user),
):
    """List available ghost mannequin views."""
    from app.services.ghost_volumetric_service import ghost_volumetric_service, RESOLUTION_OPTIONS
    return {
        "views": ghost_volumetric_service.list_views(),
        "resolutions": RESOLUTION_OPTIONS,
    }
