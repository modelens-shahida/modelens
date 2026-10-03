"""Character Version Registry: EE-F-002 V1.0 seed and LOCKED immutability."""
import pytest
import pytest_asyncio
from sqlalchemy import select, text, update, func

from app.main import app
from app.middleware.auth import create_access_token, hash_password
from app.models.db import (
    CharacterRegistryVersion,
    CharacterRuntimeV2,
    CharacterV2,
    CharacterVersionLockedError,
    User,
)
from app.services import character_versions as version_service

BASE = "/api/v1/characters-v2/EE-F-002"

CUSTOMER_FIELDS = {
    "character_id", "display_name", "character_version", "status",
    "canonical_height_cm", "stature", "body_archetype", "locked_at",
}
TECHNICAL_TERMS = (
    "adapter", "checkpoint", "seed", "workflow", "provider", "lora",
    "strength", "training", "evaluation", "score", "locked_by", "runtime",
)


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}


@pytest_asyncio.fixture
async def users(db_session):
    created = {
        "platform_admin": User(email="platform-admin@modelens.ai", hashed_password=hash_password("pw"), full_name="Platform Admin", role="admin"),
        "customer": User(email="customer@brand.com", hashed_password=hash_password("pw"), full_name="Customer", role="user"),
    }
    db_session.add_all(created.values())
    await db_session.commit()
    return created


@pytest_asyncio.fixture
async def seeded(db_session):
    return await version_service.seed_ee_f_002_v1(db_session)


async def _db_row(db_session, version="1.0"):
    """Read the row straight from the database, bypassing the identity map."""
    result = await db_session.execute(
        text(
            "SELECT status, locked, locked_at, locked_by, canonical_height_cm, stature, body_archetype "
            "FROM character_registry_versions WHERE character_id = 'EE-F-002' AND version = :v"
        ),
        {"v": version},
    )
    return result.mappings().first()


# ========================== Seed ==================================

@pytest.mark.asyncio
async def test_ee_f_002_v1_exists_locked_with_exact_values(db_session, seeded):
    row = await _db_row(db_session)
    assert row is not None
    assert row["status"] == "LOCKED"
    assert bool(row["locked"]) is True
    assert row["canonical_height_cm"] == 178
    assert row["stature"] == "TALL"
    assert row["body_archetype"] == "HIGH_FASHION_RUNWAY_SLIM"
    assert row["locked_at"] is not None
    assert row["locked_by"] == "SYSTEM_SEED"


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session, seeded):
    before = dict(await _db_row(db_session))
    again = await version_service.seed_ee_f_002_v1(db_session)
    await version_service.seed_ee_f_002_v1(db_session)

    count = await db_session.scalar(
        select(func.count()).select_from(CharacterRegistryVersion).where(
            CharacterRegistryVersion.character_id == "EE-F-002"
        )
    )
    assert count == 1
    assert again.id == seeded.id
    assert dict(await _db_row(db_session)) == before


@pytest.mark.asyncio
async def test_seed_completes_and_locks_existing_unlocked_draft(db_session):
    db_session.add(CharacterRegistryVersion(character_id="EE-F-002", version="1.0", status="DRAFT", locked=False))
    await db_session.commit()

    await version_service.seed_ee_f_002_v1(db_session)

    row = await _db_row(db_session)
    assert row["status"] == "LOCKED" and bool(row["locked"])
    assert row["canonical_height_cm"] == 178


# ========================== Immutability ==========================

@pytest.mark.asyncio
async def test_update_of_locked_version_rejected_via_api(client, db_session, users, seeded):
    before = dict(await _db_row(db_session))
    resp = await client.patch(
        f"{BASE}/versions/1.0", json={"canonical_height_cm": 180}, headers=_headers(users["platform_admin"])
    )
    assert resp.status_code == 409
    assert "LOCKED" in resp.json()["detail"]
    assert dict(await _db_row(db_session)) == before


@pytest.mark.asyncio
async def test_delete_of_locked_version_rejected_via_api(client, db_session, users, seeded):
    resp = await client.delete(f"{BASE}/versions/1.0", headers=_headers(users["platform_admin"]))
    assert resp.status_code == 409
    assert await _db_row(db_session) is not None


@pytest.mark.asyncio
async def test_patch_cannot_touch_status_or_lock_fields(client, users, seeded):
    resp = await client.patch(
        f"{BASE}/versions/1.0", json={"locked": False, "status": "DRAFT"}, headers=_headers(users["platform_admin"])
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("canonical_height_cm", 180.0),
    ("stature", "PETITE"),
    ("body_archetype", "ATHLETIC"),
    ("locked", False),
    ("status", "DRAFT"),
])
async def test_orm_guard_rejects_direct_update_of_locked_version(db_session, seeded, field, value):
    before = dict(await _db_row(db_session))
    setattr(seeded, field, value)
    with pytest.raises(CharacterVersionLockedError):
        await db_session.commit()
    await db_session.rollback()
    assert dict(await _db_row(db_session)) == before


@pytest.mark.asyncio
async def test_orm_guard_rejects_direct_delete_of_locked_version(db_session, seeded):
    await db_session.delete(seeded)
    with pytest.raises(CharacterVersionLockedError):
        await db_session.commit()
    await db_session.rollback()
    assert await _db_row(db_session) is not None


@pytest.mark.asyncio
async def test_orm_guard_rejects_bulk_update(db_session, seeded):
    with pytest.raises(CharacterVersionLockedError):
        await db_session.execute(
            update(CharacterRegistryVersion)
            .where(CharacterRegistryVersion.character_id == "EE-F-002")
            .values(canonical_height_cm=150)
        )
    await db_session.rollback()
    assert (await _db_row(db_session))["canonical_height_cm"] == 178


@pytest.mark.asyncio
async def test_non_core_fields_stay_editable_on_locked_version(db_session, seeded):
    seeded.promoted_to_production = True
    seeded.qa_snapshot = {"identity_gate": "PASS"}
    await db_session.commit()
    assert (await _db_row(db_session))["status"] == "LOCKED"


@pytest.mark.asyncio
async def test_relock_rejected(client, users, seeded):
    resp = await client.post(f"{BASE}/versions/1.0/lock", headers=_headers(users["platform_admin"]))
    assert resp.status_code == 409


# ========================== New versions ==========================

@pytest.mark.asyncio
async def test_new_version_starts_draft_and_leaves_v1_unchanged(client, db_session, users, seeded):
    admin = _headers(users["platform_admin"])
    before = dict(await _db_row(db_session))

    resp = await client.post(
        f"{BASE}/versions",
        json={"character_version": "1.1", "canonical_height_cm": 179, "release_notes": "re-measured"},
        headers=admin,
    )
    assert resp.status_code == 201, resp.text
    draft = resp.json()
    assert draft["character_version"] == "1.1"
    assert draft["status"] == "DRAFT"
    assert draft["locked"] is False
    assert draft["parent_version"] == "1.0"
    assert draft["canonical_height_cm"] == 179
    # Untouched fields are copied from the parent.
    assert draft["stature"] == "TALL"
    assert draft["body_archetype"] == "HIGH_FASHION_RUNWAY_SLIM"

    # Drafts are editable.
    resp = await client.patch(f"{BASE}/versions/1.1", json={"stature": "VERY_TALL"}, headers=admin)
    assert resp.status_code == 200
    assert resp.json()["stature"] == "VERY_TALL"

    assert dict(await _db_row(db_session)) == before

    resp = await client.get(f"{BASE}/versions", headers=admin)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert [v["character_version"] for v in body["versions"]] == ["1.1", "1.0"]


@pytest.mark.asyncio
async def test_lock_new_version_makes_it_current_and_immutable(client, db_session, users, seeded):
    admin = _headers(users["platform_admin"])
    await client.post(f"{BASE}/versions", json={"character_version": "2.0", "canonical_height_cm": 177}, headers=admin)

    resp = await client.post(f"{BASE}/versions/2.0/lock", headers=admin)
    assert resp.status_code == 200
    locked = resp.json()
    assert locked["status"] == "LOCKED" and locked["locked"] is True
    assert locked["locked_by"] == str(users["platform_admin"].id)
    assert locked["locked_at"]

    resp = await client.patch(f"{BASE}/versions/2.0", json={"canonical_height_cm": 170}, headers=admin)
    assert resp.status_code == 409

    resp = await client.get(f"{BASE}/current-version", headers=_headers(users["customer"]))
    assert resp.json()["character_version"] == "2.0"
    assert (await _db_row(db_session, "1.0"))["canonical_height_cm"] == 178


@pytest.mark.asyncio
async def test_draft_can_be_deleted(client, db_session, users, seeded):
    admin = _headers(users["platform_admin"])
    await client.post(f"{BASE}/versions", json={"character_version": "1.1"}, headers=admin)
    resp = await client.delete(f"{BASE}/versions/1.1", headers=admin)
    assert resp.status_code == 200
    assert resp.json() == {"character_id": "EE-F-002", "character_version": "1.1", "deleted": True}
    assert await _db_row(db_session, "1.1") is None


@pytest.mark.asyncio
async def test_lock_requires_core_fields(client, users):
    admin = _headers(users["platform_admin"])
    await client.post("/api/v1/characters-v2/EE-F-099/versions", json={"character_version": "0.1"}, headers=admin)
    resp = await client.post("/api/v1/characters-v2/EE-F-099/versions/0.1/lock", headers=admin)
    assert resp.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("payload,expected", [
    ({"character_version": "1.0"}, 409),
    ({"character_version": "0.9"}, 400),
    ({"character_version": "1.1", "based_on_version": "7.0"}, 404),
    ({"character_version": "v1.1"}, 422),
])
async def test_create_version_validation(client, users, seeded, payload, expected):
    resp = await client.post(f"{BASE}/versions", json=payload, headers=_headers(users["platform_admin"]))
    assert resp.status_code == expected, resp.text


@pytest.mark.asyncio
async def test_legacy_version_field_alias_accepted(client, users, seeded):
    resp = await client.post(f"{BASE}/versions", json={"version": "1.1"}, headers=_headers(users["platform_admin"]))
    assert resp.status_code == 201
    assert resp.json()["character_version"] == "1.1"


@pytest.mark.asyncio
async def test_promote_keeps_version_locked(client, db_session, users, seeded):
    resp = await client.post(f"{BASE}/promote", params={"version": "1.0"}, headers=_headers(users["platform_admin"]))
    assert resp.status_code == 200
    row = await _db_row(db_session)
    assert row["status"] == "LOCKED" and row["canonical_height_cm"] == 178


# ========================== Access control ========================

@pytest.mark.asyncio
async def test_non_admin_cannot_create_lock_or_edit_versions(client, db_session, users, seeded, test_data):
    await client.post(f"{BASE}/versions", json={"character_version": "1.1"}, headers=_headers(users["platform_admin"]))

    # A regular customer and a brand admin are both non-platform-admins.
    for headers in (_headers(users["customer"]), test_data["get_headers"]("admin")):
        assert (await client.post(f"{BASE}/versions", json={"character_version": "1.2"}, headers=headers)).status_code == 403
        assert (await client.post(f"{BASE}/versions/1.1/lock", headers=headers)).status_code == 403
        assert (await client.post(f"{BASE}/lock", params={"version": "1.1"}, headers=headers)).status_code == 403
        assert (await client.patch(f"{BASE}/versions/1.1", json={"stature": "X"}, headers=headers)).status_code == 403
        assert (await client.delete(f"{BASE}/versions/1.1", headers=headers)).status_code == 403
        assert (await client.get(f"{BASE}/versions", headers=headers)).status_code == 403
        assert (await client.get(f"{BASE}/versions/1.0", headers=headers)).status_code == 403

    assert (await client.post(f"{BASE}/versions", json={"character_version": "1.2"})).status_code == 401
    assert (await _db_row(db_session, "1.1"))["status"] == "DRAFT"
    assert await _db_row(db_session, "1.2") is None


# ========================== Customer endpoint =====================

@pytest.mark.asyncio
async def test_customer_endpoint_returns_only_safe_fields(client, db_session, users, seeded):
    db_session.add(CharacterV2(character_id="EE-F-002", display_name="Eliska Novak"))
    db_session.add(CharacterRuntimeV2(
        runtime_id="RT-EE-F-002-1.0", character_id="EE-F-002", version="1.0",
        production_model_alias="eliska_lora_v1_ckpt", default_strength=0.78,
        approved_workflows=["WF-PORTRAIT"], golden_reference_set={"seed": 1234},
    ))
    await db_session.commit()

    resp = await client.get(f"{BASE}/current-version", headers=_headers(users["customer"]))
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == CUSTOMER_FIELDS
    assert data["display_name"] == "Eliska Novak"
    assert data["character_version"] == "1.0"
    assert data["status"] == "LOCKED"
    assert data["canonical_height_cm"] == 178
    assert data["stature"] == "TALL"
    assert data["body_archetype"] == "HIGH_FASHION_RUNWAY_SLIM"

    raw = resp.text.lower()
    for term in TECHNICAL_TERMS + ("eliska_lora", "wf-portrait"):
        assert term not in raw, f"customer response leaks {term!r}"


@pytest.mark.asyncio
async def test_customer_endpoint_ignores_drafts_and_404s_without_lock(client, users, seeded):
    admin = _headers(users["platform_admin"])
    await client.post(f"{BASE}/versions", json={"character_version": "1.1"}, headers=admin)

    resp = await client.get(f"{BASE}/current-version", headers=_headers(users["customer"]))
    assert resp.json()["character_version"] == "1.0"

    resp = await client.get("/api/v1/characters-v2/EE-F-404/current-version", headers=_headers(users["customer"]))
    assert resp.status_code == 404
    assert (await client.get(f"{BASE}/current-version")).status_code == 401


def test_customer_schema_has_no_technical_fields():
    schema = app.openapi()["components"]["schemas"]["CustomerCharacterVersion"]
    assert set(schema["properties"]) == CUSTOMER_FIELDS
    for name in schema["properties"]:
        assert not any(term in name for term in TECHNICAL_TERMS)
