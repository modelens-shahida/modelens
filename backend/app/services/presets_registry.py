"""
Presets Registry: the location, lighting and campaign presets a production can use.

Same lifecycle as styling options and poses:
IN_DEVELOPMENT -> VALIDATION -> APPROVED -> PRODUCTION -> ARCHIVED.
Customers (and Production Dispatch) only ever see PRODUCTION presets, by their
stable ``preset_key``. ``technical_config`` carries the generation parameters
and is admin/runtime only:

* LIGHTING: ``{"workflow_params": {...}, ...}`` (required before APPROVED).
* CAMPAIGN: ``{"lighting_id": <LIGHTING key>, "focal_length_mm": <int>}``,
  the defaults used when a request does not choose them (required).
* LOCATION: free-form (e.g. ``{"family": "STUDIO"}``). A location may name a
  ``recommended_lighting_id``.

A live preset cannot point at a lighting preset that is not live: promoting
checks the references, and a lighting preset still used by a PRODUCTION
location or campaign cannot be archived.
"""
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Preset
from app.services.fluid_service import FOCAL_LENGTHS, LIGHTING_PRESETS

LOCATION = "LOCATION"
LIGHTING = "LIGHTING"
CAMPAIGN = "CAMPAIGN"
PRESET_TYPES = (LOCATION, LIGHTING, CAMPAIGN)

IN_DEVELOPMENT = "IN_DEVELOPMENT"
VALIDATION = "VALIDATION"
APPROVED = "APPROVED"
PRODUCTION = "PRODUCTION"
ARCHIVED = "ARCHIVED"
STATUSES = (IN_DEVELOPMENT, VALIDATION, APPROVED, PRODUCTION, ARCHIVED)

# VALIDATION -> IN_DEVELOPMENT sends a failed preset back for rework.
TRANSITIONS: dict[str, set[str]] = {
    IN_DEVELOPMENT: {VALIDATION, ARCHIVED},
    VALIDATION: {APPROVED, IN_DEVELOPMENT, ARCHIVED},
    APPROVED: {PRODUCTION, ARCHIVED},
    PRODUCTION: {ARCHIVED},
    ARCHIVED: set(),
}

EDITABLE_FIELDS = ("label", "description", "thumbnail_url", "sort_order", "recommended_lighting_id",
                   "technical_config")
# A PRODUCTION preset keeps its technical_config: changing it would change live
# generations without validation. Create a new preset instead.
LIVE_EDITABLE_FIELDS = ("label", "description", "thumbnail_url", "sort_order", "recommended_lighting_id")
KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _lighting_seed() -> list[dict]:
    return [
        {"preset_key": key, "label": p["display_name"], "description": p["description"],
         "technical_config": {k: p[k] for k in ("name", "family", "taxonomy_id", "workflow_params",
                                                "recommended_for")},
         "is_default": key == "STUDIO_SOFT_DIFFUSE"}
        for key, p in LIGHTING_PRESETS.items()
    ]


def _location(key, label, family, lighting, is_default=False):
    return {"preset_key": key, "label": label, "technical_config": {"family": family},
            "recommended_lighting_id": lighting, "is_default": is_default}


def _campaign(key, label, lighting, focal, is_default=False):
    return {"preset_key": key, "label": label, "technical_config": {"lighting_id": lighting, "focal_length_mm": focal},
            "is_default": is_default}


# The values Production Dispatch accepted before the registry existed, seeded
# as PRODUCTION (alembic presets_registry_001 holds a frozen copy).
SEED: dict[str, list[dict]] = {
    LIGHTING: _lighting_seed(),
    LOCATION: [
        _location("ENV-STU-0001", "White Seamless", "STUDIO", "STUDIO_SOFT_DIFFUSE", is_default=True),
        _location("ENV-STU-0002", "Warm Gray Studio", "STUDIO", "STUDIO_SOFT_DIFFUSE"),
        _location("ENV-STU-0003", "Cream Studio", "STUDIO", "STUDIO_SOFT_DIFFUSE"),
        _location("ENV-STU-0004", "Black Studio", "STUDIO", "DRAMATIC_CHIAROSCURO"),
        _location("ENV-INT-0001", "Minimal Interior", "INTERIOR", "STUDIO_SOFT_DIFFUSE"),
        _location("ENV-INT-0002", "Luxury Hotel", "INTERIOR", "DRAMATIC_CHIAROSCURO"),
        _location("ENV-BCH-0001", "Beach Golden Hour", "BEACH", "NATURAL_GOLDEN_HOUR"),
        _location("ENV-URB-0001", "City Street", "URBAN", "EDITORIAL_HARD_HIGH_KEY"),
    ],
    CAMPAIGN: [
        _campaign("ecommerce", "E-commerce", "STUDIO_SOFT_DIFFUSE", 85, is_default=True),
        _campaign("catalog", "Catalog", "STUDIO_SOFT_DIFFUSE", 85),
        _campaign("editorial", "Editorial", "EDITORIAL_HARD_HIGH_KEY", 50),
        _campaign("lookbook", "Lookbook", "NATURAL_GOLDEN_HOUR", 50),
        _campaign("social", "Social", "NATURAL_GOLDEN_HOUR", 35),
    ],
}


class PresetNotFound(Exception):
    """HTTP 404."""


class PresetConflict(Exception):
    """Invalid transition, duplicate, or edit of a live/archived preset (HTTP 409)."""


class PresetInvalid(Exception):
    """Well-formed request that breaks a business rule (HTTP 400)."""


async def _first(db: AsyncSession, stmt):
    return (await db.execute(stmt)).scalars().first()


def _by_key(preset_type: str, key: str):
    return select(Preset).where(Preset.preset_type == preset_type, Preset.preset_key == key)


# ========================== Reads =================================

async def get_preset(db: AsyncSession, preset_type: str, key: str) -> Preset:
    found = await _first(db, _by_key(preset_type, key))
    if not found:
        raise PresetNotFound(f"{preset_type.title()} preset {key} not found.")
    return found


async def list_presets(db: AsyncSession, preset_type: Optional[str] = None,
                       status: Optional[str] = None) -> list[Preset]:
    stmt = select(Preset).order_by(Preset.preset_type, Preset.sort_order, Preset.label, Preset.preset_key)
    if preset_type:
        stmt = stmt.where(Preset.preset_type == preset_type)
    if status:
        stmt = stmt.where(Preset.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def production_preset(db: AsyncSession, preset_type: str, key: str) -> Optional[Preset]:
    """The PRODUCTION preset with this key, or None."""
    return await _first(db, _by_key(preset_type, key).where(Preset.status == PRODUCTION))


async def default_preset(db: AsyncSession, preset_type: str) -> Optional[Preset]:
    return await _first(db, select(Preset).where(
        Preset.preset_type == preset_type, Preset.status == PRODUCTION, Preset.is_default.is_(True)))


async def customer_presets(db: AsyncSession, preset_type: str) -> list[dict]:
    """PRODUCTION presets of one type, in customer-safe form."""
    presets = await list_presets(db, preset_type, PRODUCTION)
    live_lighting = set()
    if preset_type == LOCATION:
        live_lighting = {p.preset_key for p in await list_presets(db, LIGHTING, PRODUCTION)}
    result = []
    for p in presets:
        item = {"id": p.preset_key, "label": p.label, "description": p.description,
                "thumbnail_url": p.thumbnail_url, "is_default": bool(p.is_default)}
        if preset_type == LOCATION:
            lighting = p.recommended_lighting_id
            item["recommended_lighting_id"] = lighting if lighting in live_lighting else None
        result.append(item)
    return result


# ========================== Rules =================================

async def _check_lighting_ref(db: AsyncSession, lighting_id: str, *, live: bool, field: str) -> None:
    lighting = await _first(db, _by_key(LIGHTING, lighting_id))
    if lighting is None or lighting.status == ARCHIVED:
        raise PresetInvalid(f"{field}: lighting preset {lighting_id} does not exist or is archived.")
    if live and lighting.status != PRODUCTION:
        raise PresetConflict(f"{field}: lighting preset {lighting_id} is {lighting.status}, not PRODUCTION.")


async def _check_ready(db: AsyncSession, preset: Preset, *, live: bool) -> None:
    """Config a preset needs before APPROVED (live=False) or PRODUCTION (live=True)."""
    config = preset.technical_config or {}
    if preset.preset_type == LIGHTING:
        if not isinstance(config.get("workflow_params"), dict) or not config["workflow_params"]:
            raise PresetConflict(f"Lighting preset {preset.preset_key} needs technical_config.workflow_params.")
    elif preset.preset_type == CAMPAIGN:
        if config.get("focal_length_mm") not in FOCAL_LENGTHS:
            raise PresetConflict(f"Campaign preset {preset.preset_key} needs technical_config.focal_length_mm, "
                                 f"one of {FOCAL_LENGTHS}.")
        if not config.get("lighting_id"):
            raise PresetConflict(f"Campaign preset {preset.preset_key} needs technical_config.lighting_id.")
        await _check_lighting_ref(db, config["lighting_id"], live=live, field="technical_config.lighting_id")
    elif preset.recommended_lighting_id:
        await _check_lighting_ref(db, preset.recommended_lighting_id, live=live, field="recommended_lighting_id")


async def _lighting_users(db: AsyncSession, lighting_id: str) -> list[str]:
    """PRODUCTION locations/campaigns that use this lighting preset."""
    users = []
    for p in await list_presets(db, status=PRODUCTION):
        if (p.preset_type == LOCATION and p.recommended_lighting_id == lighting_id) or (
                p.preset_type == CAMPAIGN and (p.technical_config or {}).get("lighting_id") == lighting_id):
            users.append(f"{p.preset_type.lower()} {p.preset_key}")
    return users


# ========================== Writes ================================

async def create_preset(db: AsyncSession, *, preset_type: str, preset_key: str, created_by: str,
                        **fields: Any) -> Preset:
    if preset_type not in PRESET_TYPES:
        raise PresetInvalid(f"preset_type must be one of {list(PRESET_TYPES)}.")
    if not KEY_PATTERN.match(preset_key):
        raise PresetInvalid("preset_key may only contain letters, digits, '-' and '_', e.g. ENV-STU-0005.")
    if fields.get("recommended_lighting_id"):
        if preset_type != LOCATION:
            raise PresetInvalid("Only location presets have a recommended_lighting_id.")
        await _check_lighting_ref(db, fields["recommended_lighting_id"], live=False, field="recommended_lighting_id")
    if await _first(db, _by_key(preset_type, preset_key)):
        raise PresetConflict(f"{preset_type.title()} preset {preset_key} already exists.")

    preset = Preset(
        preset_type=preset_type, preset_key=preset_key, status=IN_DEVELOPMENT, is_default=False,
        created_by=created_by, **{f: v for f, v in fields.items() if f in EDITABLE_FIELDS and v is not None},
    )
    db.add(preset)
    await db.commit()
    await db.refresh(preset)
    return preset


async def update_preset(db: AsyncSession, preset_type: str, key: str, **fields: Any) -> Preset:
    """Edit a preset. ARCHIVED presets are frozen; PRODUCTION presets only take
    display fields and recommended_lighting_id (technical_config is frozen)."""
    preset = await get_preset(db, preset_type, key)
    fields = {f: v for f, v in fields.items() if f in EDITABLE_FIELDS and v is not None}
    if preset.status == ARCHIVED:
        raise PresetConflict(f"{preset_type.title()} preset {key} is ARCHIVED and cannot be edited.")
    if preset.status == PRODUCTION:
        frozen = sorted(set(fields) - set(LIVE_EDITABLE_FIELDS))
        if frozen:
            raise PresetConflict(f"{preset_type.title()} preset {key} is PRODUCTION; {frozen} cannot be changed. "
                                 "Create a new preset instead.")
    if "recommended_lighting_id" in fields:
        if preset_type != LOCATION:
            raise PresetInvalid("Only location presets have a recommended_lighting_id.")
        await _check_lighting_ref(db, fields["recommended_lighting_id"], live=preset.status == PRODUCTION,
                                  field="recommended_lighting_id")
    for field, value in fields.items():
        setattr(preset, field, value)
    await db.commit()
    await db.refresh(preset)
    return preset


async def change_status(db: AsyncSession, preset_type: str, key: str, new_status: str, changed_by: str) -> Preset:
    preset = await get_preset(db, preset_type, key)
    if new_status not in TRANSITIONS[preset.status]:
        raise PresetConflict(
            f"Cannot move {preset_type.lower()} preset {key} from {preset.status} to {new_status}. "
            f"Allowed: {sorted(TRANSITIONS[preset.status]) or 'none'}."
        )
    if new_status in (APPROVED, PRODUCTION):
        await _check_ready(db, preset, live=new_status == PRODUCTION)
    if new_status == ARCHIVED:
        if preset.is_default:
            raise PresetConflict(f"{preset_type.title()} preset {key} is the default. Set another default first.")
        if preset_type == LIGHTING:
            users = await _lighting_users(db, key)
            if users:
                raise PresetConflict(f"Lighting preset {key} is still used by PRODUCTION {', '.join(users)}.")

    preset.status = new_status
    preset.status_changed_by = changed_by
    preset.status_changed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(preset)
    return preset


async def archive(db: AsyncSession, preset_type: str, key: str, changed_by: str) -> Preset:
    return await change_status(db, preset_type, key, ARCHIVED, changed_by)


async def set_default(db: AsyncSession, preset_type: str, key: str) -> Preset:
    """Make a PRODUCTION preset the default of its type (clears the old default)."""
    preset = await get_preset(db, preset_type, key)
    if preset.status != PRODUCTION:
        raise PresetConflict(f"Only PRODUCTION presets can be the default ({key} is {preset.status}).")
    others = await db.execute(select(Preset).where(
        Preset.preset_type == preset_type, Preset.is_default.is_(True), Preset.id != preset.id))
    for other in others.scalars().all():
        other.is_default = False
    await db.flush()
    preset.is_default = True
    await db.commit()
    await db.refresh(preset)
    return preset


async def seed_presets(db: AsyncSession) -> list[Preset]:
    """Idempotently ensure the seed presets exist as PRODUCTION.

    Existing rows are never changed. A seeded preset only becomes the default
    when its type has no default yet. Lighting is seeded first because
    locations and campaigns refer to it.
    """
    seeded = []
    for preset_type in (LIGHTING, LOCATION, CAMPAIGN):
        for order, item in enumerate(SEED[preset_type]):
            row = await _first(db, _by_key(preset_type, item["preset_key"]))
            if row is None:
                has_default = await _first(db, select(Preset).where(
                    Preset.preset_type == preset_type, Preset.is_default.is_(True)))
                row = Preset(
                    preset_type=preset_type, status=PRODUCTION, sort_order=order,
                    created_by="SYSTEM_SEED", status_changed_by="SYSTEM_SEED", status_changed_at=datetime.utcnow(),
                    **{**item, "is_default": item.get("is_default", False) and has_default is None},
                )
                db.add(row)
                await db.commit()
                await db.refresh(row)
            seeded.append(row)
    return seeded
