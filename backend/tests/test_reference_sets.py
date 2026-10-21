"""Reference sets (Character Runtime PR 4): lifecycle, immutability, hash checks at resolve, verify, seed,
admin API, audit log, migration. Test-only canonical assets with real files in local storage; no network."""
import hashlib
import importlib.util
import os
import uuid

import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

import app.models.db as models
from app.middleware.auth import create_access_token, hash_password
from app.migration_guard import table_differences
from app.models.db import (
    AuditLog, CanonicalAsset, CharacterReferenceSet, CharacterReferenceSetItem, ReferenceSetLockedError, User,
)
from app.services import character_versions as version_service
from app.services import reference_sets as rs
from app.services.storage import storage_service
from customer_safety import assert_customer_safe
from test_capability_validations import CUSTOMER_ROUTES

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATION = os.path.join(BACKEND, "alembic", "versions", "reference_sets_001.py")
BASE = "/api/v1/admin/characters/EE-F-002/reference-sets"
EE = "EE-F-002"
# (asset_id, framing, angle_code): one per role, in the seed's matching vocabulary.
ASSETS = (("CA-FACE-FRONT", "CLOSE_UP", "FRONT"), ("CA-FACE-34", "CLOSE_UP", "L30"), ("CA-PROFILE", "CLOSE_UP", "L90"),
          ("CA-BODY-FULL", "FULL_BODY", "FRONT"), ("CA-BODY-34", "FULL_BODY", "R30"))
ROLE_OF = {"CA-FACE-FRONT": "face_front", "CA-FACE-34": "face_34", "CA-PROFILE": "profile",
           "CA-BODY-FULL": "body_full", "CA-BODY-34": "body_34"}


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}


async def _asset(db, asset_id, framing="CLOSE_UP", angle="FRONT", *, version="1.0", eligible=True, hashed=True):
    data = f"{asset_id}-{uuid.uuid4().hex}".encode()
    path = storage_service.save_file_bytes(f"test-reference-sets/{uuid.uuid4().hex}/{asset_id}.png", data)
    asset = CanonicalAsset(asset_id=asset_id, character_id=EE, version=version, asset_role="GOLDEN_IDENTITY",
                           framing=framing, angle_code=angle, storage_path=path,
                           content_hash_sha256=hashlib.sha256(data).hexdigest() if hashed else None,
                           production_reference_eligible=eligible)
    db.add(asset)
    await db.commit()
    return asset


@pytest_asyncio.fixture
async def world(db_session):
    users = {
        "admin": User(email="platform-admin@modelens.ai", hashed_password=hash_password("pw"), full_name="Admin",
                      role="admin"),
        "owner": User(email="owner@brand.com", hashed_password=hash_password("pw"), full_name="Owner", role="user"),
    }
    db_session.add_all(users.values())
    await db_session.commit()
    await version_service.seed_ee_f_002_v1(db_session)
    assets = {a: await _asset(db_session, a, framing, angle) for a, framing, angle in ASSETS}
    return {"users": users, "assets": assets, "h": {k: _headers(u) for k, u in users.items()}}


def _items(*asset_ids):
    return [{"canonical_asset_id": a, "role": ROLE_OF[a]} for a in asset_ids]


ALL = tuple(a for a, _, _ in ASSETS)


async def _locked(db, *asset_ids):
    ref = await rs.create_set(db, character_id=EE, character_version="1.0", items_in=_items(*(asset_ids or ALL)),
                              created_by="admin@modelens.ai")
    return await rs.lock(db, ref, "admin@modelens.ai")


async def _audit(db):
    return list((await db.execute(select(AuditLog).where(AuditLog.action.like("reference_set_%"))
                                  .order_by(AuditLog.id))).scalars().all())


# ========================== Lifecycle =============================

@pytest.mark.asyncio
async def test_create_lock_promote_retire(db_session, world):
    ref = await rs.create_set(db_session, character_id=EE, character_version="1.0", items_in=_items(*ALL),
                              created_by="admin@modelens.ai")
    assert (ref.reference_set_id, ref.version, ref.status, ref.content_hash) == ("EE-F-002_V1.0_REF_V1", 1, "DRAFT",
                                                                                   None)
    ref = await rs.lock(db_session, ref, "anshu@modelens.ai")
    items = await rs.items(db_session, ref)
    assert [i.role for i in items] == ["face_front", "face_34", "profile", "body_full", "body_34"]
    assert all(i.content_hash_sha256 == world["assets"][i.asset_id].content_hash_sha256 for i in items)
    assert ref.content_hash == rs.content_hash([(i.asset_id, i.content_hash_sha256) for i in items])
    assert (ref.status, ref.locked_by) == ("LOCKED", "anshu@modelens.ai") and ref.locked_at

    ref, replaced = await rs.promote(db_session, ref, "anshu@modelens.ai")
    assert (ref.status, ref.promoted_by, replaced) == ("PRODUCTION", "anshu@modelens.ai", None)
    found, found_items = await rs.production_set(db_session, EE, "1.0")
    assert found.id == ref.id and len(found_items) == 5

    ref = await rs.retire(db_session, ref, "anshu@modelens.ai", "New shoot.")
    assert (ref.status, ref.retired_by, ref.retire_reason) == ("RETIRED", "anshu@modelens.ai", "New shoot.")
    with pytest.raises(rs.ReferenceSetNotFound):
        await rs.production_set(db_session, EE, "1.0")
    actions = [(e.action, e.details["from_status"], e.details["to_status"]) for e in await _audit(db_session)]
    assert actions == [("reference_set_created", None, "DRAFT"), ("reference_set_locked", "DRAFT", "LOCKED"),
                       ("reference_set_promoted", "LOCKED", "PRODUCTION"),
                       ("reference_set_retired", "PRODUCTION", "RETIRED")]


@pytest.mark.asyncio
async def test_promoting_v2_retires_v1_and_one_production_per_version(db_session, world):
    v1, _ = await rs.promote(db_session, await _locked(db_session), "a@modelens.ai")
    v2 = await _locked(db_session, "CA-FACE-FRONT", "CA-BODY-FULL")
    assert v2.reference_set_id == "EE-F-002_V1.0_REF_V2"
    v2, replaced = await rs.promote(db_session, v2, "a@modelens.ai")
    await db_session.refresh(v1)
    assert replaced.id == v1.id
    assert (v1.status, v1.retire_reason) == ("RETIRED", "Replaced by EE-F-002_V1.0_REF_V2.")
    sets = await rs.list_sets(db_session, EE, status="PRODUCTION")
    assert [s.reference_set_id for s in sets] == ["EE-F-002_V1.0_REF_V2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("step", ["lock", "promote_draft", "retire_twice"])
async def test_lifecycle_cannot_skip_steps(db_session, world, step):
    ref = await rs.create_set(db_session, character_id=EE, character_version="1.0", items_in=_items(*ALL))
    with pytest.raises(rs.ReferenceSetConflict):
        if step == "lock":
            ref = await rs.lock(db_session, ref, "a")
            await rs.lock(db_session, ref, "a")
        elif step == "promote_draft":
            await rs.promote(db_session, ref, "a")
        else:
            ref = await rs.retire(db_session, ref, "a", "x")
            await rs.retire(db_session, ref, "a", "x")


# ========================== Create / lock rules ==================

@pytest.mark.asyncio
async def test_create_rules(db_session, world):
    await _asset(db_session, "CA-INELIGIBLE", eligible=False)
    await _asset(db_session, "CA-NOHASH", hashed=False)
    await _asset(db_session, "CA-OTHER-VERSION", version="1.1")
    bad = [
        ([{"canonical_asset_id": "CA-INELIGIBLE", "role": "face_front"}], rs.ReferenceSetInvalid),
        ([{"canonical_asset_id": "CA-NOHASH", "role": "face_front"}], rs.ReferenceSetInvalid),
        ([{"canonical_asset_id": "CA-OTHER-VERSION", "role": "face_front"}], rs.ReferenceSetInvalid),
        ([{"canonical_asset_id": "CA-NOPE", "role": "face_front"}], rs.ReferenceSetNotFound),
        ([{"canonical_asset_id": "CA-FACE-FRONT", "role": "left_ear"}], rs.ReferenceSetInvalid),
        (_items("CA-FACE-FRONT") * 2, rs.ReferenceSetInvalid),
        ([], rs.ReferenceSetInvalid),
    ]
    for items_in, error in bad:
        with pytest.raises(error):
            await rs.create_set(db_session, character_id=EE, character_version="1.0", items_in=items_in)
    with pytest.raises(rs.ReferenceSetNotFound):
        await rs.create_set(db_session, character_id=EE, character_version="9.9", items_in=_items("CA-FACE-FRONT"))
    assert (await db_session.execute(select(CharacterReferenceSet))).scalars().all() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("asset_ids, missing", [(("CA-FACE-FRONT", "CA-FACE-34"), "body_full"),
                                                (("CA-BODY-FULL",), "face_front")])
async def test_lock_needs_face_front_and_body_full(db_session, world, asset_ids, missing):
    ref = await rs.create_set(db_session, character_id=EE, character_version="1.0", items_in=_items(*asset_ids))
    with pytest.raises(rs.ReferenceSetInvalid, match=missing):
        await rs.lock(db_session, ref, "a")


@pytest.mark.asyncio
async def test_lock_needs_a_locked_character_version(db_session, world):
    await version_service.create_draft_version(db_session, EE, "1.1")
    for a, framing, angle in (("CA-11-FACE", "CLOSE_UP", "FRONT"), ("CA-11-BODY", "FULL_BODY", "FRONT")):
        await _asset(db_session, a, framing, angle, version="1.1")
    ref = await rs.create_set(db_session, character_id=EE, character_version="1.1", items_in=[
        {"canonical_asset_id": "CA-11-FACE", "role": "face_front"},
        {"canonical_asset_id": "CA-11-BODY", "role": "body_full"}])
    with pytest.raises(rs.ReferenceSetConflict, match="not LOCKED"):
        await rs.lock(db_session, ref, "a")


# ========================== Immutability ==========================

@pytest.mark.asyncio
@pytest.mark.parametrize("field, value", [("content_hash", "0" * 64), ("character_version", "2.0"),
                                          ("reference_set_id", "X"), ("locked_by", "someone")])
async def test_locked_set_fields_never_change(db_session, world, field, value):
    ref = await _locked(db_session)
    setattr(ref, field, value)
    with pytest.raises(ReferenceSetLockedError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_locked_set_status_only_moves_forward_and_is_never_deleted(db_session, world):
    ref = await _locked(db_session)
    ref_id = ref.reference_set_id
    ref.status = "DRAFT"
    with pytest.raises(ReferenceSetLockedError):
        await db_session.commit()
    await db_session.rollback()
    await db_session.delete(await rs.get_set(db_session, ref_id))
    with pytest.raises(ReferenceSetLockedError):
        await db_session.commit()
    await db_session.rollback()
    for stmt in (update(CharacterReferenceSet).values(status="DRAFT"), sa.delete(CharacterReferenceSetItem)):
        with pytest.raises(ReferenceSetLockedError):
            await db_session.execute(stmt)


@pytest.mark.asyncio
async def test_locked_set_items_never_change(db_session, world):
    ref = await _locked(db_session)
    ref_pk, ref_id = ref.id, ref.reference_set_id
    item = (await rs.items(db_session, ref))[0]
    item.content_hash_sha256 = "f" * 64
    with pytest.raises(ReferenceSetLockedError):
        await db_session.commit()
    await db_session.rollback()
    extra = await _asset(db_session, "CA-EXTRA")
    db_session.add(CharacterReferenceSetItem(reference_set_id=ref_pk, canonical_asset_id=extra.id,
                                             asset_id="CA-EXTRA", role="face_34", sort_order=9))
    with pytest.raises(ReferenceSetLockedError):
        await db_session.commit()
    await db_session.rollback()
    await db_session.delete((await rs.items(db_session, await rs.get_set(db_session, ref_id)))[0])
    with pytest.raises(ReferenceSetLockedError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_draft_set_items_can_change(db_session, world):
    ref = await rs.create_set(db_session, character_id=EE, character_version="1.0", items_in=_items(*ALL))
    item = (await rs.items(db_session, ref))[-1]
    await db_session.delete(item)
    await db_session.commit()
    assert len(await rs.items(db_session, ref)) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("field, value", [("storage_path", "/uploads/other.png"), ("content_hash_sha256", "e" * 64),
                                          ("asset_role", "OTHER"), ("version", "1.1"), ("asset_id", "CA-RENAMED")])
async def test_canonical_asset_file_identity_is_frozen_while_in_a_locked_set(db_session, world, field, value):
    await _locked(db_session)
    asset = world["assets"]["CA-FACE-FRONT"]
    setattr(asset, field, value)
    with pytest.raises(ReferenceSetLockedError, match="CA-FACE-FRONT"):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_canonical_asset_qa_stays_editable_and_unlocked_assets_are_free(db_session, world):
    await _locked(db_session, "CA-FACE-FRONT", "CA-BODY-FULL")
    face = world["assets"]["CA-FACE-FRONT"]
    face.overall_qa_status, face.identity_qa, face.active_canonical = "PASS", "PASS", True
    await db_session.commit()
    free = world["assets"]["CA-PROFILE"]  # not in a locked set
    free.storage_path = "/uploads/moved.png"
    await db_session.commit()
    draft_only = await rs.create_set(db_session, character_id=EE, character_version="1.0",
                                     items_in=_items("CA-FACE-34"))
    assert draft_only.status == "DRAFT"
    world["assets"]["CA-FACE-34"].content_hash_sha256 = "d" * 64  # only in a DRAFT set: allowed
    await db_session.commit()


@pytest.mark.asyncio
async def test_canonical_asset_in_a_locked_set_cannot_be_deleted(db_session, world):
    await _locked(db_session)
    await db_session.delete(world["assets"]["CA-BODY-FULL"])
    with pytest.raises(ReferenceSetLockedError):
        await db_session.commit()
    await db_session.rollback()
    with pytest.raises(ReferenceSetLockedError):
        await db_session.execute(sa.delete(CanonicalAsset))
    with pytest.raises(ReferenceSetLockedError):
        await db_session.execute(update(CanonicalAsset).values(storage_path="/uploads/x.png"))
    await db_session.execute(update(CanonicalAsset).values(overall_qa_status="PASS"))  # QA fields: allowed


# ========================== Hash checks at resolve ================

@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", ["set_hash", "item_hash", "asset_hash"])
async def test_resolve_detects_tampering(db_session, world, tamper):
    ref, _ = await rs.promote(db_session, await _locked(db_session), "a")
    # Raw SQL, as a manual database change would be: the ORM rules cannot see it, the hash check does.
    if tamper == "set_hash":
        await db_session.execute(sa.text("UPDATE character_reference_sets SET content_hash = :h"), {"h": "0" * 64})
    elif tamper == "item_hash":
        await db_session.execute(sa.text(
            "UPDATE character_reference_set_items SET content_hash_sha256 = :h WHERE role = 'profile'"), {"h": "1" * 64})
    else:
        await db_session.execute(sa.text(
            "UPDATE canonical_assets SET content_hash_sha256 = :h WHERE asset_id = 'CA-BODY-34'"), {"h": "2" * 64})
    await db_session.commit()
    db_session.expire_all()
    with pytest.raises(rs.ReferenceSetIntegrityError):
        await rs.production_set(db_session, EE, "1.0")


@pytest.mark.asyncio
async def test_promote_refuses_a_tampered_set(db_session, world):
    ref_id = (await _locked(db_session)).reference_set_id
    await db_session.execute(sa.text("UPDATE character_reference_sets SET content_hash = :h"), {"h": "0" * 64})
    await db_session.commit()
    db_session.expire_all()
    with pytest.raises(rs.ReferenceSetConflict, match="set hash"):
        await rs.promote(db_session, await rs.get_set(db_session, ref_id), "a")


# ========================== Seed ==================================

@pytest.mark.asyncio
async def test_seed_builds_and_locks_v1_never_promotes_and_is_idempotent(db_session, world):
    ref, created = await rs.seed_ee_f_002_reference_set(db_session, "admin@modelens.ai")
    assert (created, ref.reference_set_id, ref.status) == (True, "EE-F-002_V1.0_REF_V1", "LOCKED")
    assert {i.role: i.asset_id for i in await rs.items(db_session, ref)} == {v: k for k, v in ROLE_OF.items()}
    again, created = await rs.seed_ee_f_002_reference_set(db_session, "admin@modelens.ai")
    assert (created, again.id, again.status) == (False, ref.id, "LOCKED")
    assert len(await rs.list_sets(db_session, EE)) == 1
    with pytest.raises(rs.ReferenceSetNotFound):
        await rs.production_set(db_session, EE, "1.0")


@pytest.mark.asyncio
async def test_seed_skips_ineligible_and_unhashed_assets(db_session, world):
    for asset_id in ("CA-BODY-FULL",):
        world["assets"][asset_id].production_reference_eligible = False
    await db_session.commit()
    with pytest.raises(rs.ReferenceSetInvalid, match="body_full"):
        await rs.seed_ee_f_002_reference_set(db_session, "a")
    assert await rs.list_sets(db_session, EE) == []


# ========================== Verify ================================

@pytest.mark.asyncio
async def test_verify_rereads_files(client, db_session, world):
    ref = await _locked(db_session)
    url = f"{BASE}/{ref.reference_set_id}/verify"
    ok = await client.post(url, headers=world["h"]["admin"])
    assert ok.status_code == 200 and ok.json() == {"reference_set_id": ref.reference_set_id, "ok": True,
                                                   "problems": []}
    # Overwrite one file in storage: the database is unchanged, verify catches it.
    path = world["assets"]["CA-FACE-34"].storage_path
    storage_service.save_file_bytes(path[len("/uploads/"):], b"different bytes")
    bad = (await client.post(url, headers=world["h"]["admin"])).json()
    assert bad["ok"] is False and bad["problems"] == [
        "CA-FACE-34 (face_34): file content does not match its locked hash."]
    draft = await rs.create_set(db_session, character_id=EE, character_version="1.0", items_in=_items("CA-PROFILE"))
    resp = await client.post(f"{BASE}/{draft.reference_set_id}/verify", headers=world["h"]["admin"])
    assert resp.json()["ok"] is False


# ========================== Admin API =============================

ENDPOINTS = (
    ("post", BASE, {"character_version": "1.0", "items": _items(*ALL)}),
    ("get", BASE, None),
    ("post", f"{BASE}/seed", None),
    ("get", f"{BASE}/EE-F-002_V1.0_REF_V1", None),
    ("post", f"{BASE}/EE-F-002_V1.0_REF_V1/lock", None),
    ("post", f"{BASE}/EE-F-002_V1.0_REF_V1/promote", None),
    ("post", f"{BASE}/EE-F-002_V1.0_REF_V1/retire", {"reason": "x"}),
    ("post", f"{BASE}/EE-F-002_V1.0_REF_V1/verify", None),
)


@pytest.mark.asyncio
@pytest.mark.parametrize("method, path, body", ENDPOINTS)
async def test_every_endpoint_is_platform_admin_only(client, db_session, world, method, path, body):
    call = client.get(path) if method == "get" else client.post(path, json=body)
    assert (await call).status_code == 401
    headers = world["h"]["owner"]
    call = client.get(path, headers=headers) if method == "get" else client.post(path, json=body, headers=headers)
    assert (await call).status_code == 403
    assert (await db_session.execute(select(CharacterReferenceSet))).scalars().all() == []


@pytest.mark.asyncio
async def test_api_walk_with_409s(client, db_session, world):
    admin, admin_id = world["h"]["admin"], world["users"]["admin"].id
    created = await client.post(BASE, json={"character_version": "1.0", "items": _items(*ALL)}, headers=admin)
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["reference_set_id"], body["status"], len(body["items"])) == ("EE-F-002_V1.0_REF_V1", "DRAFT", 5)
    one = f"{BASE}/EE-F-002_V1.0_REF_V1"
    assert (await client.post(f"{one}/promote", headers=admin)).status_code == 409
    locked = (await client.post(f"{one}/lock", headers=admin)).json()
    assert locked["status"] == "LOCKED" and locked["content_hash"] and all(i["content_hash_sha256"]
                                                                          for i in locked["items"])
    again = await client.post(f"{one}/lock", headers=admin)
    assert again.status_code == 409 and "only DRAFT sets can be locked" in again.json()["detail"]
    promoted = (await client.post(f"{one}/promote", headers=admin)).json()
    assert (promoted["status"], promoted["replaced_reference_set_id"]) == ("PRODUCTION", None)
    listed = (await client.get(f"{BASE}?status=PRODUCTION", headers=admin)).json()
    assert [s["reference_set_id"] for s in listed["reference_sets"]] == ["EE-F-002_V1.0_REF_V1"]
    retired = await client.post(f"{one}/retire", json={"reason": "New shoot."}, headers=admin)
    assert retired.json()["status"] == "RETIRED"
    final = await client.post(f"{one}/retire", json={"reason": "again"}, headers=admin)
    assert final.status_code == 409 and "none (final)" in final.json()["detail"]
    assert [e.action for e in await _audit(db_session)] == [
        "reference_set_created", "reference_set_locked", "reference_set_promoted", "reference_set_retired"]
    assert all(e.user_id == admin_id for e in await _audit(db_session))


@pytest.mark.asyncio
async def test_api_create_errors_and_unknown_set(client, world):
    admin = world["h"]["admin"]
    bad_role = await client.post(BASE, json={"character_version": "1.0", "items": [
        {"canonical_asset_id": "CA-FACE-FRONT", "role": "left_ear"}]}, headers=admin)
    assert bad_role.status_code == 422
    unknown = await client.post(BASE, json={"character_version": "1.0", "items": [
        {"canonical_asset_id": "CA-NOPE", "role": "face_front"}]}, headers=admin)
    assert unknown.status_code == 404
    assert (await client.get(f"{BASE}/EE-F-002_V1.0_REF_V9", headers=admin)).status_code == 404
    other = await client.post("/api/v1/admin/characters/EE-X-001/reference-sets/seed", headers=admin)
    assert other.status_code == 404


@pytest.mark.asyncio
async def test_api_seed(client, world):
    admin = world["h"]["admin"]
    first = (await client.post(f"{BASE}/seed", headers=admin)).json()
    assert (first["created"], first["status"], first["reference_set_id"]) == (True, "LOCKED", "EE-F-002_V1.0_REF_V1")
    second = (await client.post(f"{BASE}/seed", headers=admin)).json()
    assert (second["created"], second["status"]) == (False, "LOCKED")


@pytest.mark.asyncio
async def test_customer_routes_are_untouched(client, db_session, world):
    await rs.promote(db_session, await _locked(db_session), "a")
    for path in CUSTOMER_ROUTES:
        resp = await client.get(path, headers=world["h"]["owner"])
        assert resp.status_code in (200, 404, 422), path  # no option seeds here; nothing about sets leaks
        assert_customer_safe(resp.text)
        assert "REF_V" not in resp.text and "reference_set" not in resp.text


# ========================== Migration =============================

def _migration():
    spec = importlib.util.spec_from_file_location("reference_sets_001", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def chain_db(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'chain.db'}")
    skip = {"character_reference_sets", "character_reference_set_items"}
    models.Base.metadata.create_all(engine, tables=[t for n, t in models.Base.metadata.tables.items() if n not in skip])
    yield engine
    engine.dispose()


def _run(engine, step):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(_migration(), step)()


def test_migration_creates_the_model_tables_and_is_rerunnable(chain_db):
    _run(chain_db, "upgrade")
    _run(chain_db, "upgrade")
    with chain_db.connect() as conn:
        for name, model in (("character_reference_sets", CharacterReferenceSet),
                            ("character_reference_set_items", CharacterReferenceSetItem)):
            assert table_differences(conn, name, list(model.__table__.columns)) == [], name
        indexes = {ix["name"] for ix in sa.inspect(conn).get_indexes("character_reference_sets")}
    assert "uq_reference_set_production" in indexes
    _run(chain_db, "downgrade")
    with chain_db.connect() as conn:
        assert not sa.inspect(conn).has_table("character_reference_sets")


def test_one_production_set_per_character_version_in_the_database(chain_db):
    _run(chain_db, "upgrade")
    sets = sa.table("character_reference_sets", *[sa.column(c) for c in (
        "reference_set_id", "character_id", "character_version", "version", "status")])
    with chain_db.begin() as conn:
        conn.execute(sets.insert().values(reference_set_id="A", character_id=EE, character_version="1.0", version=1,
                                          status="PRODUCTION"))
        conn.execute(sets.insert().values(reference_set_id="B", character_id=EE, character_version="1.0", version=2,
                                          status="RETIRED"))
    with pytest.raises(IntegrityError):
        with chain_db.begin() as conn:
            conn.execute(sets.insert().values(reference_set_id="C", character_id=EE, character_version="1.0",
                                              version=3, status="PRODUCTION"))


def test_single_alembic_head_is_this_revision():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config(os.path.join(BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND, "alembic"))
    assert ScriptDirectory.from_config(cfg).get_heads() == ["reference_sets_001"]
