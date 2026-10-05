"""
Capability Packs service.

Character Core = who the character is (a LOCKED Character Version).
Capability     = what she can wear, carry or do: packs layered on top.

There is only one EE-F-002. Footwear, bags, motion, ... are capability packs
on top of her, never new characters, and a pack never modifies the Character
Version it belongs to.

Lifecycle (shared with appearance options):
IN_DEVELOPMENT -> VALIDATION -> APPROVED -> PRODUCTION -> ARCHIVED.
At most one PRODUCTION version per character + pack type; promoting a new
version archives the previous one. Customers only ever see PRODUCTION packs
of the current locked version, mapped to customer product types (shoes,
bags, ...) by the ``capability_product_types`` table.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import (
    AppearanceOption,
    CapabilityPack,
    CapabilityPackAdapter,
    CapabilityProductType,
    ModelArtifact,
    PoseDefinition,
)
from app.services import character_versions as version_service
from app.services.appearance_options import (
    APPROVED,
    ARCHIVED,
    IN_DEVELOPMENT,
    PRODUCTION,
    TRANSITIONS,
)

PACK_TYPES = (
    "BEAUTY_STYLING", "GARMENT", "FOOTWEAR", "BAGS", "EYEWEAR", "JEWELRY", "HEADWEAR", "MOTION",
    "CAMPAIGN_LOCATION",
)

# Seed for capability_product_types (the table is the source of truth).
# MOTION, BEAUTY_STYLING and CAMPAIGN_LOCATION have no customer product type.
DEFAULT_PRODUCT_TYPES = (
    {"product_type": "garment", "pack_type": "GARMENT", "label": "Garment", "sort_order": 10},
    {"product_type": "shoes", "pack_type": "FOOTWEAR", "label": "Footwear", "sort_order": 20},
    {"product_type": "bags", "pack_type": "BAGS", "label": "Bags", "sort_order": 30},
    {"product_type": "eyewear", "pack_type": "EYEWEAR", "label": "Eyewear", "sort_order": 40},
    {"product_type": "headwear", "pack_type": "HEADWEAR", "label": "Headwear", "sort_order": 50},
    {"product_type": "jewelry", "pack_type": "JEWELRY", "label": "Jewelry", "sort_order": 60},
)

# Seed for the framing rules on capability_product_types (moved out of
# services/compatibility.py), by pack type.
DEFAULT_FRAMING_RULES = {
    "FOOTWEAR": (["FULL_BODY", "DETAIL"], "FOOTWEAR_REQUIRES_VISIBLE_FEET"),
    "EYEWEAR": (["CLOSE_UP", "BUST", "UPPER_BODY", "PORTRAIT"], "EYEWEAR_REQUIRES_FACE_VISIBILITY"),
    "JEWELRY": (["CLOSE_UP", "BUST", "DETAIL", "UPPER_BODY"], "JEWELRY_REQUIRES_CLOSE_FRAMING"),
}

VALIDATION_CHECKS = ("identity", "face", "body", "product")
EDITABLE_FIELDS = (
    "label", "description", "thumbnail_url", "sort_order", "workflow_route", "workflow_version",
    "required_reference_assets", "supported_product_types", "compatible_appearance_options", "compatible_poses",
    "qa_rules",
)
FROZEN = (PRODUCTION, ARCHIVED)


class CapabilityNotFound(Exception):
    """HTTP 404."""


class CapabilityConflict(Exception):
    """Invalid transition, duplicate, or edit of a frozen pack (HTTP 409)."""


class CapabilityInvalid(Exception):
    """Well-formed request that breaks a business rule (HTTP 400)."""


@dataclass(frozen=True)
class ResolvedAdapter:
    adapter_id: str
    layer: Optional[str]
    kind: Optional[str]
    storage_path: Optional[str]
    checkpoint_id: Optional[str]
    reference: Optional[dict]


@dataclass(frozen=True)
class ResolvedCapabilityPack:
    """The live pack and its technical details, for the Pose Resolver and
    Runtime Dispatch. Never returned to customers."""
    internal_key: str
    character_id: str
    character_version: str
    pack_type: str
    version: int
    workflow_route: Optional[str]
    workflow_version: Optional[str]
    required_reference_assets: list = field(default_factory=list)
    supported_product_types: list = field(default_factory=list)
    compatible_appearance_options: list = field(default_factory=list)
    compatible_poses: list = field(default_factory=list)
    qa_rules: dict = field(default_factory=dict)
    validation: dict = field(default_factory=dict)
    adapters: tuple[ResolvedAdapter, ...] = ()


def internal_key(character_id: str, pack_type: str, version: int) -> str:
    """e.g. EE-F-002_FOOTWEAR_V1"""
    return f"{character_id}_{pack_type}_V{version}"


async def _first(db: AsyncSession, stmt):
    return (await db.execute(stmt)).scalars().first()


def _frozen_error(pack: CapabilityPack) -> CapabilityConflict:
    return CapabilityConflict(
        f"Capability pack {pack.internal_key} is {pack.status} and cannot be changed. Create a new version instead."
    )


async def _check_adapter(db: AsyncSession, adapter_id: str, pack: CapabilityPack) -> None:
    adapter = await _first(db, select(ModelArtifact).where(ModelArtifact.model_id == adapter_id))
    # Plain P3 model artifacts (no layer) are not adapters.
    if not adapter or adapter.layer is None:
        raise CapabilityNotFound(f"Adapter {adapter_id} not found.")
    if (adapter.character_id, adapter.character_version) != (pack.character_id, pack.character_version):
        raise CapabilityInvalid(
            f"Adapter {adapter_id} belongs to {adapter.character_id} version {adapter.character_version}."
        )


async def _check_compatibility(db: AsyncSession, character_id: str, fields: dict) -> None:
    product_types = fields.get("supported_product_types")
    if product_types:
        known = {row.product_type for row in await list_product_types(db)}
        unknown = sorted(set(product_types) - known)
        if unknown:
            raise CapabilityInvalid(f"Unknown product types {unknown}. Known: {sorted(known)}.")
    option_keys = fields.get("compatible_appearance_options")
    if option_keys:
        found = (await db.execute(select(AppearanceOption.internal_key).where(
            AppearanceOption.internal_key.in_(option_keys),
            AppearanceOption.character_id == character_id,
        ))).scalars().all()
        missing = sorted(set(option_keys) - set(found))
        if missing:
            raise CapabilityInvalid(f"Appearance options {missing} not found for {character_id}.")
    pose_ids = fields.get("compatible_poses")
    if pose_ids:
        found = (await db.execute(select(PoseDefinition.pose_id).where(
            PoseDefinition.pose_id.in_(pose_ids)))).scalars().all()
        missing = sorted(set(pose_ids) - set(found))
        if missing:
            raise CapabilityInvalid(f"Poses {missing} not found.")


def _validation_passed(pack: CapabilityPack) -> bool:
    results = pack.validation or {}
    return all(results.get(check) == "PASS" for check in VALIDATION_CHECKS)


# ========================== Reads =================================

async def list_product_types(db: AsyncSession) -> list[CapabilityProductType]:
    stmt = select(CapabilityProductType).order_by(CapabilityProductType.sort_order, CapabilityProductType.product_type)
    return list((await db.execute(stmt)).scalars().all())


async def pack_type_for(db: AsyncSession, product_type: str) -> Optional[str]:
    """Customer product type (``shoes``) -> pack type (``FOOTWEAR``).

    A pack type itself is accepted too, so packs without a customer product
    type (MOTION, CAMPAIGN_LOCATION, BEAUTY_STYLING) can be resolved.
    """
    row = await _first(db, select(CapabilityProductType).where(CapabilityProductType.product_type == product_type))
    if row:
        return row.pack_type
    return product_type.upper() if product_type.upper() in PACK_TYPES else None


async def get_pack(db: AsyncSession, key: str) -> CapabilityPack:
    found = await _first(db, select(CapabilityPack).where(CapabilityPack.internal_key == key))
    if not found:
        raise CapabilityNotFound(f"Capability pack {key} not found.")
    return found


async def list_packs(db: AsyncSession, character_id: Optional[str] = None, pack_type: Optional[str] = None,
                     status: Optional[str] = None) -> list[CapabilityPack]:
    stmt = select(CapabilityPack).order_by(
        CapabilityPack.character_id, CapabilityPack.pack_type, CapabilityPack.version,
    )
    for column, value in ((CapabilityPack.character_id, character_id), (CapabilityPack.pack_type, pack_type),
                          (CapabilityPack.status, status)):
        if value:
            stmt = stmt.where(column == value)
    return list((await db.execute(stmt)).scalars().all())


async def list_pack_adapters(db: AsyncSession, packs: list[CapabilityPack]) -> dict[int, list[CapabilityPackAdapter]]:
    """Adapter links of the given packs, by pack id."""
    links: dict[int, list[CapabilityPackAdapter]] = {pack.id: [] for pack in packs}
    if links:
        rows = await db.execute(select(CapabilityPackAdapter).where(
            CapabilityPackAdapter.pack_id.in_(links)).order_by(CapabilityPackAdapter.id))
        for link in rows.scalars().all():
            links[link.pack_id].append(link)
    return links


async def customer_capabilities(db: AsyncSession, character_id: str) -> list[tuple[CapabilityProductType, CapabilityPack]]:
    """(product type, PRODUCTION pack) pairs for the character's current locked version."""
    try:
        current = await version_service.get_current_locked_version(db, character_id)
    except version_service.CharacterVersionNotFound:
        raise CapabilityNotFound(f"Character {character_id} not found.")
    live = {
        pack.pack_type: pack
        for pack in await list_packs(db, character_id, status=PRODUCTION)
        if pack.character_version == current.version
    }
    pairs = [(pt, live[pt.pack_type]) for pt in await list_product_types(db) if pt.pack_type in live]
    return sorted(pairs, key=lambda pair: (pair[1].sort_order, pair[0].sort_order))


async def resolve_production_pack(db: AsyncSession, character_id: str,
                                  product_type: str) -> Optional[ResolvedCapabilityPack]:
    """The PRODUCTION pack serving ``product_type`` for the character's current
    locked version, with its technical details, or None when there is none.

    Internal (Pose Resolver / Runtime Dispatch); never exposed to customers.
    """
    pack_type = await pack_type_for(db, product_type)
    if pack_type is None:
        return None
    try:
        current = await version_service.get_current_locked_version(db, character_id)
    except version_service.CharacterVersionNotFound:
        return None
    pack = await _first(db, select(CapabilityPack).where(
        CapabilityPack.character_id == character_id,
        CapabilityPack.character_version == current.version,
        CapabilityPack.pack_type == pack_type,
        CapabilityPack.status == PRODUCTION,
    ))
    if pack is None:
        return None
    links = (await list_pack_adapters(db, [pack]))[pack.id]
    adapters = {a.model_id: a for a in (await db.execute(select(ModelArtifact).where(
        ModelArtifact.model_id.in_([link.adapter_id for link in links])))).scalars().all()}
    return ResolvedCapabilityPack(
        internal_key=pack.internal_key, character_id=pack.character_id, character_version=pack.character_version,
        pack_type=pack.pack_type, version=pack.version, workflow_route=pack.workflow_route,
        workflow_version=pack.workflow_version,
        required_reference_assets=list(pack.required_reference_assets or []),
        supported_product_types=list(pack.supported_product_types or []),
        compatible_appearance_options=list(pack.compatible_appearance_options or []),
        compatible_poses=list(pack.compatible_poses or []),
        qa_rules=dict(pack.qa_rules or {}), validation=dict(pack.validation or {}),
        adapters=tuple(
            ResolvedAdapter(adapter_id=a.model_id, layer=a.layer, kind=a.kind, storage_path=a.storage_path,
                            checkpoint_id=a.checkpoint_id, reference=a.reference)
            for a in (adapters.get(link.adapter_id) for link in links) if a is not None
        ),
    )


# ========================== Writes ================================

async def create_pack(db: AsyncSession, *, character_id: str, character_version: str, pack_type: str,
                      version: Optional[int], created_by: str, **fields: Any) -> CapabilityPack:
    try:
        await version_service.get_version(db, character_id, character_version)
    except version_service.CharacterVersionNotFound as exc:
        raise CapabilityNotFound(str(exc))
    if pack_type not in PACK_TYPES:
        raise CapabilityInvalid(f"Unknown pack type {pack_type}.")
    await _check_compatibility(db, character_id, fields)

    if version is None:
        latest = (await db.execute(select(func.max(CapabilityPack.version)).where(
            CapabilityPack.character_id == character_id,
            CapabilityPack.pack_type == pack_type,
        ))).scalar()
        version = (latest or 0) + 1
    key = internal_key(character_id, pack_type, version)
    if await _first(db, select(CapabilityPack).where(CapabilityPack.internal_key == key)):
        raise CapabilityConflict(f"Capability pack {key} already exists.")

    pack = CapabilityPack(
        internal_key=key, character_id=character_id, character_version=character_version, pack_type=pack_type,
        version=version, status=IN_DEVELOPMENT, created_by=created_by,
        **{f: v for f, v in fields.items() if f in EDITABLE_FIELDS and v is not None},
    )
    db.add(pack)
    await db.commit()
    await db.refresh(pack)
    return pack


async def update_pack(db: AsyncSession, key: str, **fields: Any) -> CapabilityPack:
    """Edit a pack that is not live. PRODUCTION/ARCHIVED packs are frozen:
    create a new version instead."""
    pack = await get_pack(db, key)
    if pack.status in FROZEN:
        raise _frozen_error(pack)
    await _check_compatibility(db, pack.character_id, fields)
    for name, value in fields.items():
        if name in EDITABLE_FIELDS and value is not None:
            setattr(pack, name, value)
    await db.commit()
    await db.refresh(pack)
    return pack


async def link_adapter(db: AsyncSession, key: str, adapter_id: str, linked_by: str) -> CapabilityPack:
    pack = await get_pack(db, key)
    if pack.status in FROZEN:
        raise _frozen_error(pack)
    await _check_adapter(db, adapter_id, pack)
    if await _first(db, select(CapabilityPackAdapter).where(
            CapabilityPackAdapter.pack_id == pack.id, CapabilityPackAdapter.adapter_id == adapter_id)):
        raise CapabilityConflict(f"Adapter {adapter_id} is already linked to {key}.")
    db.add(CapabilityPackAdapter(pack_id=pack.id, adapter_id=adapter_id, linked_by=linked_by))
    await db.commit()
    return pack


async def unlink_adapter(db: AsyncSession, key: str, adapter_id: str) -> CapabilityPack:
    pack = await get_pack(db, key)
    if pack.status in FROZEN:
        raise _frozen_error(pack)
    result = await db.execute(delete(CapabilityPackAdapter).where(
        CapabilityPackAdapter.pack_id == pack.id, CapabilityPackAdapter.adapter_id == adapter_id))
    if not result.rowcount:
        raise CapabilityNotFound(f"Adapter {adapter_id} is not linked to {key}.")
    await db.commit()
    return pack


async def record_validation(db: AsyncSession, key: str, results: dict[str, str], validated_by: str) -> CapabilityPack:
    """Record identity/face/body/product PASS/FAIL results. Checks may be
    recorded one at a time; earlier results are kept."""
    pack = await get_pack(db, key)
    if pack.status in FROZEN:
        raise _frozen_error(pack)
    pack.validation = {**(pack.validation or {}), **results}
    pack.validated_by = validated_by
    pack.validated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(pack)
    return pack


async def change_status(db: AsyncSession, key: str, new_status: str, changed_by: str) -> CapabilityPack:
    pack = await get_pack(db, key)
    if new_status not in TRANSITIONS[pack.status]:
        raise CapabilityConflict(
            f"Cannot move capability pack {key} from {pack.status} to {new_status}. "
            f"Allowed: {sorted(TRANSITIONS[pack.status]) or 'none'}."
        )
    if new_status == APPROVED and not _validation_passed(pack):
        raise CapabilityConflict(
            f"Capability pack {key} needs PASS validation for {list(VALIDATION_CHECKS)} before it can be APPROVED."
        )

    if new_status == PRODUCTION:
        # Only the current locked version is served, so a pack for a draft
        # version must not replace (archive) the pack customers are using.
        try:
            current = await version_service.get_current_locked_version(db, pack.character_id)
        except version_service.CharacterVersionNotFound:
            current = None
        if current is None or current.version != pack.character_version:
            raise CapabilityConflict(
                f"Capability pack {key} is for {pack.character_id} version {pack.character_version}, which is not "
                "the current locked version, so it cannot go to PRODUCTION."
            )

    now = datetime.utcnow()
    try:
        if new_status == PRODUCTION:
            # One live version per character + pack type. The previous one is
            # archived in the same transaction (flushed first so the partial
            # unique index never sees two PRODUCTION rows).
            previous = await db.execute(select(CapabilityPack).where(
                CapabilityPack.character_id == pack.character_id,
                CapabilityPack.pack_type == pack.pack_type,
                CapabilityPack.status == PRODUCTION,
            ))
            for old in previous.scalars().all():
                old.status = ARCHIVED
                old.status_changed_by = changed_by
                old.status_changed_at = now
            await db.flush()
        pack.status = new_status
        pack.status_changed_by = changed_by
        pack.status_changed_at = now
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(pack)
    return pack


async def seed_product_types(db: AsyncSession) -> list[CapabilityProductType]:
    """Idempotently ensure the default product type mapping and its framing
    rules exist. Existing rows are never changed, except that a missing
    framing rule is filled in. No pack is seeded: none has been validated."""
    for item in DEFAULT_PRODUCT_TYPES:
        row = await _first(db, select(CapabilityProductType).where(
            CapabilityProductType.product_type == item["product_type"]))
        if not row:
            row = CapabilityProductType(is_default=False, **item)
            db.add(row)
        rule = DEFAULT_FRAMING_RULES.get(row.pack_type)
        if rule and row.required_framings is None:
            row.required_framings, row.framing_rule_code = list(rule[0]), rule[1]
    await db.commit()
    return await list_product_types(db)
