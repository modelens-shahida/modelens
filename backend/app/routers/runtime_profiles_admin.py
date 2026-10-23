"""
Runtime profile admin API (platform admins only), APPEARANCE_STATUS.md section 2.2 (PR AC-1).

Create a DRAFT runtime profile for a character version (strategies, pinned
reference set, adapter and strengths, QA profile, retry policy), promote it to
PRODUCTION (retiring the previous one), retire it, and seed the EE-F-002 V1
profile as DRAFT. A PRODUCTION / RETIRED profile never changes: 409. Promotion
refuses REFERENCE_PLUS_ADAPTER unless the adapter is PRODUCTION. Every action
writes an ``audit_logs`` entry. Responses carry adapters and strengths;
customers never see this API.
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_docs import error_responses
from app.middleware.auth import require_platform_admin
from app.models.db import RuntimeProfile, User, get_db
from app.services import runtime_profiles as svc

Strategy = Literal["REFERENCE_ONLY", "REFERENCE_PLUS_ADAPTER"]
ProfileStatus = Literal["DRAFT", "PRODUCTION", "RETIRED"]
CHARACTER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,49}$"
PROFILE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$"

router = APIRouter(
    prefix="/api/v1/admin/characters",
    tags=["Runtime Profiles"],
    dependencies=[Depends(require_platform_admin)],
)


async def _run(db: AsyncSession, coro):
    try:
        return await coro
    except svc.RuntimeProfileNotFound as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except svc.RuntimeProfileConflict as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except svc.RuntimeProfileInvalid as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ========================== Schemas ===============================

class CreateRequest(BaseModel):
    character_version: str = Field(..., max_length=10, examples=["1.0"])
    default_strategy: Strategy = "REFERENCE_ONLY"
    allowed_strategies: Optional[list[Strategy]] = Field(
        None, min_length=1, max_length=2, description="Defaults to [default_strategy].")
    reference_set_id: Optional[str] = Field(None, max_length=60, description="A LOCKED or PRODUCTION reference set "
                                            "of this character version.", examples=["EE-F-002_V1.0_REF_V1"])
    adapter_id: Optional[str] = Field(None, max_length=50, description="Required with REFERENCE_PLUS_ADAPTER.",
                                      examples=["EE-F-002_CK0750"])
    adapter_strength: Optional[float] = Field(None, gt=0, le=1, description="Required with REFERENCE_PLUS_ADAPTER; "
                                              "there is no default strength.")
    fallback_adapter_strength: Optional[float] = Field(None, gt=0, le=1, description="Required with "
                                                       "REFERENCE_PLUS_ADAPTER; greater than adapter_strength.")
    qa_profile_id: Optional[str] = Field(None, max_length=100)
    fallback_retry_enabled: bool = Field(False, description="Automatic retry at the fallback strength after an "
                                         "identity QA failure. Off until decided.")
    notes: Optional[str] = Field(None, max_length=2000)


class RetireRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000, examples=["Replaced by a new reference set."])


class RuntimeProfileOut(BaseModel):
    runtime_profile_id: str = Field(..., examples=["EE-F-002_V1.0_RT_V1"])
    character_id: str
    character_version: str
    version: int
    status: str
    default_strategy: str
    allowed_strategies: list[str]
    reference_set_id: Optional[str]
    adapter_id: Optional[str]
    adapter_strength: Optional[float]
    fallback_adapter_strength: Optional[float]
    qa_profile_id: Optional[str]
    fallback_retry_enabled: bool
    notes: Optional[str]
    created_by: Optional[str]
    created_at: Optional[datetime]
    promoted_by: Optional[str]
    promoted_at: Optional[datetime]
    retired_by: Optional[str]
    retired_at: Optional[datetime]
    retire_reason: Optional[str]


class RuntimeProfileList(BaseModel):
    character_id: str
    runtime_profiles: list[RuntimeProfileOut]
    total: int


class PromoteOut(RuntimeProfileOut):
    replaced_runtime_profile_id: Optional[str] = Field(None, description="The previous PRODUCTION profile, now "
                                                       "RETIRED.")


class SeedOut(RuntimeProfileOut):
    created: bool = Field(..., description="False when the profile already existed (returned unchanged).")


async def _out(db: AsyncSession, profile: RuntimeProfile, model=RuntimeProfileOut, **extra):
    ref = await svc.reference_set_of(db, profile)
    return model(
        **{f: getattr(profile, f) for f in RuntimeProfileOut.model_fields if f != "reference_set_id"},
        reference_set_id=ref.reference_set_id if ref else None,
        **extra,
    )


CharacterId = Path(..., pattern=CHARACTER_PATTERN, examples=["EE-F-002"])
ProfileId = Path(..., pattern=PROFILE_PATTERN, examples=["EE-F-002_V1.0_RT_V1"])
ADMIN_ERRORS = error_responses(400, 401, 403, 404, 409, 422)


# ========================== Endpoints =============================

@router.post(
    "/{character_id}/runtime-profiles",
    status_code=status.HTTP_201_CREATED,
    response_model=RuntimeProfileOut,
    summary="Create a runtime profile",
    description="Creates a DRAFT runtime profile (next version for the character version). REFERENCE_PLUS_ADAPTER "
                "needs adapter_id, adapter_strength and fallback_adapter_strength (strength < fallback <= 1); "
                "without it those fields and fallback_retry_enabled must be empty. A pinned reference set must be "
                "LOCKED or PRODUCTION and of the same character version.",
    response_description="The DRAFT runtime profile.",
    operation_id="admin_create_runtime_profile",
    responses=ADMIN_ERRORS,
)
async def create_runtime_profile(
    payload: CreateRequest,
    character_id: str = CharacterId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    profile = await _run(db, svc.create_profile(db, character_id=character_id, created_by=admin.email,
                                                actor_user_id=admin.id, **payload.model_dump()))
    return await _out(db, profile)


@router.get(
    "/{character_id}/runtime-profiles",
    response_model=RuntimeProfileList,
    summary="List a character's runtime profiles",
    description="Every runtime profile of the character; filter by character_version and status.",
    response_description="The character's runtime profiles.",
    operation_id="admin_list_runtime_profiles",
    responses=error_responses(401, 403, 422),
)
async def list_runtime_profiles(
    character_id: str = CharacterId,
    character_version: Optional[str] = Query(None, max_length=10),
    profile_status: Optional[ProfileStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    profiles = await svc.list_profiles(db, character_id, character_version, profile_status)
    return RuntimeProfileList(character_id=character_id, total=len(profiles),
                              runtime_profiles=[await _out(db, p) for p in profiles])


@router.post(
    "/{character_id}/runtime-profiles/seed",
    response_model=SeedOut,
    summary="Seed the EE-F-002 V1 runtime profile",
    description="EE-F-002 only. Creates EE-F-002_V1.0_RT_V1 as DRAFT with REFERENCE_ONLY only: no adapter, no "
                "strengths, no pinned set, retry off. Never promotes. Idempotent: an existing V1 profile is "
                "returned unchanged with created=false.",
    response_description="The seeded (or existing) runtime profile.",
    operation_id="admin_seed_runtime_profile",
    responses=ADMIN_ERRORS,
)
async def seed_runtime_profile(
    character_id: str = CharacterId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    if character_id != svc.EE_F_002:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No runtime profile seed for {character_id}.")
    profile, created = await _run(db, svc.seed_ee_f_002_runtime_profile(db, admin.email, admin.id))
    return await _out(db, profile, SeedOut, created=created)


@router.get(
    "/{character_id}/runtime-profiles/{runtime_profile_id}",
    response_model=RuntimeProfileOut,
    summary="Get a runtime profile",
    description="One runtime profile.",
    response_description="The runtime profile.",
    operation_id="admin_get_runtime_profile",
    responses=error_responses(401, 403, 404, 422),
)
async def get_runtime_profile(
    character_id: str = CharacterId,
    runtime_profile_id: str = ProfileId,
    db: AsyncSession = Depends(get_db),
):
    return await _out(db, await _run(db, svc.get_profile(db, runtime_profile_id, character_id)))


@router.post(
    "/{character_id}/runtime-profiles/{runtime_profile_id}/promote",
    response_model=PromoteOut,
    summary="Promote a runtime profile to PRODUCTION",
    description="DRAFT -> PRODUCTION; the previous PRODUCTION profile of the character version is retired. Needs a "
                "LOCKED character version and a pinned set that is still LOCKED / PRODUCTION with matching hashes. "
                "409 when REFERENCE_PLUS_ADAPTER is allowed and the adapter is not PRODUCTION with a checksum.",
    response_description="The PRODUCTION runtime profile.",
    operation_id="admin_promote_runtime_profile",
    responses=ADMIN_ERRORS,
)
async def promote_runtime_profile(
    character_id: str = CharacterId,
    runtime_profile_id: str = ProfileId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    profile = await _run(db, svc.get_profile(db, runtime_profile_id, character_id))
    profile, replaced = await _run(db, svc.promote(db, profile, admin.email, admin.id))
    return await _out(db, profile, PromoteOut,
                      replaced_runtime_profile_id=replaced.runtime_profile_id if replaced else None)


@router.post(
    "/{character_id}/runtime-profiles/{runtime_profile_id}/retire",
    response_model=RuntimeProfileOut,
    summary="Retire a runtime profile",
    description="Retires a DRAFT or PRODUCTION profile (409 when already RETIRED). Retired profiles are kept, never "
                "deleted.",
    response_description="The RETIRED runtime profile.",
    operation_id="admin_retire_runtime_profile",
    responses=ADMIN_ERRORS,
)
async def retire_runtime_profile(
    payload: RetireRequest,
    character_id: str = CharacterId,
    runtime_profile_id: str = ProfileId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    profile = await _run(db, svc.get_profile(db, runtime_profile_id, character_id))
    return await _out(db, await _run(db, svc.retire(db, profile, admin.email, payload.reason, admin.id)))
