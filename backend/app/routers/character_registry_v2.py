from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from datetime import datetime

from app.models.db import (
    get_db, User,
    CharacterV2, CharacterVersion,
    CharacterIdentityDNA, CharacterBodyDNA,
    CharacterAppearanceProfile, CanonicalAsset,
    CharacterVersionQA, CharacterRuntimeV2,
)
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/characters-v2", tags=["Character Registry V2"])


# ========================== Schemas ==============================

class CharacterCreate(BaseModel):
    character_id: str = Field(..., description="e.g. EE-F-002")
    display_name: str
    internal_name: Optional[str] = None
    workspace_id: Optional[str] = None
    gender_presentation: Optional[str] = None


class CharacterVersionCreate(BaseModel):
    version: str = Field(..., description="e.g. 0.9, 1.0")
    release_notes: Optional[str] = None
    taxonomy_version: Optional[str] = "TAXREG-V1.0"


class IdentityDNACreate(BaseModel):
    version: str
    face_shape: Optional[str] = None
    eye_shape: Optional[str] = None
    eye_spacing: Optional[str] = None
    eye_color: Optional[str] = None
    brow_shape: Optional[str] = None
    nose_bridge: Optional[str] = None
    nose_width: Optional[str] = None
    lip_shape: Optional[str] = None
    lip_fullness: Optional[str] = None
    cheekbone_height: Optional[str] = None
    cheekbone_prominence: Optional[str] = None
    jaw_width: Optional[str] = None
    chin_shape: Optional[str] = None
    hairline_shape: Optional[str] = None
    age_anchor: Optional[int] = None
    identity_markers: Optional[List[Dict]] = []
    landmark_profile: Optional[Dict] = None


class BodyDNACreate(BaseModel):
    version: str
    canonical_height_cm: Optional[float] = None
    height_status: str = "ESTIMATED"
    stature_class: Optional[str] = None
    body_archetype: Optional[str] = None
    body_scale_class: Optional[str] = None
    visual_stature_target: Optional[str] = None
    head_to_body_ratio: Optional[str] = None
    shoulder_width_class: Optional[str] = None
    waist_profile: Optional[str] = None
    hip_profile: Optional[str] = None
    torso_length: Optional[str] = None
    femur_ratio: Optional[str] = None
    hand_scale: Optional[str] = None


class AppearanceCreate(BaseModel):
    version: str
    skin_depth_code: Optional[str] = None
    skin_undertone: Optional[str] = None
    skin_texture: Optional[str] = None
    hair_color: Optional[str] = None
    hair_texture: Optional[str] = None
    hair_canonical_length: Optional[str] = None
    hair_canonical_style: Optional[str] = None
    makeup_base: str = "MINIMAL"


class CanonicalAssetCreate(BaseModel):
    asset_id: str
    version: str
    asset_role: str
    framing: Optional[str] = None
    angle_code: Optional[str] = None
    camera_yaw_deg: float = 0.0
    camera_pitch_deg: float = 0.0
    body_yaw_deg: float = 0.0
    head_relative_to_body_deg: float = 0.0
    head_pitch_deg: float = 0.0
    gaze: str = "FOLLOW_HEAD"
    expression: str = "NEUTRAL"
    filename: Optional[str] = None
    original_filename: Optional[str] = None
    storage_path: Optional[str] = None
    content_hash_sha256: Optional[str] = None
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    workflow_id: Optional[str] = None
    workflow_version: Optional[str] = None
    seed: Optional[int] = None
    quality_mode: Optional[str] = None
    reference_authority_role: Optional[str] = None


class QAUpdateRequest(BaseModel):
    identity_qa: Optional[str] = None
    body_qa: Optional[str] = None
    hands_qa: Optional[str] = None
    feet_qa: Optional[str] = None
    angle_qa: Optional[str] = None
    artifact_qa: Optional[str] = None
    overall_qa_status: Optional[str] = None
    training_eligible: Optional[bool] = None
    production_reference_eligible: Optional[bool] = None


class VersionQAUpdate(BaseModel):
    identity_gate: Optional[str] = None
    body_profile_gate: Optional[str] = None
    half_body_angle_gate: Optional[str] = None
    full_body_angle_gate: Optional[str] = None
    hands_gate: Optional[str] = None
    feet_gate: Optional[str] = None
    training_gate: Optional[str] = None
    production_gate: Optional[str] = None
    notes: Optional[str] = None


# ========================== Endpoints ============================

@router.get("")
async def list_characters(
    workspace_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all characters — Character Library API."""
    query = select(CharacterV2).order_by(desc(CharacterV2.id))
    if workspace_id:
        query = query.where(CharacterV2.workspace_id == workspace_id)
    if status_filter:
        query = query.where(CharacterV2.status == status_filter)

    result = await db.execute(query)
    characters = result.scalars().all()

    char_list = []
    for c in characters:
        body = await db.execute(
            select(CharacterBodyDNA).where(
                and_(CharacterBodyDNA.character_id == c.character_id,
                     CharacterBodyDNA.version == c.current_version)
            )
        )
        body = body.scalars().first()

        golden = await db.execute(
            select(CanonicalAsset).where(
                and_(CanonicalAsset.character_id == c.character_id,
                     CanonicalAsset.asset_role == "GOLDEN_IDENTITY",
                     CanonicalAsset.active_canonical == True)
            )
        )
        golden = golden.scalars().first()

        char_list.append({
            "character_id": c.character_id,
            "display_name": c.display_name,
            "status": c.status,
            "current_version": c.current_version,
            "customer_visible": c.customer_visible,
            "production_enabled": c.production_enabled,
            "canonical_height_cm": body.canonical_height_cm if body else None,
            "stature_class": body.stature_class if body else None,
            "body_archetype": body.body_archetype if body else None,
            "golden_asset_path": golden.storage_path if golden else None,
        })

    return {"characters": char_list, "total": len(char_list)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_character(
    payload: CharacterCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new character."""
    existing = await db.execute(
        select(CharacterV2).where(CharacterV2.character_id == payload.character_id)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail=f"Character {payload.character_id} already exists.")

    character = CharacterV2(**payload.dict())
    db.add(character)
    await db.commit()
    return {"character_id": character.character_id, "status": "DEVELOPMENT"}


@router.get("/{character_id}")
async def get_character(
    character_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full character profile."""
    char = await db.execute(
        select(CharacterV2).where(CharacterV2.character_id == character_id)
    )
    char = char.scalars().first()
    if not char:
        raise HTTPException(status_code=404, detail=f"Character {character_id} not found.")

    version = char.current_version

    identity = await db.execute(
        select(CharacterIdentityDNA).where(
            and_(CharacterIdentityDNA.character_id == character_id,
                 CharacterIdentityDNA.version == version)
        )
    )
    body = await db.execute(
        select(CharacterBodyDNA).where(
            and_(CharacterBodyDNA.character_id == character_id,
                 CharacterBodyDNA.version == version)
        )
    )
    appearance = await db.execute(
        select(CharacterAppearanceProfile).where(
            and_(CharacterAppearanceProfile.character_id == character_id,
                 CharacterAppearanceProfile.version == version)
        )
    )
    qa = await db.execute(
        select(CharacterVersionQA).where(
            and_(CharacterVersionQA.character_id == character_id,
                 CharacterVersionQA.version == version)
        )
    )
    runtime = await db.execute(
        select(CharacterRuntimeV2).where(
            and_(CharacterRuntimeV2.character_id == character_id,
                 CharacterRuntimeV2.version == version)
        )
    )
    assets = await db.execute(
        select(CanonicalAsset).where(
            CanonicalAsset.character_id == character_id
        ).order_by(CanonicalAsset.asset_role)
    )

    identity = identity.scalars().first()
    body = body.scalars().first()
    appearance = appearance.scalars().first()
    qa = qa.scalars().first()
    runtime = runtime.scalars().first()
    assets = assets.scalars().all()

    return {
        "character_id": character_id,
        "display_name": char.display_name,
        "status": char.status,
        "current_version": char.current_version,
        "customer_visible": char.customer_visible,
        "production_enabled": char.production_enabled,
        "identity_dna": identity.__dict__ if identity else None,
        "body_dna": body.__dict__ if body else None,
        "appearance_profile": appearance.__dict__ if appearance else None,
        "qa_gates": qa.__dict__ if qa else None,
        "runtime_profile": runtime.__dict__ if runtime else None,
        "canonical_assets": [
            {
                "asset_id": a.asset_id,
                "asset_role": a.asset_role,
                "framing": a.framing,
                "angle_code": a.angle_code,
                "body_yaw_deg": a.body_yaw_deg,
                "head_pitch_deg": a.head_pitch_deg,
                "expression": a.expression,
                "overall_qa_status": a.overall_qa_status,
                "training_eligible": a.training_eligible,
                "production_reference_eligible": a.production_reference_eligible,
                "storage_path": a.storage_path,
                "active_canonical": a.active_canonical,
            }
            for a in assets
        ],
    }


@router.get("/{character_id}/versions")
async def get_character_versions(
    character_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all versions of a character."""
    result = await db.execute(
        select(CharacterVersion).where(
            CharacterVersion.character_id == character_id
        ).order_by(desc(CharacterVersion.id))
    )
    versions = result.scalars().all()
    return {"character_id": character_id, "versions": [
        {
            "version": v.version,
            "status": v.status,
            "locked": v.locked,
            "locked_at": str(v.locked_at) if v.locked_at else None,
            "promoted_to_production": v.promoted_to_production,
        }
        for v in versions
    ]}


@router.post("/{character_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_character_version(
    character_id: str,
    payload: CharacterVersionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new character version."""
    version = CharacterVersion(character_id=character_id, **payload.dict())
    db.add(version)
    await db.commit()
    return {"character_id": character_id, "version": payload.version, "status": "DEVELOPMENT"}


@router.post("/{character_id}/identity-dna", status_code=status.HTTP_201_CREATED)
async def create_identity_dna(
    character_id: str,
    payload: IdentityDNACreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create Identity DNA."""
    dna = CharacterIdentityDNA(character_id=character_id, **payload.dict())
    db.add(dna)
    await db.commit()
    return {"character_id": character_id, "version": payload.version, "status": "created"}


@router.post("/{character_id}/body-dna", status_code=status.HTTP_201_CREATED)
async def create_body_dna(
    character_id: str,
    payload: BodyDNACreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create Body DNA."""
    dna = CharacterBodyDNA(character_id=character_id, **payload.dict())
    db.add(dna)
    await db.commit()
    return {"character_id": character_id, "version": payload.version, "status": "created"}


@router.post("/{character_id}/appearance", status_code=status.HTTP_201_CREATED)
async def create_appearance(
    character_id: str,
    payload: AppearanceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create Appearance Profile."""
    appearance = CharacterAppearanceProfile(character_id=character_id, **payload.dict())
    db.add(appearance)
    await db.commit()
    return {"character_id": character_id, "version": payload.version, "status": "created"}


@router.post("/{character_id}/canonical-assets", status_code=status.HTTP_201_CREATED)
async def add_canonical_asset(
    character_id: str,
    payload: CanonicalAssetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a canonical asset."""
    asset = CanonicalAsset(character_id=character_id, **payload.dict())
    db.add(asset)
    await db.commit()
    return {"asset_id": asset.asset_id, "asset_role": asset.asset_role, "status": "CANDIDATE"}


@router.get("/{character_id}/canonical-assets")
async def get_canonical_assets(
    character_id: str,
    version: Optional[str] = None,
    framing: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get canonical assets."""
    query = select(CanonicalAsset).where(CanonicalAsset.character_id == character_id)
    if version:
        query = query.where(CanonicalAsset.version == version)
    if framing:
        query = query.where(CanonicalAsset.framing == framing)

    result = await db.execute(query.order_by(CanonicalAsset.asset_role))
    assets = result.scalars().all()

    return {"character_id": character_id, "assets": [
        {
            "asset_id": a.asset_id,
            "asset_role": a.asset_role,
            "framing": a.framing,
            "angle_code": a.angle_code,
            "body_yaw_deg": a.body_yaw_deg,
            "overall_qa_status": a.overall_qa_status,
            "training_eligible": a.training_eligible,
            "storage_path": a.storage_path,
            "active_canonical": a.active_canonical,
        }
        for a in assets
    ]}


@router.patch("/{character_id}/canonical-assets/{asset_id}/qa")
async def update_asset_qa(
    character_id: str,
    asset_id: str,
    payload: QAUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update QA status for a canonical asset."""
    result = await db.execute(
        select(CanonicalAsset).where(
            and_(CanonicalAsset.character_id == character_id,
                 CanonicalAsset.asset_id == asset_id)
        )
    )
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")

    for field, value in payload.dict(exclude_none=True).items():
        setattr(asset, field, value)

    await db.commit()
    return {"asset_id": asset_id, "status": "updated"}


@router.get("/{character_id}/qa")
async def get_character_qa(
    character_id: str,
    version: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get QA gates for a character version."""
    char = await db.execute(
        select(CharacterV2).where(CharacterV2.character_id == character_id)
    )
    char = char.scalars().first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found.")

    v = version or char.current_version
    result = await db.execute(
        select(CharacterVersionQA).where(
            and_(CharacterVersionQA.character_id == character_id,
                 CharacterVersionQA.version == v)
        )
    )
    qa = result.scalars().first()
    return {"character_id": character_id, "version": v, "qa": qa.__dict__ if qa else None}


@router.patch("/{character_id}/qa")
async def update_version_qa(
    character_id: str,
    version: str,
    payload: VersionQAUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update QA gates for a character version."""
    result = await db.execute(
        select(CharacterVersionQA).where(
            and_(CharacterVersionQA.character_id == character_id,
                 CharacterVersionQA.version == version)
        )
    )
    qa = result.scalars().first()

    if not qa:
        qa = CharacterVersionQA(character_id=character_id, version=version)
        db.add(qa)

    for field, value in payload.dict(exclude_none=True).items():
        setattr(qa, field, value)

    qa.reviewed_at = datetime.utcnow()
    await db.commit()
    return {"character_id": character_id, "version": version, "status": "updated"}


@router.get("/{character_id}/runtime-profile")
async def get_runtime_profile(
    character_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get Character Runtime Profile for Studios."""
    char = await db.execute(
        select(CharacterV2).where(CharacterV2.character_id == character_id)
    )
    char = char.scalars().first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found.")

    runtime = await db.execute(
        select(CharacterRuntimeV2).where(
            and_(CharacterRuntimeV2.character_id == character_id,
                 CharacterRuntimeV2.version == char.current_version)
        )
    )
    runtime = runtime.scalars().first()

    return {
        "character_id": character_id,
        "version": char.current_version,
        "status": char.status,
        "production_enabled": char.production_enabled,
        "runtime": runtime.__dict__ if runtime else None,
    }


@router.post("/{character_id}/lock")
async def lock_character_version(
    character_id: str,
    version: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lock a character version."""
    result = await db.execute(
        select(CharacterVersion).where(
            and_(CharacterVersion.character_id == character_id,
                 CharacterVersion.version == version)
        )
    )
    char_version = result.scalars().first()
    if not char_version:
        raise HTTPException(status_code=404, detail="Character version not found.")

    if char_version.locked:
        raise HTTPException(status_code=409, detail=f"Version {version} is already locked.")

    char_version.locked = True
    char_version.locked_at = datetime.utcnow()
    char_version.locked_by = str(current_user.id)
    char_version.status = "LOCKED"

    char = await db.execute(
        select(CharacterV2).where(CharacterV2.character_id == character_id)
    )
    char = char.scalars().first()
    if char:
        char.status = "LOCKED"

    await db.commit()
    return {"character_id": character_id, "version": version, "status": "LOCKED"}


@router.post("/{character_id}/promote")
async def promote_to_production(
    character_id: str,
    version: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Promote locked character to PRODUCTION."""
    result = await db.execute(
        select(CharacterVersion).where(
            and_(CharacterVersion.character_id == character_id,
                 CharacterVersion.version == version)
        )
    )
    char_version = result.scalars().first()
    if not char_version:
        raise HTTPException(status_code=404, detail="Character version not found.")

    if not char_version.locked:
        raise HTTPException(status_code=400, detail="Must be LOCKED before PRODUCTION.")

    char_version.promoted_to_production = True
    char_version.promoted_at = datetime.utcnow()
    char_version.status = "PRODUCTION"

    char = await db.execute(
        select(CharacterV2).where(CharacterV2.character_id == character_id)
    )
    char = char.scalars().first()
    if char:
        char.status = "PRODUCTION"
        char.production_enabled = True
        char.customer_visible = True

    await db.commit()
    return {"character_id": character_id, "version": version, "status": "PRODUCTION"}


@router.patch("/{character_id}/status")
async def update_character_status(
    character_id: str,
    new_status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update character lifecycle status."""
    valid_statuses = ["DEVELOPMENT", "VALIDATION", "LOCKED", "PRODUCTION", "DEPRECATED", "ARCHIVED"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Options: {valid_statuses}")

    result = await db.execute(
        select(CharacterV2).where(CharacterV2.character_id == character_id)
    )
    char = result.scalars().first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found.")

    char.status = new_status
    await db.commit()
    return {"character_id": character_id, "status": new_status}
