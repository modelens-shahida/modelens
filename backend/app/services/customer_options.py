"""
Customer option lists and id resolution (Character Runtime PR 3).

What a customer may pick = what is live in the definition tables (appearance
options and capability packs in PRODUCTION, ACTIVE poses offered for a product
type, presets in PRODUCTION) **and** PROMOTED for the character's current
locked version in ``capability_validations``. The definition tables still
hold labels, descriptions and thumbnails; the PROMOTED record gives the
namespaced customer id (``hair_canonical``, ``pose_walking``,
``scene_env-stu-0001`` ...), ``group`` and ``recommended``. ``is_default``
still comes from the definition tables (their admin "set default" endpoints
keep working; poses use the per-product-type default of the pose mapping);
the record's own ``is_default`` is stored for later per-character defaults.

Every option comes back in the agreed option object (DESIGN.md section 4):
``id, label, thumbnail_url, group, is_default, recommended``, plus the extra
fields the existing routes already returned (``description``; poses
``category`` and ``recommended_framing``; locations
``recommended_lighting_id``, now a namespaced lighting id).

Dispatch resolves ids through the same lists, so a customer can only produce
with what they can see. It accepts the namespaced id or the old id (``canonical``,
``walking``, ``ENV-STU-0001``, ``ecommerce``) of a PROMOTED option; anything
else is a customer-safe 422.

There is no fallback to the definition tables alone: an option that is live
there but not promoted for the character is not offered.
"""
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import CapabilityValidation, CharacterRegistryVersion
from app.services import appearance_options as appearance_service
from app.services import capability_packs as pack_service
from app.services import capability_validations as cv
from app.services import character_versions as version_service
from app.services import pose_resolver as pose_service
from app.services import presets_registry as preset_service

POSE_PREFIX = "pose_"


@dataclass
class Choice:
    """One option a customer may pick: the definition row, its PROMOTED record and its customer form."""
    definition: Any
    record: CapabilityValidation
    item: dict


async def _promoted(db: AsyncSession, character_id: str, character_version: str,
                    capability_type: str) -> dict[tuple[str, int], CapabilityValidation]:
    return {(r.capability_key, r.capability_version): r
            for r in await cv.promoted(db, character_id, character_version, capability_type)}


def _option(record: CapabilityValidation, definition, is_default: Optional[bool] = None, **extra) -> dict:
    return {
        "id": record.customer_id,
        "label": definition.label,
        "thumbnail_url": definition.thumbnail_url,
        "group": record.group,
        "is_default": bool(definition.is_default if is_default is None else is_default),
        "recommended": bool(record.recommended),
        "description": definition.description,
        **extra,
    }


def matches(record: CapabilityValidation, requested: str, old_id: str) -> bool:
    """A requested id names this option: the namespaced id or the old id (case-insensitive)."""
    value = str(requested).strip().lower()
    return value in (record.customer_id.lower(), old_id.lower())


# ========================== Styling options ======================

async def styling_choices(db: AsyncSession, character_id: str) -> dict[str, list[Choice]]:
    """Customer category key (hair, makeup, ...) -> choices, in display order. NAILS has no
    capability type (DESIGN.md open question 12), so it is always empty."""
    grouped = await appearance_service.customer_styling_options(db, character_id)  # 404 for an unknown character
    current = await version_service.get_current_locked_version(db, character_id)
    result: dict[str, list[Choice]] = {key: [] for key in grouped}
    for category, (key, _) in appearance_service.CATEGORIES.items():
        if category not in cv.APPEARANCE_TYPES:
            continue
        promoted = await _promoted(db, character_id, current.version, cv.APPEARANCE_TYPES[category][0])
        for option in grouped[key]:
            record = promoted.get((option.option_id, option.version))
            if record is not None:
                result[key].append(Choice(option, record, _option(record, option)))
    return result


# ========================== Product types ========================

async def product_type_choices(db: AsyncSession, character_id: str) -> list[Choice]:
    pairs = await pack_service.customer_capabilities(db, character_id)  # 404 for an unknown character
    current = await version_service.get_current_locked_version(db, character_id)
    promoted = await _promoted(db, character_id, current.version, "PRODUCT_TYPE")
    choices = []
    for product_type, pack in pairs:
        record = promoted.get((product_type.product_type, pack.version))
        if record is not None:
            choices.append(Choice(product_type, record, _option(record, pack, is_default=product_type.is_default)))
    return choices


async def product_type_promoted(db: AsyncSession, character_id: str, product_type: str) -> bool:
    return any(c.definition.product_type == product_type for c in await product_type_choices(db, character_id))


# ========================== Poses =================================

async def pose_choices(db: AsyncSession, character_id: str, product_type: str) -> list[Choice]:
    """Poses for the product type, in display order, exactly one default when any are offered."""
    offered = await pose_service.customer_poses(db, character_id, product_type)  # 404 / 422 as before
    if not offered:
        return []
    if not await product_type_promoted(db, character_id, product_type):
        return []
    current = await version_service.get_current_locked_version(db, character_id)
    promoted = await _promoted(db, character_id, current.version, "POSE")
    kept = [(pose, is_default, promoted[(pose.pose_id, 1)]) for pose, is_default in offered
            if (pose.pose_id, 1) in promoted]
    if kept and not any(is_default for _, is_default, _ in kept):
        kept[0] = (kept[0][0], True, kept[0][2])
    return [Choice(pose, record, _option(record, pose, is_default=is_default, category=pose.category,
                                         recommended_framing=pose.recommended_framing))
            for pose, is_default, record in kept]


def pose_old_id(choice: Choice) -> str:
    return choice.definition.pose_id


# ========================== Presets ===============================

async def _current_versions(db: AsyncSession) -> list[tuple[str, str]]:
    ids = sorted(set((await db.execute(select(CharacterRegistryVersion.character_id))).scalars().all()))
    current = []
    for character_id in ids:
        try:
            current.append((character_id, (await version_service.get_current_locked_version(db, character_id)).version))
        except version_service.CharacterVersionNotFound:
            continue
    return current


async def _preset_records(db: AsyncSession, preset_type: str,
                          character_id: Optional[str]) -> dict[str, CapabilityValidation]:
    """preset_key -> PROMOTED record. For one character, or (the /presets routes, which name no
    character) for any character's current locked version, the first character by id winning."""
    capability_type = cv.PRESET_TYPES[preset_type][0]
    if character_id is not None:
        try:
            versions = [(character_id, (await version_service.get_current_locked_version(db, character_id)).version)]
        except version_service.CharacterVersionNotFound:
            return {}
    else:
        versions = await _current_versions(db)
    records: dict[str, CapabilityValidation] = {}
    for char, version in versions:
        for (key, capability_version), record in (await _promoted(db, char, version, capability_type)).items():
            if capability_version == 1:
                records.setdefault(key, record)
    return records


async def preset_choices(db: AsyncSession, preset_type: str, character_id: Optional[str] = None) -> list[Choice]:
    presets = await preset_service.list_presets(db, preset_type, preset_service.PRODUCTION)
    records = await _preset_records(db, preset_type, character_id)
    lighting_ids: dict[str, str] = {}
    if preset_type == preset_service.LOCATION:
        lighting_ids = {c.definition.preset_key: c.record.customer_id
                        for c in await preset_choices(db, preset_service.LIGHTING, character_id)}
    choices = []
    for preset in presets:
        record = records.get(preset.preset_key)
        if record is None:
            continue
        extra = {}
        if preset_type == preset_service.LOCATION:
            extra["recommended_lighting_id"] = lighting_ids.get(preset.recommended_lighting_id)
        choices.append(Choice(preset, record, _option(record, preset, **extra)))
    return choices


def preset_old_id(choice: Choice) -> str:
    return choice.definition.preset_key


def appearance_old_id(choice: Choice) -> str:
    return choice.definition.option_id.lower()
