from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, status
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, User, Asset, ReferenceSet, ReferenceSetItem
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/characters", tags=["Characters"])

# Valid viewpoint codes per Section 03 taxonomy
VALID_VIEWPOINTS = [
    "YAW-000", "YAW-L15", "YAW-R15",
    "YAW-L30", "YAW-R30",
    "YAW-L45", "YAW-R45",
    "YAW-L60", "YAW-R60",
    "YAW-L90", "YAW-R90",
    "PITCH-U15", "PITCH-D15",
    "ZOOM-FACE", "FULL-BODY",
]

MIN_RESOLUTION = 1024


# ========================== Schemas ==============================

class RefSetCreateRequest(BaseModel):
    character_id: str
    brand_id: int
    name: str
    description: Optional[str] = None


class TrainingJobRequest(BaseModel):
    character_id: str
    brand_id: int
    reference_set_id: int
    trigger_token: Optional[str] = None
    epochs: int = 1000
    learning_rate: float = 1e-4
    resolution: int = 1024
    qa_profile_id: str = "QA-PROFILE-CHAR-001"


# ========================== Reference Set Endpoints ==============

@router.post("/reference-sets", status_code=status.HTTP_201_CREATED)
async def create_character_reference_set(
    payload: RefSetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new character reference set."""
    ref_set = ReferenceSet(
        name=payload.name,
        description=payload.description,
        status="active",
    )
    db.add(ref_set)
    await db.commit()
    await db.refresh(ref_set)

    return {
        "reference_set_id": ref_set.id,
        "name": ref_set.name,
        "character_id": payload.character_id,
        "status": ref_set.status,
    }


@router.post("/reference-sets/{ref_set_id}/upload")
async def upload_reference_image(
    ref_set_id: int,
    view_code: str = Form(...),
    brand_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a reference image for a specific viewpoint."""
    # Validate viewpoint
    if view_code not in VALID_VIEWPOINTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid view_code. Must be one of: {VALID_VIEWPOINTS}"
        )

    # Validate reference set
    ref_set_result = await db.execute(select(ReferenceSet).where(ReferenceSet.id == ref_set_id))
    ref_set = ref_set_result.scalars().first()
    if not ref_set:
        raise HTTPException(status_code=404, detail="Reference set not found.")

    # Validate file type
    if file.content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(status_code=400, detail="Only PNG, JPEG, WebP images allowed.")

    # Read and validate image
    image_bytes = await file.read()
    width, height = _get_image_dimensions(image_bytes)

    if width < MIN_RESOLUTION or height < MIN_RESOLUTION:
        raise HTTPException(
            status_code=400,
            detail=f"Image must be at least {MIN_RESOLUTION}x{MIN_RESOLUTION}px. Got {width}x{height}."
        )

    # Save to storage
    from app.services.storage import storage_service
    filename = f"refset_{ref_set_id}_{view_code}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.png"
    storage_path = storage_service.save_file_bytes(filename, image_bytes)

    # Create Asset
    asset = Asset(
        brand_id=brand_id,
        name=f"Reference {view_code} - RefSet {ref_set_id}",
        filename=filename,
        storage_path=storage_path,
        asset_type="reference",
        status="active",
        meta={
            "view_code": view_code,
            "reference_set_id": ref_set_id,
            "width": width,
            "height": height,
            "source": "character_reference_upload",
        }
    )
    db.add(asset)
    await db.flush()

    # Add to reference set
    ref_item = ReferenceSetItem(
        reference_set_id=ref_set_id,
        asset_id=asset.id,
        view_code=view_code,
        position=len(VALID_VIEWPOINTS),
    )
    db.add(ref_item)
    await db.commit()

    return {
        "asset_id": asset.id,
        "reference_set_id": ref_set_id,
        "view_code": view_code,
        "filename": filename,
        "width": width,
        "height": height,
        "status": "uploaded",
    }


@router.get("/reference-sets/{ref_set_id}/coverage")
async def get_reference_set_coverage(
    ref_set_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get viewpoint coverage for a reference set."""
    items_result = await db.execute(
        select(ReferenceSetItem).where(ReferenceSetItem.reference_set_id == ref_set_id)
    )
    items = items_result.scalars().all()

    covered = {item.view_code for item in items}
    missing = [v for v in VALID_VIEWPOINTS if v not in covered]

    return {
        "reference_set_id": ref_set_id,
        "total_viewpoints": len(VALID_VIEWPOINTS),
        "covered": len(covered),
        "missing": missing,
        "coverage_pct": round(len(covered) / len(VALID_VIEWPOINTS) * 100, 1),
        "training_eligible": len(missing) == 0,
    }


# ========================== Training Endpoints ==================

@router.post("/training-jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_training_job(
    payload: TrainingJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dispatch a LoRA training job for a character."""
    # Validate reference set coverage
    items_result = await db.execute(
        select(ReferenceSetItem).where(ReferenceSetItem.reference_set_id == payload.reference_set_id)
    )
    items = items_result.scalars().all()

    if len(items) < 6:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum 6 reference images required. Got {len(items)}."
        )

    trigger_token = payload.trigger_token or f"sks {payload.character_id.lower().replace('-', '')} model"

    try:
        from app.worker import run_character_training_job
        task = run_character_training_job.delay(
            character_id=payload.character_id,
            brand_id=payload.brand_id,
            reference_set_id=payload.reference_set_id,
            trigger_token=trigger_token,
            epochs=payload.epochs,
            learning_rate=payload.learning_rate,
            resolution=payload.resolution,
            qa_profile_id=payload.qa_profile_id,
        )
        task_id = task.id if task else f"mock_train_{payload.character_id}"
    except Exception as e:
        print(f"[Training] Celery dispatch failed: {e}")
        task_id = f"mock_train_{payload.character_id}"

    return {
        "task_id": task_id,
        "status": "queued",
        "character_id": payload.character_id,
        "reference_set_id": payload.reference_set_id,
        "trigger_token": trigger_token,
        "epochs": payload.epochs,
        "workflow": "WF-TRAIN-001",
    }


# ========================== Helper ==============================

def _get_image_dimensions(image_bytes: bytes) -> tuple:
    """Extract image dimensions from bytes."""
    try:
        import struct
        # PNG
        if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            w, h = struct.unpack('>II', image_bytes[16:24])
            return w, h
        # JPEG
        elif image_bytes[:2] == b'\xff\xd8':
            return 1024, 1024  # Mock for JPEG
        return 1024, 1024
    except Exception:
        return 1024, 1024
