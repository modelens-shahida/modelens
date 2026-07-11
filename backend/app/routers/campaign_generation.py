import uuid
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import (
    get_db, User, Campaign, Brand, BrandMember,
    AIJob, Asset, Character, CharacterVersion,
)
from app.middleware.auth import get_current_user
from app.worker import process_campaign_generation

router = APIRouter(tags=["Campaign Generation"])

class CampaignGenerationRequest(BaseModel):
    character_id: int
    character_version_id: int
    workflow_template_id: Optional[int] = None
    prompt_template_id: Optional[int] = None
    asset_ids: List[int] = Field(default_factory=list)
    garment_asset_ids: List[int] = Field(default_factory=list)
    pose_reference_asset_id: Optional[int] = None
    location_reference_asset_id: Optional[int] = None
    number_of_outputs: int = Field(default=1, ge=1, le=10)
    generation_parameters: dict = Field(default_factory=dict)
    idempotency_key: Optional[str] = None

class GenerationCancelRequest(BaseModel):
    reason: Optional[str] = None

async def _get_user_brand_role(user_id: int, brand_id: int, db: AsyncSession) -> str:
    owner = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.owner_id == user_id))
    if owner.scalars().first():
        return "owner"
    member = await db.execute(select(BrandMember).where(BrandMember.brand_id == brand_id, BrandMember.user_id == user_id))
    m = member.scalars().first()
    return m.role if m else "none"

async def _validate_assets_belong_to_brand(asset_ids: List[int], brand_id: int, db: AsyncSession):
    for asset_id in asset_ids:
        result = await db.execute(select(Asset).where(Asset.id == asset_id))
        asset = result.scalars().first()
        if not asset or asset.brand_id != brand_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Asset {asset_id} does not belong to this brand.")

@router.post("/api/v1/campaigns/{campaign_id}/generate", status_code=status.HTTP_201_CREATED)
async def generate_campaign(campaign_id: int, payload: CampaignGenerationRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    campaign_result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = campaign_result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    role = await _get_user_brand_role(current_user.id, campaign.brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this brand.")
    if role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot generate content.")
    char_result = await db.execute(select(Character).where(Character.id == payload.character_id, Character.brand_id == campaign.brand_id))
    character = char_result.scalars().first()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found in this brand.")
    version_result = await db.execute(select(CharacterVersion).where(CharacterVersion.id == payload.character_version_id, CharacterVersion.character_id == payload.character_id))
    version = version_result.scalars().first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character version not found.")
    all_asset_ids = payload.asset_ids + payload.garment_asset_ids + ([payload.pose_reference_asset_id] if payload.pose_reference_asset_id else []) + ([payload.location_reference_asset_id] if payload.location_reference_asset_id else [])
    await _validate_assets_belong_to_brand(all_asset_ids, campaign.brand_id, db)
    idempotency_key = payload.idempotency_key or str(uuid.uuid4())
    existing_job = await db.execute(select(AIJob).where(AIJob.brand_id == campaign.brand_id, AIJob.inputs["idempotency_key"].astext == idempotency_key))
    if existing_job.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate generation request.")
    parent_job = AIJob(user_id=current_user.id, brand_id=campaign.brand_id, status="queued", job_type="campaign_generation", inputs={"campaign_id": campaign_id, "character_id": payload.character_id, "character_version_id": payload.character_version_id, "mlflow_run_id": version.mlflow_run_id, "number_of_outputs": payload.number_of_outputs, "generation_parameters": payload.generation_parameters, "idempotency_key": idempotency_key}, outputs={})
    db.add(parent_job)
    await db.flush()
    child_job_ids = []
    for i in range(payload.number_of_outputs):
        child_job = AIJob(user_id=current_user.id, brand_id=campaign.brand_id, status="queued", job_type="campaign_generation_output", inputs={"parent_job_id": parent_job.id, "output_index": i, "campaign_id": campaign_id, "character_version_id": payload.character_version_id, "mlflow_run_id": version.mlflow_run_id, "generation_parameters": payload.generation_parameters, "idempotency_key": f"{idempotency_key}_output_{i}"}, outputs={})
        db.add(child_job)
        await db.flush()
        child_job_ids.append(child_job.id)
    await db.commit()
    await db.refresh(parent_job)
    try:
        from app.worker import process_campaign_generation
        process_campaign_generation.delay(parent_job.id)
    except Exception as e:
        print(f"[CampaignGeneration] Celery dispatch failed: {e}")
    return {"job_id": parent_job.id, "child_job_ids": child_job_ids, "status": "queued", "idempotency_key": idempotency_key, "number_of_outputs": payload.number_of_outputs, "mlflow_run_id": version.mlflow_run_id}

@router.get("/api/v1/campaigns/{campaign_id}/generations")
async def list_campaign_generations(campaign_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    campaign_result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = campaign_result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    role = await _get_user_brand_role(current_user.id, campaign.brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this brand.")
    jobs_result = await db.execute(select(AIJob).where(AIJob.brand_id == campaign.brand_id, AIJob.job_type == "campaign_generation", AIJob.inputs["campaign_id"].astext == str(campaign_id)).order_by(AIJob.created_at.desc()))
    jobs = jobs_result.scalars().all()
    return [{"job_id": j.id, "status": j.status, "inputs": j.inputs, "outputs": j.outputs, "created_at": j.created_at.isoformat()} for j in jobs]

@router.get("/api/v1/generations/{job_id}")
async def get_generation_status(job_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job_result = await db.execute(select(AIJob).where(AIJob.id == job_id))
    job = job_result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation job not found.")
    role = await _get_user_brand_role(current_user.id, job.brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this brand.")
    children_result = await db.execute(select(AIJob).where(AIJob.inputs["parent_job_id"].astext == str(job_id), AIJob.job_type == "campaign_generation_output"))
    children = children_result.scalars().all()
    completed = sum(1 for c in children if c.status == "completed")
    failed = sum(1 for c in children if c.status == "failed")
    total = len(children) or 1
    progress = int((completed / total) * 100)
    return {"job_id": job.id, "status": job.status, "progress": progress, "completed_outputs": completed, "failed_outputs": failed, "total_outputs": total, "generated_asset_ids": job.outputs.get("generated_asset_ids", []), "mlflow_run_id": job.inputs.get("mlflow_run_id"), "created_at": job.created_at.isoformat()}

@router.post("/api/v1/generations/{job_id}/cancel")
async def cancel_generation(job_id: int, payload: GenerationCancelRequest = GenerationCancelRequest(), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job_result = await db.execute(select(AIJob).where(AIJob.id == job_id))
    job = job_result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation job not found.")
    role = await _get_user_brand_role(current_user.id, job.brand_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Owner or Admin role to cancel.")
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot cancel job with status: {job.status}")
    job.status = "cancelled"
    updated_outputs = dict(job.outputs)
    updated_outputs["cancel_reason"] = payload.reason or "Cancelled by user"
    updated_outputs["cancelled_at"] = datetime.utcnow().isoformat()
    job.outputs = updated_outputs
    await db.commit()
    return {"job_id": job_id, "status": "cancelled", "reason": payload.reason}
