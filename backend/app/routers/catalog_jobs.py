from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, User, CatalogJob, CatalogJobItem, Brand, BrandMember
from app.middleware.auth import get_current_user
from app.worker import process_catalog_job, process_catalog_item
from app.services.storage import storage_service
import os
import uuid

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
    products: List[dict] = Field(default_factory=list)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_catalog_job(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new catalog batch job supporting both JSON and FormData."""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        brand_id_val = form.get("brand_id")
        brand_id = int(brand_id_val) if brand_id_val else None
        engine_mode = form.get("fashn_mode") or form.get("engine_mode") or "product_to_model"
        generation_mode = form.get("generation_mode") or "studio_quality"
        model_identity = form.get("model_identity") or "Maya"
        pose = form.get("pose") or "Catalog Standing"
        background = form.get("background") or "Soft Front Studio"
        aspect_ratio = form.get("aspect_ratio") or "4:5"
        resolution = form.get("resolution") or "2K"
        
        products = []
        uploaded_files = form.getlist("products")
        for i, file in enumerate(uploaded_files):
            sku_tag = form.get(f"sku_{i}") or f"SKU-{i+1}"
            filename = file.filename or "file.png"
            file_ext = os.path.splitext(filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_bytes = await file.read()
            storage_path = storage_service.save_file_bytes(unique_filename, file_bytes)
            products.append({
                "sku_tag": sku_tag,
                "image_path": storage_path
            })
    else:
        json_data = await request.json()
        payload = CatalogJobCreate(**json_data)
        brand_id = payload.brand_id
        engine_mode = payload.engine_mode
        generation_mode = payload.generation_mode
        model_identity = payload.model_identity
        pose = payload.pose
        background = payload.background
        aspect_ratio = payload.aspect_ratio
        resolution = payload.resolution
        products = payload.products

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

    if not products:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one product is required.")

    credits_per_sku = CREDITS_PER_SKU.get(generation_mode, 5)
    credits_needed = len(products) * credits_per_sku

    if (current_user.credits or 0) < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {credits_needed}, have {current_user.credits or 0}."
        )

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


@router.get("/{job_id}")
async def get_catalog_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get catalog job status with per-SKU tracking."""
    result = await db.execute(
        select(CatalogJob).where(CatalogJob.id == job_id, CatalogJob.user_id == current_user.id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog job not found.")

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


@router.post("/{job_id}/cancel")
async def cancel_catalog_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel catalog job and refund credits."""
    result = await db.execute(
        select(CatalogJob).where(CatalogJob.id == job_id, CatalogJob.user_id == current_user.id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog job not found.")
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot cancel job with status: {job.status}")

    job.status = "cancelled"
    refund = job.credits_reserved - job.credits_consumed
    current_user.credits = (current_user.credits or 0) + refund
    await db.commit()

    return {"job_id": job.id, "status": "cancelled", "credits_refunded": refund}


@router.post("/{job_id}/retry")
async def retry_catalog_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
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


@router.post("/{job_id}/items/{item_id}/retry")
async def retry_catalog_item(
    job_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
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
