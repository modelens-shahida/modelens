"""
Reference sets: the immutable, hashed set of canonical assets that carries a
character version's identity (docs/character-runtime/DESIGN.md sections 2,
3.1 and 8, PR 4).

Lifecycle: DRAFT -> LOCKED -> PRODUCTION -> RETIRED (any non-final status can
be retired). A DRAFT set's items can change; locking copies each asset's
sha256 onto its item and stores ``content_hash`` = sha256 over the ordered
(asset_id, sha256) pairs. From then on the set and its items never change
(ORM rules in app/models/db.py), and the canonical assets in it keep their
file identity. At most one PRODUCTION set per character version: promoting a
set retires the previous one.

``production_set`` is the read the resolver uses (PR 5). It re-checks the
hashes every time and raises ``ReferenceSetIntegrityError`` on any mismatch.
``verify`` additionally re-reads every file from storage and re-hashes it (an
admin check; too slow for every dispatch).

Roles and the EE-F-002 V1 seed are to be confirmed by Aryan/Shahida. The seed
only builds and locks ``EE-F-002_V1.0_REF_V1`` from production-reference
eligible assets; it never promotes. Every write adds an ``audit_logs`` entry in
the same transaction.
"""
import hashlib
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import (
    REFERENCE_SET_TRANSITIONS as TRANSITIONS,
    CanonicalAsset,
    CharacterReferenceSet,
    CharacterReferenceSetItem,
)
from app.services import character_versions as version_service
from app.services.audit import write_audit_log

DRAFT, LOCKED, PRODUCTION, RETIRED = "DRAFT", "LOCKED", "PRODUCTION", "RETIRED"
# To be confirmed by Aryan/Shahida (DESIGN.md section 6: face front, face 3/4, profile, full body front,
# full body 3/4).
ROLES = ("face_front", "face_34", "profile", "body_full", "body_34")
REQUIRED_ROLES = ("face_front", "body_full")

EE_F_002 = "EE-F-002"
# Seed: which eligible V1.0 canonical asset goes into which role, by its framing / angle. To be confirmed
# by Aryan/Shahida.
SEED_ROLE_MATCH = {
    "face_front": {"framings": ("CLOSE_UP", "PORTRAIT", "HEAD", "FACE"), "angles": ("FRONT", "F", "000")},
    "face_34": {"framings": ("CLOSE_UP", "PORTRAIT", "HEAD", "FACE"), "angles": ("L30", "R30", "L45", "R45", "34")},
    "profile": {"framings": ("CLOSE_UP", "PORTRAIT", "HEAD", "FACE"), "angles": ("L90", "R90", "PROFILE")},
    "body_full": {"framings": ("FULL_BODY",), "angles": ("FRONT", "F", "000")},
    "body_34": {"framings": ("FULL_BODY",), "angles": ("L30", "R30", "L45", "R45", "34")},
}


class ReferenceSetNotFound(Exception):
    """HTTP 404."""


class ReferenceSetConflict(Exception):
    """Locked set, skipped lifecycle step, or a duplicate (HTTP 409)."""


class ReferenceSetInvalid(Exception):
    """Well-formed request that breaks a rule (HTTP 400)."""


class ReferenceSetIntegrityError(Exception):
    """A locked set's hashes do not match its items or assets any more."""


def set_id(character_id: str, character_version: str, version: int) -> str:
    return f"{character_id}_V{character_version}_REF_V{version}"


def content_hash(pairs: list[tuple[str, str]]) -> str:
    """sha256 over the ordered (asset_id, sha256) pairs (DESIGN.md 3.1)."""
    digest = hashlib.sha256()
    for asset_id, sha in pairs:
        digest.update(f"{asset_id}:{sha}\n".encode())
    return digest.hexdigest()


async def _audit(db, action: str, ref: CharacterReferenceSet, actor: Optional[str], actor_user_id: Optional[int],
                 from_status: Optional[str], **extra: Any) -> None:
    await write_audit_log(db, action, user_id=actor_user_id, details={
        "actor_email": actor, "reference_set_id": ref.reference_set_id, "character_id": ref.character_id,
        "character_version": ref.character_version, "version": ref.version, "from_status": from_status,
        "to_status": ref.status, **extra,
    })


def _move(ref: CharacterReferenceSet, new_status: str) -> str:
    allowed = TRANSITIONS[ref.status]
    if new_status not in allowed:
        raise ReferenceSetConflict(f"Reference set {ref.reference_set_id} is {ref.status} and cannot move to "
                                   f"{new_status}. Allowed next statuses: {', '.join(sorted(allowed)) or 'none (final)'}.")
    old, ref.status = ref.status, new_status
    return old


# ========================== Reads =================================

async def get_set(db: AsyncSession, reference_set_id: str, character_id: Optional[str] = None) -> CharacterReferenceSet:
    stmt = select(CharacterReferenceSet).where(CharacterReferenceSet.reference_set_id == reference_set_id)
    if character_id:
        stmt = stmt.where(CharacterReferenceSet.character_id == character_id)
    found = (await db.execute(stmt)).scalars().first()
    if not found:
        raise ReferenceSetNotFound(f"Reference set {reference_set_id} not found.")
    return found


async def list_sets(db: AsyncSession, character_id: str, character_version: Optional[str] = None,
                    status: Optional[str] = None) -> list[CharacterReferenceSet]:
    stmt = select(CharacterReferenceSet).where(CharacterReferenceSet.character_id == character_id).order_by(
        CharacterReferenceSet.character_version, CharacterReferenceSet.version)
    if character_version:
        stmt = stmt.where(CharacterReferenceSet.character_version == character_version)
    if status:
        stmt = stmt.where(CharacterReferenceSet.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def items(db: AsyncSession, ref: CharacterReferenceSet) -> list[CharacterReferenceSetItem]:
    return list((await db.execute(select(CharacterReferenceSetItem).where(
        CharacterReferenceSetItem.reference_set_id == ref.id).order_by(
        CharacterReferenceSetItem.sort_order, CharacterReferenceSetItem.role,
        CharacterReferenceSetItem.id))).scalars().all())


async def _assets(db: AsyncSession, set_items: list[CharacterReferenceSetItem]) -> dict[int, CanonicalAsset]:
    ids = [i.canonical_asset_id for i in set_items]
    if not ids:
        return {}
    rows = (await db.execute(select(CanonicalAsset).where(CanonicalAsset.id.in_(ids)))).scalars().all()
    return {a.id: a for a in rows}


async def check_integrity(db: AsyncSession, ref: CharacterReferenceSet) -> list[CharacterReferenceSetItem]:
    """The items of a locked set, after checking that the set hash matches the items and each item's hash
    matches its canonical asset's current hash. Raises ReferenceSetIntegrityError."""
    set_items = await items(db, ref)
    if not set_items or not ref.content_hash:
        raise ReferenceSetIntegrityError(f"Reference set {ref.reference_set_id} has no locked content.")
    if content_hash([(i.asset_id, i.content_hash_sha256 or "") for i in set_items]) != ref.content_hash:
        raise ReferenceSetIntegrityError(f"Reference set {ref.reference_set_id}: set hash does not match its items.")
    assets = await _assets(db, set_items)
    for item in set_items:
        asset = assets.get(item.canonical_asset_id)
        if asset is None or asset.asset_id != item.asset_id or asset.content_hash_sha256 != item.content_hash_sha256:
            raise ReferenceSetIntegrityError(
                f"Reference set {ref.reference_set_id}: asset {item.asset_id} ({item.role}) no longer matches.")
    return set_items


async def production_set(db: AsyncSession, character_id: str,
                         character_version: str) -> tuple[CharacterReferenceSet, list[CharacterReferenceSetItem]]:
    """The PRODUCTION set of a character version and its items, hash-checked (the resolver read, PR 5)."""
    found = (await db.execute(select(CharacterReferenceSet).where(
        CharacterReferenceSet.character_id == character_id,
        CharacterReferenceSet.character_version == character_version,
        CharacterReferenceSet.status == PRODUCTION))).scalars().first()
    if found is None:
        raise ReferenceSetNotFound(f"{character_id} version {character_version} has no production reference set.")
    return found, await check_integrity(db, found)


async def verify(db: AsyncSession, ref: CharacterReferenceSet, read_bytes) -> dict:
    """Deep check: the hashes (as check_integrity) plus every file re-read with ``read_bytes(storage_path)``
    and re-hashed. Returns {ok, problems: [...]}, never raises for a mismatch."""
    problems: list[str] = []
    if ref.status == DRAFT:
        return {"ok": False, "problems": ["The set is DRAFT; lock it first."]}
    try:
        set_items = await check_integrity(db, ref)
    except ReferenceSetIntegrityError as exc:
        return {"ok": False, "problems": [str(exc)]}
    assets = await _assets(db, set_items)
    for item in set_items:
        asset = assets[item.canonical_asset_id]
        try:
            data = read_bytes(asset.storage_path)
        except Exception:
            problems.append(f"{item.asset_id} ({item.role}): file could not be read.")
            continue
        if hashlib.sha256(data).hexdigest() != item.content_hash_sha256:
            problems.append(f"{item.asset_id} ({item.role}): file content does not match its locked hash.")
    return {"ok": not problems, "problems": problems}


# ========================== Writes ================================

async def create_set(db: AsyncSession, *, character_id: str, character_version: str, items_in: list[dict],
                     created_by: Optional[str] = None, actor_user_id: Optional[int] = None) -> CharacterReferenceSet:
    """A DRAFT set with the next version number. ``items_in``: [{canonical_asset_id, role}] in display order;
    canonical_asset_id is the canonical asset's ``asset_id``."""
    try:
        await version_service.get_version(db, character_id, character_version)
    except version_service.CharacterVersionNotFound as exc:
        raise ReferenceSetNotFound(str(exc))
    if not items_in:
        raise ReferenceSetInvalid("A reference set needs at least one item.")
    asset_ids = [str(i.get("canonical_asset_id")) for i in items_in]
    if len(set(asset_ids)) != len(asset_ids):
        raise ReferenceSetInvalid("Each canonical asset can be in a set only once.")
    rows = {a.asset_id: a for a in (await db.execute(select(CanonicalAsset).where(
        CanonicalAsset.asset_id.in_(asset_ids)))).scalars().all()}
    for item in items_in:
        role, asset = item.get("role"), rows.get(str(item.get("canonical_asset_id")))
        if role not in ROLES:
            raise ReferenceSetInvalid(f"role must be one of {', '.join(ROLES)}.")
        if asset is None:
            raise ReferenceSetNotFound(f"Canonical asset {item.get('canonical_asset_id')} not found.")
        if (asset.character_id, asset.version) != (character_id, character_version):
            raise ReferenceSetInvalid(f"Canonical asset {asset.asset_id} belongs to {asset.character_id} version "
                                      f"{asset.version}, not {character_id} version {character_version}.")
        if not asset.production_reference_eligible:
            raise ReferenceSetInvalid(f"Canonical asset {asset.asset_id} is not production-reference eligible.")
        if not asset.content_hash_sha256:
            raise ReferenceSetInvalid(f"Canonical asset {asset.asset_id} has no content hash.")

    latest = (await db.execute(select(func.max(CharacterReferenceSet.version)).where(
        CharacterReferenceSet.character_id == character_id,
        CharacterReferenceSet.character_version == character_version))).scalar() or 0
    ref = CharacterReferenceSet(reference_set_id=set_id(character_id, character_version, latest + 1),
                                character_id=character_id, character_version=character_version, version=latest + 1,
                                status=DRAFT, created_by=created_by)
    db.add(ref)
    await db.flush()
    for order, item in enumerate(items_in):
        asset = rows[str(item["canonical_asset_id"])]
        db.add(CharacterReferenceSetItem(reference_set_id=ref.id, canonical_asset_id=asset.id, asset_id=asset.asset_id,
                                         role=item["role"], sort_order=order))
    await db.flush()
    await _audit(db, "reference_set_created", ref, created_by, actor_user_id, None,
                 items=[{"asset_id": str(i["canonical_asset_id"]), "role": i["role"]} for i in items_in])
    await db.commit()
    await db.refresh(ref)
    return ref


async def lock(db: AsyncSession, ref: CharacterReferenceSet, locked_by: str,
               actor_user_id: Optional[int] = None) -> CharacterReferenceSet:
    """DRAFT -> LOCKED: copy each asset's hash onto its item and store the set hash. Needs face_front and
    body_full, current eligible assets with hashes, and a LOCKED character version."""
    if ref.status != DRAFT:
        raise ReferenceSetConflict(f"Reference set {ref.reference_set_id} is {ref.status}; only DRAFT sets can be "
                                   "locked.")
    version = await version_service.get_version(db, ref.character_id, ref.character_version)
    if not version_service.is_locked(version):
        raise ReferenceSetConflict(f"{ref.character_id} version {ref.character_version} is not LOCKED; lock the "
                                   "character version first.")
    set_items = await items(db, ref)
    missing = [r for r in REQUIRED_ROLES if r not in {i.role for i in set_items}]
    if missing:
        raise ReferenceSetInvalid(f"A reference set needs {', '.join(missing)} before it can be locked.")
    assets = await _assets(db, set_items)
    for item in set_items:
        asset = assets[item.canonical_asset_id]
        if not asset.production_reference_eligible or not asset.content_hash_sha256:
            raise ReferenceSetInvalid(f"Canonical asset {asset.asset_id} is no longer eligible or has no hash.")
        item.content_hash_sha256 = asset.content_hash_sha256
    await db.flush()  # items first: they are frozen once the set is LOCKED
    ref.content_hash = content_hash([(i.asset_id, i.content_hash_sha256) for i in set_items])
    old = _move(ref, LOCKED)
    ref.locked_at, ref.locked_by = datetime.utcnow(), locked_by
    await _audit(db, "reference_set_locked", ref, locked_by, actor_user_id, old, content_hash=ref.content_hash)
    await db.commit()
    await db.refresh(ref)
    return ref


async def promote(db: AsyncSession, ref: CharacterReferenceSet, promoted_by: str,
                  actor_user_id: Optional[int] = None) -> tuple[CharacterReferenceSet, Optional[CharacterReferenceSet]]:
    """LOCKED -> PRODUCTION after a hash check; retires the previous PRODUCTION set of the character version."""
    if ref.status != LOCKED:
        raise ReferenceSetConflict(f"Reference set {ref.reference_set_id} is {ref.status}; only LOCKED sets can be "
                                   "promoted.")
    try:
        await check_integrity(db, ref)
    except ReferenceSetIntegrityError as exc:
        raise ReferenceSetConflict(str(exc))
    now = datetime.utcnow()
    replaced = (await db.execute(select(CharacterReferenceSet).where(
        CharacterReferenceSet.character_id == ref.character_id,
        CharacterReferenceSet.character_version == ref.character_version,
        CharacterReferenceSet.status == PRODUCTION))).scalars().first()
    if replaced is not None:
        old = _move(replaced, RETIRED)
        replaced.retired_at, replaced.retired_by = now, promoted_by
        replaced.retire_reason = f"Replaced by {ref.reference_set_id}."
        await _audit(db, "reference_set_retired", replaced, promoted_by, actor_user_id, old,
                     reason=replaced.retire_reason)
        await db.flush()  # free the one-PRODUCTION slot first
    old = _move(ref, PRODUCTION)
    ref.promoted_at, ref.promoted_by = now, promoted_by
    await _audit(db, "reference_set_promoted", ref, promoted_by, actor_user_id, old,
                 replaced=replaced.reference_set_id if replaced else None)
    await db.commit()
    await db.refresh(ref)
    return ref, replaced


async def retire(db: AsyncSession, ref: CharacterReferenceSet, retired_by: str, reason: str,
                 actor_user_id: Optional[int] = None) -> CharacterReferenceSet:
    if not (reason or "").strip():
        raise ReferenceSetInvalid("A reason is required to retire a reference set.")
    old = _move(ref, RETIRED)
    ref.retired_at, ref.retired_by, ref.retire_reason = datetime.utcnow(), retired_by, reason.strip()
    await _audit(db, "reference_set_retired", ref, retired_by, actor_user_id, old, reason=ref.retire_reason)
    await db.commit()
    await db.refresh(ref)
    return ref


# ========================== EE-F-002 V1 seed =====================

def _seed_picks(assets: list[CanonicalAsset]) -> list[dict]:
    """One asset per role (first match by framing and angle, then by asset id), in ROLES order."""
    picks, used = [], set()
    for role in ROLES:
        rule = SEED_ROLE_MATCH[role]
        for asset in sorted(assets, key=lambda a: a.asset_id):
            if asset.asset_id in used:
                continue
            if (asset.framing or "").upper() in rule["framings"] and (asset.angle_code or "").upper() in rule["angles"]:
                picks.append({"canonical_asset_id": asset.asset_id, "role": role})
                used.add(asset.asset_id)
                break
    return picks


async def seed_ee_f_002_reference_set(db: AsyncSession, seeded_by: str,
                                      actor_user_id: Optional[int] = None) -> tuple[CharacterReferenceSet, bool]:
    """Build and lock EE-F-002_V1.0_REF_V1 from V1.0's production-reference eligible assets with a hash.
    Idempotent: an existing V1 set is returned unchanged (created=False). Never promotes. Raises
    ReferenceSetInvalid when face_front or body_full has no eligible asset."""
    ref_id = set_id(EE_F_002, "1.0", 1)
    existing = (await db.execute(select(CharacterReferenceSet).where(
        CharacterReferenceSet.reference_set_id == ref_id))).scalars().first()
    if existing is not None:
        return existing, False
    eligible = (await db.execute(select(CanonicalAsset).where(
        CanonicalAsset.character_id == EE_F_002, CanonicalAsset.version == "1.0",
        CanonicalAsset.production_reference_eligible.is_(True),
        CanonicalAsset.content_hash_sha256.isnot(None)))).scalars().all()
    picks = _seed_picks(list(eligible))
    missing = [r for r in REQUIRED_ROLES if r not in {p["role"] for p in picks}]
    if missing:
        raise ReferenceSetInvalid(f"No production-reference eligible EE-F-002 V1.0 asset for {', '.join(missing)}; "
                                  "nothing was created.")
    ref = await create_set(db, character_id=EE_F_002, character_version="1.0", items_in=picks, created_by=seeded_by,
                           actor_user_id=actor_user_id)
    return await lock(db, ref, seeded_by, actor_user_id), True
