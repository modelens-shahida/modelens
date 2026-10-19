from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, User, CatalogJob, CatalogJobItem, Brand, BrandMember
from app.middleware.auth import check_brand_role, get_current_user
from app.services.catalog_availability import CATALOG_DISABLED_RESPONSE, require_catalog_jobs_enabled
from app.services.job_access import require_readable
from app.worker import process_catalog_job, process_catalog_item
from app.services.storage import storage_service
import uuid
from app.api_docs import error_responses
from app.services.job_refunds import refund_job
from app.routers.body_parsing import parse_body, read_form_or_json
from app.services.input_paths import check_request_paths
from app.services.job_images import MAX_UPLOAD_BYTES, UPLOAD_TYPES, check_upload

router = APIRouter(prefix="/api/v1/catalog-jobs", tags=["Catalog Studio"])

CREDITS_PER_SKU = {
    "fast_draft": 2,
    "studio_quality": 5,
}

class CatalogJobCreate(BaseModel):
    brand_id: int
    engine_mode: Optional[str] = "product_to_model"
    generation_mode: Optional[str] = "studio_quality"
    model_identity: Optional[str] = "Maya"
    pose: Optional[str] = "Catalog Standing"
    background: Optional[str] = "Soft Front Studio"
    aspect_ratio: Optional[str] = "4:5"
    resolution: Optional[str] = "2K"
    products: List[dict] = Field(
        default_factory=list,
        description="`{sku_tag, image_path}` per product; `image_path` is the `storage_path` of an image asset "
                    "of the same brand (`POST /api/v1/assets`).",
    )


class CatalogJobForm(BaseModel):
    brand_id: Optional[int] = None


@router.get(
    "/marketplaces",
    summary="Get supported marketplaces",
    description=(
        "Get supported marketplace channels.\n"
        "\n"
        "No authentication required."
    ),
    response_description="Supported marketplace channels.",
    operation_id="get_catalog_marketplaces",
)
async def get_marketplaces():
    """Get supported marketplace channels."""
    return {"marketplaces": ["shopify", "amazon", "myntra", "woocommerce"]}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a catalog job",
    description=(
        "Create a new catalog batch job supporting both JSON and FormData. Without `brand_id` (FormData) the "
        "caller's first brand is used. The caller must own the brand or be a member with at least the editor "
        "role (else 403); an unknown brand returns 404. Nothing is stored, queued or charged when rejected.\n"
        "\n"
        f"Product images: multipart `products` files must each be {UPLOAD_TYPES} (decoded, not judged by name "
        f"or content type) of at most {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. JSON `products[].image_path` must "
        "be the `storage_path` of an image asset of the same brand; anything else (missing, external URLs, other "
        "buckets, `..`, another brand's file) is reported as not found. Any bad image is a 422 naming the "
        "product index, before anything is charged, stored, written or queued.\n"
        "\n"
        "**Disabled in production** while `CATALOG_JOBS_ENABLED` is off: answers 503 for every caller, "
        "before anything is reserved, written, uploaded or queued."
    ),
    response_description="The created catalog job with reserved credits.",
    operation_id="create_catalog_job",
    responses={**error_responses(400, 401, 402, 403, 404, 422), **CATALOG_DISABLED_RESPONSE},
)
async def create_catalog_job(
    request: Request,
    current_user: User = Depends(require_catalog_jobs_enabled),
    db: AsyncSession = Depends(get_db),
):
    """Create a new catalog batch job supporting both JSON and FormData."""
    form, json_data = await read_form_or_json(request)
    if form is not None:
        brand_id_val = form.get("brand_id")
        brand_id = parse_body(CatalogJobForm, {"brand_id": brand_id_val}).brand_id if brand_id_val else None
        engine_mode = form.get("fashn_mode") or form.get("engine_mode") or "product_to_model"
        generation_mode = form.get("generation_mode") or "studio_quality"
        model_identity = form.get("model_identity") or "Maya"
        pose = form.get("pose") or "Catalog Standing"
        background = form.get("background") or "Soft Front Studio"
        aspect_ratio = form.get("aspect_ratio") or "4:5"
        resolution = form.get("resolution") or "2K"
        
        # Files are saved once the brand is authorized
        products = []
        files_to_save = [(form.get(f"sku_{i}") or f"SKU-{i+1}", file)
                         for i, file in enumerate(form.getlist("products"))]
    else:
        payload = parse_body(CatalogJobCreate, json_data)
        brand_id = payload.brand_id
        engine_mode = payload.engine_mode
        generation_mode = payload.generation_mode
        model_identity = payload.model_identity
        pose = payload.pose
        background = payload.background
        aspect_ratio = payload.aspect_ratio
        resolution = payload.resolution
        products = payload.products
        files_to_save = []

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

    if not products and not files_to_save:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one product is required.")

    # Every product image, checked before any credits are charged or anything is stored, written or
    # queued: JSON image_paths must be image assets of this brand, uploads real images (422 otherwise).
    await check_request_paths(db, brand_id, [(f"products[{i}].image_path", p.get("image_path"))
                                             for i, p in enumerate(products)])
    extensions, errors = [], []
    for index, (_, file) in enumerate(files_to_save):
        extension, problem = (None, "is not a file") if isinstance(file, str) else await check_upload(file)
        extensions.append(extension)
        if problem:
            errors.append(f"products[{index}] {problem}.")
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=" ".join(errors))

    credits_per_sku = CREDITS_PER_SKU.get(generation_mode, 5)
    credits_needed = (len(products) + len(files_to_save)) * credits_per_sku

    if (current_user.credits or 0) < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {credits_needed}, have {current_user.credits or 0}."
        )

    for (sku_tag, file), extension in zip(files_to_save, extensions):
        unique_filename = f"{uuid.uuid4()}{extension}"
        file_bytes = await file.read()
        storage_path = storage_service.save_file_bytes(unique_filename, file_bytes)
        products.append({
            "sku_tag": sku_tag,
            "image_path": storage_path
        })

    current_user.credits = (current_user.credits or 0) - credits_needed

    job = CatalogJob(
        user_id=current_user.id,
        brand_id=brand_id,
        status="queued",
        engine_mode=engine_mode,
        generation_mode=generation_mode,
        model_identity=model_identity,
        pose=pose,
        background=background,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        total_items=len(products),
        credits_reserved=credits_needed,
    )
    db.add(job)
    await db.flush()

    for product in products:
        item = CatalogJobItem(
            job_id=job.id,
            sku_tag=product.get("sku_tag", f"SKU-{job.id}"),
            product_image_path=product.get("image_path", ""),
            status="queued",
        )
        db.add(item)

    await db.commit()
    await db.refresh(job)

    try:
        process_catalog_job.delay(job.id)
    except Exception as e:
        print(f"[CatalogJob] Celery dispatch failed: {e}")

    return {
        "job_id": job.id,
        "status": job.status,
        "total_items": job.total_items,
        "credits_reserved": credits_needed,
    }


@router.get(
    "/{job_id}",
    summary="Get a catalog job",
    description="Get catalog job status with per-SKU tracking. Members of the job's brand (any role) and "
                "platform admins only; anyone else gets the same 404 as an unknown id.",
    response_description="Catalog job status with per-SKU progress.",
    operation_id="get_catalog_job",
    responses=error_responses(401, 404, 422),
)
async def get_catalog_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get catalog job status with per-SKU tracking."""
    result = await db.execute(select(CatalogJob).where(CatalogJob.id == job_id))
    job = await require_readable(db, current_user, result.scalars().first(), "Catalog job not found.")

    items_result = await db.execute(select(CatalogJobItem).where(CatalogJobItem.job_id == job_id))
    items = items_result.scalars().all()

    progress = int((job.completed_items / job.total_items) * 100) if job.total_items > 0 else 0

    return {
        "job_id": job.id,
        "status": job.status,
        "progress": progress,
        "total_items": job.total_items,
        "completed_items": job.completed_items,
        "failed_items": job.failed_items,
        "engine_mode": job.engine_mode,
        "generation_mode": job.generation_mode,
        "items": [
            {
                "id": i.id,
                "sku_tag": i.sku_tag,
                "status": i.status,
                "output_url": i.output_url,
                "quality_score": i.quality_score,
                "fidelity_status": i.fidelity_status,
            }
            for i in items
        ],
        "created_at": job.created_at.isoformat(),
    }


@router.post(
    "/{job_id}/cancel",
    summary="Cancel a catalog job",
    description="Cancel catalog job and refund credits.",
    response_description="The cancelled job; reserved credits are refunded.",
    operation_id="cancel_catalog_job",
    responses=error_responses(401, 404, 409, 422),
)
async def cancel_catalog_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel catalog job and refund credits."""
    # Locked: a second cancel or the worker's item refunds wait, then see the new state.
    result = await db.execute(
        select(CatalogJob).where(CatalogJob.id == job_id, CatalogJob.user_id == current_user.id)
        .with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog job not found.")
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot cancel job with status: {job.status}")

    job.status = "cancelled"
    # What is still unused and not refunded already (failed items were refunded one by one)
    refund = await refund_job(db, "catalog_job", job, "cancelled")
    await db.commit()

    return {"job_id": job.id, "status": "cancelled", "credits_refunded": refund}


@router.post(
    "/{job_id}/retry",
    summary="Retry a catalog job",
    description="Retry a failed catalog job. Disabled in production (503) while `CATALOG_JOBS_ENABLED` is off.",
    response_description="The catalog job re-queued for processing.",
    operation_id="retry_catalog_job",
    responses={**error_responses(401, 404, 409, 422), **CATALOG_DISABLED_RESPONSE},
)
async def retry_catalog_job(
    job_id: int,
    current_user: User = Depends(require_catalog_jobs_enabled),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed catalog job."""
    result = await db.execute(
        select(CatalogJob).where(CatalogJob.id == job_id, CatalogJob.user_id == current_user.id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog job not found.")
    if job.status != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot retry job with status: {job.status}")

    # Re-queue the failed items and the job
    job.status = "queued"
    job.progress = 0
    job.error_message = None

    items_result = await db.execute(
        select(CatalogJobItem).where(CatalogJobItem.job_id == job_id, CatalogJobItem.status == "failed")
    )
    failed_items = items_result.scalars().all()
    for item in failed_items:
        item.status = "queued"
        item.error_message = None

    await db.commit()

    try:
        process_catalog_job.delay(job.id)
    except Exception as e:
        print(f"[CatalogJob] Retry dispatch failed: {e}")

    return {"job_id": job.id, "status": "queued"}


@router.post(
    "/{job_id}/items/{item_id}/retry",
    summary="Retry a catalog item",
    description="Retry a failed catalog item. Disabled in production (503) while `CATALOG_JOBS_ENABLED` is off.",
    response_description="The catalog item re-queued for processing.",
    operation_id="retry_catalog_item",
    responses={**error_responses(401, 404, 409, 422), **CATALOG_DISABLED_RESPONSE},
)
async def retry_catalog_item(
    job_id: int,
    item_id: int,
    current_user: User = Depends(require_catalog_jobs_enabled),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed catalog item."""
    result = await db.execute(
        select(CatalogJobItem).where(CatalogJobItem.id == item_id, CatalogJobItem.job_id == job_id)
    )
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog item not found.")
    if item.status != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed items can be retried.")

    item.status = "queued"
    item.error_message = None
    await db.commit()

    try:
        process_catalog_item.delay(item_id)
    except Exception as e:
        print(f"[CatalogItem] Retry dispatch failed: {e}")

    return {"item_id": item_id, "status": "queued"}
