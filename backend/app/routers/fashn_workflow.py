from fastapi import APIRouter, HTTPException, Depends, Header, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid
import asyncio

from app.models.db import get_db, User, CatalogJob
from app.middleware.auth import get_current_user
from app.services.fashn_service import fashn_service
from app.services.credits_sync_service import credits_sync_service
from app.config import settings

router = APIRouter(prefix="/api/v1/fashn", tags=["FASHN Workflow Integration"])

INTERNAL_SECRET = getattr(settings, "INTERNAL_CALLBACK_SECRET", "modelens-internal-secret")

# ========================== Credit Rates =========================

FASHN_CREDIT_RATES = {
    "standard": {
        "1k": 1,
        "2k": 2,
        "4k": 4,
        "default": 2,
    },
    "quality": {
        "1k": 2,
        "2k": 4,
        "4k": 7,
        "default": 4,
    },
    "max": {
        "1k": 3,
        "2k": 5,
        "4k": 8,
        "default": 5,
    },
}


def estimate_fashn_credits(
    mode: str,
    resolution: str = "2k",
    num_images: int = 1,
    generation_mode: str = "quality",
) -> int:
    """Estimate credits for FASHN try-on job."""
    rates = FASHN_CREDIT_RATES.get(generation_mode.lower(), FASHN_CREDIT_RATES["quality"])
    per_image = rates.get(resolution.lower(), rates["default"])
    return per_image * num_images


# ========================== Schemas ==============================

class ProductToModelRequest(BaseModel):
    product_image_url: str
    face_reference_url: Optional[str] = None
    pose_reference_url: Optional[str] = None
    background_reference_url: Optional[str] = None
    prompt: Optional[str] = None
    aspect_ratio: str = "4:5"
    resolution: str = "2k"
    generation_mode: str = "quality"
    num_images: int = 1
    character_id: Optional[str] = None
    product_id: Optional[str] = None


class TryOnMaxRequest(BaseModel):
    product_image_url: str
    model_image_url: str
    prompt: Optional[str] = None
    aspect_ratio: str = "4:5"
    resolution: str = "2k"
    generation_mode: str = "quality"
    num_images: int = 1
    character_id: Optional[str] = None
    product_id: Optional[str] = None


class FashnCreditEstimateRequest(BaseModel):
    mode: str = Field(..., description="product-to-model or try-on-max")
    resolution: str = "2k"
    num_images: int = 1
    generation_mode: str = "quality"


class FashnWebhookPayload(BaseModel):
    job_id: str
    status: str
    output: Optional[List[Dict]] = None
    error: Optional[str] = None


# ========================== Background Task =====================

async def poll_fashn_job(
    job_id: str,
    fashn_job_id: str,
    brand_id: int,
    db: AsyncSession,
):
    """Poll FASHN job status and update our job record."""
    max_polls = 30
    poll_interval = 10

    for _ in range(max_polls):
        await asyncio.sleep(poll_interval)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{fashn_service.base_url}/status/{fashn_job_id}",
                    headers=fashn_service.headers,
                )
                if response.status_code == 200:
                    data = response.json()
                    fashn_status = data.get("status", "processing")

                    result = await db.execute(
                        select(CatalogJob).where(CatalogJob.job_id == job_id)
                    )
                    job = result.scalars().first()

                    if job:
                        if fashn_status == "completed":
                            job.status = "completed"
                            job.completed_skus = 1
                            await db.commit()
                            await credits_sync_service.finalize_credits(job_id, db)
                            break
                        elif fashn_status in ["failed", "error"]:
                            job.status = "failed"
                            await db.commit()
                            await credits_sync_service.refund_credits(
                                job_id, "FASHN generation failed", db
                            )
                            break
        except Exception:
            continue


# ========================== Endpoints ============================

@router.post("/estimate")
async def estimate_fashn_credits_endpoint(
    payload: FashnCreditEstimateRequest,
    current_user: User = Depends(get_current_user),
):
    """Estimate credits for FASHN try-on job."""
    credits = estimate_fashn_credits(
        mode=payload.mode,
        resolution=payload.resolution,
        num_images=payload.num_images,
        generation_mode=payload.generation_mode,
    )
    return {
        "estimated_credits": credits,
        "mode": payload.mode,
        "resolution": payload.resolution,
        "num_images": payload.num_images,
        "generation_mode": payload.generation_mode,
        "rates": FASHN_CREDIT_RATES,
    }


@router.post("/check")
async def check_fashn_credits(
    payload: FashnCreditEstimateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pre-flight credit check for FASHN try-on."""
    brand_id = getattr(current_user, 'brand_id', None)
    if not brand_id:
        raise HTTPException(status_code=400, detail="No brand associated.")

    required = estimate_fashn_credits(
        mode=payload.mode,
        resolution=payload.resolution,
        num_images=payload.num_images,
        generation_mode=payload.generation_mode,
    )

    check = await credits_sync_service.check_sufficient_credits(brand_id, required, db)
    return {
        "sufficient": check["sufficient"],
        "balance": check["balance"],
        "required": required,
        "shortfall": check["shortfall"],
    }


@router.post("/product-to-model", status_code=status.HTTP_201_CREATED)
async def product_to_model(
    payload: ProductToModelRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FASHN Product-to-Model try-on with credit reservation."""
    brand_id = getattr(current_user, 'brand_id', None)
    if not brand_id:
        raise HTTPException(status_code=400, detail="No brand associated.")

    # Estimate and reserve credits
    required = estimate_fashn_credits(
        mode="product-to-model",
        resolution=payload.resolution,
        num_images=payload.num_images,
        generation_mode=payload.generation_mode,
    )

    job_id = str(uuid.uuid4())

    # Reserve credits
    await credits_sync_service.reserve_credits(
        brand_id=brand_id,
        user_id=current_user.id,
        amount=required,
        generation_id=job_id,
        description=f"FASHN product-to-model: {payload.resolution}",
        db=db,
    )

    # Create job record
    job = CatalogJob(
        job_id=job_id,
        user_id=current_user.id,
        brand_id=brand_id,
        status="processing",
        quality_mode=payload.generation_mode,
        total_skus=payload.num_images,
        meta={
            "fashn_mode": "product-to-model",
            "character_id": payload.character_id,
            "product_id": payload.product_id,
            "resolution": payload.resolution,
            "aspect_ratio": payload.aspect_ratio,
            "credits_reserved": required,
        }
    )
    db.add(job)
    await db.commit()

    # Call FASHN API
    try:
        result = await fashn_service.generate_product_to_model(
            product_image_url=payload.product_image_url,
            face_reference_url=payload.face_reference_url,
            pose_reference_url=payload.pose_reference_url,
            background_reference_url=payload.background_reference_url,
            prompt=payload.prompt,
            aspect_ratio=payload.aspect_ratio,
            resolution=payload.resolution,
            generation_mode=payload.generation_mode,
            num_images=payload.num_images,
        )

        fashn_job_id = result.get("id", job_id)
        fashn_status = result.get("status", "processing")

        # Update job
        job.meta["fashn_job_id"] = fashn_job_id
        job.meta["fashn_status"] = fashn_status

        if fashn_status == "completed":
            job.status = "completed"
            job.completed_skus = payload.num_images
            await db.commit()
            await credits_sync_service.finalize_credits(job_id, db)
        else:
            await db.commit()
            # Poll in background
            background_tasks.add_task(
                poll_fashn_job, job_id, fashn_job_id, brand_id, db
            )

        return {
            "job_id": job_id,
            "fashn_job_id": fashn_job_id,
            "status": fashn_status,
            "credits_reserved": required,
            "output": result.get("output", []),
            "mode": "product-to-model",
        }

    except Exception as e:
        job.status = "failed"
        await db.commit()
        await credits_sync_service.refund_credits(job_id, str(e), db)
        raise HTTPException(status_code=500, detail=f"FASHN API error: {str(e)}")


@router.post("/try-on-max", status_code=status.HTTP_201_CREATED)
async def try_on_max(
    payload: TryOnMaxRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FASHN Try-On Max with credit reservation."""
    brand_id = getattr(current_user, 'brand_id', None)
    if not brand_id:
        raise HTTPException(status_code=400, detail="No brand associated.")

    required = estimate_fashn_credits(
        mode="try-on-max",
        resolution=payload.resolution,
        num_images=payload.num_images,
        generation_mode=payload.generation_mode,
    )

    job_id = str(uuid.uuid4())

    await credits_sync_service.reserve_credits(
        brand_id=brand_id,
        user_id=current_user.id,
        amount=required,
        generation_id=job_id,
        description=f"FASHN try-on-max: {payload.resolution}",
        db=db,
    )

    job = CatalogJob(
        job_id=job_id,
        user_id=current_user.id,
        brand_id=brand_id,
        status="processing",
        quality_mode=payload.generation_mode,
        total_skus=payload.num_images,
        meta={
            "fashn_mode": "try-on-max",
            "character_id": payload.character_id,
            "product_id": payload.product_id,
            "resolution": payload.resolution,
            "aspect_ratio": payload.aspect_ratio,
            "credits_reserved": required,
        }
    )
    db.add(job)
    await db.commit()

    try:
        result = await fashn_service.generate_try_on_max(
            product_image_url=payload.product_image_url,
            model_image_url=payload.model_image_url,
            prompt=payload.prompt,
            aspect_ratio=payload.aspect_ratio,
            resolution=payload.resolution,
            generation_mode=payload.generation_mode,
            num_images=payload.num_images,
        )

        fashn_job_id = result.get("id", job_id)
        fashn_status = result.get("status", "processing")

        job.meta["fashn_job_id"] = fashn_job_id
        job.meta["fashn_status"] = fashn_status

        if fashn_status == "completed":
            job.status = "completed"
            job.completed_skus = payload.num_images
            await db.commit()
            await credits_sync_service.finalize_credits(job_id, db)
        else:
            await db.commit()
            background_tasks.add_task(
                poll_fashn_job, job_id, fashn_job_id, brand_id, db
            )

        return {
            "job_id": job_id,
            "fashn_job_id": fashn_job_id,
            "status": fashn_status,
            "credits_reserved": required,
            "output": result.get("output", []),
            "mode": "try-on-max",
        }

    except Exception as e:
        job.status = "failed"
        await db.commit()
        await credits_sync_service.refund_credits(job_id, str(e), db)
        raise HTTPException(status_code=500, detail=f"FASHN API error: {str(e)}")


@router.get("/jobs/{job_id}")
async def get_fashn_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get FASHN job status."""
    result = await db.execute(
        select(CatalogJob).where(CatalogJob.job_id == job_id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return {
        "job_id": job_id,
        "status": job.status,
        "fashn_mode": job.meta.get("fashn_mode") if job.meta else None,
        "fashn_job_id": job.meta.get("fashn_job_id") if job.meta else None,
        "credits_reserved": job.meta.get("credits_reserved") if job.meta else None,
        "completed": job.completed_skus or 0,
        "created_at": str(job.created_at),
    }


@router.post("/webhook")
async def fashn_webhook(
    payload: FashnWebhookPayload,
    x_internal_secret: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """FASHN webhook callback for job completion/failure."""
    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret.")

    result = await db.execute(
        select(CatalogJob).where(CatalogJob.job_id == payload.job_id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if payload.status == "completed":
        job.status = "completed"
        job.completed_skus = 1
        await db.commit()
        await credits_sync_service.finalize_credits(payload.job_id, db)
        return {"status": "finalized", "job_id": payload.job_id}

    elif payload.status in ["failed", "error"]:
        job.status = "failed"
        await db.commit()
        await credits_sync_service.refund_credits(
            payload.job_id, payload.error or "FASHN failed", db
        )
        return {"status": "refunded", "job_id": payload.job_id}

    return {"status": "acknowledged", "job_id": payload.job_id}


@router.get("/rates")
async def get_fashn_rates(
    current_user: User = Depends(get_current_user),
):
    """Get FASHN credit rates."""
    return {
        "rates": FASHN_CREDIT_RATES,
        "modes": ["product-to-model", "try-on-max"],
        "resolutions": ["1k", "2k", "4k"],
        "generation_modes": ["standard", "quality", "max"],
    }
