"""
Capability validations: per-character validation and promotion records.

The definition tables (appearance options, capability packs, poses, presets)
say what a capability *is*. A ``capability_validations`` row says whether it
is validated and promoted *for one character version*
(docs/character-runtime/DESIGN.md sections 3.1 and 8, PR 1). The Option API
will return only PROMOTED records; until the customer routes switch over
(PR 3), they keep reading the definition tables and nothing customers see
changes.

Lifecycle: REGISTERED -> VALIDATING -> VALIDATED -> PROMOTED -> RETIRED, with
REJECTED when a check fails (back to VALIDATING for rework). Promotion is only
from VALIDATED and retires the previously promoted version of the same
capability. Who validated and who promoted are recorded separately; whether
they must be different people is still an open question (DESIGN.md 7.7), so
it is not enforced.

``backfill_promoted`` writes one PROMOTED record for everything customers can
use today. It only inserts what is missing and never changes an existing
record, so it is safe to run again. Alembic ``capability_validations_001``
holds a frozen copy of the same rules.

Every write (register, start validation, record validation, promote, retire)
adds an ``audit_logs`` entry in the same transaction: who (user id + email),
what (action + capability), from/to status, and when (``created_at``).
"""
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import (
    CAPABILITY_TRANSITIONS as TRANSITIONS,
    AppearanceOption,
    CapabilityPack,
    CapabilityProductType,
    CapabilityValidation,
    CharacterRegistryVersion,
    Preset,
)
from app.services import character_versions as version_service
from app.services import pose_resolver as pose_service
from app.services.audit import write_audit_log

REGISTERED = "REGISTERED"
VALIDATING = "VALIDATING"
VALIDATED = "VALIDATED"
PROMOTED = "PROMOTED"
REJECTED = "REJECTED"
RETIRED = "RETIRED"
STATUSES = tuple(TRANSITIONS)

CAPABILITY_TYPES = (
    "HAIR", "MAKEUP", "EXPRESSION", "JEWELRY", "BEAUTY_DIRECTION", "POSE", "CAMERA", "SCENE", "LIGHTING",
    "CAMPAIGN", "PRODUCT_TYPE",
)
VALIDATION_CHECKS = ("identity", "face", "body", "product")
CUSTOMER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")

BACKFILL_ACTOR = "SYSTEM_BACKFILL"
# Appearance category -> (capability type, customer id prefix). NAILS has no
# capability type (DESIGN.md open question 12) and is not backfilled.
APPEARANCE_TYPES = {
    "HAIR_STYLE": ("HAIR", "hair_"),
    "MAKEUP_STYLE": ("MAKEUP", "makeup_"),
    "EXPRESSION": ("EXPRESSION", "expr_"),
    "JEWELRY": ("JEWELRY", "jewelry_"),
    "BEAUTY_DIRECTION": ("BEAUTY_DIRECTION", "beauty_"),
}
# Preset type -> (capability type, customer id prefix).
PRESET_TYPES = {
    "LOCATION": ("SCENE", "scene_"),
    "LIGHTING": ("LIGHTING", "lighting_"),
    "CAMPAIGN": ("CAMPAIGN", "campaign_"),
}


class CapabilityNotFound(Exception):
    """HTTP 404."""


class CapabilityConflict(Exception):
    """Duplicate record, customer id in use, or a skipped lifecycle step (HTTP 409)."""


class CapabilityInvalid(Exception):
    """Well-formed request that breaks a business rule (HTTP 400)."""


async def _first(db: AsyncSession, stmt):
    return (await db.execute(stmt)).scalars().first()


def _label(record: CapabilityValidation) -> str:
    return f"{record.capability_type} {record.capability_key} v{record.capability_version}"


def _move(record: CapabilityValidation, new_status: str) -> None:
    allowed = TRANSITIONS[record.status]
    if new_status not in allowed:
        next_steps = ", ".join(sorted(allowed)) or "none (final)"
        raise CapabilityConflict(f"{_label(record)} is {record.status} and cannot move to {new_status}. "
                                 f"Allowed next statuses: {next_steps}.")
    record.status = new_status


async def _audit(db: AsyncSession, action: str, record: CapabilityValidation, actor: Optional[str],
                 actor_user_id: Optional[int], from_status: Optional[str], **extra: Any) -> None:
    """One audit_logs entry, flushed with the change it describes (the caller commits)."""
    await write_audit_log(db, action, user_id=actor_user_id, details={
        "actor_email": actor,
        "character_id": record.character_id,
        "character_version": record.character_version,
        "capability_type": record.capability_type,
        "capability_key": record.capability_key,
        "capability_version": record.capability_version,
        "customer_id": record.customer_id,
        "from_status": from_status,
        "to_status": record.status,
        **extra,
    })


# ========================== Reads =================================

async def get_record(db: AsyncSession, character_id: str, character_version: str, capability_type: str,
                     capability_key: str, capability_version: int) -> CapabilityValidation:
    found = await _first(db, select(CapabilityValidation).where(
        CapabilityValidation.character_id == character_id,
        CapabilityValidation.character_version == character_version,
        CapabilityValidation.capability_type == capability_type,
        CapabilityValidation.capability_key == capability_key,
        CapabilityValidation.capability_version == capability_version,
    ))
    if not found:
        raise CapabilityNotFound(
            f"{capability_type} {capability_key} v{capability_version} is not registered for "
            f"{character_id} version {character_version}.")
    return found


async def list_records(db: AsyncSession, character_id: Optional[str] = None, character_version: Optional[str] = None,
                       capability_type: Optional[str] = None, status: Optional[str] = None) -> list[CapabilityValidation]:
    stmt = select(CapabilityValidation).order_by(
        CapabilityValidation.character_id, CapabilityValidation.character_version,
        CapabilityValidation.capability_type, CapabilityValidation.sort_order,
        CapabilityValidation.capability_key, CapabilityValidation.capability_version,
    )
    for column, value in ((CapabilityValidation.character_id, character_id),
                          (CapabilityValidation.character_version, character_version),
                          (CapabilityValidation.capability_type, capability_type),
                          (CapabilityValidation.status, status)):
        if value:
            stmt = stmt.where(column == value)
    return list((await db.execute(stmt)).scalars().all())


async def promoted(db: AsyncSession, character_id: str, character_version: str,
                   capability_type: Optional[str] = None) -> list[CapabilityValidation]:
    """The PROMOTED records of a character version: what customers may use."""
    return await list_records(db, character_id, character_version, capability_type, PROMOTED)


async def _customer_id_holder(db: AsyncSession, record: CapabilityValidation) -> Optional[CapabilityValidation]:
    """A live record of a *different* capability that already uses the customer id."""
    rows = await db.execute(select(CapabilityValidation).where(
        CapabilityValidation.character_id == record.character_id,
        CapabilityValidation.character_version == record.character_version,
        CapabilityValidation.customer_id == record.customer_id,
        CapabilityValidation.status.notin_((RETIRED, REJECTED)),
    ))
    for other in rows.scalars().all():
        if (other.capability_type, other.capability_key) != (record.capability_type, record.capability_key):
            return other
    return None


# ========================== Writes ================================

async def register(db: AsyncSession, *, character_id: str, character_version: str, capability_type: str,
                   capability_key: str, capability_version: int, customer_id: str, group: Optional[str] = None,
                   sort_order: int = 0, registered_by: Optional[str] = None,
                   actor_user_id: Optional[int] = None) -> CapabilityValidation:
    try:
        await version_service.get_version(db, character_id, character_version)
    except version_service.CharacterVersionNotFound as exc:
        raise CapabilityNotFound(str(exc))
    if capability_type not in CAPABILITY_TYPES:
        raise CapabilityInvalid(f"capability_type must be one of {', '.join(CAPABILITY_TYPES)}.")
    if not KEY_PATTERN.match(capability_key or ""):
        raise CapabilityInvalid("capability_key must be letters, digits, '_' or '-' (at most 80).")
    if not isinstance(capability_version, int) or capability_version < 1:
        raise CapabilityInvalid("capability_version must be a positive integer.")
    if not CUSTOMER_ID_PATTERN.match(customer_id or ""):
        raise CapabilityInvalid("customer_id must be lowercase letters, digits, '_' or '-' (at most 80).")

    try:
        await get_record(db, character_id, character_version, capability_type, capability_key, capability_version)
    except CapabilityNotFound:
        pass
    else:
        raise CapabilityConflict(f"{capability_type} {capability_key} v{capability_version} is already registered "
                                 f"for {character_id} version {character_version}.")
    record = CapabilityValidation(
        character_id=character_id, character_version=character_version, capability_type=capability_type,
        capability_key=capability_key, capability_version=capability_version, customer_id=customer_id,
        status=REGISTERED, group=group, sort_order=sort_order, is_default=False, recommended=False,
    )
    holder = await _customer_id_holder(db, record)
    if holder:
        raise CapabilityConflict(f"customer_id {customer_id} is already used by {holder.capability_type} "
                                 f"{holder.capability_key}.")
    db.add(record)
    await db.flush()
    await _audit(db, "capability_registered", record, registered_by, actor_user_id, None)
    await db.commit()
    await db.refresh(record)
    return record


async def start_validation(db: AsyncSession, record: CapabilityValidation, started_by: Optional[str] = None,
                           actor_user_id: Optional[int] = None) -> CapabilityValidation:
    from_status = record.status
    _move(record, VALIDATING)
    await _audit(db, "capability_validation_started", record, started_by, actor_user_id, from_status)
    await db.commit()
    await db.refresh(record)
    return record


async def record_validation(db: AsyncSession, record: CapabilityValidation, checks: dict[str, str],
                            evidence: Optional[dict[str, Any]], validated_by: str,
                            actor_user_id: Optional[int] = None) -> CapabilityValidation:
    """VALIDATED when every check is PASS, REJECTED otherwise."""
    if set(checks) != set(VALIDATION_CHECKS) or any(v not in ("PASS", "FAIL") for v in checks.values()):
        raise CapabilityInvalid(f"checks must give PASS or FAIL for each of {', '.join(VALIDATION_CHECKS)}.")
    if record.status not in (REGISTERED, VALIDATING):
        raise CapabilityConflict(f"{_label(record)} is {record.status}; validation results can be recorded only "
                                 f"for REGISTERED or VALIDATING records (start validation again first).")
    passed = all(v == "PASS" for v in checks.values())
    from_status = record.status
    _move(record, VALIDATED if passed else REJECTED)
    record.validation = {"checks": dict(checks), "evidence": evidence or {}}
    record.validated_by = validated_by
    record.validated_at = datetime.utcnow()
    await _audit(db, "capability_validated" if passed else "capability_rejected", record, validated_by,
                 actor_user_id, from_status, checks=dict(checks))
    await db.commit()
    await db.refresh(record)
    return record


async def promote(db: AsyncSession, record: CapabilityValidation, promoted_by: str, *, is_default: bool = False,
                  recommended: bool = False,
                  actor_user_id: Optional[int] = None) -> tuple[CapabilityValidation, Optional[CapabilityValidation]]:
    """Promote a VALIDATED record. Retires the previously promoted version of the
    same capability and, for a default, clears the old default of the type.
    Returns (record, replaced record or None). The promoter may be the validator
    (four-eyes rule pending, DESIGN.md 7.7)."""
    if record.status != VALIDATED:
        raise CapabilityConflict(f"{_label(record)} is {record.status}; only VALIDATED records can be promoted.")
    holder = await _customer_id_holder(db, record)
    if holder:
        raise CapabilityConflict(f"customer_id {record.customer_id} is already used by {holder.capability_type} "
                                 f"{holder.capability_key}.")
    now = datetime.utcnow()
    live = await promoted(db, record.character_id, record.character_version, record.capability_type)
    replaced = next((r for r in live if r.capability_key == record.capability_key), None)
    if replaced:
        _move(replaced, RETIRED)
        replaced.retired_by, replaced.retired_at = promoted_by, now
        replaced.retire_reason = f"Replaced by version {record.capability_version}."
        replaced.is_default = False
        await _audit(db, "capability_retired", replaced, promoted_by, actor_user_id, PROMOTED,
                     reason=replaced.retire_reason, replaced_by_version=record.capability_version)
    if is_default:
        for other in live:
            if other.is_default:
                other.is_default = False
    await db.flush()  # free the one-PROMOTED-per-capability slot before taking it
    _move(record, PROMOTED)
    record.promoted_by, record.promoted_at = promoted_by, now
    record.is_default, record.recommended = is_default, recommended
    await _audit(db, "capability_promoted", record, promoted_by, actor_user_id, VALIDATED,
                 is_default=is_default, recommended=recommended,
                 replaced_version=replaced.capability_version if replaced else None)
    await db.commit()
    await db.refresh(record)
    return record, replaced


async def retire(db: AsyncSession, record: CapabilityValidation, retired_by: str, reason: str,
                 actor_user_id: Optional[int] = None) -> CapabilityValidation:
    if not (reason or "").strip():
        raise CapabilityInvalid("A reason is required to retire a capability.")
    from_status = record.status
    _move(record, RETIRED)
    record.retired_by, record.retired_at, record.retire_reason = retired_by, datetime.utcnow(), reason.strip()
    record.is_default = False
    await _audit(db, "capability_retired", record, retired_by, actor_user_id, from_status, reason=record.retire_reason)
    await db.commit()
    await db.refresh(record)
    return record


# ========================== Backfill ==============================

def _item(character_id, character_version, capability_type, key, version, customer_id, *, is_default, sort_order,
          source, source_key) -> dict:
    return {
        "character_id": character_id, "character_version": character_version, "capability_type": capability_type,
        "capability_key": key, "capability_version": version, "customer_id": customer_id,
        "is_default": bool(is_default), "sort_order": sort_order or 0,
        "validation": {"backfill": {"source": source, "source_key": source_key, "source_status": "PRODUCTION"}},
    }


async def _current_versions(db: AsyncSession) -> list[tuple[str, str]]:
    """(character_id, current locked version) of every character that has one."""
    ids = sorted(set((await db.execute(select(CharacterRegistryVersion.character_id))).scalars().all()))
    current = []
    for character_id in ids:
        try:
            current.append((character_id, (await version_service.get_current_locked_version(db, character_id)).version))
        except version_service.CharacterVersionNotFound:
            continue
    return current


async def backfill_plan(db: AsyncSession) -> list[dict]:
    """A PROMOTED record for everything customers can use today:

    * appearance options in PRODUCTION (not NAILS), per their own character version;
    * customer product types whose capability pack is in PRODUCTION;
    * for each character's current locked version, the poses offered for any
      product type (``pose_resolver.customer_poses``) and every PRODUCTION
      location, lighting and campaign preset.
    """
    plan: list[dict] = []
    options = (await db.execute(select(AppearanceOption).where(AppearanceOption.status == "PRODUCTION")
                                .order_by(AppearanceOption.id))).scalars().all()
    for o in options:
        if o.category not in APPEARANCE_TYPES:
            continue
        capability_type, prefix = APPEARANCE_TYPES[o.category]
        plan.append(_item(o.character_id, o.character_version, capability_type, o.option_id, o.version,
                          prefix + o.option_id.lower(), is_default=o.is_default, sort_order=o.sort_order,
                          source="appearance_options", source_key=o.internal_key))

    product_types = (await db.execute(select(CapabilityProductType).order_by(CapabilityProductType.id))).scalars().all()
    packs = (await db.execute(select(CapabilityPack).where(CapabilityPack.status == "PRODUCTION")
                              .order_by(CapabilityPack.id))).scalars().all()
    for pack in packs:
        for pt in product_types:
            if pt.pack_type == pack.pack_type:
                plan.append(_item(pack.character_id, pack.character_version, "PRODUCT_TYPE", pt.product_type,
                                  pack.version, pt.product_type, is_default=pt.is_default, sort_order=pt.sort_order,
                                  source="capability_packs", source_key=pack.internal_key))

    presets = (await db.execute(select(Preset).where(Preset.status == "PRODUCTION").order_by(Preset.id))).scalars().all()
    for character_id, character_version in await _current_versions(db):
        seen = set()
        for pt in product_types:
            for pose, _ in await pose_service.customer_poses(db, character_id, pt.product_type):
                if pose.pose_id in seen:
                    continue
                seen.add(pose.pose_id)
                plan.append(_item(character_id, character_version, "POSE", pose.pose_id, 1, "pose_" + pose.pose_id,
                                  is_default=False, sort_order=pose.sort_order,
                                  source="pose_definitions", source_key=pose.pose_id))
        for p in presets:
            if p.preset_type not in PRESET_TYPES:
                continue
            capability_type, prefix = PRESET_TYPES[p.preset_type]
            plan.append(_item(character_id, character_version, capability_type, p.preset_key, 1,
                              prefix + p.preset_key.lower(), is_default=p.is_default, sort_order=p.sort_order,
                              source="presets", source_key=f"{p.preset_type}:{p.preset_key}"))
    return plan


async def backfill_promoted(db: AsyncSession) -> list[CapabilityValidation]:
    """Insert the missing records of ``backfill_plan`` as PROMOTED. Never changes
    an existing record; skips an item whose capability already has a PROMOTED
    version or whose customer id is promoted for another capability."""
    existing = (await db.execute(select(CapabilityValidation))).scalars().all()
    versions = {(r.character_id, r.character_version, r.capability_type, r.capability_key, r.capability_version)
                for r in existing}
    live = {(r.character_id, r.character_version, r.capability_type, r.capability_key)
            for r in existing if r.status == PROMOTED}
    live_ids = {(r.character_id, r.character_version, r.customer_id) for r in existing if r.status == PROMOTED}
    now = datetime.utcnow()
    created = []
    for item in await backfill_plan(db):
        version_key = (item["character_id"], item["character_version"], item["capability_type"],
                       item["capability_key"], item["capability_version"])
        key = version_key[:4]
        customer = (item["character_id"], item["character_version"], item["customer_id"])
        if version_key in versions or key in live or customer in live_ids:
            continue
        versions.add(version_key)
        live.add(key)
        live_ids.add(customer)
        record = CapabilityValidation(
            **item, status=PROMOTED, recommended=False, validated_by=BACKFILL_ACTOR, validated_at=now,
            promoted_by=BACKFILL_ACTOR, promoted_at=now,
        )
        db.add(record)
        created.append(record)
    await db.commit()
    return created
