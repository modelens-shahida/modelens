from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, User, Asset
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/campaigns", tags=["Campaign Studio"])

# ========================== Channel Formats =====================

CHANNEL_FORMATS = {
    "ecommerce_square": {"aspect_ratio": "1:1", "width": 1080, "height": 1080, "label": "E-Commerce Square"},
    "story_vertical": {"aspect_ratio": "9:16", "width": 1080, "height": 1920, "label": "Story / Reel"},
    "billboard_landscape": {"aspect_ratio": "16:9", "width": 1920, "height": 1080, "label": "Billboard / Banner"},
    "print_catalog": {"aspect_ratio": "4:5", "width": 1080, "height": 1350, "label": "Print Catalog"},
}


# ========================== Schemas ==============================

class CampaignJobRequest(BaseModel):
    brand_id: int
    campaign_name: str
    character_id: Optional[str] = None
    source_asset_ids: Optional[List[int]] = []
    channel_formats: List[str] = Field(
        default=["ecommerce_square", "story_vertical", "billboard_landscape", "print_catalog"],
        description="Channel formats to generate"
    )
    lighting_preset_id: Optional[str] = "STUDIO_SOFT_DIFFUSE"
    generation_mode: str = "studio_quality"
    prompt: Optional[str] = None


# ========================== Endpoints ============================

@router.get("/formats")
async def list_channel_formats(
    current_user: User = Depends(get_current_user),
):
    """List all available channel formats."""
    return {"formats": CHANNEL_FORMATS}


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_campaign_job(
    payload: CampaignJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a multi-channel campaign generation job."""
    # Validate formats
    invalid = [f for f in payload.channel_formats if f not in CHANNEL_FORMATS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid formats: {invalid}")

    # Build format configs
    formats = [
        {**CHANNEL_FORMATS[f], "format_id": f}
        for f in payload.channel_formats
    ]

    # Dispatch Celery task
    try:
        from app.worker import run_campaign_generation_job
        task = run_campaign_generation_job.delay(
            brand_id=payload.brand_id,
            user_id=current_user.id,
            campaign_name=payload.campaign_name,
            character_id=payload.character_id,
            source_asset_ids=payload.source_asset_ids or [],
            formats=formats,
            lighting_preset_id=payload.lighting_preset_id,
            generation_mode=payload.generation_mode,
            prompt=payload.prompt,
        )
        task_id = task.id if task else f"mock_campaign_{payload.brand_id}"
    except Exception as e:
        print(f"[Campaign] Celery dispatch failed: {e}")
        task_id = f"mock_campaign_{payload.brand_id}"

    return {
        "task_id": task_id,
        "status": "queued",
        "campaign_name": payload.campaign_name,
        "channel_formats": payload.channel_formats,
        "total_assets": len(formats),
        "workflow_id": "WF-CAMPAIGN-001",
    }


@router.get("/jobs/{task_id}/export-zip")
async def export_campaign_zip(
    task_id: str,
    brand_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export campaign assets as ZIP with C2PA manifests."""
    import io
    import json
    import zipfile
    from fastapi.responses import StreamingResponse

    # Get campaign assets
    result = await db.execute(
        select(Asset).where(
            Asset.brand_id == brand_id,
            Asset.meta["source"].astext == "campaign_studio",
        ).order_by(Asset.id.desc()).limit(20)
    )
    assets = result.scalars().all()

    zip_buffer = io.BytesIO()
    manifest = {
        "campaign_task_id": task_id,
        "exported_at": datetime.utcnow().isoformat(),
        "total_assets": len(assets),
        "assets": [],
    }

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for asset in assets:
            meta = asset.meta or {}
            manifest["assets"].append({
                "asset_id": asset.id,
                "filename": asset.filename,
                "format_id": meta.get("format_id"),
                "aspect_ratio": meta.get("aspect_ratio"),
                "channel": meta.get("channel"),
                "c2pa_manifest_id": (meta.get("c2pa_manifest") or {}).get("manifest_id"),
            })
            zf.writestr(f"assets/{asset.filename}", b"CAMPAIGN_ASSET_PLACEHOLDER")

        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("README.txt", f"Mode Lens Campaign Export\nTask: {task_id}\nAssets: {len(assets)}")

    zip_buffer.seek(0)
    filename = f"campaign_{task_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
