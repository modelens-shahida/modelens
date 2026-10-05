from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
import asyncio
import json
import uuid

from app.models.db import (
    get_db, User,
    CatalogJob, CatalogJobItem,
    PoseGeometryPreset,
)
from app.middleware.auth import get_current_user
from app.api_docs import error_responses
from app.services.production_presets import ENVIRONMENT_PRESETS

router = APIRouter(prefix="/api/v1", tags=["Generation API & WebSockets"])


# ========================== Schemas ==============================

class AngleSlot(BaseModel):
    angle_code: str
    framing: str = "FULL_BODY"
    body_yaw_deg: float = 0.0
    head_pitch_deg: float = 0.0
    expression: str = "NEUTRAL"
    pose_id: Optional[str] = None


class GenerationRequest(BaseModel):
    product_id: str
    character_id: str = Field(..., description="e.g. EE-F-002")
    character_version: str = "1.0"
    angle_slots: List[AngleSlot]
    environment_id: Optional[str] = None
    quality_mode: str = "STUDIO_QUALITY"
    output_format: str = "PNG"
    project_name: Optional[str] = None


class QAEvaluationResponse(BaseModel):
    asset_id: str
    identity_similarity: Optional[float] = None
    pose_accuracy: Optional[float] = None
    hand_qa: Optional[str] = None
    feet_qa: Optional[str] = None
    garment_qa: Optional[str] = None
    overall_score: Optional[float] = None
    status: str = "NOT_REVIEWED"


# ========================== WebSocket Manager ====================

class GenerationConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast_progress(self, job_id: str, event: Dict):
        if job_id in self.active_connections:
            dead = []
            for ws in self.active_connections[job_id]:
                try:
                    await ws.send_json(event)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active_connections[job_id].remove(ws)


manager = GenerationConnectionManager()


# ========================== Generation Endpoints =================

@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    summary="Create a generation job",
    description="Create a new generation job with character, product, angles and environment.",
    response_description="The created generation job.",
    operation_id="create_generation_job",
    responses=error_responses(401, 422),
)
async def create_generation_job(
    payload: GenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new generation job with character, product, angles and environment."""
    job_id = str(uuid.uuid4())

    job = CatalogJob(
        job_id=job_id,
        user_id=current_user.id,
        brand_id=current_user.brand_id if hasattr(current_user, 'brand_id') else 1,
        status="queued",
        quality_mode=payload.quality_mode,
        total_skus=len(payload.angle_slots),
        meta={
            "character_id": payload.character_id,
            "character_version": payload.character_version,
            "product_id": payload.product_id,
            "environment_id": payload.environment_id,
            "project_name": payload.project_name,
            "angle_slots": [slot.dict() for slot in payload.angle_slots],
        }
    )
    db.add(job)
    await db.commit()

    return {
        "job_id": job_id,
        "status": "queued",
        "total_angles": len(payload.angle_slots),
        "character_id": payload.character_id,
        "product_id": payload.product_id,
        "quality_mode": payload.quality_mode,
        "websocket_url": f"/api/v1/ws/generation/{job_id}",
        "created_at": str(datetime.utcnow()),
    }


@router.get(
    "/generate/{job_id}",
    summary="Get a generation job",
    description="Get generation job status and results.",
    response_description="Generation job status and results.",
    operation_id="get_generation_job",
    responses=error_responses(401, 404, 422),
)
async def get_generation_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get generation job status and results."""
    result = await db.execute(
        select(CatalogJob).where(CatalogJob.job_id == job_id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    items = await db.execute(
        select(CatalogJobItem).where(CatalogJobItem.job_id == job.id)
    )
    items = items.scalars().all()

    return {
        "job_id": job_id,
        "status": job.status,
        "total_angles": job.total_skus,
        "completed": job.completed_skus or 0,
        "failed": job.failed_skus or 0,
        "quality_mode": job.quality_mode,
        "meta": job.meta,
        "results": [
            {
                "item_id": item.id,
                "angle_code": item.meta.get("angle_code") if item.meta else None,
                "status": item.status,
                "output_url": item.output_image_url,
                "qa_score": item.qa_score,
            }
            for item in items
        ],
        "created_at": str(job.created_at),
    }


# ========================== WebSocket Endpoint ===================

@router.websocket("/ws/generation/{job_id}")
async def generation_websocket(
    job_id: str,
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
):
    """WebSocket for real-time generation progress per angle tile."""
    await manager.connect(job_id, websocket)
    try:
        # Send initial connection event
        await websocket.send_json({
            "event": "connected",
            "job_id": job_id,
            "message": "Connected to generation stream",
            "timestamp": str(datetime.utcnow()),
        })

        while True:
            # Poll job status
            result = await db.execute(
                select(CatalogJob).where(CatalogJob.job_id == job_id)
            )
            job = result.scalars().first()

            if job:
                await websocket.send_json({
                    "event": "progress",
                    "job_id": job_id,
                    "status": job.status,
                    "completed": job.completed_skus or 0,
                    "total": job.total_skus or 0,
                    "failed": job.failed_skus or 0,
                    "timestamp": str(datetime.utcnow()),
                })

                if job.status in ["completed", "failed", "partial"]:
                    await websocket.send_json({
                        "event": "finished",
                        "job_id": job_id,
                        "status": job.status,
                        "timestamp": str(datetime.utcnow()),
                    })
                    break

            await asyncio.sleep(2)

    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)


# ========================== Preset Pickers =======================

@router.get(
    "/pose-geometry-presets",
    summary="List pose/angle presets",
    description="Get pose/angle presets for Create Production drawer.",
    response_description="Pose and angle presets for the Create Production drawer.",
    operation_id="list_pose_geometry_presets",
    responses=error_responses(401, 422),
)
async def get_pose_presets(
    family: Optional[str] = None,
    framing: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pose/angle presets for Create Production drawer."""
    query = select(PoseGeometryPreset).where(
        PoseGeometryPreset.customer_visible == True,
        PoseGeometryPreset.status == "APPROVED",
    )
    if family:
        query = query.where(PoseGeometryPreset.family == family)

    result = await db.execute(query.order_by(PoseGeometryPreset.id))
    presets = result.scalars().all()

    return {"presets": [
        {
            "preset_id": p.preset_id,
            "display_name": p.display_name,
            "family": p.family,
            "body_yaw": p.body_yaw,
            "head_yaw": p.head_yaw,
            "head_pitch": p.head_pitch,
            "gaze": p.gaze,
            "expression_id": p.expression_id,
            "complexity": p.complexity,
            "risk": p.risk,
        }
        for p in presets
    ]}


@router.get(
    "/environments",
    summary="List environment presets",
    description="Get environment presets for Create Production background picker.",
    response_description="Environment presets for the background picker.",
    operation_id="list_environment_presets",
    responses=error_responses(401, 422),
)
async def get_environments(
    family: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get environment presets for Create Production background picker."""
    environments = [dict(env) for env in ENVIRONMENT_PRESETS]

    if family:
        environments = [e for e in environments if e["family"] == family]

    return {"environments": environments, "total": len(environments)}


# ========================== QA Evaluation ========================

@router.get(
    "/qa/evaluations/{asset_id}",
    summary="Get QA scores for an asset",
    description="Get QA evaluation scores for a generated asset.",
    response_description="QA evaluation scores for the generated asset.",
    operation_id="get_generation_qa_evaluation",
    responses=error_responses(401, 422),
)
async def get_qa_evaluation(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get QA evaluation scores for a generated asset."""
    from app.models.db import CanonicalAsset

    result = await db.execute(
        select(CanonicalAsset).where(CanonicalAsset.asset_id == asset_id)
    )
    asset = result.scalars().first()

    if not asset:
        return {
            "asset_id": asset_id,
            "identity_similarity": None,
            "pose_accuracy": None,
            "hand_qa": "NOT_REVIEWED",
            "feet_qa": "NOT_REVIEWED",
            "garment_qa": "NOT_REVIEWED",
            "overall_score": None,
            "status": "NOT_REVIEWED",
        }

    return {
        "asset_id": asset_id,
        "identity_qa": asset.identity_qa,
        "body_qa": asset.body_qa,
        "hand_qa": asset.hands_qa,
        "feet_qa": asset.feet_qa,
        "angle_qa": asset.angle_qa,
        "artifact_qa": asset.artifact_qa,
        "overall_qa_status": asset.overall_qa_status,
        "training_eligible": asset.training_eligible,
        "production_reference_eligible": asset.production_reference_eligible,
        "status": asset.overall_qa_status,
    }
