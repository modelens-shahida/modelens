"""
Character Version Registry service.

A character version freezes the Character Core (who the character is:
height, stature, body archetype). Once a version is LOCKED it can never be
changed or deleted; changes go into a NEW version that starts as DRAFT.

The rules are enforced twice:
  * here, so callers get a clear error before anything is written, and
  * by ORM guards on ``CharacterRegistryVersion`` (app.models.db), so no
    other code path can change a locked row either.
"""
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import CharacterRegistryVersion, CharacterVersionLockedError

STATUS_DRAFT = "DRAFT"
STATUS_LOCKED = "LOCKED"

EDITABLE_CORE_FIELDS = ("canonical_height_cm", "stature", "body_archetype", "taxonomy_version", "release_notes")
REQUIRED_TO_LOCK = ("canonical_height_cm", "stature", "body_archetype")

VERSION_PATTERN = re.compile(r"^\d+\.\d+$")

# EE-F-002 (Eliska Novak) V1.0 — the locked flagship Character Core.
EE_F_002_V1 = {
    "character_id": "EE-F-002",
    "version": "1.0",
    "status": STATUS_LOCKED,
    "locked": True,
    "canonical_height_cm": 178.0,
    "stature": "TALL",
    "body_archetype": "HIGH_FASHION_RUNWAY_SLIM",
    "locked_by": "SYSTEM_SEED",
    "release_notes": "EE-F-002 Eliska Novak V1.0 Character Core lock.",
}


class CharacterVersionNotFound(Exception):
    pass


class CharacterVersionConflict(Exception):
    """Invalid state transition or duplicate version (HTTP 409)."""


class CharacterVersionInvalid(Exception):
    """Well-formed request that breaks a business rule (HTTP 400)."""


def version_key(version: str) -> tuple[int, ...]:
    """Numeric sort key, so 1.10 sorts after 1.9 (non-numeric parts sort as 0)."""
    return tuple(int(part) if part.isdigit() else 0 for part in version.split("."))


def is_locked(version: CharacterRegistryVersion) -> bool:
    return bool(version.locked) or version.status == STATUS_LOCKED


async def list_versions(db: AsyncSession, character_id: str) -> list[CharacterRegistryVersion]:
    result = await db.execute(
        select(CharacterRegistryVersion).where(CharacterRegistryVersion.character_id == character_id)
    )
    return sorted(result.scalars().all(), key=lambda v: version_key(v.version), reverse=True)


async def get_version(db: AsyncSession, character_id: str, version: str) -> CharacterRegistryVersion:
    result = await db.execute(
        select(CharacterRegistryVersion).where(
            CharacterRegistryVersion.character_id == character_id,
            CharacterRegistryVersion.version == version,
        )
    )
    found = result.scalars().first()
    if not found:
        raise CharacterVersionNotFound(f"Character {character_id} version {version} not found.")
    return found


async def get_current_locked_version(db: AsyncSession, character_id: str) -> CharacterRegistryVersion:
    locked = [v for v in await list_versions(db, character_id) if is_locked(v)]
    if not locked:
        raise CharacterVersionNotFound(f"Character {character_id} has no locked version.")
    return locked[0]


async def create_draft_version(
    db: AsyncSession,
    character_id: str,
    version: str,
    based_on: Optional[str] = None,
    **fields: Any,
) -> CharacterRegistryVersion:
    """Create a new DRAFT version, copying the Character Core from ``based_on``
    (default: the latest existing version) and applying ``fields`` on top."""
    if not VERSION_PATTERN.match(version):
        raise CharacterVersionInvalid("Version must look like MAJOR.MINOR, e.g. 1.1 or 2.0.")

    existing = await list_versions(db, character_id)
    if any(v.version == version for v in existing):
        raise CharacterVersionConflict(f"Character {character_id} version {version} already exists.")
    if existing and version_key(version) <= version_key(existing[0].version):
        raise CharacterVersionInvalid(
            f"New version must be greater than the latest version {existing[0].version}."
        )

    parent = None
    if based_on:
        parent = await get_version(db, character_id, based_on)
    elif existing:
        parent = existing[0]

    draft = CharacterRegistryVersion(
        character_id=character_id,
        version=version,
        status=STATUS_DRAFT,
        locked=False,
        parent_version=parent.version if parent else None,
        canonical_height_cm=parent.canonical_height_cm if parent else None,
        stature=parent.stature if parent else None,
        body_archetype=parent.body_archetype if parent else None,
        taxonomy_version=parent.taxonomy_version if parent else None,
    )
    for field, value in fields.items():
        if field in EDITABLE_CORE_FIELDS and value is not None:
            setattr(draft, field, value)

    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return draft


async def update_draft_version(
    db: AsyncSession, character_id: str, version: str, **fields: Any
) -> CharacterRegistryVersion:
    target = await get_version(db, character_id, version)
    if is_locked(target):
        raise CharacterVersionLockedError(character_id, version, "modified")
    for field, value in fields.items():
        if field in EDITABLE_CORE_FIELDS and value is not None:
            setattr(target, field, value)
    await db.commit()
    await db.refresh(target)
    return target


async def delete_draft_version(db: AsyncSession, character_id: str, version: str) -> None:
    target = await get_version(db, character_id, version)
    if is_locked(target):
        raise CharacterVersionLockedError(character_id, version, "deleted")
    await db.delete(target)
    await db.commit()


async def lock_version(
    db: AsyncSession, character_id: str, version: str, locked_by: str
) -> CharacterRegistryVersion:
    """One-way DRAFT -> LOCKED transition."""
    target = await get_version(db, character_id, version)
    if is_locked(target):
        raise CharacterVersionConflict(f"Character {character_id} version {version} is already LOCKED.")
    missing = [f for f in REQUIRED_TO_LOCK if getattr(target, f) in (None, "")]
    if missing:
        raise CharacterVersionInvalid(f"Cannot lock: missing Character Core fields {missing}.")

    target.locked = True
    target.status = STATUS_LOCKED
    target.locked_at = datetime.utcnow()
    target.locked_by = locked_by
    await db.commit()
    await db.refresh(target)
    return target


async def seed_ee_f_002_v1(db: AsyncSession) -> CharacterRegistryVersion:
    """Idempotently ensure EE-F-002 V1.0 exists and is LOCKED.

    A locked row is never touched. A pre-existing unlocked 1.0 draft is
    completed with the canonical values and locked. Nothing else is changed.
    """
    seed = EE_F_002_V1
    result = await db.execute(
        select(CharacterRegistryVersion).where(
            CharacterRegistryVersion.character_id == seed["character_id"],
            CharacterRegistryVersion.version == seed["version"],
        )
    )
    row = result.scalars().first()
    if row is not None and is_locked(row):
        return row

    if row is None:
        row = CharacterRegistryVersion(character_id=seed["character_id"], version=seed["version"])
        db.add(row)
    for field, value in seed.items():
        setattr(row, field, value)
    row.locked_at = datetime.utcnow()
    await db.commit()
    await db.refresh(row)
    return row
