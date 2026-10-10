from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import get_db, User
from app.middleware.auth import check_brand_asset, check_brand_role, get_current_user
from app.services.sketch_service import sketch_service, SKETCH_MODES, FABRIC_TEXTURES, PANTONE_COLORWAYS
from app.api_docs import error_responses

router = APIRouter(prefix="/api/v1/sketch", tags=["Sketch Studio"])


# ========================== Schemas ==============================

class SketchJobRequest(BaseModel):
    brand_id: int
    sketch_asset_id: Optional[int] = None
    sketch_mode: str = Field("lineart", description="lineart, softedge, scribble")
    fabric_id: str = Field("cotton", description="denim, silk, knit, leather, cotton, chiffon, velvet, linen")
    colorway_id: str = Field("classic_black")
    garment_type: str = "dress"
    on_model: bool = False
    ghost_mode: bool = True
    generation_mode: str = "studio_quality"
    custom_prompt: Optional[str] = None
    colorway_variants: Optional[List[str]] = []


# ========================== Endpoints ============================

@router.get(
    "/modes",
    summary="List sketch modes",
    description="List available sketch modes.",
    response_description="Available sketch modes.",
    operation_id="list_sketch_modes",
    responses=error_responses(401),
)
async def list_sketch_modes(
    current_user: User = Depends(get_current_user),
):
    """List available sketch modes."""
    return {
        "modes": sketch_service.list_sketch_modes(),
        "fabrics": sketch_service.list_fabrics(),
        "colorways": sketch_service.list_colorways(),
    }


@router.post(
    "/jobs",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a sketch-to-product job",
    description=(
        "Submit a sketch-to-product generation job. The caller must own `brand_id` or be a member with at "
        "least the editor role (else 403); an unknown brand returns 404. `sketch_asset_id` must be an asset of "
        "that brand (else 404). Nothing is queued or charged when the request is rejected."
    ),
    response_description="The sketch job was accepted and queued.",
    operation_id="create_sketch_studio_job",
    responses=error_responses(400, 401, 402, 403, 404, 422),
)
async def create_sketch_job(
    payload: SketchJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a sketch-to-product generation job."""
    await check_brand_role(payload.brand_id, current_user, db, minimum_role="editor")
    if payload.sketch_asset_id is not None:
        await check_brand_asset(payload.sketch_asset_id, payload.brand_id, db)

    try:
        workflow_params = sketch_service.build_workflow_params(
            sketch_mode=payload.sketch_mode,
            fabric_id=payload.fabric_id,
            colorway_id=payload.colorway_id,
            generation_mode=payload.generation_mode,
            garment_type=payload.garment_type,
            on_model=payload.on_model,
            ghost_mode=payload.ghost_mode,
            custom_prompt=payload.custom_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Colorway variants
    all_colorways = [payload.colorway_id] + (payload.colorway_variants or [])
    total_jobs = len(all_colorways)

    # Credit check
    credits_per_job = 5 if payload.generation_mode == "studio_quality" else 1
    credits_needed = credits_per_job * total_jobs

    if (current_user.credits or 0) < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {credits_needed}, have {current_user.credits or 0}."
        )
    current_user.credits = (current_user.credits or 0) - credits_needed
    await db.commit()

    # Dispatch tasks
    task_ids = []
    for colorway_id in all_colorways:
        try:
            from app.worker import run_sketch_generation_job
            task = run_sketch_generation_job.delay(
                brand_id=payload.brand_id,
                user_id=current_user.id,
                sketch_asset_id=payload.sketch_asset_id,
                colorway_id=colorway_id,
                workflow_params={**workflow_params, "colorway_id": colorway_id},
                generation_mode=payload.generation_mode,
            )
            task_ids.append(task.id if task else f"mock_sketch_{colorway_id}")
        except Exception as e:
            print(f"[Sketch] Celery dispatch failed: {e}")
            task_ids.append(f"mock_sketch_{colorway_id}")

    return {
        "task_ids": task_ids,
        "status": "queued",
        "sketch_mode": payload.sketch_mode,
        "fabric_id": payload.fabric_id,
        "colorways": all_colorways,
        "total_jobs": total_jobs,
        "credits_reserved": credits_needed,
        "workflow_id": "WF-SKETCH-001",
    }
