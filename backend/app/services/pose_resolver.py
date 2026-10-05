"""
Pose Resolver service.

Different products need different poses (shoes: foot forward, profile, ...;
jewelry: ear, neck, wrist detail, ...). Which poses go with which product
type is data (``pose_product_types``), never frontend code.

Poses are layered on top of the character and never modify her Character
Version. A pose is offered for a character + product type only when the
character's capability pack for that product type is in PRODUCTION
(``capability_packs.resolve_production_pack``). If the pack lists
``compatible_poses`` only those are offered; otherwise every active pose
mapped to the product type is.

Pose adapters (Training Registry adapters with layer POSE), geometry presets,
control references and workflow params are admin/runtime only.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import CapabilityProductType, ModelArtifact, PoseDefinition, PoseGeometryPreset, PoseProductType
from app.services import capability_packs as pack_service
from app.services import character_versions as version_service
from app.services.compatibility import load_framing_rules

ACTIVE = "ACTIVE"
ARCHIVED = "ARCHIVED"
CATEGORIES = ("static", "motion", "detail", "portrait")
FRAMINGS = ("full_body", "three_quarter", "half_body", "close_up", "detail")
POSE_LAYER = "POSE"

EDITABLE_FIELDS = (
    "label", "description", "category", "thumbnail_url", "recommended_framing", "sort_order",
    "pose_adapter_id", "geometry_preset_id", "control_reference", "workflow_params",
)

# Seed catalog (metadata only: no technical refs, no thumbnails yet).
DEFAULT_POSES = (
    ("standing", "Standing", "static", "full_body", "Relaxed full-length standing pose that shows the whole garment."),
    ("walking", "Walking", "motion", "full_body", "Mid-stride walk that shows how the product moves."),
    ("editorial", "Editorial", "static", "full_body", "Styled fashion-editorial stance with more attitude than a catalog pose."),
    ("seated", "Seated", "static", "full_body", "Seated pose that shows drape and fit when sitting."),
    ("garment_interaction", "Garment Interaction", "static", "three_quarter",
     "Hands on the garment (collar, hem, pocket) to draw attention to a detail."),
    ("foot_forward", "Foot Forward", "static", "full_body", "Full-length stance with one foot forward to show the shoe."),
    ("full_body_profile", "Profile", "static", "full_body", "Full-length side view that shows the shoe's silhouette."),
    ("shoe_detail", "Shoe Detail", "detail", "detail", "Close crop on the feet that shows materials and finish."),
    ("hand_carry", "Hand Carry", "static", "three_quarter", "Bag held by the handle at the side."),
    ("shoulder_carry", "Shoulder", "static", "three_quarter", "Bag worn on the shoulder."),
    ("crossbody", "Crossbody", "static", "three_quarter", "Bag worn across the body."),
    ("bag_detail", "Product Detail", "detail", "detail", "Close crop on the bag that shows hardware and materials."),
    ("portrait", "Portrait", "portrait", "close_up", "Front-facing head-and-shoulders portrait."),
    ("head_turn_30", "30° Turn", "portrait", "close_up", "Head turned 30° from camera."),
    ("head_turn_45", "45° Turn", "portrait", "close_up", "Head turned 45° from camera."),
    ("head_profile", "Head Profile", "portrait", "close_up", "Head in side profile."),
    ("temple_adjustment", "Temple Adjustment", "detail", "close_up", "Hand adjusting the frame at the temple."),
    ("ear_detail", "Ear Detail", "detail", "detail", "Close crop on the ear for earrings."),
    ("neck_detail", "Neck Detail", "detail", "detail", "Close crop on the neck and collarbone for necklaces."),
    ("wrist_detail", "Wrist Detail", "detail", "detail", "Close crop on the wrist for bracelets and watches."),
    ("hand_detail", "Hand Detail", "detail", "detail", "Close crop on the hand for rings."),
)

# Product type -> poses in display order; the first one is the default.
DEFAULT_POSE_PRODUCT_TYPES = {
    "garment": ("standing", "walking", "editorial", "seated", "garment_interaction"),
    "shoes": ("foot_forward", "full_body_profile", "walking", "shoe_detail"),
    "bags": ("hand_carry", "shoulder_carry", "crossbody", "walking", "bag_detail"),
    "eyewear": ("portrait", "head_turn_30", "head_turn_45", "head_profile", "temple_adjustment"),
    "jewelry": ("portrait", "ear_detail", "neck_detail", "wrist_detail", "hand_detail"),
    "headwear": ("portrait", "head_turn_45", "head_profile"),
}


class PoseNotFound(Exception):
    """Unknown pose, character or adapter (HTTP 404)."""


class PoseConflict(Exception):
    """Duplicate pose or edit of an archived pose (HTTP 409)."""


class PoseInvalid(Exception):
    """Well-formed request that breaks a business rule (HTTP 400)."""


class UnknownProductType(Exception):
    """Product type not in capability_product_types (HTTP 422)."""


class PoseNotAllowed(Exception):
    """The pose is not offered for this character + product type."""


@dataclass(frozen=True)
class ResolvedPose:
    """A pose with its technical refs, for Runtime Dispatch. Never returned
    to customers."""
    pose_id: str
    label: str
    category: str
    recommended_framing: str
    character_id: str
    character_version: str
    product_type: str
    pack: pack_service.ResolvedCapabilityPack
    # Only set when the adapter was trained for this character version;
    # otherwise runtime relies on the geometry / control reference.
    pose_adapter: Optional[pack_service.ResolvedAdapter] = None
    geometry: Optional[dict] = None
    control_reference: Optional[dict] = None
    workflow_params: dict = field(default_factory=dict)


async def _first(db: AsyncSession, stmt):
    return (await db.execute(stmt)).scalars().first()


async def _product_type(db: AsyncSession, product_type: str) -> CapabilityProductType:
    row = await _first(db, select(CapabilityProductType).where(CapabilityProductType.product_type == product_type))
    if row is None:
        known = [r.product_type for r in await pack_service.list_product_types(db)]
        raise UnknownProductType(f"Unknown product type {product_type}. Known: {known}.")
    return row


async def _check_framing(db: AsyncSession, pose: PoseDefinition, product_type: CapabilityProductType) -> None:
    rule = (await load_framing_rules(db)).get(product_type.pack_type.upper())
    if rule and pose.recommended_framing.upper() not in rule["required_framings"]:
        raise PoseInvalid(
            f"{rule['message']}: pose {pose.pose_id} uses {pose.recommended_framing} framing; {product_type.product_type} "
            f"needs one of {[f.lower() for f in rule['required_framings']]}."
        )


async def _check_refs(db: AsyncSession, fields: dict) -> None:
    adapter_id = fields.get("pose_adapter_id")
    if adapter_id:
        adapter = await _first(db, select(ModelArtifact).where(ModelArtifact.model_id == adapter_id))
        if not adapter or adapter.layer is None:
            raise PoseNotFound(f"Adapter {adapter_id} not found.")
        if adapter.layer != POSE_LAYER:
            raise PoseInvalid(f"Adapter {adapter_id} is a {adapter.layer} adapter; a pose needs a POSE adapter.")
    preset_id = fields.get("geometry_preset_id")
    if preset_id and not await _first(db, select(PoseGeometryPreset).where(PoseGeometryPreset.preset_id == preset_id)):
        raise PoseNotFound(f"Pose geometry preset {preset_id} not found.")
    if fields.get("category") is not None and fields["category"] not in CATEGORIES:
        raise PoseInvalid(f"Unknown category {fields['category']}. Known: {list(CATEGORIES)}.")
    if fields.get("recommended_framing") is not None and fields["recommended_framing"] not in FRAMINGS:
        raise PoseInvalid(f"Unknown framing {fields['recommended_framing']}. Known: {list(FRAMINGS)}.")


def _archived_error(pose: PoseDefinition) -> PoseConflict:
    return PoseConflict(f"Pose {pose.pose_id} is archived and cannot be changed.")


# ========================== Reads =================================

async def get_pose(db: AsyncSession, pose_id: str) -> PoseDefinition:
    pose = await _first(db, select(PoseDefinition).where(PoseDefinition.pose_id == pose_id))
    if pose is None:
        raise PoseNotFound(f"Pose {pose_id} not found.")
    return pose


async def list_poses(db: AsyncSession, product_type: Optional[str] = None,
                     status: Optional[str] = None) -> list[PoseDefinition]:
    stmt = select(PoseDefinition)
    if product_type:
        await _product_type(db, product_type)
        stmt = stmt.join(PoseProductType, PoseProductType.pose_definition_id == PoseDefinition.id).where(
            PoseProductType.product_type == product_type).order_by(PoseProductType.sort_order)
    if status:
        stmt = stmt.where(PoseDefinition.status == status)
    stmt = stmt.order_by(PoseDefinition.sort_order, PoseDefinition.pose_id)
    return list((await db.execute(stmt)).scalars().all())


async def list_mappings(db: AsyncSession, poses: list[PoseDefinition]) -> dict[int, list[PoseProductType]]:
    """Product type mappings of the given poses, by pose row id."""
    mappings: dict[int, list[PoseProductType]] = {pose.id: [] for pose in poses}
    if mappings:
        rows = await db.execute(select(PoseProductType).where(
            PoseProductType.pose_definition_id.in_(mappings)).order_by(PoseProductType.product_type))
        for row in rows.scalars().all():
            mappings[row.pose_definition_id].append(row)
    return mappings


async def _offered(db: AsyncSession, character_id: str,
                   product_type: str) -> tuple[Optional[pack_service.ResolvedCapabilityPack],
                                               list[tuple[PoseDefinition, bool]]]:
    """The PRODUCTION pack and the (pose, is_default) pairs it offers."""
    await _product_type(db, product_type)
    try:
        await version_service.get_current_locked_version(db, character_id)
    except version_service.CharacterVersionNotFound:
        raise PoseNotFound(f"Character {character_id} not found.")
    pack = await pack_service.resolve_production_pack(db, character_id, product_type)
    if pack is None:
        return None, []
    rows = (await db.execute(
        select(PoseDefinition, PoseProductType)
        .join(PoseProductType, PoseProductType.pose_definition_id == PoseDefinition.id)
        .where(PoseProductType.product_type == product_type, PoseDefinition.status == ACTIVE)
        .order_by(PoseProductType.sort_order, PoseDefinition.sort_order, PoseDefinition.pose_id)
    )).all()
    allowed = set(pack.compatible_poses)
    offered = [(pose, bool(mapping.is_default)) for pose, mapping in rows if not allowed or pose.pose_id in allowed]
    # Exactly one default when anything is offered: if the stored default is
    # filtered out (e.g. by the pack's compatible_poses), the first pose is.
    if offered and not any(is_default for _, is_default in offered):
        offered[0] = (offered[0][0], True)
    return pack, offered


async def customer_poses(db: AsyncSession, character_id: str, product_type: str) -> list[tuple[PoseDefinition, bool]]:
    """(pose, is_default) pairs a customer may pick for the character and
    product type, in display order. Empty when the pack is not in PRODUCTION."""
    return (await _offered(db, character_id, product_type))[1]


async def resolve_pose(db: AsyncSession, character_id: str, product_type: str, pose_id: str) -> ResolvedPose:
    """The pose with its technical refs, for Runtime Dispatch.

    Raises UnknownProductType, PoseNotFound (unknown character) or
    PoseNotAllowed when the pose is not offered for this character and
    product type (no PRODUCTION pack, not mapped, archived, or excluded by
    the pack's compatible_poses).
    """
    pack, offered = await _offered(db, character_id, product_type)
    if pack is None:
        raise PoseNotAllowed(f"{character_id} has no PRODUCTION capability pack for {product_type}.")
    pose = next((p for p, _ in offered if p.pose_id == pose_id), None)
    if pose is None:
        raise PoseNotAllowed(f"Pose {pose_id} is not available for {character_id} with {product_type}.")

    adapter = None
    if pose.pose_adapter_id:
        row = await _first(db, select(ModelArtifact).where(ModelArtifact.model_id == pose.pose_adapter_id))
        if row is not None and (row.character_id, row.character_version) == (pack.character_id, pack.character_version):
            adapter = pack_service.ResolvedAdapter(
                adapter_id=row.model_id, layer=row.layer, kind=row.kind, storage_path=row.storage_path,
                checkpoint_id=row.checkpoint_id, reference=row.reference)
    geometry = None
    if pose.geometry_preset_id:
        preset = await _first(db, select(PoseGeometryPreset).where(
            PoseGeometryPreset.preset_id == pose.geometry_preset_id))
        if preset is not None:
            geometry = {column.name: getattr(preset, column.name) for column in PoseGeometryPreset.__table__.columns
                        if column.name not in ("id", "created_at")}
    return ResolvedPose(
        pose_id=pose.pose_id, label=pose.label, category=pose.category,
        recommended_framing=pose.recommended_framing, character_id=pack.character_id,
        character_version=pack.character_version, product_type=product_type, pack=pack, pose_adapter=adapter,
        geometry=geometry, control_reference=dict(pose.control_reference) if pose.control_reference else None,
        workflow_params=dict(pose.workflow_params or {}),
    )


# ========================== Writes ================================

async def create_pose(db: AsyncSession, *, pose_id: str, created_by: str, **fields: Any) -> PoseDefinition:
    await _check_refs(db, fields)
    if await _first(db, select(PoseDefinition).where(PoseDefinition.pose_id == pose_id)):
        raise PoseConflict(f"Pose {pose_id} already exists.")
    pose = PoseDefinition(
        pose_id=pose_id, status=ACTIVE, created_by=created_by, updated_by=created_by,
        **{f: v for f, v in fields.items() if f in EDITABLE_FIELDS and v is not None},
    )
    db.add(pose)
    await db.commit()
    await db.refresh(pose)
    return pose


async def update_pose(db: AsyncSession, pose_id: str, updated_by: str, **fields: Any) -> PoseDefinition:
    pose = await get_pose(db, pose_id)
    if pose.status == ARCHIVED:
        raise _archived_error(pose)
    await _check_refs(db, fields)
    for name, value in fields.items():
        if name in EDITABLE_FIELDS and value is not None:
            setattr(pose, name, value)
    if fields.get("recommended_framing"):
        # A new framing must still satisfy every product type it is mapped to.
        for mapping in (await list_mappings(db, [pose]))[pose.id]:
            try:
                await _check_framing(db, pose, await _product_type(db, mapping.product_type))
            except PoseInvalid:
                await db.rollback()
                raise
    pose.updated_by = updated_by
    await db.commit()
    await db.refresh(pose)
    return pose


async def _clear_default(db: AsyncSession, product_type: str) -> None:
    await db.execute(update(PoseProductType).where(
        PoseProductType.product_type == product_type, PoseProductType.is_default.is_(True)).values(is_default=False))
    await db.flush()


async def map_pose(db: AsyncSession, pose_id: str, product_type: str, *, is_default: bool = False,
                   sort_order: Optional[int] = None) -> PoseDefinition:
    """Offer a pose for a product type (or update its order/default). The
    pose's framing must satisfy the product type's framing rule."""
    pose = await get_pose(db, pose_id)
    if pose.status == ARCHIVED:
        raise _archived_error(pose)
    product = await _product_type(db, product_type)
    await _check_framing(db, pose, product)
    mapping = await _first(db, select(PoseProductType).where(
        PoseProductType.pose_definition_id == pose.id, PoseProductType.product_type == product_type))
    try:
        if is_default:
            await _clear_default(db, product_type)
        if mapping is None:
            mapping = PoseProductType(pose_definition_id=pose.id, product_type=product_type,
                                      sort_order=pose.sort_order if sort_order is None else sort_order)
            db.add(mapping)
        elif sort_order is not None:
            mapping.sort_order = sort_order
        if is_default:
            mapping.is_default = True
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return pose


async def unmap_pose(db: AsyncSession, pose_id: str, product_type: str) -> PoseDefinition:
    pose = await get_pose(db, pose_id)
    mapping = await _first(db, select(PoseProductType).where(
        PoseProductType.pose_definition_id == pose.id, PoseProductType.product_type == product_type))
    if mapping is None:
        raise PoseNotFound(f"Pose {pose_id} is not mapped to {product_type}.")
    await db.delete(mapping)
    await db.commit()
    return pose


async def set_default(db: AsyncSession, product_type: str, pose_id: str) -> PoseDefinition:
    """Make ``pose_id`` the one default pose for ``product_type``. It must
    already be mapped to it."""
    pose = await get_pose(db, pose_id)
    if pose.status == ARCHIVED:
        raise _archived_error(pose)
    await _product_type(db, product_type)
    mapping = await _first(db, select(PoseProductType).where(
        PoseProductType.pose_definition_id == pose.id, PoseProductType.product_type == product_type))
    if mapping is None:
        raise PoseInvalid(f"Pose {pose_id} is not mapped to {product_type}; map it first.")
    try:
        await _clear_default(db, product_type)
        mapping.is_default = True
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return pose


async def archive_pose(db: AsyncSession, pose_id: str, archived_by: str) -> PoseDefinition:
    """Hide a pose everywhere. Its mappings are kept for history but it stops
    being any product type's default. Archiving is final."""
    pose = await get_pose(db, pose_id)
    if pose.status == ARCHIVED:
        raise _archived_error(pose)
    await db.execute(update(PoseProductType).where(
        PoseProductType.pose_definition_id == pose.id).values(is_default=False))
    pose.status = ARCHIVED
    pose.archived_by = archived_by
    pose.archived_at = datetime.utcnow()
    pose.updated_by = archived_by
    await db.commit()
    await db.refresh(pose)
    return pose


async def seed_poses(db: AsyncSession) -> list[PoseDefinition]:
    """Idempotently ensure the default pose catalog and product type mapping
    exist (metadata only). Existing poses and mappings are never changed, and
    a product type that already has a default keeps it. Nothing is shown to
    customers until a capability pack is promoted to PRODUCTION."""
    await pack_service.seed_product_types(db)
    poses = {pose.pose_id: pose for pose in (await db.execute(select(PoseDefinition))).scalars().all()}
    for order, (pose_id, label, category, framing, description) in enumerate(DEFAULT_POSES, start=1):
        if pose_id not in poses:
            poses[pose_id] = PoseDefinition(
                pose_id=pose_id, label=label, category=category, recommended_framing=framing,
                description=description, sort_order=order * 10, status=ACTIVE, created_by="SYSTEM_SEED")
            db.add(poses[pose_id])
    await db.flush()
    for product_type, pose_ids in DEFAULT_POSE_PRODUCT_TYPES.items():
        existing = (await db.execute(select(PoseProductType).where(
            PoseProductType.product_type == product_type))).scalars().all()
        mapped = {m.pose_definition_id for m in existing}
        has_default = any(m.is_default for m in existing)
        for order, pose_id in enumerate(pose_ids, start=1):
            pose = poses[pose_id]
            if pose.id in mapped:
                continue
            db.add(PoseProductType(pose_definition_id=pose.id, product_type=product_type, sort_order=order * 10,
                                   is_default=order == 1 and not has_default))
    await db.commit()
    return await list_poses(db)
