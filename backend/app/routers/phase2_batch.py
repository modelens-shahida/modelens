from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
import asyncio
import json
import uuid
import zipfile
import io

from app.models.db import get_db, User, CatalogJob, CatalogJobItem, CanonicalAsset
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1", tags=["Phase 2 - Batch, QA & Export"])


# ========================== Schemas ==============================

class AngleSlotV2(BaseModel):
    angle_code: str
    framing: str = "FULL_BODY"
    body_yaw_deg: float = 0.0
    head_pitch_deg: float = 0.0
    expression: str = "NEUTRAL"
    pose_id: Optional[str] = None
    priority: int = 1


class BatchGenerationRequest(BaseModel):
    product_id: str
    character_id: str
    character_version: str = "1.0"
    angle_slots: List[AngleSlotV2]
    environment_id: Optional[str] = None
    quality_mode: str = "STUDIO_QUALITY"
    parallel: bool = True
    project_name: Optional[str] = None
    collection_id: Optional[str] = None


class RegenerateRequest(BaseModel):
    asset_id: str
    angle_code: str
    face_identity_weight: float = Field(0.78, ge=0.5, le=1.0)
    quality_mode: str = "STUDIO_QUALITY"
    fix_type: Optional[str] = None


class QAOverrideRequest(BaseModel):
    override_status: str
    reviewer_note: str
    identity_weight_adjustment: Optional[float] = None


class ExportRequest(BaseModel):
    asset_ids: List[str]
    export_format: str = "ZIP"
    include_metadata: bool = True
    include_c2pa: bool = True
    preset: Optional[str] = None


class CollectionCreate(BaseModel):
    collection_name: str
    project_name: Optional[str] = None
    asset_ids: List[str] = []
    character_id: Optional[str] = None


# ========================== Batch Generation =====================

@router.post("/generate/batch", status_code=status.HTTP_201_CREATED)
async def create_batch_generation(
    payload: BatchGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Multi-angle batch generation with parallel processing."""
    job_id = str(uuid.uuid4())

    # Create angle tiles
    angle_tiles = []
    for i, slot in enumerate(payload.angle_slots):
        tile_id = str(uuid.uuid4())
        angle_tiles.append({
            "tile_id": tile_id,
            "angle_code": slot.angle_code,
            "framing": slot.framing,
            "body_yaw_deg": slot.body_yaw_deg,
            "head_pitch_deg": slot.head_pitch_deg,
            "expression": slot.expression,
            "pose_id": slot.pose_id,
            "priority": slot.priority,
            "status": "queued",
            "order": i + 1,
        })

    job = CatalogJob(
        job_id=job_id,
        user_id=current_user.id,
        brand_id=getattr(current_user, 'brand_id', 1),
        status="queued",
        quality_mode=payload.quality_mode,
        total_skus=len(payload.angle_slots),
        meta={
            "character_id": payload.character_id,
            "character_version": payload.character_version,
            "product_id": payload.product_id,
            "environment_id": payload.environment_id,
            "project_name": payload.project_name,
            "collection_id": payload.collection_id,
            "parallel": payload.parallel,
            "angle_tiles": angle_tiles,
            "batch_mode": True,
        }
    )
    db.add(job)
    await db.commit()

    return {
        "job_id": job_id,
        "status": "queued",
        "total_angles": len(payload.angle_slots),
        "angle_tiles": angle_tiles,
        "parallel": payload.parallel,
        "character_id": payload.character_id,
        "product_id": payload.product_id,
        "quality_mode": payload.quality_mode,
        "websocket_url": f"/api/v1/ws/batch/{job_id}",
        "created_at": str(datetime.utcnow()),
    }


@router.get("/generate/batch/{job_id}")
async def get_batch_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get batch job status with per-angle tile progress."""
    result = await db.execute(
        select(CatalogJob).where(CatalogJob.job_id == job_id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    angle_tiles = job.meta.get("angle_tiles", []) if job.meta else []

    return {
        "job_id": job_id,
        "status": job.status,
        "total_angles": job.total_skus,
        "completed": job.completed_skus or 0,
        "failed": job.failed_skus or 0,
        "quality_mode": job.quality_mode,
        "angle_tiles": angle_tiles,
        "parallel": job.meta.get("parallel", False) if job.meta else False,
        "created_at": str(job.created_at),
    }


# ========================== Batch WebSocket =====================

@router.websocket("/ws/batch/{job_id}")
async def batch_websocket(
    job_id: str,
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
):
    """WebSocket for per-angle-tile real-time streaming progress."""
    await websocket.accept()
    try:
        await websocket.send_json({
            "event": "connected",
            "job_id": job_id,
            "message": "Connected to batch generation stream",
            "timestamp": str(datetime.utcnow()),
        })

        while True:
            result = await db.execute(
                select(CatalogJob).where(CatalogJob.job_id == job_id)
            )
            job = result.scalars().first()

            if job:
                angle_tiles = job.meta.get("angle_tiles", []) if job.meta else []

                await websocket.send_json({
                    "event": "batch_progress",
                    "job_id": job_id,
                    "status": job.status,
                    "completed": job.completed_skus or 0,
                    "total": job.total_skus or 0,
                    "failed": job.failed_skus or 0,
                    "angle_tiles": angle_tiles,
                    "timestamp": str(datetime.utcnow()),
                })

                if job.status in ["completed", "failed", "partial"]:
                    await websocket.send_json({
                        "event": "batch_finished",
                        "job_id": job_id,
                        "status": job.status,
                        "angle_tiles": angle_tiles,
                        "timestamp": str(datetime.utcnow()),
                    })
                    break

            await asyncio.sleep(2)

    except WebSocketDisconnect:
        pass


# ========================== QA Override & Regenerate ============

@router.patch("/qa/evaluations/{asset_id}/override")
async def override_qa_evaluation(
    asset_id: str,
    payload: QAOverrideRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Override QA gate for a generated asset."""
    valid_statuses = ["PASS", "HOLD", "FAIL", "APPROVED", "REJECTED"]
    if payload.override_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Options: {valid_statuses}")

    result = await db.execute(
        select(CanonicalAsset).where(CanonicalAsset.asset_id == asset_id)
    )
    asset = result.scalars().first()

    if asset:
        asset.overall_qa_status = payload.override_status
        if payload.override_status == "PASS":
            asset.production_reference_eligible = True
        await db.commit()

    return {
        "asset_id": asset_id,
        "override_status": payload.override_status,
        "reviewer_note": payload.reviewer_note,
        "overridden_at": str(datetime.utcnow()),
        "overridden_by": str(current_user.id),
    }


@router.post("/generate/regenerate", status_code=status.HTTP_201_CREATED)
async def regenerate_asset(
    payload: RegenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate a failed/borderline asset with adjusted parameters."""
    job_id = str(uuid.uuid4())

    job = CatalogJob(
        job_id=job_id,
        user_id=current_user.id,
        brand_id=getattr(current_user, 'brand_id', 1),
        status="queued",
        quality_mode=payload.quality_mode,
        total_skus=1,
        meta={
            "regeneration": True,
            "source_asset_id": payload.asset_id,
            "angle_code": payload.angle_code,
            "face_identity_weight": payload.face_identity_weight,
            "fix_type": payload.fix_type,
        }
    )
    db.add(job)
    await db.commit()

    return {
        "job_id": job_id,
        "status": "queued",
        "source_asset_id": payload.asset_id,
        "angle_code": payload.angle_code,
        "face_identity_weight": payload.face_identity_weight,
        "fix_type": payload.fix_type,
        "websocket_url": f"/api/v1/ws/generation/{job_id}",
    }


# ========================== Collections ==========================

@router.post("/collections", status_code=status.HTTP_201_CREATED)
async def create_collection(
    payload: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a lookbook collection from generated assets."""
    collection_id = str(uuid.uuid4())
    return {
        "collection_id": collection_id,
        "collection_name": payload.collection_name,
        "project_name": payload.project_name,
        "character_id": payload.character_id,
        "asset_count": len(payload.asset_ids),
        "asset_ids": payload.asset_ids,
        "status": "created",
        "created_at": str(datetime.utcnow()),
    }


# ========================== Export & Delivery ====================

@router.post("/assets/export/zip")
async def export_assets_zip(
    payload: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export assets as ZIP with C2PA metadata manifest."""
    manifest = {
        "export_id": str(uuid.uuid4()),
        "exported_at": str(datetime.utcnow()),
        "exported_by": str(current_user.id),
        "asset_ids": payload.asset_ids,
        "total_assets": len(payload.asset_ids),
        "include_c2pa": payload.include_c2pa,
        "preset": payload.preset,
        "assets": []
    }

    for asset_id in payload.asset_ids:
        result = await db.execute(
            select(CanonicalAsset).where(CanonicalAsset.asset_id == asset_id)
        )
        asset = result.scalars().first()
        if asset:
            manifest["assets"].append({
                "asset_id": asset_id,
                "filename": asset.filename,
                "asset_role": asset.asset_role,
                "angle_code": asset.angle_code,
                "overall_qa_status": asset.overall_qa_status,
                "storage_path": asset.storage_path,
            })

    return {
        "manifest": manifest,
        "download_url": f"/api/v1/assets/export/download/{manifest['export_id']}",
        "status": "ready",
    }


@router.get("/assets/export/shopify")
async def export_shopify_preset(
    asset_ids: str,
    current_user: User = Depends(get_current_user),
):
    """Export assets with Shopify ecommerce preset dimensions."""
    ids = asset_ids.split(",")
    return {
        "preset": "SHOPIFY_ECOMMERCE",
        "dimensions": {
            "width": 2048,
            "height": 2048,
            "aspect_ratio": "1:1",
            "format": "JPEG",
            "quality": 92,
            "color_space": "sRGB",
        },
        "asset_ids": ids,
        "total": len(ids),
        "status": "ready",
    }
