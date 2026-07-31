from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, User, VideoProject, VideoClip, VideoRender
from app.middleware.auth import get_current_user
from app.worker import process_video_generation, process_video_render

router = APIRouter(prefix="/api/v1/video-projects", tags=["Move Studio"])

# ========================== Motion Presets =======================

MOTION_PRESETS = [
    "SUBTLE_FASHION", "RUNWAY_WALK", "ORBIT", "PUSH_IN", "PAN", "HANDHELD"
]

CREDITS_PER_CLIP = 5

# ========================== Schemas ==============================

class VideoProjectCreate(BaseModel):
    brand_id: int
    name: str = Field(..., max_length=255)
    master_prompt: Optional[str] = None
    aspect_ratio: Optional[str] = "16:9"
    mode: Optional[str] = "standard"


class StoryboardCreate(BaseModel):
    master_prompt: Optional[str] = None
    motion_preset: Optional[str] = "SUBTLE_FASHION"
    duration: Optional[float] = 4.0
    num_clips: int = Field(default=3, ge=1, le=5)
    start_image_url: Optional[str] = None
    end_image_url: Optional[str] = None


class GenerateRequest(BaseModel):
    provider: Optional[str] = "AUTO"


class RenderRequest(BaseModel):
    audio_url: Optional[str] = None
    logo_url: Optional[str] = None
    resolution: Optional[str] = "1080p"


# ========================== Endpoints ============================

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_video_project(
    payload: VideoProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new video project."""
    project = VideoProject(
        user_id=current_user.id,
        brand_id=payload.brand_id,
        name=payload.name,
        master_prompt=payload.master_prompt,
        aspect_ratio=payload.aspect_ratio,
        mode=payload.mode,
        status="draft",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    return {
        "project_id": project.id,
        "name": project.name,
        "status": project.status,
        "created_at": project.created_at.isoformat(),
    }


@router.get("/{project_id}")
async def get_video_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get video project metadata and timeline."""
    result = await db.execute(
        select(VideoProject).where(VideoProject.id == project_id, VideoProject.user_id == current_user.id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")

    clips_result = await db.execute(
        select(VideoClip).where(VideoClip.project_id == project_id).order_by(VideoClip.position)
    )
    clips = clips_result.scalars().all()

    renders_result = await db.execute(
        select(VideoRender).where(VideoRender.project_id == project_id).order_by(VideoRender.created_at.desc())
    )
    renders = renders_result.scalars().all()

    return {
        "project_id": project.id,
        "name": project.name,
        "master_prompt": project.master_prompt,
        "aspect_ratio": project.aspect_ratio,
        "mode": project.mode,
        "status": project.status,
        "clips": [
            {
                "id": c.id,
                "position": c.position,
                "prompt": c.prompt,
                "motion_preset": c.motion_preset,
                "duration": c.duration,
                "status": c.status,
                "clip_url": c.clip_url,
                "provider": c.provider,
            }
            for c in clips
        ],
        "renders": [
            {
                "id": r.id,
                "status": r.status,
                "output_url": r.output_url,
                "duration_seconds": r.duration_seconds,
            }
            for r in renders
        ],
        "created_at": project.created_at.isoformat(),
    }


@router.post("/{project_id}/storyboard", status_code=status.HTTP_201_CREATED)
async def create_storyboard(
    project_id: int,
    payload: StoryboardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Initialize storyboard with 1-5 clips."""
    result = await db.execute(
        select(VideoProject).where(VideoProject.id == project_id, VideoProject.user_id == current_user.id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")

    # Delete existing clips
    existing = await db.execute(select(VideoClip).where(VideoClip.project_id == project_id))
    for clip in existing.scalars().all():
        await db.delete(clip)

    # Create new clips
    clips = []
    for i in range(payload.num_clips):
        clip = VideoClip(
            project_id=project_id,
            position=i,
            prompt=payload.master_prompt or project.master_prompt,
            motion_preset=payload.motion_preset,
            duration=payload.duration,
            start_image_url=payload.start_image_url if i == 0 else None,
            end_image_url=payload.end_image_url if i == payload.num_clips - 1 else None,
            status="queued",
        )
        db.add(clip)
        clips.append(clip)

    project.master_prompt = payload.master_prompt or project.master_prompt
    await db.commit()

    return {
        "project_id": project_id,
        "clips_created": payload.num_clips,
        "motion_preset": payload.motion_preset,
    }


@router.post("/{project_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_video(
    project_id: int,
    payload: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reserve credits and trigger animation generation."""
    result = await db.execute(
        select(VideoProject).where(VideoProject.id == project_id, VideoProject.user_id == current_user.id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")

    clips_result = await db.execute(
        select(VideoClip).where(VideoClip.project_id == project_id, VideoClip.status == "queued")
    )
    clips = clips_result.scalars().all()
    if not clips:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No queued clips to generate.")

    # Check credits
    credits_needed = len(clips) * CREDITS_PER_CLIP
    if (current_user.credits or 0) < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Need {credits_needed}, have {current_user.credits or 0}."
        )

    current_user.credits = (current_user.credits or 0) - credits_needed
    project.status = "generating"
    await db.commit()

    # Dispatch Celery task
    try:
        process_video_generation.delay(project_id, payload.provider or "AUTO")
    except Exception as e:
        print(f"[VideoProject] Celery dispatch failed: {e}")

    return {
        "project_id": project_id,
        "status": "generating",
        "clips_queued": len(clips),
        "credits_reserved": credits_needed,
    }


@router.post("/{project_id}/render", status_code=status.HTTP_202_ACCEPTED)
async def render_video(
    project_id: int,
    payload: RenderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit timeline to FFmpeg renderer."""
    result = await db.execute(
        select(VideoProject).where(VideoProject.id == project_id, VideoProject.user_id == current_user.id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")

    render = VideoRender(
        project_id=project_id,
        status="queued",
        resolution=payload.resolution,
        audio_url=payload.audio_url,
        logo_url=payload.logo_url,
    )
    db.add(render)
    await db.commit()
    await db.refresh(render)

    try:
        process_video_render.delay(render.id)
    except Exception as e:
        print(f"[VideoRender] Celery dispatch failed: {e}")

    return {"render_id": render.id, "status": "queued"}


# ========================== Generation Job Status ================

gen_router = APIRouter(prefix="/api/v1/generation-jobs", tags=["Move Studio"])


@gen_router.get("/{job_id}")
async def get_generation_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get generation job status."""
    result = await db.execute(
        select(VideoClip).where(VideoClip.id == job_id)
    )
    clip = result.scalars().first()
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation job not found.")

    return {
        "job_id": clip.id,
        "status": clip.status,
        "clip_url": clip.clip_url,
        "provider": clip.provider,
        "position": clip.position,
    }
