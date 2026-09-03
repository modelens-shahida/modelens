from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import get_db, User
from app.middleware.auth import get_current_user
from app.services.fluid_service import fluid_service, LIGHTING_PRESETS, FOCAL_LENGTHS, APERTURES

router = APIRouter(prefix="/api/v1/fluid", tags=["Fluid Studio"])


# ========================== Schemas ==============================

class FluidJobRequest(BaseModel):
    preset_id: str = Field(..., description="STUDIO_SOFT_DIFFUSE, EDITORIAL_HARD_HIGH_KEY, NATURAL_GOLDEN_HOUR, DRAMATIC_CHIAROSCURO, CYBERPUNK_NEON")
    brand_id: int
    source_asset_id: Optional[int] = None
    character_id: Optional[str] = None
    focal_length_mm: int = Field(85, description="35, 50, 85, 105")
    aperture: float = Field(2.8, description="1.4, 1.8, 2.8, 4.0, 5.6, 8.0")
    generation_mode: str = "studio_quality"
    prompt: Optional[str] = None
    custom_params: Optional[Dict[str, Any]] = None


# ========================== Endpoints ============================

@router.get("/presets")
async def list_fluid_presets(
    current_user: User = Depends(get_current_user),
):
    """List all available lighting presets."""
    return {
        "presets": fluid_service.list_presets(),
        "total": len(LIGHTING_PRESETS),
        "focal_lengths": FOCAL_LENGTHS,
        "apertures": APERTURES,
    }


@router.get("/presets/{preset_id}")
async def get_fluid_preset(
    preset_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get a specific lighting preset."""
    preset = fluid_service.get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset {preset_id} not found.")
    return preset


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_fluid_job(
    payload: FluidJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a Fluid Studio editorial generation job."""
    # Validate preset
    preset = fluid_service.get_preset(payload.preset_id)
    if not preset:
        raise HTTPException(status_code=400, detail=f"Invalid preset: {payload.preset_id}")

    # Build workflow params
    try:
        workflow_params = fluid_service.build_workflow_params(
            preset_id=payload.preset_id,
            focal_length_mm=payload.focal_length_mm,
            aperture=payload.aperture,
            character_id=payload.character_id,
            source_asset_id=payload.source_asset_id,
            custom_params=payload.custom_params,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Dispatch Celery task
    try:
        from app.worker import run_fluid_generation_job
        task = run_fluid_generation_job.delay(
            brand_id=payload.brand_id,
            user_id=current_user.id,
            preset_id=payload.preset_id,
            source_asset_id=payload.source_asset_id,
            character_id=payload.character_id,
            workflow_params=workflow_params,
            generation_mode=payload.generation_mode,
            prompt=payload.prompt,
        )
        task_id = task.id if task else f"mock_fluid_{payload.preset_id}"
    except Exception as e:
        print(f"[Fluid] Celery dispatch failed: {e}")
        task_id = f"mock_fluid_{payload.preset_id}"

    return {
        "task_id": task_id,
        "status": "queued",
        "preset_id": payload.preset_id,
        "preset_name": preset["display_name"],
        "focal_length_mm": payload.focal_length_mm,
        "aperture": f"f/{payload.aperture}",
        "taxonomy_id": preset["taxonomy_id"],
        "workflow_id": "WF-FLUID-001",
    }
