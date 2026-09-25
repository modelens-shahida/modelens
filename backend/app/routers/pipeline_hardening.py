from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, User, CatalogJob, GhostJob
from app.middleware.auth import get_current_user
from app.services.pipeline_hardening import (
    pipeline_hardening,
    JobStatus,
    TERMINAL_STATES,
    PROVIDER_TIMEOUTS,
    RETRY_CONFIG,
    validate_transition,
    get_provider_timeout,
    calculate_backoff,
    is_retryable_error,
)

router = APIRouter(prefix="/api/v1", tags=["Pipeline Hardening"])


# ========================== Schemas ==============================

class CancelJobRequest(BaseModel):
    reason: str = "User cancelled"


class DLQRouteRequest(BaseModel):
    error: str
    brand_id: int


# ========================== Helpers ==============================

async def get_job_by_id(job_id: str, db: AsyncSession):
    """Get job from CatalogJob or GhostJob."""
    result = await db.execute(
        select(CatalogJob).where(CatalogJob.job_id == job_id)
    )
    job = result.scalars().first()

    if not job:
        result = await db.execute(
            select(GhostJob).where(GhostJob.job_id == job_id)
        )
        job = result.scalars().first()

    return job


# ========================== Endpoints ============================

@router.post("/generate/{job_id}/cancel")
async def cancel_generation_job(
    job_id: str,
    payload: CancelJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a generation job with immediate credit refund."""
    job = await get_job_by_id(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    # Verify ownership
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this job.")

    brand_id = getattr(current_user, 'brand_id', None) or getattr(job, 'brand_id', None) or 1

    result = await pipeline_hardening.cancel_job(
        job=job,
        brand_id=brand_id,
        user_id=current_user.id,
        db=db,
        reason=payload.reason,
    )

    if not result["cancelled"]:
        raise HTTPException(
            status_code=400,
            detail=result["reason"]
        )

    return result


@router.get("/generate/{job_id}/status")
async def get_job_lifecycle_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed job lifecycle status with transition history."""
    job = await get_job_by_id(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    meta = job.meta or {}
    status_history = meta.get("status_history", [])
    is_terminal = job.status in [s.value for s in TERMINAL_STATES]

    return {
        "job_id": job_id,
        "status": job.status,
        "is_terminal": is_terminal,
        "can_cancel": not is_terminal,
        "status_history": status_history,
        "created_at": str(job.created_at),
        "meta": {
            "fashn_job_id": meta.get("fashn_job_id"),
            "credits_reserved": meta.get("credits_reserved"),
            "dlq_error": meta.get("dlq_error"),
        }
    }


@router.post("/generate/{job_id}/dlq")
async def route_job_to_dlq(
    job_id: str,
    payload: DLQRouteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Route an unrecoverable job to Dead Letter Queue."""
    job = await get_job_by_id(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    result = await pipeline_hardening.route_to_dlq(
        job=job,
        error=payload.error,
        db=db,
        brand_id=payload.brand_id,
    )

    return result


@router.get("/pipeline/config")
async def get_pipeline_config(
    current_user: User = Depends(get_current_user),
):
    """Get pipeline configuration - timeouts, retry settings."""
    return {
        "provider_timeouts": PROVIDER_TIMEOUTS,
        "retry_config": RETRY_CONFIG,
        "job_statuses": [s.value for s in JobStatus],
        "terminal_states": [s.value for s in TERMINAL_STATES],
        "valid_transitions": {
            k.value: [v.value for v in vals]
            for k, vals in {
                JobStatus.QUEUED: [JobStatus.PROCESSING, JobStatus.CANCELLED],
                JobStatus.PROCESSING: [JobStatus.STREAMING, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED],
                JobStatus.STREAMING: [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED],
            }.items()
        }
    }


@router.get("/pipeline/dlq")
async def get_dlq_jobs(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get jobs in Dead Letter Queue."""
    result = await db.execute(
        select(CatalogJob)
        .where(CatalogJob.status == JobStatus.DLQ.value)
        .order_by(CatalogJob.id.desc())
        .limit(limit)
    )
    jobs = result.scalars().all()

    return {
        "dlq_jobs": [
            {
                "job_id": j.job_id,
                "status": j.status,
                "error": j.meta.get("dlq_error") if j.meta else None,
                "dlq_at": j.meta.get("dlq_at") if j.meta else None,
                "created_at": str(j.created_at),
            }
            for j in jobs
        ],
        "total": len(jobs),
    }


@router.post("/pipeline/timeout-config")
async def get_timeout_for_job(
    provider: str,
    resolution: str = "standard",
    current_user: User = Depends(get_current_user),
):
    """Get timeout configuration for a provider/resolution."""
    timeout = get_provider_timeout(provider, resolution)
    backoff_delays = [calculate_backoff(i) for i in range(RETRY_CONFIG["max_retries"])]

    return {
        "provider": provider,
        "resolution": resolution,
        "timeout_seconds": timeout,
        "max_retries": RETRY_CONFIG["max_retries"],
        "backoff_delays": backoff_delays,
    }
