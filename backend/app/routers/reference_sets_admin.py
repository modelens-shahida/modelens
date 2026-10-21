"""
Reference set admin API (platform admins only), DESIGN.md section 5.

Build a DRAFT set of a character version's canonical assets, lock it (hashes
frozen), promote it to PRODUCTION (retiring the previous one), retire it, and
verify it (re-read every file and re-hash it). A locked set never changes:
409. Every action writes an ``audit_logs`` entry. Admin responses include
asset ids and hashes; customers never see this API.

The role list and the EE-F-002 V1 seed are to be confirmed by Aryan/Shahida.
The seed builds and locks ``EE-F-002_V1.0_REF_V1``; it never promotes.
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_docs import error_responses
from app.middleware.auth import require_platform_admin
from app.models.db import CharacterReferenceSet, User, get_db
from app.services import reference_sets as svc
from app.services.job_images import storage_key
from app.services.storage import storage_service

Role = Literal["face_front", "face_34", "profile", "body_full", "body_34"]
SetStatus = Literal["DRAFT", "LOCKED", "PRODUCTION", "RETIRED"]
CHARACTER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,49}$"
SET_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$"

router = APIRouter(
    prefix="/api/v1/admin/characters",
    tags=["Reference Sets"],
    dependencies=[Depends(require_platform_admin)],
)


async def _run(db: AsyncSession, coro):
    try:
        return await coro
    except svc.ReferenceSetNotFound as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except svc.ReferenceSetConflict as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except svc.ReferenceSetInvalid as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ========================== Schemas ===============================

class ItemIn(BaseModel):
    canonical_asset_id: str = Field(..., max_length=50, description="The canonical asset's asset_id.",
                                    examples=["CA-EE-F-002-FACE-FRONT-001"])
    role: Role


class CreateRequest(BaseModel):
    character_version: str = Field(..., max_length=10, examples=["1.0"])
    items: list[ItemIn] = Field(..., min_length=1, max_length=20)


class RetireRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000, examples=["Replaced after a new face shoot."])


class ItemOut(BaseModel):
    canonical_asset_id: str
    role: str
    sort_order: int
    content_hash_sha256: Optional[str]


class ReferenceSetOut(BaseModel):
    reference_set_id: str = Field(..., examples=["EE-F-002_V1.0_REF_V1"])
    character_id: str
    character_version: str
    version: int
    status: str
    content_hash: Optional[str]
    created_by: Optional[str]
    locked_at: Optional[datetime]
    locked_by: Optional[str]
    promoted_at: Optional[datetime]
    promoted_by: Optional[str]
    retired_at: Optional[datetime]
    retired_by: Optional[str]
    retire_reason: Optional[str]
    created_at: Optional[datetime]
    items: list[ItemOut]


class ReferenceSetList(BaseModel):
    character_id: str
    reference_sets: list[ReferenceSetOut]
    total: int


class PromoteOut(ReferenceSetOut):
    replaced_reference_set_id: Optional[str] = Field(None, description="The previous PRODUCTION set, now RETIRED.")


class SeedOut(ReferenceSetOut):
    created: bool = Field(..., description="False when the set already existed (returned unchanged).")


class VerifyOut(BaseModel):
    reference_set_id: str
    ok: bool
    problems: list[str]


async def _out(db: AsyncSession, ref: CharacterReferenceSet, model=ReferenceSetOut, **extra):
    set_items = await svc.items(db, ref)
    return model(
        **{f: getattr(ref, f) for f in ReferenceSetOut.model_fields if f != "items"},
        items=[ItemOut(canonical_asset_id=i.asset_id, role=i.role, sort_order=i.sort_order,
                       content_hash_sha256=i.content_hash_sha256) for i in set_items],
        **extra,
    )


def _read_bytes(path: Optional[str]) -> bytes:
    return storage_service.read_file_bytes(storage_key(path or ""))


CharacterId = Path(..., pattern=CHARACTER_PATTERN, examples=["EE-F-002"])
SetId = Path(..., pattern=SET_PATTERN, examples=["EE-F-002_V1.0_REF_V1"])
ADMIN_ERRORS = error_responses(400, 401, 403, 404, 409, 422)


# ========================== Endpoints =============================

@router.post(
    "/{character_id}/reference-sets",
    status_code=status.HTTP_201_CREATED,
    response_model=ReferenceSetOut,
    summary="Create a reference set",
    description="Creates a DRAFT reference set (next version for the character version) from canonical assets of "
                "that character version that are production-reference eligible and have a content hash. Roles: "
                "face_front, face_34, profile, body_full, body_34 (to be confirmed by Aryan/Shahida).",
    response_description="The DRAFT reference set.",
    operation_id="admin_create_character_reference_set",
    responses=ADMIN_ERRORS,
)
async def create_reference_set(
    payload: CreateRequest,
    character_id: str = CharacterId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    ref = await _run(db, svc.create_set(db, character_id=character_id, character_version=payload.character_version,
                                        items_in=[i.model_dump() for i in payload.items], created_by=admin.email,
                                        actor_user_id=admin.id))
    return await _out(db, ref)


@router.get(
    "/{character_id}/reference-sets",
    response_model=ReferenceSetList,
    summary="List a character's reference sets",
    description="Every reference set of the character with its items and hashes; filter by character_version "
                "and status.",
    response_description="The character's reference sets.",
    operation_id="admin_list_character_reference_sets",
    responses=error_responses(401, 403, 422),
)
async def list_reference_sets(
    character_id: str = CharacterId,
    character_version: Optional[str] = Query(None, max_length=10),
    set_status: Optional[SetStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    sets = await svc.list_sets(db, character_id, character_version, set_status)
    return ReferenceSetList(character_id=character_id, total=len(sets),
                            reference_sets=[await _out(db, s) for s in sets])


@router.post(
    "/{character_id}/reference-sets/seed",
    response_model=SeedOut,
    summary="Seed the EE-F-002 V1 reference set",
    description="EE-F-002 only. Builds EE-F-002_V1.0_REF_V1 from V1.0's production-reference eligible canonical "
                "assets (one per role, matched by framing and angle; to be confirmed by Aryan/Shahida) and locks "
                "it. Never promotes. Idempotent: an existing V1 set is returned unchanged with created=false. 400 "
                "when face_front or body_full has no eligible asset.",
    response_description="The seeded (or existing) reference set.",
    operation_id="admin_seed_character_reference_set",
    responses=ADMIN_ERRORS,
)
async def seed_reference_set(
    character_id: str = CharacterId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    if character_id != svc.EE_F_002:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No reference set seed for {character_id}.")
    ref, created = await _run(db, svc.seed_ee_f_002_reference_set(db, admin.email, admin.id))
    return await _out(db, ref, SeedOut, created=created)


@router.get(
    "/{character_id}/reference-sets/{reference_set_id}",
    response_model=ReferenceSetOut,
    summary="Get a reference set",
    description="One reference set with its items and hashes.",
    response_description="The reference set.",
    operation_id="admin_get_character_reference_set",
    responses=error_responses(401, 403, 404, 422),
)
async def get_reference_set(
    character_id: str = CharacterId,
    reference_set_id: str = SetId,
    db: AsyncSession = Depends(get_db),
):
    return await _out(db, await _run(db, svc.get_set(db, reference_set_id, character_id)))


@router.post(
    "/{character_id}/reference-sets/{reference_set_id}/lock",
    response_model=ReferenceSetOut,
    summary="Lock a reference set",
    description="DRAFT -> LOCKED: copies each asset's sha256 onto its item and stores the set hash. Needs "
                "face_front and body_full and a LOCKED character version. A locked set never changes.",
    response_description="The LOCKED reference set.",
    operation_id="admin_lock_character_reference_set",
    responses=ADMIN_ERRORS,
)
async def lock_reference_set(
    character_id: str = CharacterId,
    reference_set_id: str = SetId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    ref = await _run(db, svc.get_set(db, reference_set_id, character_id))
    return await _out(db, await _run(db, svc.lock(db, ref, admin.email, admin.id)))


@router.post(
    "/{character_id}/reference-sets/{reference_set_id}/promote",
    response_model=PromoteOut,
    summary="Promote a reference set to PRODUCTION",
    description="LOCKED -> PRODUCTION after a hash check; the previous PRODUCTION set of the character version is "
                "retired. 409 from any other status or when the hashes no longer match.",
    response_description="The PRODUCTION reference set.",
    operation_id="admin_promote_character_reference_set",
    responses=ADMIN_ERRORS,
)
async def promote_reference_set(
    character_id: str = CharacterId,
    reference_set_id: str = SetId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    ref = await _run(db, svc.get_set(db, reference_set_id, character_id))
    ref, replaced = await _run(db, svc.promote(db, ref, admin.email, admin.id))
    return await _out(db, ref, PromoteOut,
                      replaced_reference_set_id=replaced.reference_set_id if replaced else None)


@router.post(
    "/{character_id}/reference-sets/{reference_set_id}/retire",
    response_model=ReferenceSetOut,
    summary="Retire a reference set",
    description="Retires a set from any status except RETIRED (409). Retired sets are kept, never deleted.",
    response_description="The RETIRED reference set.",
    operation_id="admin_retire_character_reference_set",
    responses=ADMIN_ERRORS,
)
async def retire_reference_set(
    payload: RetireRequest,
    character_id: str = CharacterId,
    reference_set_id: str = SetId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    ref = await _run(db, svc.get_set(db, reference_set_id, character_id))
    return await _out(db, await _run(db, svc.retire(db, ref, admin.email, payload.reason, admin.id)))


@router.post(
    "/{character_id}/reference-sets/{reference_set_id}/verify",
    response_model=VerifyOut,
    summary="Verify a reference set",
    description="Checks the set hash against its items and each item against its canonical asset, then re-reads "
                "every file from storage and re-hashes it. Changes nothing; `ok` is false with the problems "
                "listed on any mismatch.",
    response_description="The verification result.",
    operation_id="admin_verify_character_reference_set",
    responses=error_responses(401, 403, 404, 422),
)
async def verify_reference_set(
    character_id: str = CharacterId,
    reference_set_id: str = SetId,
    db: AsyncSession = Depends(get_db),
):
    ref = await _run(db, svc.get_set(db, reference_set_id, character_id))
    result = await svc.verify(db, ref, _read_bytes)
    return VerifyOut(reference_set_id=ref.reference_set_id, **result)
