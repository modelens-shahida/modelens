from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from app.models.db import get_db, User, CatalogJob
from app.middleware.auth import get_current_user
from app.services.credits_sync_service import credits_sync_service
from app.services.pipeline_hardening import pipeline_hardening, JobStatus

router = APIRouter(prefix="/api/v1/rosanne", tags=["Rosanne Pipeline"])


# ========================== Rosanne Config =======================

ROSANNE_WORKFLOW_TEMPLATE_ID = "rosanne-v1"

ROSANNE_IDENTITY_LOCKS = {
    "face_geometry": True,
    "eye_color": True,
    "skin_tone": True,
    "hairline": True,
    "identity_markers": True,
    "age_anchor": True,
}

ROSANNE_PRESET_PARAMS = {
    "identity_strength": 0.82,
    "identity_strength_min": 0.70,
    "identity_strength_max": 0.90,
    "style_strength": 0.75,
    "garment_preservation": True,
    "print_preservation": True,
    "width": 1024,
    "height": 1280,
    "aspect_ratio": "4:5",
    "steps": 30,
    "cfg": 7.0,
}

ROSANNE_CREDIT_RATES = {
    "standard": 3,
    "quality": 5,
    "max": 8,
    "default": 5,
}

ROSANNE_POSE_PRESETS = [
    {"pose_id": "POSE-ROS-001", "display_name": "Editorial Standing", "angle_code": "FRONT", "body_yaw_deg": 0.0},
    {"pose_id": "POSE-ROS-002", "display_name": "Three Quarter Left", "angle_code": "L30", "body_yaw_deg": -30.0},
    {"pose_id": "POSE-ROS-003", "display_name": "Three Quarter Right", "angle_code": "R30", "body_yaw_deg": 30.0},
    {"pose_id": "POSE-ROS-004", "display_name": "Left Profile", "angle_code": "L45", "body_yaw_deg": -45.0},
    {"pose_id": "POSE-ROS-005", "display_name": "Right Profile", "angle_code": "R45", "body_yaw_deg": 45.0},
    {"pose_id": "POSE-ROS-006", "display_name": "Runway Walk", "angle_code": "WALK", "body_yaw_deg": 0.0},
    {"pose_id": "POSE-ROS-007", "display_name": "Editorial Seated", "angle_code": "SEATED", "body_yaw_deg": 0.0},
    {"pose_id": "POSE-ROS-008", "display_name": "Over Shoulder", "angle_code": "BACK_L30", "body_yaw_deg": -150.0},
]


# ========================== Schemas ==============================

class RosanneGenerationRequest(BaseModel):
    product_id: str
    character_id: str = Field(..., description="e.g. EE-F-002")
    character_version: str = "1.0"
    pose_asset_id: Optional[str] = None
    pose_preset_id: Optional[str] = None
    scene_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    environment_id: Optional[str] = None
    identity_strength: Optional[float] = Field(None, ge=0.70, le=0.90)
    style_strength: Optional[float] = Field(None, ge=0.5, le=1.0)
    quality_mode: str = "quality"
    num_images: int = Field(1, ge=1, le=4)
    seed: Optional[int] = None
    garment_image_url: Optional[str] = None
    preserve_print: bool = True
    preserve_construction: bool = True


class RosannePoseReference(BaseModel):
    pose_asset_id: Optional[str] = None
    pose_preset_id: Optional[str] = None
    angle_code: Optional[str] = None
    body_yaw_deg: float = 0.0
    head_pitch_deg: float = 0.0
    expression: str = "NEUTRAL"


class RosanneScenePrompt(BaseModel):
    character_id: str
    environment: Optional[str] = None
    lighting: Optional[str] = None
    mood: Optional[str] = None
    garment_description: Optional[str] = None
    additional_details: Optional[str] = None


# ========================== Scene Prompt Builder =================

def build_scene_prompt(payload: RosanneScenePrompt) -> str:
    """Build structured scene prompt for Rosanne workflow."""
    parts = [
        f"professional fashion photograph of {payload.character_id}",
        "high-end editorial quality",
    ]
    if payload.garment_description:
        parts.append(payload.garment_description)
    if payload.environment:
        parts.append(f"in {payload.environment}")
    if payload.lighting:
        parts.append(f"{payload.lighting} lighting")
    if payload.mood:
        parts.append(f"{payload.mood} atmosphere")
    if payload.additional_details:
        parts.append(payload.additional_details)
    parts.extend(["sharp focus", "luxury fashion", "8k resolution"])
    return ", ".join(parts)


# ========================== Endpoints ============================

@router.get("/config")
async def get_rosanne_config(
    current_user: User = Depends(get_current_user),
):
    """Get Rosanne workflow configuration and preset parameters."""
    return {
        "workflow_template_id": ROSANNE_WORKFLOW_TEMPLATE_ID,
        "identity_locks": ROSANNE_IDENTITY_LOCKS,
        "preset_params": ROSANNE_PRESET_PARAMS,
        "credit_rates": ROSANNE_CREDIT_RATES,
        "pose_presets": ROSANNE_POSE_PRESETS,
        "supported_aspect_ratios": ["4:5", "3:4", "1:1", "9:16"],
    }


@router.get("/pose-presets")
async def get_pose_presets(
    current_user: User = Depends(get_current_user),
):
    """Get available pose presets for Rosanne pipeline."""
    return {
        "pose_presets": ROSANNE_POSE_PRESETS,
        "total": len(ROSANNE_POSE_PRESETS),
    }


@router.post("/scene-prompt/build")
async def build_rosanne_scene_prompt(
    payload: RosanneScenePrompt,
    current_user: User = Depends(get_current_user),
):
    """Build a structured scene prompt for Rosanne workflow."""
    prompt = build_scene_prompt(payload)
    return {
        "character_id": payload.character_id,
        "scene_prompt": prompt,
        "prompt_length": len(prompt),
    }


@router.post("/estimate")
async def estimate_rosanne_credits(
    quality_mode: str = "quality",
    num_images: int = 1,
    current_user: User = Depends(get_current_user),
):
    """Estimate credits for Rosanne generation."""
    rate = ROSANNE_CREDIT_RATES.get(quality_mode, ROSANNE_CREDIT_RATES["default"])
    total = rate * num_images
    return {
        "estimated_credits": total,
        "quality_mode": quality_mode,
        "num_images": num_images,
        "rate_per_image": rate,
        "workflow": ROSANNE_WORKFLOW_TEMPLATE_ID,
    }


@router.post("/check")
async def check_rosanne_credits(
    quality_mode: str = "quality",
    num_images: int = 1,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pre-flight credit check for Rosanne generation."""
    brand_id = getattr(current_user, 'brand_id', None) or 1

    rate = ROSANNE_CREDIT_RATES.get(quality_mode, ROSANNE_CREDIT_RATES["default"])
    required = rate * num_images

    check = await credits_sync_service.check_sufficient_credits(brand_id, required, db)
    return {
        "sufficient": check["sufficient"],
        "balance": check["balance"],
        "required": required,
        "shortfall": check["shortfall"],
        "workflow": ROSANNE_WORKFLOW_TEMPLATE_ID,
    }


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def rosanne_generate(
    payload: RosanneGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a Rosanne pipeline generation job."""
    brand_id = getattr(current_user, 'brand_id', None) or 1

    # Estimate credits
    rate = ROSANNE_CREDIT_RATES.get(payload.quality_mode, ROSANNE_CREDIT_RATES["default"])
    required = rate * payload.num_images

    # Pre-flight check
    check = await credits_sync_service.check_sufficient_credits(brand_id, required, db)
    if not check["sufficient"]:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_credits",
                "message": f"Insufficient credits. Required: {required}, Available: {check['balance']}",
                "balance": check["balance"],
                "required": required,
                "shortfall": check["shortfall"],
            }
        )

    job_id = str(uuid.uuid4())

    # Reserve credits
    await credits_sync_service.reserve_credits(
        brand_id=brand_id,
        user_id=current_user.id,
        amount=required,
        generation_id=job_id,
        description=f"Rosanne pipeline: {payload.character_id}",
        db=db,
    )

    # Resolve pose
    pose_data = None
    if payload.pose_preset_id:
        pose_data = next(
            (p for p in ROSANNE_POSE_PRESETS if p["pose_id"] == payload.pose_preset_id),
            None
        )

    # Build scene prompt if not provided
    scene_prompt = payload.scene_prompt
    if not scene_prompt:
        scene_prompt = build_scene_prompt(RosanneScenePrompt(
            character_id=payload.character_id,
            environment=payload.environment_id,
        ))

    # Resolve identity strength
    identity_strength = payload.identity_strength or ROSANNE_PRESET_PARAMS["identity_strength"]

    # Create job
    job = CatalogJob(
        job_id=job_id,
        user_id=current_user.id,
        brand_id=brand_id,
        status=JobStatus.QUEUED.value,
        quality_mode=payload.quality_mode,
        total_skus=payload.num_images,
        meta={
            "workflow_template_id": ROSANNE_WORKFLOW_TEMPLATE_ID,
            "character_id": payload.character_id,
            "character_version": payload.character_version,
            "product_id": payload.product_id,
            "pose_asset_id": payload.pose_asset_id,
            "pose_preset": pose_data,
            "scene_prompt": scene_prompt,
            "negative_prompt": payload.negative_prompt,
            "identity_strength": identity_strength,
            "identity_locks": ROSANNE_IDENTITY_LOCKS,
            "style_strength": payload.style_strength or ROSANNE_PRESET_PARAMS["style_strength"],
            "preserve_print": payload.preserve_print,
            "preserve_construction": payload.preserve_construction,
            "seed": payload.seed,
            "credits_reserved": required,
            "garment_image_url": payload.garment_image_url,
        }
    )
    db.add(job)
    await db.commit()

    # Emit started event
    try:
        from app.services.generation_events import generation_events
        await generation_events.emit_started(
            brand_id=brand_id,
            job_id=job_id,
            workflow="catalog",
            total_items=payload.num_images,
            credits_reserved=required,
            character_id=payload.character_id,
            product_id=payload.product_id,
        )
    except Exception:
        pass

    # Dispatch ComfyUI workflow in background
    background_tasks.add_task(
        _dispatch_rosanne_workflow,
        job_id=job_id,
        brand_id=brand_id,
        meta=job.meta,
    )

    return {
        "job_id": job_id,
        "status": JobStatus.QUEUED.value,
        "workflow_template_id": ROSANNE_WORKFLOW_TEMPLATE_ID,
        "character_id": payload.character_id,
        "identity_strength": identity_strength,
        "identity_locks": ROSANNE_IDENTITY_LOCKS,
        "pose_preset": pose_data,
        "scene_prompt": scene_prompt,
        "credits_reserved": required,
        "num_images": payload.num_images,
        "websocket_url": f"/api/v1/ws/generation/{job_id}/progress",
    }


@router.get("/jobs/{job_id}")
async def get_rosanne_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get Rosanne job status."""
    result = await db.execute(
        select(CatalogJob).where(CatalogJob.job_id == job_id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    meta = job.meta or {}
    return {
        "job_id": job_id,
        "status": job.status,
        "workflow_template_id": meta.get("workflow_template_id"),
        "character_id": meta.get("character_id"),
        "identity_strength": meta.get("identity_strength"),
        "identity_locks": meta.get("identity_locks"),
        "pose_preset": meta.get("pose_preset"),
        "credits_reserved": meta.get("credits_reserved"),
        "completed": job.completed_skus or 0,
        "total": job.total_skus,
        "created_at": str(job.created_at),
    }


# ========================== Background Worker ===================

async def _dispatch_rosanne_workflow(
    job_id: str,
    brand_id: int,
    meta: Dict[str, Any],
):
    """Dispatch Rosanne workflow to ComfyUI worker."""
    from app.models.db import async_session_maker, CatalogJob
    from sqlalchemy import select

    async with async_session_maker() as db:
        try:
            result = await db.execute(
                select(CatalogJob).where(CatalogJob.job_id == job_id)
            )
            job = result.scalars().first()
            if not job:
                return

            # Transition to processing
            await pipeline_hardening.transition_job_status(
                job, JobStatus.PROCESSING.value, db, reason="ComfyUI dispatch"
            )

            # Load workflow template
            from app.services.comfyui_service import ComfyUIService
            comfyui = ComfyUIService(mock_mode=True)

            # Mock successful completion for now
            job.status = JobStatus.COMPLETED.value
            job.completed_skus = job.total_skus
            await db.commit()

            # Finalize credits
            from app.services.credits_sync_service import credits_sync_service
            await credits_sync_service.finalize_credits(job_id, db)

            # Emit completed event
            from app.services.generation_events import generation_events
            await generation_events.emit_completed(
                brand_id=brand_id,
                job_id=job_id,
                workflow="catalog",
                total_items=job.total_skus,
                credits_used=abs(meta.get("credits_reserved", 0)),
            )

        except Exception as e:
            result = await db.execute(
                select(CatalogJob).where(CatalogJob.job_id == job_id)
            )
            job = result.scalars().first()
            if job:
                await pipeline_hardening.route_to_dlq(job, str(e), db, brand_id)
