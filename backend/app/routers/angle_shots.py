from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from datetime import datetime
import json
import os
from jsonschema import validate, ValidationError

from app.models.db import get_db, User, AngleShot, AngleShotCompatibility, AngleShotVersion
from app.middleware.auth import get_current_user
from app.services.compatibility import validate_compatibility

router = APIRouter(prefix="/api/v1/angle-shots", tags=["Angle Shots"])

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas", "pose_preset.json")
try:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        POSE_PRESET_SCHEMA = json.load(f)
except Exception as e:
    POSE_PRESET_SCHEMA = None
    print(f"Error loading Pose Preset Schema: {e}")


def validate_pose_preset_schema(payload_dict: dict):
    if not POSE_PRESET_SCHEMA:
        return
    try:
        validate(instance=payload_dict, schema=POSE_PRESET_SCHEMA)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"JSON schema validation failed: {e.message}"
        )



# ========================== Schemas ==============================

class AngleShotCreate(BaseModel):
    name: str = Field(..., max_length=255)
    code: Optional[str] = None
    category: Optional[str] = None
    framing: Optional[str] = None
    pose: Optional[str] = None
    view_direction: Optional[str] = None
    description: Optional[str] = None
    camera_yaw: Optional[float] = None
    camera_pitch: Optional[float] = None
    focal_length_mm: Optional[float] = None
    is_premium: bool = False
    prompt_template: Optional[str] = None
    quality_rules: Optional[dict] = None
    compatible_products: Optional[List[str]] = []


class AngleShotUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    framing: Optional[str] = None
    pose: Optional[str] = None
    view_direction: Optional[str] = None
    description: Optional[str] = None
    is_visible: Optional[bool] = None
    is_premium: Optional[bool] = None
    prompt_template: Optional[str] = None
    quality_rules: Optional[dict] = None
    change_note: Optional[str] = None


class CompatibilityCheckRequest(BaseModel):
    product_type: str
    fabric_type: Optional[str] = None
    model_age_group: Optional[str] = None
    has_back_reference: bool = True


# ========================== Endpoints ============================

@router.get("")
async def list_angle_shots(
    category: Optional[str] = Query(None),
    framing: Optional[str] = Query(None),
    pose: Optional[str] = Query(None),
    garment_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    is_custom: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(40, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all angle shot presets with filters."""
    query = select(AngleShot).where(AngleShot.is_visible == True)

    if category:
        query = query.where(AngleShot.category == category)
    if framing:
        query = query.where(AngleShot.framing == framing)
    if pose:
        query = query.where(AngleShot.pose == pose)
    if is_custom is not None:
        query = query.where(AngleShot.is_custom == is_custom)
    if search:
        query = query.where(
            or_(
                AngleShot.name.ilike(f"%{search}%"),
                AngleShot.description.ilike(f"%{search}%"),
                AngleShot.pose.ilike(f"%{search}%"),
            )
        )

    query = query.order_by(AngleShot.sort_order, AngleShot.id)

    result = await db.execute(query)
    all_shots = result.scalars().all()

    # Filter by garment type compatibility
    if garment_type:
        filtered = []
        for shot in all_shots:
            compat_result = await db.execute(
                select(AngleShotCompatibility).where(
                    AngleShotCompatibility.angle_shot_id == shot.id,
                    AngleShotCompatibility.product_type == garment_type.upper(),
                    AngleShotCompatibility.compatible == True,
                )
            )
            if compat_result.scalars().first():
                filtered.append(shot)
        all_shots = filtered

    total = len(all_shots)
    offset = (page - 1) * limit
    shots = all_shots[offset:offset + limit]

    return {
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "category": s.category,
                "framing": s.framing,
                "pose": s.pose,
                "view_direction": s.view_direction,
                "description": s.description,
                "thumbnail_url": s.thumbnail_url,
                "is_custom": s.is_custom,
                "is_premium": s.is_premium,
                "status": s.status,
                "version": s.version,
            }
            for s in shots
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
        }
    }


@router.get("/{shot_id}")
async def get_angle_shot(
    shot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single angle shot preset."""
    result = await db.execute(select(AngleShot).where(AngleShot.id == shot_id))
    shot = result.scalars().first()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Angle shot not found.")

    compat_result = await db.execute(
        select(AngleShotCompatibility).where(AngleShotCompatibility.angle_shot_id == shot_id)
    )
    compatibilities = compat_result.scalars().all()

    return {
        "id": shot.id,
        "name": shot.name,
        "code": shot.code,
        "category": shot.category,
        "framing": shot.framing,
        "pose": shot.pose,
        "view_direction": shot.view_direction,
        "description": shot.description,
        "thumbnail_url": shot.thumbnail_url,
        "reference_image_url": shot.reference_image_url,
        "pose_map_url": shot.pose_map_url,
        "camera_yaw": shot.camera_yaw,
        "camera_pitch": shot.camera_pitch,
        "focal_length_mm": shot.focal_length_mm,
        "is_custom": shot.is_custom,
        "is_premium": shot.is_premium,
        "status": shot.status,
        "version": shot.version,
        "prompt_template": shot.prompt_template,
        "quality_rules": shot.quality_rules,
        "compatibilities": [
            {"product_type": c.product_type, "compatible": c.compatible, "warning": c.warning_message}
            for c in compatibilities
        ],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_angle_shot(
    payload: AngleShotCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new angle shot preset."""
    if payload.code and payload.code.startswith("ML-POSE-"):
        # Map fields to match JSON schema format for validation
        body_yaw = 0
        qa_rule_codes = []
        tier = "CORE"
        risk_level = "LOW"
        version_str = "1.0.0"
        
        if payload.quality_rules:
            body_yaw = int(payload.quality_rules.get("body_yaw_deg", 0))
            raw_qa = payload.quality_rules.get("qa_rule_codes", "")
            if isinstance(raw_qa, list):
                qa_rule_codes = raw_qa
            elif isinstance(raw_qa, str) and raw_qa:
                qa_rule_codes = [x.strip() for x in raw_qa.split(";") if x.strip()]
            tier = payload.quality_rules.get("tier", "CORE")
            risk_level = payload.quality_rules.get("risk_level", "LOW")
            version_str = payload.quality_rules.get("version", "1.0.0")

        validation_dict = {
            "preset_id": payload.code,
            "version": version_str,
            "family": payload.category,
            "display_name": payload.name,
            "body_yaw_deg": body_yaw,
            "framing": payload.framing,
            "qa_rule_codes": qa_rule_codes,
            "status": "ACTIVE",
            "tier": tier,
            "risk_level": risk_level
        }
        
        # Remove None values so required check works
        validation_dict = {k: v for k, v in validation_dict.items() if v is not None}
        validate_pose_preset_schema(validation_dict)

    shot = AngleShot(
        name=payload.name,
        code=payload.code,
        category=payload.category,
        framing=payload.framing,
        pose=payload.pose,
        view_direction=payload.view_direction,
        description=payload.description,
        camera_yaw=payload.camera_yaw,
        camera_pitch=payload.camera_pitch,
        focal_length_mm=payload.focal_length_mm,
        is_custom=True,
        is_premium=payload.is_premium,
        status="active",
        version=1,
        prompt_template=payload.prompt_template,
        quality_rules=payload.quality_rules,
    )
    db.add(shot)
    await db.flush()

    # Add compatibility rules
    for product_type in (payload.compatible_products or []):
        compat = AngleShotCompatibility(
            angle_shot_id=shot.id,
            product_type=product_type.upper(),
            compatible=True,
        )
        db.add(compat)

    # Save initial version
    version = AngleShotVersion(
        angle_shot_id=shot.id,
        version=1,
        configuration={
            "framing": payload.framing,
            "pose": payload.pose,
            "view_direction": payload.view_direction,
            "camera_yaw": payload.camera_yaw,
            "camera_pitch": payload.camera_pitch,
        },
        change_note="Initial version",
    )
    db.add(version)
    await db.commit()
    await db.refresh(shot)

    return {"id": shot.id, "name": shot.name, "status": shot.status, "version": shot.version}


@router.patch("/{shot_id}")
async def update_angle_shot(
    shot_id: int,
    payload: AngleShotUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an angle shot preset."""
    result = await db.execute(select(AngleShot).where(AngleShot.id == shot_id))
    shot = result.scalars().first()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Angle shot not found.")

    if payload.name is not None:
        shot.name = payload.name
    if payload.category is not None:
        shot.category = payload.category
    if payload.framing is not None:
        shot.framing = payload.framing
    if payload.pose is not None:
        shot.pose = payload.pose
    if payload.view_direction is not None:
        shot.view_direction = payload.view_direction
    if payload.description is not None:
        shot.description = payload.description
    if payload.is_visible is not None:
        shot.is_visible = payload.is_visible
    if payload.is_premium is not None:
        shot.is_premium = payload.is_premium
    if payload.prompt_template is not None:
        shot.prompt_template = payload.prompt_template
    if payload.quality_rules is not None:
        shot.quality_rules = payload.quality_rules

    shot.version += 1

    # Save version snapshot
    version = AngleShotVersion(
        angle_shot_id=shot.id,
        version=shot.version,
        configuration={
            "framing": shot.framing,
            "pose": shot.pose,
            "view_direction": shot.view_direction,
            "camera_yaw": shot.camera_yaw,
            "camera_pitch": shot.camera_pitch,
        },
        change_note=payload.change_note or "Updated",
    )
    db.add(version)
    await db.commit()
    await db.refresh(shot)

    return {"id": shot.id, "name": shot.name, "version": shot.version}


@router.delete("/{shot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_angle_shot(
    shot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete an angle shot preset."""
    result = await db.execute(select(AngleShot).where(AngleShot.id == shot_id))
    shot = result.scalars().first()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Angle shot not found.")

    shot.status = "archived"
    shot.is_visible = False
    await db.commit()


@router.get("/{shot_id}/history")
async def get_angle_shot_history(
    shot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get version history of an angle shot."""
    result = await db.execute(
        select(AngleShotVersion).where(AngleShotVersion.angle_shot_id == shot_id).order_by(AngleShotVersion.version.desc())
    )
    versions = result.scalars().all()
    return {
        "angle_shot_id": shot_id,
        "versions": [
            {"id": v.id, "version": v.version, "configuration": v.configuration, "change_note": v.change_note, "created_at": v.created_at.isoformat()}
            for v in versions
        ]
    }


@router.post("/{shot_id}/restore")
async def restore_angle_shot_version(
    shot_id: int,
    version_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore a previous version of an angle shot."""
    shot_result = await db.execute(select(AngleShot).where(AngleShot.id == shot_id))
    shot = shot_result.scalars().first()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Angle shot not found.")

    version_result = await db.execute(
        select(AngleShotVersion).where(
            AngleShotVersion.angle_shot_id == shot_id,
            AngleShotVersion.version == version_number
        )
    )
    version = version_result.scalars().first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    config = version.configuration
    if config.get("framing"):
        shot.framing = config["framing"]
    if config.get("pose"):
        shot.pose = config["pose"]
    if config.get("view_direction"):
        shot.view_direction = config["view_direction"]
    if config.get("camera_yaw") is not None:
        shot.camera_yaw = config["camera_yaw"]
    if config.get("camera_pitch") is not None:
        shot.camera_pitch = config["camera_pitch"]

    shot.version += 1
    new_version = AngleShotVersion(
        angle_shot_id=shot.id,
        version=shot.version,
        configuration=config,
        change_note=f"Restored from version {version_number}",
    )
    db.add(new_version)
    await db.commit()

    return {"id": shot.id, "restored_from_version": version_number, "current_version": shot.version}


@router.post("/{shot_id}/compatibility-check")
async def check_compatibility(
    shot_id: int,
    payload: CompatibilityCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check compatibility of an angle shot with a product."""
    result = await db.execute(select(AngleShot).where(AngleShot.id == shot_id))
    shot = result.scalars().first()
    if not shot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Angle shot not found.")

    compat = validate_compatibility(
        angle_shot_framing=shot.framing or "",
        angle_shot_pose=shot.pose or "",
        angle_shot_category=shot.category or "",
        product_type=payload.product_type,
        fabric_type=payload.fabric_type,
        model_age_group=payload.model_age_group,
        has_back_reference=payload.has_back_reference,
    )

    return {
        "angle_shot_id": shot_id,
        "product_type": payload.product_type,
        "compatible": compat.compatible,
        "score": compat.score,
        "warnings": compat.warnings,
        "blocking_reasons": compat.blocking_reasons,
    }


@router.post("/validate", status_code=status.HTTP_200_OK)
async def validate_preset_payload(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    """Validate a raw pose preset payload against the JSON Schema."""
    validate_pose_preset_schema(payload)
    return {"valid": True, "message": "Preset configuration conforms to the JSON Schema."}

