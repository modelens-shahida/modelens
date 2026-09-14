from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import (
    get_db, User,
    CharacterIdentityProfile,
    CharacterBodyProfile,
    CharacterSkinProfile,
    CharacterHairProfile,
    CharacterRuntimeProfile,
)
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/characters", tags=["Character Registry"])


# ========================== Schemas ==============================

class CharacterIdentityCreate(BaseModel):
    character_id: str = Field(..., description="e.g. EE-F-002")
    internal_name: Optional[str] = None
    display_name: Optional[str] = None
    workspace_id: Optional[str] = None
    age_anchor: Optional[int] = None
    face_shape: Optional[str] = None
    eye_shape: Optional[str] = None
    eye_spacing: Optional[str] = None
    nose_bridge: Optional[str] = None
    cheekbone_height: Optional[str] = None
    jaw_width: Optional[str] = None
    chin_shape: Optional[str] = None
    identity_markers: Optional[List[Dict]] = []
    meta: Optional[Dict[str, Any]] = None


class CharacterBodyCreate(BaseModel):
    body_profile_id: str
    character_id: str
    height_cm: Optional[float] = None
    height_band: Optional[str] = None
    build_code: Optional[str] = None
    frame_code: Optional[str] = None
    head_body_ratio: Optional[float] = None
    shoulders_width: Optional[str] = None
    torso_length: Optional[str] = None
    waist_position: Optional[str] = None
    hip_width: Optional[str] = None
    leg_proportion: Optional[str] = None
    arm_length: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class CharacterSkinCreate(BaseModel):
    skin_profile_id: str
    character_id: str
    depth_code: Optional[str] = None
    undertone_code: Optional[str] = None
    chroma_code: Optional[str] = None
    pore_density: Optional[str] = None
    microtexture: Optional[str] = None
    under_eye_texture: Optional[str] = None
    sebum_code: Optional[str] = None
    age_profile: Optional[str] = None
    permanent_markers: Optional[List[Dict]] = []
    meta: Optional[Dict[str, Any]] = None


class CharacterHairCreate(BaseModel):
    hair_dna_id: str
    character_id: str
    natural_color: Optional[str] = None
    undertone: Optional[str] = None
    hairline: Optional[str] = None
    density: Optional[str] = None
    strand_thickness: Optional[str] = None
    natural_texture: Optional[str] = None
    canonical_length: Optional[str] = None
    canonical_part: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class CharacterRuntimeCreate(BaseModel):
    runtime_profile_id: str
    character_id: str
    character_version: Optional[str] = "1.0"
    identity_profile_id: Optional[str] = None
    body_profile_id: Optional[str] = None
    skin_profile_id: Optional[str] = None
    hair_profile_id: Optional[str] = None
    production_model_alias: Optional[str] = None
    default_strength: Optional[float] = 0.78
    approved_workflows: Optional[List[str]] = []
    strength_overrides: Optional[Dict[str, float]] = {}


# ========================== Endpoints ============================

@router.get("")
async def list_characters(
    workspace_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all characters."""
    query = select(CharacterIdentityProfile)
    if workspace_id:
        query = query.where(CharacterIdentityProfile.workspace_id == workspace_id)
    result = await db.execute(query)
    characters = result.scalars().all()
    return {"characters": [
        {
            "character_id": c.character_id,
            "display_name": c.display_name,
            "internal_name": c.internal_name,
            "status": c.status,
            "customer_visible": c.customer_visible,
            "production_enabled": c.production_enabled,
            "golden_character_version": c.golden_character_version,
        }
        for c in characters
    ]}


@router.post("/identity", status_code=status.HTTP_201_CREATED)
async def create_character_identity(
    payload: CharacterIdentityCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a character identity profile."""
    existing = await db.execute(
        select(CharacterIdentityProfile).where(
            CharacterIdentityProfile.character_id == payload.character_id
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail=f"Character {payload.character_id} already exists.")

    profile = CharacterIdentityProfile(**payload.dict())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return {"character_id": profile.character_id, "status": profile.status}


@router.get("/{character_id}")
async def get_character(
    character_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full character profile."""
    identity = await db.execute(
        select(CharacterIdentityProfile).where(
            CharacterIdentityProfile.character_id == character_id
        )
    )
    identity = identity.scalars().first()
    if not identity:
        raise HTTPException(status_code=404, detail=f"Character {character_id} not found.")

    body = await db.execute(
        select(CharacterBodyProfile).where(CharacterBodyProfile.character_id == character_id)
    )
    skin = await db.execute(
        select(CharacterSkinProfile).where(CharacterSkinProfile.character_id == character_id)
    )
    hair = await db.execute(
        select(CharacterHairProfile).where(CharacterHairProfile.character_id == character_id)
    )
    runtime = await db.execute(
        select(CharacterRuntimeProfile).where(CharacterRuntimeProfile.character_id == character_id)
    )

    body = body.scalars().first()
    skin = skin.scalars().first()
    hair = hair.scalars().first()
    runtime = runtime.scalars().first()

    return {
        "character_id": character_id,
        "identity": identity.__dict__ if identity else None,
        "body_profile": body.__dict__ if body else None,
        "skin_profile": skin.__dict__ if skin else None,
        "hair_profile": hair.__dict__ if hair else None,
        "runtime_profile": runtime.__dict__ if runtime else None,
    }


@router.post("/{character_id}/body", status_code=status.HTTP_201_CREATED)
async def create_body_profile(
    character_id: str,
    payload: CharacterBodyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create character body profile."""
    profile = CharacterBodyProfile(**payload.dict())
    db.add(profile)
    await db.commit()
    return {"body_profile_id": profile.body_profile_id, "status": "created"}


@router.post("/{character_id}/skin", status_code=status.HTTP_201_CREATED)
async def create_skin_profile(
    character_id: str,
    payload: CharacterSkinCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create character skin profile."""
    profile = CharacterSkinProfile(**payload.dict())
    db.add(profile)
    await db.commit()
    return {"skin_profile_id": profile.skin_profile_id, "status": "created"}


@router.post("/{character_id}/hair", status_code=status.HTTP_201_CREATED)
async def create_hair_profile(
    character_id: str,
    payload: CharacterHairCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create character hair DNA profile."""
    profile = CharacterHairProfile(**payload.dict())
    db.add(profile)
    await db.commit()
    return {"hair_dna_id": profile.hair_dna_id, "status": "created"}


@router.post("/{character_id}/runtime", status_code=status.HTTP_201_CREATED)
async def create_runtime_profile(
    character_id: str,
    payload: CharacterRuntimeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create character runtime profile."""
    profile = CharacterRuntimeProfile(**payload.dict())
    db.add(profile)
    await db.commit()
    return {"runtime_profile_id": profile.runtime_profile_id, "status": "created"}


@router.patch("/{character_id}/status")
async def update_character_status(
    character_id: str,
    new_status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update character lifecycle status."""
    valid_statuses = [
        "CHAR_CONCEPT", "CHAR_DISCOVERY", "CHAR_MASTER_SELECTED",
        "CHAR_IDENTITY_VALIDATION", "CHAR_BODY_VALIDATION",
        "CHAR_PRODUCTION_VALIDATION", "CHAR_DATASET_APPROVED",
        "CHAR_MODEL_TRAINED", "CHAR_GOLDEN", "CHAR_ACTIVE", "CHAR_RETIRED"
    ]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Options: {valid_statuses}")

    result = await db.execute(
        select(CharacterIdentityProfile).where(
            CharacterIdentityProfile.character_id == character_id
        )
    )
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Character not found.")

    profile.status = new_status
    if new_status == "CHAR_GOLDEN":
        profile.production_enabled = True
        profile.customer_visible = True

    await db.commit()
    return {"character_id": character_id, "status": new_status}
