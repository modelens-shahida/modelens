"""
Capability validation admin API (platform admins only).

Per-character validation and promotion of every customer-visible capability
(docs/character-runtime/DESIGN.md section 5): register -> validate -> promote
-> retire, plus listing. The lifecycle rules live in
``app/services/capability_validations.py``; a step the lifecycle does not
allow is a 409 that names the current status and the allowed next ones.

Who validated and who promoted are recorded separately. They may be the same
platform admin: the four-eyes rule (DESIGN.md open question 7) is pending.
Every action writes an ``audit_logs`` entry (who, what, from/to status, when).

These responses are admin-only and include internal keys, versions and
evidence. Customer routes are unchanged and never read this API.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_docs import error_responses
from app.middleware.auth import require_platform_admin
from app.models.db import CapabilityValidation, User, get_db
from app.services import capability_validations as svc
from app.services import character_versions as version_service

CapabilityType = Literal[
    "HAIR", "MAKEUP", "EXPRESSION", "JEWELRY", "BEAUTY_DIRECTION", "POSE", "CAMERA", "SCENE", "LIGHTING",
    "CAMPAIGN", "PRODUCT_TYPE",
]
CapabilityStatus = Literal["REGISTERED", "VALIDATING", "VALIDATED", "PROMOTED", "REJECTED", "RETIRED"]
CheckResult = Literal["PASS", "FAIL"]
KEY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$"
CHARACTER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,49}$"

router = APIRouter(
    prefix="/api/v1/admin/characters",
    tags=["Capability Validations"],
    dependencies=[Depends(require_platform_admin)],
)


async def _run(db: AsyncSession, coro):
    """Translate service errors into HTTP errors; nothing half-done is kept."""
    try:
        return await coro
    except svc.CapabilityNotFound as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except svc.CapabilityConflict as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except svc.CapabilityInvalid as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


async def _version(db: AsyncSession, character_id: str, character_version: Optional[str]) -> str:
    """The requested character version, or the character's current locked version."""
    if character_version:
        return character_version
    try:
        return (await version_service.get_current_locked_version(db, character_id)).version
    except version_service.CharacterVersionNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def _record(db: AsyncSession, character_id: str, character_version: Optional[str], capability_type: str,
                  capability_key: str, capability_version: int) -> CapabilityValidation:
    version = await _version(db, character_id, character_version)
    return await _run(db, svc.get_record(db, character_id, version, capability_type, capability_key,
                                         capability_version))


# ========================== Schemas ===============================

class AdminCapability(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    character_id: str = Field(..., examples=["EE-F-002"])
    character_version: str = Field(..., examples=["1.0"])
    capability_type: str = Field(..., examples=["BEAUTY_DIRECTION"])
    capability_key: str = Field(..., examples=["QUIET_LUXURY"])
    capability_version: int = Field(..., examples=[1])
    customer_id: str = Field(..., examples=["beauty_quiet_luxury"])
    status: str = Field(..., examples=["REGISTERED"])
    validation: Optional[dict[str, Any]] = None
    validated_by: Optional[str] = None
    validated_at: Optional[datetime] = None
    promoted_by: Optional[str] = None
    promoted_at: Optional[datetime] = None
    retired_by: Optional[str] = None
    retired_at: Optional[datetime] = None
    retire_reason: Optional[str] = None
    is_default: bool
    recommended: bool
    group: Optional[str] = None
    sort_order: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminCapabilityList(BaseModel):
    character_id: str
    capabilities: list[AdminCapability]
    total: int


class RegisterRequest(BaseModel):
    character_version: str = Field(..., max_length=10, examples=["1.0"])
    capability_type: CapabilityType
    capability_key: str = Field(..., pattern=KEY_PATTERN, examples=["QUIET_LUXURY"])
    capability_version: int = Field(1, ge=1)
    customer_id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$", examples=["beauty_quiet_luxury"])
    group: Optional[str] = Field(None, max_length=30, examples=["Luxury"])
    sort_order: int = Field(0, ge=0)


class _Target(BaseModel):
    capability_version: int = Field(..., ge=1)
    character_version: Optional[str] = Field(
        None, max_length=10, description="Defaults to the character's current locked version.")


class ValidationChecks(BaseModel):
    identity: CheckResult
    face: CheckResult
    body: CheckResult
    product: CheckResult


class ValidationRequest(_Target):
    checks: ValidationChecks
    evidence: Optional[dict[str, Any]] = Field(
        None, examples=[{"sample_production_ids": ["prd_val_001"], "notes": "Identity stable across 24 samples."}])


class ValidationResponse(BaseModel):
    status: str = Field(..., examples=["VALIDATED"])
    validated_by: Optional[str]
    validated_at: Optional[datetime]


class PromoteRequest(_Target):
    is_default: bool = False
    recommended: bool = False


class PromoteResponse(BaseModel):
    status: str = Field(..., examples=["PROMOTED"])
    promoted_by: Optional[str]
    promoted_at: Optional[datetime]
    replaced_version: Optional[int] = Field(None, description="The previously promoted version, now RETIRED.")


class RetireRequest(_Target):
    reason: str = Field(..., min_length=1, max_length=1000, examples=["Hand artefacts at 4K."])


class RetireResponse(BaseModel):
    status: str = Field(..., examples=["RETIRED"])
    retired_by: Optional[str]
    retired_at: Optional[datetime]
    retire_reason: Optional[str]


CharacterId = Path(..., pattern=CHARACTER_PATTERN, examples=["EE-F-002"])
CapabilityKey = Path(..., pattern=KEY_PATTERN, examples=["QUIET_LUXURY"])
ADMIN_ERRORS = error_responses(400, 401, 403, 404, 409, 422)


# ========================== Endpoints =============================

@router.post(
    "/{character_id}/capabilities",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminCapability,
    summary="Register a capability for a character version",
    description="Registers a capability (hair, makeup, expression, jewelry, beauty direction, pose, camera, scene, "
                "lighting, campaign or product type) for one character version. It starts REGISTERED and is not "
                "visible to customers. 409 when the same capability version is already registered or the customer "
                "id is used by another live capability of the character version.",
    response_description="The registered capability record.",
    operation_id="register_character_capability",
    responses=ADMIN_ERRORS,
)
async def register_capability(
    payload: RegisterRequest,
    character_id: str = CharacterId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    return await _run(db, svc.register(
        db, character_id=character_id, registered_by=admin.email, actor_user_id=admin.id, **payload.model_dump()))


@router.get(
    "/{character_id}/capabilities",
    response_model=AdminCapabilityList,
    summary="List a character's capability records",
    description="Every capability record of the character (all versions and statuses), with validation evidence "
                "and who validated, promoted or retired it. Filter by `type`, `status` and `character_version`.",
    response_description="The character's capability records.",
    operation_id="list_character_capabilities",
    responses=error_responses(401, 403, 422),
)
async def list_capabilities(
    character_id: str = CharacterId,
    capability_type: Optional[CapabilityType] = Query(None, alias="type"),
    capability_status: Optional[CapabilityStatus] = Query(None, alias="status"),
    character_version: Optional[str] = Query(None, max_length=10),
    db: AsyncSession = Depends(get_db),
):
    records = await svc.list_records(db, character_id, character_version, capability_type, capability_status)
    return AdminCapabilityList(character_id=character_id, total=len(records),
                               capabilities=[AdminCapability.model_validate(r) for r in records])


@router.post(
    "/{character_id}/capabilities/{capability_type}/{capability_key}/validation/start",
    response_model=AdminCapability,
    summary="Start validating a capability",
    description="Moves a REGISTERED, VALIDATED or REJECTED record to VALIDATING (e.g. rework after a rejection). "
                "409 from any other status.",
    response_description="The capability record, now VALIDATING.",
    operation_id="start_character_capability_validation",
    responses=ADMIN_ERRORS,
)
async def start_validation(
    payload: _Target,
    capability_type: CapabilityType,
    character_id: str = CharacterId,
    capability_key: str = CapabilityKey,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    record = await _record(db, character_id, payload.character_version, capability_type, capability_key,
                           payload.capability_version)
    return await _run(db, svc.start_validation(db, record, admin.email, admin.id))


@router.post(
    "/{character_id}/capabilities/{capability_type}/{capability_key}/validation",
    response_model=ValidationResponse,
    summary="Record a capability's validation",
    description="Records the identity, face, body and product checks with evidence. Every check PASS -> "
                "VALIDATED; any FAIL -> REJECTED. Allowed from REGISTERED or VALIDATING (a REJECTED record is "
                "started again first); 409 otherwise.",
    response_description="The validation result: VALIDATED or REJECTED.",
    operation_id="validate_character_capability",
    responses=ADMIN_ERRORS,
)
async def validate_capability(
    payload: ValidationRequest,
    capability_type: CapabilityType,
    character_id: str = CharacterId,
    capability_key: str = CapabilityKey,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    record = await _record(db, character_id, payload.character_version, capability_type, capability_key,
                           payload.capability_version)
    record = await _run(db, svc.record_validation(db, record, payload.checks.model_dump(), payload.evidence,
                                                  admin.email, admin.id))
    return ValidationResponse(status=record.status, validated_by=record.validated_by,
                              validated_at=record.validated_at)


@router.post(
    "/{character_id}/capabilities/{capability_type}/{capability_key}/promote",
    response_model=PromoteResponse,
    summary="Promote a validated capability",
    description="Promotes a VALIDATED record; 409 from any other status. The previously promoted version of the "
                "same capability is retired (`replaced_version`), and `is_default` clears the old default of the "
                "type. The promoter may be the validator (four-eyes rule pending).",
    response_description="The promotion result.",
    operation_id="promote_character_capability",
    responses=ADMIN_ERRORS,
)
async def promote_capability(
    payload: PromoteRequest,
    capability_type: CapabilityType,
    character_id: str = CharacterId,
    capability_key: str = CapabilityKey,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    record = await _record(db, character_id, payload.character_version, capability_type, capability_key,
                           payload.capability_version)
    record, replaced = await _run(db, svc.promote(db, record, admin.email, is_default=payload.is_default,
                                                  recommended=payload.recommended, actor_user_id=admin.id))
    return PromoteResponse(status=record.status, promoted_by=record.promoted_by, promoted_at=record.promoted_at,
                           replaced_version=replaced.capability_version if replaced else None)


@router.post(
    "/{character_id}/capabilities/{capability_type}/{capability_key}/retire",
    response_model=RetireResponse,
    summary="Retire a capability",
    description="Retires a record from any status except RETIRED (409). Retired records are kept, never deleted.",
    response_description="The retirement result.",
    operation_id="retire_character_capability",
    responses=ADMIN_ERRORS,
)
async def retire_capability(
    payload: RetireRequest,
    capability_type: CapabilityType,
    character_id: str = CharacterId,
    capability_key: str = CapabilityKey,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    record = await _record(db, character_id, payload.character_version, capability_type, capability_key,
                           payload.capability_version)
    record = await _run(db, svc.retire(db, record, admin.email, payload.reason, admin.id))
    return RetireResponse(status=record.status, retired_by=record.retired_by, retired_at=record.retired_at,
                          retire_reason=record.retire_reason)
