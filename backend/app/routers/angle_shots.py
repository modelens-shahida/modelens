from fastapi import APIRouter, HTTPException, Depends, Query, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
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


class ReorderItem(BaseModel):
    id: int
    sort_order: Optional[int] = None
    sortOrder: Optional[int] = None


class ReorderRequest(BaseModel):
    orders: List[ReorderItem]


class BulkUpdateRequest(BaseModel):
    ids: List[int]
    status: Optional[str] = None
    is_visible: Optional[bool] = None
    isVisible: Optional[bool] = None
    is_premium: Optional[bool] = None
    isPremium: Optional[bool] = None


class CustomUploadUrlRequest(BaseModel):
    fileName: str
    mimeType: str
    fileSize: int


class CustomAngleShotCreate(BaseModel):
    name: str
    referenceImageKey: str
    productTypes: List[str]
    ageGroups: List[str]
    requestedFraming: str
    visibility: Optional[str] = "ORGANIZATION"


# ========================== Endpoints ============================

@router.get("")
async def list_angle_shots(
    category: Optional[str] = Query(None),
    ageGroup: Optional[str] = Query(None),
    framing: Optional[str] = Query(None),
    pose: Optional[str] = Query(None),
    poseType: Optional[str] = Query(None),
    view_direction: Optional[str] = Query(None),
    viewDirection: Optional[str] = Query(None),
    garment_type: Optional[str] = Query(None),
    productType: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    is_custom: Optional[bool] = Query(None),
    source: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(40, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all angle shot presets with filters, computed facets, and pagination."""
    query = select(AngleShot).where(AngleShot.is_visible == True).options(selectinload(AngleShot.compatibilities))

    # Resolve viewDirection / view_direction
    resolved_view_dir = viewDirection or view_direction
    if resolved_view_dir:
        query = query.where(AngleShot.view_direction == resolved_view_dir)

    # Resolve framing
    if framing:
        query = query.where(AngleShot.framing == framing)

    # Resolve pose / poseType
    resolved_pose = poseType or pose
    if resolved_pose:
        query = query.where(AngleShot.pose.ilike(f"%{resolved_pose}%"))

    # Resolve source / is_custom
    if source:
        if source.upper() == "SYSTEM":
            query = query.where(AngleShot.is_custom == False)
        else:
            query = query.where(AngleShot.is_custom == True)
    elif is_custom is not None:
        query = query.where(AngleShot.is_custom == is_custom)

    # Resolve search
    if search:
        query = query.where(
            or_(
                AngleShot.name.ilike(f"%{search}%"),
                AngleShot.description.ilike(f"%{search}%"),
                AngleShot.pose.ilike(f"%{search}%"),
                AngleShot.code.ilike(f"%{search}%"),
            )
        )

    query = query.order_by(AngleShot.sort_order, AngleShot.id)

    result = await db.execute(query)
    all_shots = result.scalars().all()

    # Apply ageGroup / category filters in Python for SQLite JSON compatibility
    resolved_age_group = ageGroup or category
    if resolved_age_group:
        filtered = []
        for s in all_shots:
            match_category = s.category and resolved_age_group.lower() in s.category.lower()
            match_age_group = False
            if s.age_groups:
                match_age_group = any(resolved_age_group.upper() == str(ag).upper() for ag in s.age_groups)
            if match_category or match_age_group:
                filtered.append(s)
        all_shots = filtered

    # Filter by garment type / productType compatibility
    resolved_prod_type = productType or garment_type
    if resolved_prod_type:
        filtered = []
        for shot in all_shots:
            compat_result = await db.execute(
                select(AngleShotCompatibility).where(
                    AngleShotCompatibility.angle_shot_id == shot.id,
                    AngleShotCompatibility.product_type == resolved_prod_type.upper(),
                    AngleShotCompatibility.compatible == True,
                )
            )
            if compat_result.scalars().first():
                filtered.append(shot)
        all_shots = filtered

    # Compute facets counts over all matched shots (before pagination)
    from collections import Counter
    framing_counts = Counter()
    view_direction_counts = Counter()
    pose_counts = Counter()

    for s in all_shots:
        if s.framing:
            framing_counts[s.framing] += 1
        if s.view_direction:
            view_direction_counts[s.view_direction] += 1
        if s.pose:
            pose_counts[s.pose] += 1

    facets = {
        "framing": dict(framing_counts),
        "viewDirection": dict(view_direction_counts),
        "poseType": dict(pose_counts),
    }

    total = len(all_shots)
    offset = (page - 1) * limit
    shots = all_shots[offset:offset + limit]

    return {
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "slug": s.slug or s.name.lower().replace(" ", "-").replace("—", "-"),
                "category": s.category,
                "framing": s.framing,
                "pose": s.pose,
                "viewDirection": s.view_direction,
                "view_direction": s.view_direction,
                "poseType": s.pose,
                "description": s.description,
                "thumbnailUrl": s.thumbnail_url,
                "thumbnail_url": s.thumbnail_url,
                "is_custom": s.is_custom,
                "isPremium": s.is_premium,
                "is_premium": s.is_premium,
                "status": s.status,
                "version": s.version,
                "productTypes": [c.product_type for c in s.compatibilities if c.compatible],
                "ageGroups": s.age_groups or ([s.category.upper()] if s.category else []),
                "tags": s.tags or [],
            }
            for s in shots
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
        },
        "facets": facets,
    }
@router.get("/facets")
async def get_filter_facets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all available unique filter options for angle shots."""
    # Query distinct tags if any exist in the database
    result = await db.execute(select(AngleShot).where(AngleShot.is_visible == True))
    shots = result.scalars().all()
    
    unique_tags = set()
    for s in shots:
        if s.tags:
            for t in s.tags:
                unique_tags.add(t)

    return {
        "productTypes": [
            "APPAREL", "DRESS", "TOP", "BOTTOM", "OUTERWEAR", "SWIMWEAR", 
            "ACTIVEWEAR", "FOOTWEAR", "BAG", "EYEWEAR", "HEADWEAR", "JEWELRY", "ACCESSORY"
        ],
        "ageGroups": ["BABY", "KID", "TEEN", "ADULT", "SENIOR"],
        "framings": [
            "EXTREME_CLOSE_UP", "CLOSE_UP", "HEADSHOT", "BUST", "UPPER_BODY", 
            "THREE_QUARTER", "AMERICAN_SHOT", "FULL_BODY", "WIDE", "DETAIL"
        ],
        "viewDirections": [
            "FRONT", "FRONT_LEFT", "FRONT_RIGHT", "LEFT_PROFILE", "RIGHT_PROFILE", 
            "BACK", "BACK_LEFT", "BACK_RIGHT", "TOP_DOWN", "LOW_ANGLE"
        ],
        "poseTypes": [
            "NEUTRAL", "RELAXED", "ENGAGED", "HANDS_AT_SIDES", "HANDS_IN_POCKETS", 
            "ONE_HAND_IN_POCKET", "HAND_ON_HIP", "ARMS_CROSSED", "WALKING", "TURNING", 
            "SEATED", "LEANING", "CUSTOM"
        ],
        "tags": list(unique_tags)
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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new angle shot preset supporting both JSON and FormData."""
    import os
    import uuid
    from app.services.storage import storage_service
    from app.worker import process_custom_angle_shot

    content_type = request.headers.get("content-type", "")
    reference_image_url = None
    is_custom = False

    if "multipart/form-data" in content_type:
        form = await request.form()
        name = form.get("name")
        code = form.get("code")
        category = form.get("category")
        framing = form.get("framing")
        pose = form.get("pose")
        view_direction = form.get("view_direction")
        description = form.get("description")
        
        file = form.get("reference_image")
        if file:
            filename = file.filename or "file.png"
            file_ext = os.path.splitext(filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_bytes = await file.read()
            storage_service.save_file_bytes(unique_filename, file_bytes)
            reference_image_url = f"/uploads/{unique_filename}"
            is_custom = True
            
        camera_yaw = float(form.get("camera_yaw")) if form.get("camera_yaw") else None
        camera_pitch = float(form.get("camera_pitch")) if form.get("camera_pitch") else None
        focal_length_mm = float(form.get("focal_length_mm")) if form.get("focal_length_mm") else None
        is_premium = form.get("is_premium") == "true"
        prompt_template = form.get("prompt_template")
        
        quality_rules = None
        compatible_products = []
    else:
        json_data = await request.json()
        payload = AngleShotCreate(**json_data)
        name = payload.name
        code = payload.code
        category = payload.category
        framing = payload.framing
        pose = payload.pose
        view_direction = payload.view_direction
        description = payload.description
        camera_yaw = payload.camera_yaw
        camera_pitch = payload.camera_pitch
        focal_length_mm = payload.focal_length_mm
        is_premium = payload.is_premium
        prompt_template = payload.prompt_template
        quality_rules = payload.quality_rules
        compatible_products = payload.compatible_products or []
        is_custom = True

    if code and code.startswith("ML-POSE-"):
        # Map fields to match JSON schema format for validation
        body_yaw = 0
        qa_rule_codes = []
        tier = "CORE"
        risk_level = "LOW"
        version_str = "1.0.0"
        
        if quality_rules:
            body_yaw = int(quality_rules.get("body_yaw_deg", 0))
            raw_qa = quality_rules.get("qa_rule_codes", "")
            if isinstance(raw_qa, list):
                qa_rule_codes = raw_qa
            elif isinstance(raw_qa, str) and raw_qa:
                qa_rule_codes = [x.strip() for x in raw_qa.split(";") if x.strip()]
            tier = quality_rules.get("tier", "CORE")
            risk_level = quality_rules.get("risk_level", "LOW")
            version_str = quality_rules.get("version", "1.0.0")

        validation_dict = {
            "preset_id": code,
            "version": version_str,
            "family": category,
            "display_name": name,
            "body_yaw_deg": body_yaw,
            "framing": framing,
            "qa_rule_codes": qa_rule_codes,
            "status": "ACTIVE",
            "tier": tier,
            "risk_level": risk_level
        }
        
        validation_dict = {k: v for k, v in validation_dict.items() if v is not None}
        validate_pose_preset_schema(validation_dict)

    shot = AngleShot(
        name=name,
        code=code,
        category=category,
        framing=framing,
        pose=pose,
        view_direction=view_direction,
        description=description,
        camera_yaw=camera_yaw,
        camera_pitch=camera_pitch,
        focal_length_mm=focal_length_mm,
        is_custom=is_custom,
        is_premium=is_premium,
        status="processing" if is_custom and "multipart/form-data" in content_type else "active",
        version=1,
        prompt_template=prompt_template,
        quality_rules=quality_rules,
        reference_image_url=reference_image_url,
    )
    db.add(shot)
    await db.flush()

    # Add compatibility rules
    for product_type in compatible_products:
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
            "framing": framing,
            "pose": pose,
            "view_direction": view_direction,
            "camera_yaw": camera_yaw,
            "camera_pitch": camera_pitch,
        },
        change_note="Initial version",
    )
    db.add(version)
    await db.commit()
    await db.refresh(shot)

    # Trigger Pose extraction task if it's a custom upload
    if is_custom and "multipart/form-data" in content_type:
        try:
            process_custom_angle_shot.delay(shot.id)
        except Exception as celery_err:
            print(f"[AngleShot] Celery dispatch failed: {celery_err}")

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


@router.post("/admin/reorder")
@router.post("/reorder")
async def reorder_angle_shots(
    payload: ReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reorder multiple angle shot presets."""
    for item in payload.orders:
        sort_val = item.sort_order if item.sort_order is not None else item.sortOrder
        if sort_val is None:
            continue
        result = await db.execute(select(AngleShot).where(AngleShot.id == item.id))
        shot = result.scalars().first()
        if shot:
            shot.sort_order = sort_val
            
    await db.commit()
    return {"success": True, "message": "Presets reordered successfully."}


@router.post("/admin/bulk-update")
@router.post("/bulk-update")
async def bulk_update_angle_shots(
    payload: BulkUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk update multiple angle shot presets."""
    updated_count = 0
    for shot_id in payload.ids:
        result = await db.execute(select(AngleShot).where(AngleShot.id == shot_id))
        shot = result.scalars().first()
        if not shot:
            continue
            
        if payload.status is not None:
            shot.status = payload.status
            
        # is_visible
        vis_val = payload.is_visible if payload.is_visible is not None else payload.isVisible
        if vis_val is not None:
            shot.is_visible = vis_val
            
        # is_premium
        prem_val = payload.is_premium if payload.is_premium is not None else payload.isPremium
        if prem_val is not None:
            shot.is_premium = prem_val
            
        updated_count += 1
        
    await db.commit()
    return {"success": True, "updated_count": updated_count}


@router.post("/custom/upload-url")
async def request_custom_upload_url(
    payload: CustomUploadUrlRequest,
    current_user: User = Depends(get_current_user),
):
    """Request a mock or pre-signed upload URL for a custom reference image."""
    import uuid
    # Generate a unique key for the organization/user upload
    unique_id = uuid.uuid4()
    ext = os.path.splitext(payload.fileName)[1] or ".jpg"
    key = f"organizations/org_default/custom-poses/{unique_id}{ext}"
    
    return {
        "uploadUrl": f"http://localhost:8000/api/v1/assets/upload/mock?key={key}",
        "referenceImageKey": key
    }


@router.post("/custom")
async def create_custom_angle_shot_custom(
    payload: CustomAngleShotCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a custom preset from an uploaded reference image key."""
    # Create the AngleShot record matching the spec
    shot = AngleShot(
        name=payload.name,
        code=f"ML-POSE-CUST-{int(datetime.utcnow().timestamp())}",
        slug=payload.name.lower().replace(" ", "-").replace("—", "-"),
        framing=payload.requestedFraming,
        view_direction="FRONT",  # default
        pose="CUSTOM",
        reference_image_url=f"/uploads/{payload.referenceImageKey}",
        is_custom=True,
        status="processing",  # will be marked ACTIVE after worker processing
        version=1,
        age_groups=payload.ageGroups,
        tags=["custom"],
    )
    db.add(shot)
    await db.flush()

    # Add compatibility rules
    for product_type in payload.productTypes:
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
            "framing": payload.requestedFraming,
            "pose": "CUSTOM",
            "reference_image_url": shot.reference_image_url,
        },
        change_note="Created custom angle-shot from reference image.",
    )
    db.add(version)
    await db.commit()
    await db.refresh(shot)

    # Trigger async worker pose extraction if worker module is available
    from app.worker import process_custom_angle_shot
    try:
        process_custom_angle_shot.delay(shot.id)
    except Exception as e:
        print(f"[AngleShot] Celery dispatch failed: {e}")

    return {
        "id": shot.id,
        "name": shot.name,
        "status": shot.status,
        "version": shot.version
    }

