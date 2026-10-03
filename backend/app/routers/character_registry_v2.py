from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from datetime import datetime

from app.models.db import (
    get_db, User,
    CharacterV2, CharacterRegistryVersion,
    CharacterIdentityDNA, CharacterBodyDNA,
    CharacterAppearanceProfile, CanonicalAsset,
    CharacterVersionQA, CharacterRuntimeV2,
)
from app.middleware.auth import get_current_user, require_platform_admin
from app.services import character_versions as version_service
from app.api_docs import error_responses

router = APIRouter(prefix="/api/v1/characters-v2", tags=["Character Registry V2"])


# ========================== Schemas ==============================

class CharacterCreate(BaseModel):
    character_id: str = Field(..., description="e.g. EE-F-002")
    display_name: str
    internal_name: Optional[str] = None
    workspace_id: Optional[str] = None
    gender_presentation: Optional[str] = None


class CharacterVersionCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{
            "character_version": "1.1",
            "based_on_version": "1.0",
            "canonical_height_cm": 179,
            "release_notes": "Height re-measured from new canonical full-body set.",
        }]},
    )

    character_version: str = Field(
        ...,
        validation_alias=AliasChoices("character_version", "version"),
        pattern=r"^\d+\.\d+$",
        description="New version in MAJOR.MINOR form (e.g. 1.1, 2.0). Must be greater than every existing version. `version` is accepted as an alias.",
        examples=["1.1"],
    )
    based_on_version: Optional[str] = Field(
        None, description="Version to copy the Character Core from. Defaults to the latest existing version.", examples=["1.0"]
    )
    canonical_height_cm: Optional[float] = Field(None, gt=0, lt=300, description="Overrides the copied height.", examples=[179])
    stature: Optional[str] = Field(None, max_length=30, description="Overrides the copied stature class.", examples=["TALL"])
    body_archetype: Optional[str] = Field(None, max_length=50, description="Overrides the copied body archetype.", examples=["HIGH_FASHION_RUNWAY_SLIM"])
    taxonomy_version: Optional[str] = Field(None, max_length=20, description="Taxonomy version the core was coded against.", examples=["TAXREG-V1.0"])
    release_notes: Optional[str] = Field(None, description="What changed in this version.")


class CharacterVersionUpdate(BaseModel):
    """Editable Character Core fields of a DRAFT version. LOCKED versions reject every change."""
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"canonical_height_cm": 179}]})

    canonical_height_cm: Optional[float] = Field(None, gt=0, lt=300, examples=[179])
    stature: Optional[str] = Field(None, max_length=30, examples=["TALL"])
    body_archetype: Optional[str] = Field(None, max_length=50, examples=["HIGH_FASHION_RUNWAY_SLIM"])
    taxonomy_version: Optional[str] = Field(None, max_length=20, examples=["TAXREG-V1.0"])
    release_notes: Optional[str] = None


class CharacterVersionAdmin(BaseModel):
    """Full character version record (admin only)."""
    character_id: str = Field(..., examples=["EE-F-002"])
    character_version: str = Field(..., examples=["1.0"])
    status: Optional[str] = Field(None, description="DRAFT or LOCKED.", examples=["LOCKED"])
    locked: bool = Field(..., examples=[True])
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = Field(None, examples=["SYSTEM_SEED"])
    canonical_height_cm: Optional[float] = Field(None, examples=[178.0])
    stature: Optional[str] = Field(None, examples=["TALL"])
    body_archetype: Optional[str] = Field(None, examples=["HIGH_FASHION_RUNWAY_SLIM"])
    parent_version: Optional[str] = Field(None, description="Version this one was created from.", examples=[None])
    taxonomy_version: Optional[str] = None
    promoted_to_production: Optional[bool] = None
    promoted_at: Optional[datetime] = None
    release_notes: Optional[str] = None
    dna_snapshot: Optional[Dict[str, Any]] = None
    qa_snapshot: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CharacterVersionList(BaseModel):
    character_id: str = Field(..., examples=["EE-F-002"])
    versions: List[CharacterVersionAdmin] = Field(..., description="Newest version first.")
    total: int = Field(..., examples=[1])


class CharacterVersionDeleted(BaseModel):
    character_id: str = Field(..., examples=["EE-F-002"])
    character_version: str = Field(..., examples=["1.1"])
    deleted: bool = Field(True, examples=[True])


class CustomerCharacterVersion(BaseModel):
    """Customer-safe view of a character's current locked version.

    Only Character Core fields; never adapters, checkpoints, seeds, workflows,
    providers, LoRA strengths, training runs or evaluation scores.
    """
    character_id: str = Field(..., examples=["EE-F-002"])
    display_name: Optional[str] = Field(None, examples=["Eliska Novak"])
    character_version: str = Field(..., examples=["1.0"])
    status: str = Field(..., examples=["LOCKED"])
    canonical_height_cm: Optional[float] = Field(None, examples=[178.0])
    stature: Optional[str] = Field(None, examples=["TALL"])
    body_archetype: Optional[str] = Field(None, examples=["HIGH_FASHION_RUNWAY_SLIM"])
    locked_at: Optional[datetime] = None


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

@router.get(
    "",
    summary="List characters (v2)",
    description="List all characters — Character Library API.",
    response_description="Characters in the Character Library.",
    operation_id="list_characters_v2",
    responses=error_responses(401, 422),
)
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


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a character (v2)",
    description="Create a new character.",
    response_description="The created character.",
    operation_id="create_character_v2",
    responses=error_responses(401, 409, 422),
)
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


@router.get(
    "/{character_id}",
    summary="Get a character (v2)",
    description="Get full character profile.",
    response_description="Full character profile.",
    operation_id="get_character_v2",
    responses=error_responses(401, 404, 422),
)
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


# ========================== Character Versions ===================
# Versions freeze the Character Core. LOCKED versions are immutable (enforced
# in app.services.character_versions and by ORM guards); changes go into a new
# DRAFT version. All writes and the full record are platform-admin only.

_ADMIN_NOTE = "\n\nRequires a platform admin (`User.role` admin/owner)."


def _version_out(v: CharacterRegistryVersion) -> CharacterVersionAdmin:
    return CharacterVersionAdmin(
        character_id=v.character_id,
        character_version=v.version,
        status=v.status,
        locked=bool(v.locked),
        locked_at=v.locked_at,
        locked_by=v.locked_by,
        canonical_height_cm=v.canonical_height_cm,
        stature=v.stature,
        body_archetype=v.body_archetype,
        parent_version=v.parent_version,
        taxonomy_version=v.taxonomy_version,
        promoted_to_production=v.promoted_to_production,
        promoted_at=v.promoted_at,
        release_notes=v.release_notes,
        dna_snapshot=v.dna_snapshot,
        qa_snapshot=v.qa_snapshot,
        meta=v.meta,
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, version_service.CharacterVersionNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, version_service.CharacterVersionConflict):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


_SERVICE_ERRORS = (
    version_service.CharacterVersionNotFound,
    version_service.CharacterVersionConflict,
    version_service.CharacterVersionInvalid,
)


@router.get(
    "/{character_id}/versions",
    response_model=CharacterVersionList,
    summary="List character versions",
    description="List every version of a character, newest first, with full details." + _ADMIN_NOTE,
    response_description="All versions of the character.",
    operation_id="get_character_versions",
    responses=error_responses(401, 403, 422),
)
async def get_character_versions(
    character_id: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    versions = await version_service.list_versions(db, character_id)
    return CharacterVersionList(
        character_id=character_id,
        versions=[_version_out(v) for v in versions],
        total=len(versions),
    )


@router.post(
    "/{character_id}/versions",
    status_code=status.HTTP_201_CREATED,
    response_model=CharacterVersionAdmin,
    summary="Create a draft character version",
    description=(
        "Create a new version of a character in `DRAFT` status. The Character Core "
        "(height, stature, body archetype, taxonomy version) is copied from "
        "`based_on_version` (default: the latest version) and any fields in the body "
        "are applied on top. Existing versions, including LOCKED ones, are left untouched.\n"
        "\n"
        "Errors: `400` invalid version number or not greater than the latest version; "
        "`404` `based_on_version` not found; `409` version already exists." + _ADMIN_NOTE
    ),
    response_description="The created DRAFT version.",
    operation_id="create_character_version",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def create_character_version(
    character_id: str,
    payload: CharacterVersionCreate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        draft = await version_service.create_draft_version(
            db,
            character_id,
            payload.character_version,
            based_on=payload.based_on_version,
            canonical_height_cm=payload.canonical_height_cm,
            stature=payload.stature,
            body_archetype=payload.body_archetype,
            taxonomy_version=payload.taxonomy_version,
            release_notes=payload.release_notes,
        )
    except _SERVICE_ERRORS as exc:
        raise _http_error(exc)
    return _version_out(draft)


@router.get(
    "/{character_id}/current-version",
    response_model=CustomerCharacterVersion,
    summary="Get the current locked character version",
    description=(
        "Customer-safe view of the character's current (highest) LOCKED version: "
        "identity and Character Core fields only. Technical fields (adapters, "
        "checkpoints, seeds, workflows, providers, LoRA strengths, training runs, "
        "evaluation scores) are never returned.\n"
        "\n"
        "Available to any authenticated user. `404` if the character has no locked version."
    ),
    response_description="The current locked version, customer-facing fields only.",
    operation_id="get_current_character_version",
    responses=error_responses(401, 404, 422),
)
async def get_current_character_version(
    character_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        current = await version_service.get_current_locked_version(db, character_id)
    except _SERVICE_ERRORS as exc:
        raise _http_error(exc)
    char = (await db.execute(
        select(CharacterV2).where(CharacterV2.character_id == character_id)
    )).scalars().first()
    return CustomerCharacterVersion(
        character_id=current.character_id,
        display_name=char.display_name if char else None,
        character_version=current.version,
        status=version_service.STATUS_LOCKED,
        canonical_height_cm=current.canonical_height_cm,
        stature=current.stature,
        body_archetype=current.body_archetype,
        locked_at=current.locked_at,
    )


@router.get(
    "/{character_id}/versions/{version}",
    response_model=CharacterVersionAdmin,
    summary="Get a character version",
    description="Get one version of a character with full details." + _ADMIN_NOTE,
    response_description="The character version.",
    operation_id="get_character_version",
    responses=error_responses(401, 403, 404, 422),
)
async def get_character_version(
    character_id: str,
    version: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        found = await version_service.get_version(db, character_id, version)
    except _SERVICE_ERRORS as exc:
        raise _http_error(exc)
    return _version_out(found)


@router.patch(
    "/{character_id}/versions/{version}",
    response_model=CharacterVersionAdmin,
    summary="Update a draft character version",
    description=(
        "Edit the Character Core of a `DRAFT` version. A LOCKED version can never be "
        "changed: the request is rejected with `409` and the version is left untouched; "
        "create a new version instead. Unknown fields (e.g. `status`, `locked`) are rejected with `422`."
        + _ADMIN_NOTE
    ),
    response_description="The updated DRAFT version.",
    operation_id="update_character_version",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def update_character_version(
    character_id: str,
    version: str,
    payload: CharacterVersionUpdate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        updated = await version_service.update_draft_version(
            db, character_id, version, **payload.model_dump(exclude_none=True)
        )
    except _SERVICE_ERRORS as exc:
        raise _http_error(exc)
    return _version_out(updated)


@router.delete(
    "/{character_id}/versions/{version}",
    response_model=CharacterVersionDeleted,
    summary="Delete a draft character version",
    description=(
        "Delete a `DRAFT` version. LOCKED versions can never be deleted (`409`)." + _ADMIN_NOTE
    ),
    response_description="Confirmation that the draft was deleted.",
    operation_id="delete_character_version",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def delete_character_version(
    character_id: str,
    version: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await version_service.delete_draft_version(db, character_id, version)
    except _SERVICE_ERRORS as exc:
        raise _http_error(exc)
    return CharacterVersionDeleted(character_id=character_id, character_version=version)


@router.post(
    "/{character_id}/versions/{version}/lock",
    response_model=CharacterVersionAdmin,
    summary="Lock a character version",
    description=(
        "Lock a `DRAFT` version (one-way). After locking, the Character Core can never be "
        "changed or deleted. `locked_by` is set to the calling admin's user ID.\n"
        "\n"
        "Errors: `400` canonical_height_cm, stature or body_archetype missing; "
        "`409` already locked." + _ADMIN_NOTE
    ),
    response_description="The LOCKED version.",
    operation_id="lock_character_version_by_path",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def lock_character_version_by_path(
    character_id: str,
    version: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        locked = await version_service.lock_version(db, character_id, version, locked_by=str(current_user.id))
    except _SERVICE_ERRORS as exc:
        raise _http_error(exc)
    return _version_out(locked)


@router.post(
    "/{character_id}/identity-dna",
    status_code=status.HTTP_201_CREATED,
    summary="Create character identity DNA",
    description="Create Identity DNA.",
    response_description="The created identity DNA record.",
    operation_id="create_identity_dna",
    responses=error_responses(401, 422),
)
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


@router.post(
    "/{character_id}/body-dna",
    status_code=status.HTTP_201_CREATED,
    summary="Create character body DNA",
    description="Create Body DNA.",
    response_description="The created body DNA record.",
    operation_id="create_body_dna",
    responses=error_responses(401, 422),
)
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


@router.post(
    "/{character_id}/appearance",
    status_code=status.HTTP_201_CREATED,
    summary="Create a character appearance profile",
    description="Create Appearance Profile.",
    response_description="The created appearance profile.",
    operation_id="create_appearance",
    responses=error_responses(401, 422),
)
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


@router.post(
    "/{character_id}/canonical-assets",
    status_code=status.HTTP_201_CREATED,
    summary="Register a canonical asset",
    description="Register a canonical asset.",
    response_description="The registered canonical asset.",
    operation_id="add_canonical_asset",
    responses=error_responses(401, 422),
)
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


@router.get(
    "/{character_id}/canonical-assets",
    summary="List canonical assets",
    description="Get canonical assets.",
    response_description="Canonical assets for the character.",
    operation_id="get_canonical_assets",
    responses=error_responses(401, 422),
)
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


@router.patch(
    "/{character_id}/canonical-assets/{asset_id}/qa",
    summary="Update canonical asset QA",
    description="Update QA status for a canonical asset.",
    response_description="The canonical asset with its updated QA status.",
    operation_id="update_asset_qa",
    responses=error_responses(401, 404, 422),
)
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


@router.get(
    "/{character_id}/qa",
    summary="Get character QA gates",
    description="Get QA gates for a character version.",
    response_description="QA gate status for the character version.",
    operation_id="get_character_qa",
    responses=error_responses(401, 404, 422),
)
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


@router.patch(
    "/{character_id}/qa",
    summary="Update character QA gates",
    description="Update QA gates for a character version.",
    response_description="The updated QA gates.",
    operation_id="update_version_qa",
    responses=error_responses(401, 422),
)
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


@router.get(
    "/{character_id}/runtime-profile",
    summary="Get character runtime profile",
    description="Get Character Runtime Profile for Studios.",
    response_description="Runtime profile consumed by the studios.",
    operation_id="get_runtime_profile",
    responses=error_responses(401, 404, 422),
)
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


@router.post(
    "/{character_id}/lock",
    response_model=CharacterVersionAdmin,
    summary="Lock a character version (query form)",
    description=(
        "Deprecated alias of `POST /api/v1/characters-v2/{character_id}/versions/{version}/lock` "
        "taking the version as a `version` query parameter. Same rules: one-way, "
        "`400` if Character Core fields are missing, `409` if already locked." + _ADMIN_NOTE
    ),
    response_description="The LOCKED version.",
    operation_id="lock_character_version",
    responses=error_responses(400, 401, 403, 404, 409, 422),
    deprecated=True,
)
async def lock_character_version(
    character_id: str,
    version: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        locked = await version_service.lock_version(db, character_id, version, locked_by=str(current_user.id))
    except _SERVICE_ERRORS as exc:
        raise _http_error(exc)
    return _version_out(locked)


@router.post(
    "/{character_id}/promote",
    summary="Promote a character to production",
    description=(
        "Promote a LOCKED character version to PRODUCTION: flags the version as promoted "
        "(its Character Core and LOCKED status are unchanged) and marks the character "
        "production-enabled and customer-visible." + _ADMIN_NOTE
    ),
    response_description="The character promoted to PRODUCTION.",
    operation_id="promote_to_production",
    responses=error_responses(400, 401, 403, 404, 422),
)
async def promote_to_production(
    character_id: str,
    version: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Promote locked character to PRODUCTION."""
    try:
        char_version = await version_service.get_version(db, character_id, version)
    except _SERVICE_ERRORS as exc:
        raise _http_error(exc)

    if not version_service.is_locked(char_version):
        raise HTTPException(status_code=400, detail="Must be LOCKED before PRODUCTION.")

    char_version.promoted_to_production = True
    char_version.promoted_at = datetime.utcnow()

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


@router.patch(
    "/{character_id}/status",
    summary="Update character status (v2)",
    description="Update character lifecycle status.",
    response_description="The character with its updated lifecycle status.",
    operation_id="update_character_status_v2",
    responses=error_responses(400, 401, 404, 422),
)
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
