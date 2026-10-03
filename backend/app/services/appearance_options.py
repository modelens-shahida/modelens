"""
Appearance / Styling Options service.

Character Core = who the character is (a LOCKED Character Version).
Appearance    = how she is styled: options layered on top of the core.

An option belongs to a Character Version but never modifies it, so
EE-F-002 + SOFT_WAVES + QUIET_LUXURY still resolves to EE-F-002 V1.0.

Lifecycle: IN_DEVELOPMENT -> VALIDATION -> APPROVED -> PRODUCTION -> ARCHIVED.
Customers only ever see PRODUCTION options of the current locked version, so
promoting an option is all it takes for the frontend to show it.
"""
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import AppearanceOption, ModelArtifact
from app.services import character_versions as version_service

IN_DEVELOPMENT = "IN_DEVELOPMENT"
VALIDATION = "VALIDATION"
APPROVED = "APPROVED"
PRODUCTION = "PRODUCTION"
ARCHIVED = "ARCHIVED"
STATUSES = (IN_DEVELOPMENT, VALIDATION, APPROVED, PRODUCTION, ARCHIVED)

# VALIDATION -> IN_DEVELOPMENT sends a failed option back for rework.
TRANSITIONS: dict[str, set[str]] = {
    IN_DEVELOPMENT: {VALIDATION, ARCHIVED},
    VALIDATION: {APPROVED, IN_DEVELOPMENT, ARCHIVED},
    APPROVED: {PRODUCTION, ARCHIVED},
    PRODUCTION: {ARCHIVED},
    ARCHIVED: set(),
}

# Category -> (customer key, internal key segment).
CATEGORIES = {
    "HAIR_STYLE": ("hair", "HAIR"),
    "MAKEUP_STYLE": ("makeup", "MAKEUP"),
    "EXPRESSION": ("expression", "EXPRESSION"),
    "NAILS": ("nails", "NAILS"),
    "JEWELRY": ("jewelry", "JEWELRY"),
    "BEAUTY_DIRECTION": ("beauty_direction", "BEAUTY"),
}

VALIDATION_CHECKS = ("identity", "face", "body", "capability")
EDITABLE_FIELDS = ("label", "description", "thumbnail_url", "sort_order", "adapter_id",
                   "validation", "compatibility_notes", "qa_rules")
OPTION_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

# The canonical default look of EE-F-002 V1.0. Other styles are not seeded:
# they are not validated yet and must go through the lifecycle.
EE_F_002_DEFAULTS = (
    {"category": "HAIR_STYLE", "option_id": "CANONICAL", "label": "Canonical Straight",
     "description": "Sleek natural center-part editorial straight."},
    {"category": "MAKEUP_STYLE", "option_id": "NATURAL", "label": "Natural Minimal",
     "description": "Clean bare-skin finish with subtle hydration."},
    {"category": "EXPRESSION", "option_id": "NEUTRAL_EDITORIAL", "label": "Neutral Editorial",
     "description": "High-fashion, poised and confident."},
)


class AppearanceNotFound(Exception):
    """HTTP 404."""


class AppearanceConflict(Exception):
    """Invalid transition, duplicate, or edit of a live option (HTTP 409)."""


class AppearanceInvalid(Exception):
    """Well-formed request that breaks a business rule (HTTP 400)."""


def internal_key(character_id: str, category: str, option_id: str, version: int) -> str:
    """e.g. EE-F-002_HAIR_SOFT-WAVES_V1"""
    return f"{character_id}_{CATEGORIES[category][1]}_{option_id.replace('_', '-')}_V{version}"


async def _first(db: AsyncSession, stmt):
    return (await db.execute(stmt)).scalars().first()


async def _require_version(db: AsyncSession, character_id: str, character_version: str) -> None:
    try:
        await version_service.get_version(db, character_id, character_version)
    except version_service.CharacterVersionNotFound as exc:
        raise AppearanceNotFound(str(exc))


async def _check_adapter(db: AsyncSession, adapter_id: str, character_id: str, character_version: str) -> None:
    adapter = await _first(db, select(ModelArtifact).where(ModelArtifact.model_id == adapter_id))
    if not adapter or adapter.layer is None:
        raise AppearanceNotFound(f"Adapter {adapter_id} not found.")
    if adapter.layer != "APPEARANCE":
        raise AppearanceInvalid(f"Adapter {adapter_id} is a {adapter.layer} adapter, not APPEARANCE.")
    if (adapter.character_id, adapter.character_version) != (character_id, character_version):
        raise AppearanceInvalid(
            f"Adapter {adapter_id} belongs to {adapter.character_id} version {adapter.character_version}."
        )


def _validation_passed(option: AppearanceOption) -> bool:
    results = option.validation or {}
    return all(results.get(check) == "PASS" for check in VALIDATION_CHECKS)


# ========================== Reads =================================

async def get_option(db: AsyncSession, key: str) -> AppearanceOption:
    found = await _first(db, select(AppearanceOption).where(AppearanceOption.internal_key == key))
    if not found:
        raise AppearanceNotFound(f"Appearance option {key} not found.")
    return found


async def list_options(db: AsyncSession, character_id: Optional[str] = None, character_version: Optional[str] = None,
                       category: Optional[str] = None, status: Optional[str] = None) -> list[AppearanceOption]:
    stmt = select(AppearanceOption).order_by(
        AppearanceOption.character_id, AppearanceOption.category, AppearanceOption.sort_order,
        AppearanceOption.option_id, AppearanceOption.version,
    )
    for column, value in ((AppearanceOption.character_id, character_id),
                          (AppearanceOption.character_version, character_version),
                          (AppearanceOption.category, category), (AppearanceOption.status, status)):
        if value:
            stmt = stmt.where(column == value)
    return list((await db.execute(stmt)).scalars().all())


async def customer_styling_options(db: AsyncSession, character_id: str) -> dict[str, list[AppearanceOption]]:
    """PRODUCTION options of the character's current locked version, by customer category key."""
    try:
        current = await version_service.get_current_locked_version(db, character_id)
    except version_service.CharacterVersionNotFound:
        raise AppearanceNotFound(f"Character {character_id} not found.")
    options = await list_options(db, character_id, current.version, status=PRODUCTION)
    grouped: dict[str, list[AppearanceOption]] = {key: [] for key, _ in CATEGORIES.values()}
    for option in sorted(options, key=lambda o: (o.sort_order, o.label)):
        grouped[CATEGORIES[option.category][0]].append(option)
    return grouped


# ========================== Writes ================================

async def create_option(db: AsyncSession, *, character_id: str, character_version: str, category: str,
                        option_id: str, version: Optional[int], created_by: str, **fields: Any) -> AppearanceOption:
    await _require_version(db, character_id, character_version)
    if not OPTION_ID_PATTERN.match(option_id):
        raise AppearanceInvalid("option_id must be UPPER_SNAKE_CASE, e.g. SOFT_WAVES.")
    if fields.get("adapter_id"):
        await _check_adapter(db, fields["adapter_id"], character_id, character_version)

    if version is None:
        latest = (await db.execute(select(func.max(AppearanceOption.version)).where(
            AppearanceOption.character_id == character_id,
            AppearanceOption.character_version == character_version,
            AppearanceOption.category == category,
            AppearanceOption.option_id == option_id,
        ))).scalar()
        version = (latest or 0) + 1
    key = internal_key(character_id, category, option_id, version)
    if await _first(db, select(AppearanceOption).where(AppearanceOption.internal_key == key)):
        raise AppearanceConflict(f"Appearance option {key} already exists.")

    option = AppearanceOption(
        internal_key=key, character_id=character_id, character_version=character_version,
        category=category, option_id=option_id, version=version, status=IN_DEVELOPMENT,
        is_default=False, created_by=created_by,
        **{f: v for f, v in fields.items() if f in EDITABLE_FIELDS and v is not None},
    )
    db.add(option)
    await db.commit()
    await db.refresh(option)
    return option


async def update_option(db: AsyncSession, key: str, **fields: Any) -> AppearanceOption:
    """Edit an option that is not live. PRODUCTION/ARCHIVED options are frozen:
    create a new version instead."""
    option = await get_option(db, key)
    if option.status in (PRODUCTION, ARCHIVED):
        raise AppearanceConflict(
            f"Appearance option {key} is {option.status} and cannot be edited. Create a new version instead."
        )
    if fields.get("adapter_id"):
        await _check_adapter(db, fields["adapter_id"], option.character_id, option.character_version)
    for field, value in fields.items():
        if field in EDITABLE_FIELDS and value is not None:
            if field == "validation":
                # Checks are recorded one at a time; keep the ones already given.
                value = {**(option.validation or {}), **value}
            setattr(option, field, value)
    await db.commit()
    await db.refresh(option)
    return option


async def change_status(db: AsyncSession, key: str, new_status: str, changed_by: str) -> AppearanceOption:
    option = await get_option(db, key)
    if new_status not in TRANSITIONS[option.status]:
        raise AppearanceConflict(
            f"Cannot move appearance option {key} from {option.status} to {new_status}. "
            f"Allowed: {sorted(TRANSITIONS[option.status]) or 'none'}."
        )
    if new_status == APPROVED and not _validation_passed(option):
        raise AppearanceConflict(
            f"Appearance option {key} needs PASS validation for {list(VALIDATION_CHECKS)} before it can be APPROVED."
        )

    if new_status == PRODUCTION:
        # One live version per option: the previous PRODUCTION version is archived
        # and hands over its default flag.
        previous = await db.execute(select(AppearanceOption).where(
            AppearanceOption.character_id == option.character_id,
            AppearanceOption.character_version == option.character_version,
            AppearanceOption.category == option.category,
            AppearanceOption.option_id == option.option_id,
            AppearanceOption.status == PRODUCTION,
        ))
        inherit_default = False
        for old in previous.scalars().all():
            inherit_default = inherit_default or old.is_default
            old.status = ARCHIVED
            old.is_default = False
            old.status_changed_by = changed_by
            old.status_changed_at = datetime.utcnow()
        await db.flush()
        option.is_default = inherit_default
    if new_status == ARCHIVED:
        option.is_default = False

    option.status = new_status
    option.status_changed_by = changed_by
    option.status_changed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(option)
    return option


async def set_default(db: AsyncSession, key: str) -> AppearanceOption:
    """Make a PRODUCTION option the default of its category (clears the old default)."""
    option = await get_option(db, key)
    if option.status != PRODUCTION:
        raise AppearanceConflict(f"Only PRODUCTION options can be the default (option {key} is {option.status}).")
    others = await db.execute(select(AppearanceOption).where(
        AppearanceOption.character_id == option.character_id,
        AppearanceOption.character_version == option.character_version,
        AppearanceOption.category == option.category,
        AppearanceOption.is_default.is_(True),
        AppearanceOption.id != option.id,
    ))
    for other in others.scalars().all():
        other.is_default = False
    await db.flush()
    option.is_default = True
    await db.commit()
    await db.refresh(option)
    return option


async def seed_ee_f_002_defaults(db: AsyncSession) -> list[AppearanceOption]:
    """Idempotently ensure the EE-F-002 V1.0 canonical look exists as PRODUCTION defaults.

    Existing rows are never changed. A seeded option only becomes the default
    when its category has no default yet.
    """
    seeded = []
    for item in EE_F_002_DEFAULTS:
        key = internal_key("EE-F-002", item["category"], item["option_id"], 1)
        row = await _first(db, select(AppearanceOption).where(AppearanceOption.internal_key == key))
        if row is None:
            has_default = await _first(db, select(AppearanceOption).where(
                AppearanceOption.character_id == "EE-F-002",
                AppearanceOption.character_version == "1.0",
                AppearanceOption.category == item["category"],
                AppearanceOption.is_default.is_(True),
            ))
            row = AppearanceOption(
                internal_key=key, character_id="EE-F-002", character_version="1.0", version=1,
                status=PRODUCTION, is_default=has_default is None, sort_order=0,
                created_by="SYSTEM_SEED", status_changed_by="SYSTEM_SEED", status_changed_at=datetime.utcnow(),
                compatibility_notes="Canonical V1.0 look, part of the EE-F-002 Character Core lock.",
                **item,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
        seeded.append(row)
    return seeded
