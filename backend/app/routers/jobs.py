from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import (
    get_db,
    AIJob,
    User,
    Brand,
    BrandMember,
    WorkflowTemplate
)
from app.middleware.auth import get_current_user, ROLE_HIERARCHY
from app.middleware.rate_limit import redis_client, RateLimiter
from app.worker import process_generation_job, process_workflow_job

logger = logging.getLogger("modelens.jobs")

router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["Jobs"]
)

# --- Request / Response Schemas ---

class JobGenerateRequest(BaseModel):
    brand_id: int
    workflow_template_id: int
    inputs: dict = Field(default_factory=dict, description="Input variables and S3 URLs for generation")
    callback_url: Optional[str] = Field(None, description="Optional webhook URL to notify on completion/failure")


class JobWorkflowRequest(BaseModel):
    brand_id: int
    workflow_type: str = Field(..., description="Type of generation workflow: on_model_replacement | flat_lay_to_model | mannequin_to_model | background_replacement | video_generation")
    inputs: dict = Field(default_factory=dict, description="Input variables including source_asset_id, character_id, character_version_id, background_style, motion_type, etc.")
    callback_url: Optional[str] = Field(None, description="Optional webhook callback URL")


class JobResponse(BaseModel):
    id: int
    user_id: int
    brand_id: int
    workflow_template_id: Optional[int] = None
    asset_id: Optional[int] = None
    status: str
    job_type: str
    inputs: dict
    outputs: dict
    callback_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Endpoints ---

@router.post("/generate", status_code=status.HTTP_201_CREATED, response_model=JobResponse, dependencies=[Depends(RateLimiter(requests_limit=10, window_seconds=60))])
async def generate_job(
    payload: JobGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers an AI generation job.
    Validates user has at least 'editor' role, verifies credits, deducts 1 credit,
    inserts job record, caches status, and enqueues background worker.
    """
    # 1. Verify brand exists and current user has access
    brand_query = select(Brand).where(Brand.id == payload.brand_id)
    brand_res = await db.execute(brand_query)
    brand = brand_res.scalars().first()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found"
        )

    is_owner = brand.owner_id == current_user.id
    is_editor = False
    if not is_owner:
        member_query = select(BrandMember).where(
            BrandMember.brand_id == payload.brand_id,
            BrandMember.user_id == current_user.id
        )
        member_res = await db.execute(member_query)
        membership = member_res.scalars().first()
        if membership:
            user_level = ROLE_HIERARCHY.get(membership.role, 0)
            if user_level >= ROLE_HIERARCHY.get("editor", 0):
                is_editor = True

    if not is_owner and not is_editor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires at least 'editor' role on this brand."
        )

    # 2. Verify workflow template exists
    wf_query = select(WorkflowTemplate).where(WorkflowTemplate.id == payload.workflow_template_id)
    wf_res = await db.execute(wf_query)
    wf_template = wf_res.scalars().first()
    if not wf_template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow template not found"
        )

    # 3. Credit validation & deduction
    # Force loading of user from database session to ensure current value is correct
    user_query = select(User).where(User.id == current_user.id)
    user_res = await db.execute(user_query)
    db_user = user_res.scalars().first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if db_user.credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient credits. Remaining: {db_user.credits}"
        )

    # Deduct 1 credit
    db_user.credits -= 1
    db.add(db_user)

    # 4. Insert Job Record
    job = AIJob(
        user_id=db_user.id,
        brand_id=payload.brand_id,
        workflow_template_id=payload.workflow_template_id,
        status="pending",
        job_type="generation",
        inputs=payload.inputs,
        outputs={},
        callback_url=payload.callback_url,
        error_message=None
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # 5. Cache initial job state in Redis
    job_data = {
        "id": job.id,
        "user_id": job.user_id,
        "brand_id": job.brand_id,
        "workflow_template_id": job.workflow_template_id,
        "asset_id": job.asset_id,
        "status": job.status,
        "job_type": job.job_type,
        "inputs": job.inputs,
        "outputs": job.outputs,
        "callback_url": job.callback_url,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }
    try:
        await redis_client.set(f"job:{job.id}:status", json.dumps(job_data), ex=3600)
    except Exception as e:
        logger.warning(f"Failed to write job status to Redis cache: {e}")

    # 6. Dispatch Celery task
    process_generation_job.delay(job.id)

    return job


@router.post("/workflow", status_code=status.HTTP_201_CREATED, response_model=JobResponse, dependencies=[Depends(RateLimiter(requests_limit=10, window_seconds=60))])
async def generate_workflow_job(
    payload: JobWorkflowRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers an AI generation workflow job.
    Validates user has at least 'editor' role, verifies credits, deducts 1 credit,
    inserts job record, caches status, and enqueues background worker.
    """
    # 1. Verify brand exists and current user has access
    brand_query = select(Brand).where(Brand.id == payload.brand_id)
    brand_res = await db.execute(brand_query)
    brand = brand_res.scalars().first()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found"
        )

    is_owner = brand.owner_id == current_user.id
    is_editor = False
    if not is_owner:
        member_query = select(BrandMember).where(
            BrandMember.brand_id == payload.brand_id,
            BrandMember.user_id == current_user.id
        )
        member_res = await db.execute(member_query)
        membership = member_res.scalars().first()
        if membership:
            user_level = ROLE_HIERARCHY.get(membership.role, 0)
            if user_level >= ROLE_HIERARCHY.get("editor", 0):
                is_editor = True

    if not is_owner and not is_editor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires at least 'editor' role on this brand."
        )

    # Validate workflow type
    allowed_types = ["on_model_replacement", "flat_lay_to_model", "mannequin_to_model", "background_replacement", "video_generation"]
    if payload.workflow_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid workflow_type. Allowed: {allowed_types}"
        )

    # 2. Credit validation & deduction
    user_query = select(User).where(User.id == current_user.id)
    user_res = await db.execute(user_query)
    db_user = user_res.scalars().first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if db_user.credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient credits. Remaining: {db_user.credits}"
        )

    # Deduct 1 credit
    db_user.credits -= 1
    db.add(db_user)

    # Combine workflow_type into inputs
    job_inputs = {**payload.inputs, "workflow_type": payload.workflow_type}

    # 3. Insert Job Record
    job = AIJob(
        user_id=db_user.id,
        brand_id=payload.brand_id,
        workflow_template_id=None,
        status="pending",
        job_type="workflow",
        inputs=job_inputs,
        outputs={},
        callback_url=payload.callback_url,
        error_message=None
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # 4. Cache initial job state in Redis
    job_data = {
        "id": job.id,
        "user_id": job.user_id,
        "brand_id": job.brand_id,
        "workflow_template_id": job.workflow_template_id,
        "asset_id": job.asset_id,
        "status": job.status,
        "job_type": job.job_type,
        "inputs": job.inputs,
        "outputs": job.outputs,
        "callback_url": job.callback_url,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }
    try:
        await redis_client.set(f"job:{job.id}:status", json.dumps(job_data), ex=3600)
    except Exception as e:
        logger.warning(f"Failed to write job status to Redis cache: {e}")

    # 5. Dispatch Celery task
    process_workflow_job.delay(job.id)

    return job


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    brand_id: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all AI jobs for brands the user belongs to with pagination.
    """
    # Find brands user has access to
    owned_query = select(Brand.id).where(Brand.owner_id == current_user.id)
    owned_res = await db.execute(owned_query)
    accessible_brand_ids = set(owned_res.scalars().all())

    member_query = select(BrandMember.brand_id).where(BrandMember.user_id == current_user.id)
    member_res = await db.execute(member_query)
    accessible_brand_ids.update(member_res.scalars().all())

    if not accessible_brand_ids:
        return []

    query = select(AIJob)
    if brand_id is not None:
        if brand_id not in accessible_brand_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this brand's jobs"
            )
        query = query.where(AIJob.brand_id == brand_id)
    else:
        query = query.where(AIJob.brand_id.in_(list(accessible_brand_ids)))

    query = query.order_by(AIJob.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/workflow-templates", response_model=List[dict])
async def list_workflow_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all available workflow templates.
    """
    query = select(WorkflowTemplate)
    res = await db.execute(query)
    templates = res.scalars().all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "workflow_json": t.workflow_json
        }
        for t in templates
    ]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Checks the status of an AI job.
    Tries Redis status cache first to bypass database load, fallback to PostgreSQL on miss.
    Verifies that caller has brand access.
    """
    # 1. Try Redis cache first
    cached_val = None
    try:
        cached_val = await redis_client.get(f"job:{job_id}:status")
    except Exception as e:
        logger.warning(f"Failed to read job status from Redis cache: {e}")

    if cached_val:
        try:
            job_data = json.loads(cached_val)
            brand_id = job_data.get("brand_id")

            # Verify caller brand membership
            brand_query = select(Brand).where(Brand.id == brand_id)
            brand_res = await db.execute(brand_query)
            brand = brand_res.scalars().first()
            if not brand:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Brand not found"
                )

            is_member = brand.owner_id == current_user.id
            if not is_member:
                member_query = select(BrandMember).where(
                    BrandMember.brand_id == brand_id,
                    BrandMember.user_id == current_user.id
                )
                member_res = await db.execute(member_query)
                is_member = member_res.scalars().first() is not None

            if not is_member:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this brand's jobs"
                )

            # Parse datetimes to keep Pydantic serialization happy
            if "created_at" in job_data and job_data["created_at"]:
                job_data["created_at"] = datetime.fromisoformat(job_data["created_at"])
            if "updated_at" in job_data and job_data["updated_at"]:
                job_data["updated_at"] = datetime.fromisoformat(job_data["updated_at"])

            return job_data
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error parsing cached job JSON: {e}")
            # Fall through to DB query on cache parsing errors

    # 2. Fallback to Postgres query
    query = select(AIJob).where(AIJob.id == job_id)
    res = await db.execute(query)
    job = res.scalars().first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    # Verify brand membership
    brand_query = select(Brand).where(Brand.id == job.brand_id)
    brand_res = await db.execute(brand_query)
    brand = brand_res.scalars().first()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found"
        )

    is_member = brand.owner_id == current_user.id
    if not is_member:
        member_query = select(BrandMember).where(
            BrandMember.brand_id == job.brand_id,
            BrandMember.user_id == current_user.id
        )
        member_res = await db.execute(member_query)
        is_member = member_res.scalars().first() is not None

    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this brand's jobs"
        )

    # Proactively populate Redis if it was a cache miss
    try:
        job_data = {
            "id": job.id,
            "user_id": job.user_id,
            "brand_id": job.brand_id,
            "workflow_template_id": job.workflow_template_id,
            "asset_id": job.asset_id,
            "status": job.status,
            "job_type": job.job_type,
            "inputs": job.inputs,
            "outputs": job.outputs,
            "callback_url": job.callback_url,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }
        await redis_client.set(f"job:{job.id}:status", json.dumps(job_data), ex=3600)
    except Exception as e:
        logger.warning(f"Failed to populate job status in Redis cache: {e}")

    return job
