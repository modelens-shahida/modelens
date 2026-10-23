"""
Runtime profiles: the approved way to run one character version
(docs/character-runtime/APPEARANCE_STATUS.md sections 1.3, 4.3 and 7, PR AC-1).

A profile names the default and allowed strategies (``REFERENCE_ONLY``,
``REFERENCE_PLUS_ADAPTER``), the pinned reference set, the adapter with its
strength and stronger fallback strength, the QA profile and the automatic
retry policy (``fallback_retry_enabled``, off by default and until decided).
Strengths are data on the profile, never a constant here: a profile that
allows ``REFERENCE_PLUS_ADAPTER`` must carry both values.

Lifecycle: DRAFT -> PRODUCTION -> RETIRED (a DRAFT can also be retired). At
most one PRODUCTION profile per character version: promoting a profile
retires the previous one. A PRODUCTION / RETIRED profile never changes except
its status (ORM rules in app/models/db.py). Promotion refuses
``REFERENCE_PLUS_ADAPTER`` unless the adapter is PRODUCTION: EVALUATION /
EXPERIMENTAL adapters are never in a PRODUCTION profile.

The EE-F-002 seed creates ``EE-F-002_V1.0_RT_V1`` as DRAFT, REFERENCE_ONLY,
with no adapter; it never promotes. Every write adds an ``audit_logs`` entry
in the same transaction. Nothing here is customer-facing.
"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import (
    RUNTIME_PROFILE_TRANSITIONS as TRANSITIONS,
    CharacterReferenceSet,
    ModelArtifact,
    QAProfile,
    RuntimeProfile,
)
from app.services import character_versions as version_service
from app.services import reference_sets as reference_set_service
from app.services.audit import write_audit_log

DRAFT, PRODUCTION, RETIRED = "DRAFT", "PRODUCTION", "RETIRED"
REFERENCE_ONLY, REFERENCE_PLUS_ADAPTER = "REFERENCE_ONLY", "REFERENCE_PLUS_ADAPTER"
STRATEGIES = (REFERENCE_ONLY, REFERENCE_PLUS_ADAPTER)
# A pinned reference set must be one of these.
PINNABLE_SET_STATUSES = ("LOCKED", "PRODUCTION")
# Adapters a DRAFT profile may name; PRODUCTION is required at promotion.
USABLE_ADAPTER_STATUSES = ("EXPERIMENTAL", "EVALUATION", "PRODUCTION")
EE_F_002 = "EE-F-002"


class RuntimeProfileNotFound(Exception):
    """HTTP 404."""


class RuntimeProfileConflict(Exception):
    """Frozen profile, skipped lifecycle step, or an adapter not in PRODUCTION (HTTP 409)."""


class RuntimeProfileInvalid(Exception):
    """Well-formed request that breaks a rule (HTTP 400)."""


def profile_id(character_id: str, character_version: str, version: int) -> str:
    return f"{character_id}_V{character_version}_RT_V{version}"


async def _audit(db, action: str, profile: RuntimeProfile, actor: Optional[str], actor_user_id: Optional[int],
                 from_status: Optional[str], **extra: Any) -> None:
    await write_audit_log(db, action, user_id=actor_user_id, details={
        "actor_email": actor, "runtime_profile_id": profile.runtime_profile_id,
        "character_id": profile.character_id, "character_version": profile.character_version,
        "version": profile.version, "from_status": from_status, "to_status": profile.status, **extra,
    })


def _move(profile: RuntimeProfile, new_status: str) -> str:
    allowed = TRANSITIONS[profile.status]
    if new_status not in allowed:
        raise RuntimeProfileConflict(
            f"Runtime profile {profile.runtime_profile_id} is {profile.status} and cannot move to {new_status}. "
            f"Allowed next statuses: {', '.join(sorted(allowed)) or 'none (final)'}.")
    old, profile.status = profile.status, new_status
    return old


# ========================== Reads =================================

async def get_profile(db: AsyncSession, runtime_profile_id: str,
                      character_id: Optional[str] = None) -> RuntimeProfile:
    stmt = select(RuntimeProfile).where(RuntimeProfile.runtime_profile_id == runtime_profile_id)
    if character_id:
        stmt = stmt.where(RuntimeProfile.character_id == character_id)
    found = (await db.execute(stmt)).scalars().first()
    if not found:
        raise RuntimeProfileNotFound(f"Runtime profile {runtime_profile_id} not found.")
    return found


async def list_profiles(db: AsyncSession, character_id: str, character_version: Optional[str] = None,
                        status: Optional[str] = None) -> list[RuntimeProfile]:
    stmt = select(RuntimeProfile).where(RuntimeProfile.character_id == character_id).order_by(
        RuntimeProfile.character_version, RuntimeProfile.version)
    if character_version:
        stmt = stmt.where(RuntimeProfile.character_version == character_version)
    if status:
        stmt = stmt.where(RuntimeProfile.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def production_profile(db: AsyncSession, character_id: str, character_version: str) -> RuntimeProfile:
    """The PRODUCTION profile of a character version (the resolver read, AC-5)."""
    found = (await db.execute(select(RuntimeProfile).where(
        RuntimeProfile.character_id == character_id, RuntimeProfile.character_version == character_version,
        RuntimeProfile.status == PRODUCTION))).scalars().first()
    if found is None:
        raise RuntimeProfileNotFound(f"{character_id} version {character_version} has no production runtime profile.")
    return found


async def reference_set_of(db: AsyncSession, profile: RuntimeProfile) -> Optional[CharacterReferenceSet]:
    if profile.reference_set_id is None:
        return None
    return await db.get(CharacterReferenceSet, profile.reference_set_id)


# ========================== Rules =================================

def _check_strategies(default_strategy: str, allowed: list[str]) -> list[str]:
    if not allowed:
        raise RuntimeProfileInvalid("allowed_strategies needs at least one strategy.")
    unknown = [s for s in allowed if s not in STRATEGIES]
    if unknown or default_strategy not in STRATEGIES:
        raise RuntimeProfileInvalid(f"Strategies must be among {', '.join(STRATEGIES)}.")
    if len(set(allowed)) != len(allowed):
        raise RuntimeProfileInvalid("allowed_strategies lists a strategy twice.")
    if default_strategy not in allowed:
        raise RuntimeProfileInvalid(f"default_strategy {default_strategy} must be in allowed_strategies.")
    return [s for s in STRATEGIES if s in allowed]


def _check_adapter_fields(allowed: list[str], adapter_id: Optional[str], strength: Optional[float],
                          fallback: Optional[float], retry: bool) -> None:
    if REFERENCE_PLUS_ADAPTER not in allowed:
        if adapter_id or strength is not None or fallback is not None or retry:
            raise RuntimeProfileInvalid("adapter_id, adapter_strength, fallback_adapter_strength and "
                                        "fallback_retry_enabled need REFERENCE_PLUS_ADAPTER in allowed_strategies.")
        return
    if not adapter_id or strength is None or fallback is None:
        raise RuntimeProfileInvalid("REFERENCE_PLUS_ADAPTER needs adapter_id, adapter_strength and "
                                    "fallback_adapter_strength; there is no default strength.")
    if not 0 < strength <= 1:
        raise RuntimeProfileInvalid("adapter_strength must be greater than 0 and at most 1.")
    if not strength < fallback <= 1:
        raise RuntimeProfileInvalid("fallback_adapter_strength must be greater than adapter_strength and at most 1.")


async def _adapter(db: AsyncSession, adapter_id: str, character_id: str, character_version: str) -> ModelArtifact:
    adapter = (await db.execute(select(ModelArtifact).where(ModelArtifact.model_id == adapter_id))).scalars().first()
    if adapter is None or adapter.layer is None:
        raise RuntimeProfileNotFound(f"Adapter {adapter_id} not found.")
    if (adapter.character_id, adapter.character_version) != (character_id, character_version):
        raise RuntimeProfileInvalid(f"Adapter {adapter_id} belongs to {adapter.character_id} version "
                                    f"{adapter.character_version}, not {character_id} version {character_version}.")
    return adapter


async def _reference_set(db: AsyncSession, reference_set_id: str, character_id: str,
                         character_version: str) -> CharacterReferenceSet:
    try:
        ref = await reference_set_service.get_set(db, reference_set_id, character_id)
    except reference_set_service.ReferenceSetNotFound as exc:
        raise RuntimeProfileNotFound(str(exc))
    if ref.character_version != character_version:
        raise RuntimeProfileInvalid(f"Reference set {reference_set_id} is for {character_id} version "
                                    f"{ref.character_version}, not {character_version}.")
    if ref.status not in PINNABLE_SET_STATUSES:
        raise RuntimeProfileInvalid(f"Reference set {reference_set_id} is {ref.status}; a runtime profile can pin "
                                    "only a LOCKED or PRODUCTION set.")
    return ref


# ========================== Writes ================================

async def create_profile(db: AsyncSession, *, character_id: str, character_version: str,
                         default_strategy: str = REFERENCE_ONLY, allowed_strategies: Optional[list[str]] = None,
                         reference_set_id: Optional[str] = None, adapter_id: Optional[str] = None,
                         adapter_strength: Optional[float] = None, fallback_adapter_strength: Optional[float] = None,
                         qa_profile_id: Optional[str] = None, fallback_retry_enabled: bool = False,
                         notes: Optional[str] = None, created_by: Optional[str] = None,
                         actor_user_id: Optional[int] = None, audit_action: str = "runtime_profile_created",
                         ) -> RuntimeProfile:
    """A DRAFT profile with the next version number for the character version."""
    try:
        await version_service.get_version(db, character_id, character_version)
    except version_service.CharacterVersionNotFound as exc:
        raise RuntimeProfileNotFound(str(exc))
    allowed = _check_strategies(default_strategy, list(
        [default_strategy] if allowed_strategies is None else allowed_strategies))
    _check_adapter_fields(allowed, adapter_id, adapter_strength, fallback_adapter_strength, fallback_retry_enabled)
    if adapter_id:
        adapter = await _adapter(db, adapter_id, character_id, character_version)
        if adapter.status not in USABLE_ADAPTER_STATUSES:
            raise RuntimeProfileInvalid(f"Adapter {adapter_id} is {adapter.status} and cannot be used.")
    ref = await _reference_set(db, reference_set_id, character_id, character_version) if reference_set_id else None
    if qa_profile_id and (await db.execute(select(QAProfile.id).where(
            QAProfile.qa_profile_id == qa_profile_id))).first() is None:
        raise RuntimeProfileNotFound(f"QA profile {qa_profile_id} not found.")

    latest = (await db.execute(select(func.max(RuntimeProfile.version)).where(
        RuntimeProfile.character_id == character_id,
        RuntimeProfile.character_version == character_version))).scalar() or 0
    profile = RuntimeProfile(
        runtime_profile_id=profile_id(character_id, character_version, latest + 1), character_id=character_id,
        character_version=character_version, version=latest + 1, status=DRAFT, default_strategy=default_strategy,
        allowed_strategies=allowed, reference_set_id=ref.id if ref else None, adapter_id=adapter_id,
        adapter_strength=adapter_strength, fallback_adapter_strength=fallback_adapter_strength,
        qa_profile_id=qa_profile_id, fallback_retry_enabled=fallback_retry_enabled, notes=notes,
        created_by=created_by)
    db.add(profile)
    await db.flush()
    await _audit(db, audit_action, profile, created_by, actor_user_id, None,
                 default_strategy=default_strategy, allowed_strategies=allowed,
                 reference_set_id=ref.reference_set_id if ref else None, adapter_id=adapter_id,
                 adapter_strength=adapter_strength, fallback_adapter_strength=fallback_adapter_strength,
                 qa_profile_id=qa_profile_id, fallback_retry_enabled=fallback_retry_enabled)
    await db.commit()
    await db.refresh(profile)
    return profile


async def promote(db: AsyncSession, profile: RuntimeProfile, promoted_by: str,
                  actor_user_id: Optional[int] = None) -> tuple[RuntimeProfile, Optional[RuntimeProfile]]:
    """DRAFT -> PRODUCTION; retires the previous PRODUCTION profile of the character version. Needs a LOCKED
    character version, a pinned set that is still LOCKED / PRODUCTION with matching hashes, and, when
    REFERENCE_PLUS_ADAPTER is allowed, a PRODUCTION adapter with a checksum."""
    if profile.status != DRAFT:
        raise RuntimeProfileConflict(f"Runtime profile {profile.runtime_profile_id} is {profile.status}; only DRAFT "
                                     "profiles can be promoted.")
    version = await version_service.get_version(db, profile.character_id, profile.character_version)
    if not version_service.is_locked(version):
        raise RuntimeProfileConflict(f"{profile.character_id} version {profile.character_version} is not LOCKED; "
                                     "lock the character version first.")
    ref = await reference_set_of(db, profile)
    if ref is not None:
        if ref.status not in PINNABLE_SET_STATUSES:
            raise RuntimeProfileConflict(f"Pinned reference set {ref.reference_set_id} is {ref.status}.")
        try:
            await reference_set_service.check_integrity(db, ref)
        except reference_set_service.ReferenceSetIntegrityError as exc:
            raise RuntimeProfileConflict(str(exc))
    if REFERENCE_PLUS_ADAPTER in (profile.allowed_strategies or []):
        adapter = await _adapter(db, profile.adapter_id, profile.character_id, profile.character_version)
        if adapter.status != PRODUCTION or not adapter.checksum_sha256:
            raise RuntimeProfileConflict(
                f"Adapter {adapter.model_id} is {adapter.status}{'' if adapter.checksum_sha256 else ' without a checksum'}"
                "; REFERENCE_PLUS_ADAPTER needs a PRODUCTION adapter with a checksum.")
    now = datetime.utcnow()
    replaced = (await db.execute(select(RuntimeProfile).where(
        RuntimeProfile.character_id == profile.character_id,
        RuntimeProfile.character_version == profile.character_version,
        RuntimeProfile.status == PRODUCTION))).scalars().first()
    if replaced is not None:
        old = _move(replaced, RETIRED)
        replaced.retired_at, replaced.retired_by = now, promoted_by
        replaced.retire_reason = f"Replaced by {profile.runtime_profile_id}."
        await _audit(db, "runtime_profile_retired", replaced, promoted_by, actor_user_id, old,
                     reason=replaced.retire_reason)
        await db.flush()  # free the one-PRODUCTION slot first
    old = _move(profile, PRODUCTION)
    profile.promoted_at, profile.promoted_by = now, promoted_by
    await _audit(db, "runtime_profile_promoted", profile, promoted_by, actor_user_id, old,
                 replaced=replaced.runtime_profile_id if replaced else None)
    await db.commit()
    await db.refresh(profile)
    return profile, replaced


async def retire(db: AsyncSession, profile: RuntimeProfile, retired_by: str, reason: str,
                 actor_user_id: Optional[int] = None) -> RuntimeProfile:
    if not (reason or "").strip():
        raise RuntimeProfileInvalid("A reason is required to retire a runtime profile.")
    old = _move(profile, RETIRED)
    profile.retired_at, profile.retired_by, profile.retire_reason = datetime.utcnow(), retired_by, reason.strip()
    await _audit(db, "runtime_profile_retired", profile, retired_by, actor_user_id, old, reason=profile.retire_reason)
    await db.commit()
    await db.refresh(profile)
    return profile


# ========================== EE-F-002 V1 seed =====================

async def seed_ee_f_002_runtime_profile(db: AsyncSession, seeded_by: str,
                                        actor_user_id: Optional[int] = None) -> tuple[RuntimeProfile, bool]:
    """Create EE-F-002_V1.0_RT_V1 as DRAFT: REFERENCE_ONLY only, no adapter, no strengths, no pinned set,
    retry off. Idempotent: an existing V1 profile is returned unchanged (created=False). Never promotes."""
    existing = (await db.execute(select(RuntimeProfile).where(
        RuntimeProfile.runtime_profile_id == profile_id(EE_F_002, "1.0", 1)))).scalars().first()
    if existing is not None:
        return existing, False
    profile = await create_profile(db, character_id=EE_F_002, character_version="1.0",
                                   default_strategy=REFERENCE_ONLY, allowed_strategies=[REFERENCE_ONLY],
                                   created_by=seeded_by, actor_user_id=actor_user_id,
                                   audit_action="runtime_profile_seeded")
    return profile, True
