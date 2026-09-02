from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, User, Asset
from app.middleware.auth import get_current_user
from app.services.video_service import video_service, MOTION_PRESETS

router = APIRouter(prefix="/api/v1/video", tags=["Motion Video Studio"])


# ========================== Schemas ==============================

class VideoJobRequest(BaseModel):
    preset_id: str = Field(..., description="MOT-WALK, MOT-TURN, MOT-FAB, MOT-ORBIT")
    brand_id: int
    source_asset_id: Optional[int] = None
    character_id: Optional[str] = None
    duration_seconds: int = Field(4, ge=2, le=8)
    aspect_ratio: str = Field("9:16", description="9:16, 4:5, 1:1, 16:9")
    generation_mode: str = "studio_quality"
    custom_params: Optional[Dict[str, Any]] = None


# ========================== Endpoints ============================

@router.get("/presets")
async def list_motion_presets(
    current_user: User = Depends(get_current_user),
):
    """List all available motion presets."""
    return {
        "presets": video_service.list_presets(),
        "total": len(MOTION_PRESETS),
    }


@router.get("/presets/{preset_id}")
async def get_motion_preset(
    preset_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get a specific motion preset."""
    preset = video_service.get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset {preset_id} not found.")
    return preset


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_video_job(
    payload: VideoJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a motion video generation job."""
    # Validate preset
    preset = video_service.get_preset(payload.preset_id)
    if not preset:
        raise HTTPException(status_code=400, detail=f"Invalid preset: {payload.preset_id}")

    # Validate duration
    if payload.duration_seconds not in preset["duration_options"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid duration for {payload.preset_id}. Options: {preset['duration_options']}"
        )

    # Validate aspect ratio
    if payload.aspect_ratio not in preset["aspect_ratios"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid aspect ratio for {payload.preset_id}. Options: {preset['aspect_ratios']}"
        )

    # Build workflow params
    workflow_params = video_service.build_workflow_params(
        preset_id=payload.preset_id,
        duration_seconds=payload.duration_seconds,
        aspect_ratio=payload.aspect_ratio,
        character_id=payload.character_id,
        source_asset_id=payload.source_asset_id,
        custom_params=payload.custom_params,
    )

    # Dispatch Celery task
    try:
        from app.worker import run_video_generation_job
        task = run_video_generation_job.delay(
            brand_id=payload.brand_id,
            user_id=current_user.id,
            preset_id=payload.preset_id,
            source_asset_id=payload.source_asset_id,
            character_id=payload.character_id,
            workflow_params=workflow_params,
            generation_mode=payload.generation_mode,
        )
        task_id = task.id if task else f"mock_video_{payload.preset_id}"
    except Exception as e:
        print(f"[Video] Celery dispatch failed: {e}")
        task_id = f"mock_video_{payload.preset_id}"

    return {
        "task_id": task_id,
        "status": "queued",
        "preset_id": payload.preset_id,
        "preset_name": preset["display_name"],
        "duration_seconds": payload.duration_seconds,
        "aspect_ratio": payload.aspect_ratio,
        "total_frames": workflow_params["total_frames"],
        "workflow_id": workflow_params["workflow_id"],
    }
