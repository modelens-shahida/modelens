"""Runtime profiles and adapter EVALUATION status (APPEARANCE_STATUS.md PR AC-1): lifecycle, rules, freezing,
one PRODUCTION per character version, strengths only from data, adapter status endpoint, seed, admin API, audit
log, Character rows untouched, migration. No network."""
import ast
import hashlib
import importlib.util
import inspect
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
    AuditLog, CanonicalAsset, ExperimentRun, ModelArtifact, QAProfile, RuntimeProfile, RuntimeProfileFrozenError, User,
)
from app.services import character_versions as version_service
from app.services import reference_sets as rs
from app.services import runtime_profiles as rp
from app.services import training_registry as training
from app.services.storage import storage_service
from customer_safety import assert_customer_safe
from test_capability_validations import CUSTOMER_ROUTES

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATION = os.path.join(BACKEND, "alembic", "versions", "runtime_profiles_001.py")
BASE = "/api/v1/admin/characters/EE-F-002/runtime-profiles"
ADAPTERS = "/api/v1/admin/training/adapters"
EE = "EE-F-002"
ADAPTER = "EE-F-002_CK0750"
SHA = "a" * 64
# Test values only; the code under test never holds a strength.
STRENGTH, FALLBACK = 0.4, 0.6
PLUS = {"default_strategy": "REFERENCE_ONLY", "allowed_strategies": ["REFERENCE_ONLY", "REFERENCE_PLUS_ADAPTER"],
        "adapter_id": ADAPTER, "adapter_strength": STRENGTH, "fallback_adapter_strength": FALLBACK}


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}


async def _adapter(db, adapter_id=ADAPTER, status="EXPERIMENTAL", *, version="1.0", checksum=SHA,
                   path="/models/ck.safetensors", kind="TRAINED_MODEL"):
    adapter = ModelArtifact(model_id=adapter_id, character_id=EE, character_version=version, layer="IDENTITY", kind=kind,
                            storage_path=path, checksum_sha256=checksum, status=status, created_by="test")
    db.add(adapter)
    await db.commit()
    return adapter


async def _canonical(db, asset_id, framing, angle):
    data = f"{asset_id}-{uuid.uuid4().hex}".encode()
    path = storage_service.save_file_bytes(f"test-runtime-profiles/{uuid.uuid4().hex}/{asset_id}.png", data)
    db.add(CanonicalAsset(asset_id=asset_id, character_id=EE, version="1.0", asset_role="GOLDEN_IDENTITY",
                          framing=framing, angle_code=angle, storage_path=path,
                          content_hash_sha256=hashlib.sha256(data).hexdigest(), production_reference_eligible=True))
    await db.commit()


async def _locked_set(db):
    await _canonical(db, "CA-FACE", "CLOSE_UP", "FRONT")
    await _canonical(db, "CA-BODY", "FULL_BODY", "FRONT")
    ref = await rs.create_set(db, character_id=EE, character_version="1.0", items_in=[
        {"canonical_asset_id": "CA-FACE", "role": "face_front"}, {"canonical_asset_id": "CA-BODY", "role": "body_full"}])
    return await rs.lock(db, ref, "admin@modelens.ai")


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
    return {"users": users, "h": {k: _headers(u) for k, u in users.items()}}


async def _audit(db, prefix="runtime_profile_"):
    return list((await db.execute(select(AuditLog).where(AuditLog.action.like(f"{prefix}%"))
                                  .order_by(AuditLog.id))).scalars().all())


async def _create(db, **kw):
    return await rp.create_profile(db, character_id=EE, character_version="1.0", created_by="admin@modelens.ai", **kw)


# ========================== Lifecycle =============================

@pytest.mark.asyncio
async def test_create_promote_retire_with_audit(db_session, world):
    profile = await _create(db_session)
    assert (profile.runtime_profile_id, profile.version, profile.status) == ("EE-F-002_V1.0_RT_V1", 1, "DRAFT")
    assert (profile.default_strategy, profile.allowed_strategies) == ("REFERENCE_ONLY", ["REFERENCE_ONLY"])
    assert (profile.adapter_id, profile.adapter_strength, profile.fallback_adapter_strength) == (None, None, None)
    assert profile.fallback_retry_enabled is False
    profile, replaced = await rp.promote(db_session, profile, "anshu@modelens.ai")
    assert (profile.status, profile.promoted_by, replaced) == ("PRODUCTION", "anshu@modelens.ai", None)
    assert (await rp.production_profile(db_session, EE, "1.0")).id == profile.id
    profile = await rp.retire(db_session, profile, "anshu@modelens.ai", "Superseded.")
    assert (profile.status, profile.retire_reason) == ("RETIRED", "Superseded.")
    with pytest.raises(rp.RuntimeProfileNotFound):
        await rp.production_profile(db_session, EE, "1.0")
    assert [(e.action, e.details["from_status"], e.details["to_status"]) for e in await _audit(db_session)] == [
        ("runtime_profile_created", None, "DRAFT"), ("runtime_profile_promoted", "DRAFT", "PRODUCTION"),
        ("runtime_profile_retired", "PRODUCTION", "RETIRED")]


@pytest.mark.asyncio
async def test_promoting_v2_retires_v1_one_production_per_version(db_session, world):
    v1, _ = await rp.promote(db_session, await _create(db_session), "a")
    v2 = await _create(db_session)
    assert v2.runtime_profile_id == "EE-F-002_V1.0_RT_V2"
    v2, replaced = await rp.promote(db_session, v2, "a")
    await db_session.refresh(v1)
    assert replaced.id == v1.id and (v1.status, v1.retire_reason) == ("RETIRED", "Replaced by EE-F-002_V1.0_RT_V2.")
    assert [p.runtime_profile_id for p in await rp.list_profiles(db_session, EE, status="PRODUCTION")] == [
        "EE-F-002_V1.0_RT_V2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("step", ["promote_twice", "promote_retired", "retire_twice"])
async def test_lifecycle_cannot_skip_or_go_back(db_session, world, step):
    profile = await _create(db_session)
    with pytest.raises(rp.RuntimeProfileConflict):
        if step == "promote_twice":
            profile, _ = await rp.promote(db_session, profile, "a")
            await rp.promote(db_session, profile, "a")
        elif step == "promote_retired":
            profile = await rp.retire(db_session, profile, "a", "x")
            await rp.promote(db_session, profile, "a")
        else:
            profile = await rp.retire(db_session, profile, "a", "x")
            await rp.retire(db_session, profile, "a", "x")


@pytest.mark.asyncio
async def test_promote_needs_a_locked_character_version(db_session, world):
    await version_service.create_draft_version(db_session, EE, "1.1")
    profile = await rp.create_profile(db_session, character_id=EE, character_version="1.1")
    with pytest.raises(rp.RuntimeProfileConflict, match="not LOCKED"):
        await rp.promote(db_session, profile, "a")


# ========================== Create rules ==========================

@pytest.mark.asyncio
async def test_create_rules(db_session, world):
    await _adapter(db_session)
    await _adapter(db_session, "ADP-ARCHIVED", "ARCHIVED")
    await _adapter(db_session, "ADP-OTHER-VERSION", version="1.1")
    bad = [
        (dict(default_strategy="REFERENCE_PLUS_ADAPTER", allowed_strategies=["REFERENCE_ONLY"]),
         rp.RuntimeProfileInvalid),
        (dict(allowed_strategies=[]), rp.RuntimeProfileInvalid),
        (dict(allowed_strategies=["REFERENCE_ONLY", "REFERENCE_ONLY"]), rp.RuntimeProfileInvalid),
        (dict(allowed_strategies=["LORA_ONLY"]), rp.RuntimeProfileInvalid),
        # Adapter fields without REFERENCE_PLUS_ADAPTER.
        (dict(adapter_id=ADAPTER), rp.RuntimeProfileInvalid),
        (dict(fallback_retry_enabled=True), rp.RuntimeProfileInvalid),
        # REFERENCE_PLUS_ADAPTER without its data: there is no default strength.
        ({**PLUS, "adapter_strength": None}, rp.RuntimeProfileInvalid),
        ({**PLUS, "fallback_adapter_strength": None}, rp.RuntimeProfileInvalid),
        ({**PLUS, "adapter_id": None}, rp.RuntimeProfileInvalid),
        ({**PLUS, "adapter_strength": 0}, rp.RuntimeProfileInvalid),
        ({**PLUS, "fallback_adapter_strength": STRENGTH}, rp.RuntimeProfileInvalid),
        ({**PLUS, "fallback_adapter_strength": 1.5}, rp.RuntimeProfileInvalid),
        ({**PLUS, "adapter_id": "ADP-NOPE"}, rp.RuntimeProfileNotFound),
        ({**PLUS, "adapter_id": "ADP-ARCHIVED"}, rp.RuntimeProfileInvalid),
        ({**PLUS, "adapter_id": "ADP-OTHER-VERSION"}, rp.RuntimeProfileInvalid),
        (dict(reference_set_id="EE-F-002_V1.0_REF_V9"), rp.RuntimeProfileNotFound),
        (dict(qa_profile_id="QA-NOPE"), rp.RuntimeProfileNotFound),
    ]
    for kw, error in bad:
        with pytest.raises(error):
            await _create(db_session, **kw)
    with pytest.raises(rp.RuntimeProfileNotFound):
        await rp.create_profile(db_session, character_id=EE, character_version="9.9")
    assert (await db_session.execute(select(RuntimeProfile))).scalars().all() == []


@pytest.mark.asyncio
async def test_create_with_adapter_set_and_qa_profile(db_session, world):
    await _adapter(db_session, status="EVALUATION")
    ref = await _locked_set(db_session)
    db_session.add(QAProfile(qa_profile_id="QA-PROFILE-IDENTITY-001"))
    await db_session.commit()
    profile = await _create(db_session, **PLUS, reference_set_id=ref.reference_set_id,
                            qa_profile_id="QA-PROFILE-IDENTITY-001")
    assert (profile.adapter_strength, profile.fallback_adapter_strength) == (STRENGTH, FALLBACK)
    assert profile.reference_set_id == ref.id and profile.fallback_retry_enabled is False
    assert profile.allowed_strategies == ["REFERENCE_ONLY", "REFERENCE_PLUS_ADAPTER"]
    created = (await _audit(db_session))[0].details
    assert (created["adapter_id"], created["adapter_strength"], created["reference_set_id"]) == (
        ADAPTER, STRENGTH, ref.reference_set_id)


@pytest.mark.asyncio
async def test_a_draft_reference_set_cannot_be_pinned(db_session, world):
    await _canonical(db_session, "CA-FACE", "CLOSE_UP", "FRONT")
    draft = await rs.create_set(db_session, character_id=EE, character_version="1.0",
                                items_in=[{"canonical_asset_id": "CA-FACE", "role": "face_front"}])
    with pytest.raises(rp.RuntimeProfileInvalid, match="LOCKED or PRODUCTION"):
        await _create(db_session, reference_set_id=draft.reference_set_id)


# ========================== Promotion gates =======================

@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_status", ["EXPERIMENTAL", "EVALUATION"])
async def test_promote_refuses_adapter_strategy_unless_adapter_is_production(db_session, world, adapter_status):
    await _adapter(db_session, status=adapter_status)
    profile = await _create(db_session, **PLUS)
    with pytest.raises(rp.RuntimeProfileConflict, match=adapter_status):
        await rp.promote(db_session, profile, "a")
    assert (await rp.get_profile(db_session, profile.runtime_profile_id)).status == "DRAFT"


@pytest.mark.asyncio
async def test_promote_with_a_production_adapter(db_session, world):
    adapter = await _adapter(db_session, status="EVALUATION")
    profile = await _create(db_session, **PLUS)
    adapter.status = "PRODUCTION"  # as a PASSED training run promotion would
    await db_session.commit()
    profile, _ = await rp.promote(db_session, profile, "a")
    assert profile.status == "PRODUCTION"


@pytest.mark.asyncio
async def test_promote_refuses_a_tampered_pinned_set(db_session, world):
    ref = await _locked_set(db_session)
    profile_ref = (await _create(db_session, reference_set_id=ref.reference_set_id)).runtime_profile_id
    await db_session.execute(sa.text("UPDATE character_reference_sets SET content_hash = :h"), {"h": "0" * 64})
    await db_session.commit()
    db_session.expire_all()
    with pytest.raises(rp.RuntimeProfileConflict, match="set hash"):
        await rp.promote(db_session, await rp.get_profile(db_session, profile_ref), "a")


# ========================== Freezing ==============================

@pytest.mark.asyncio
@pytest.mark.parametrize("field, value", [("adapter_strength", 0.9), ("allowed_strategies", ["REFERENCE_PLUS_ADAPTER"]),
                                          ("fallback_retry_enabled", True), ("runtime_profile_id", "X"),
                                          ("character_version", "2.0"), ("notes", "edited")])
async def test_production_profile_never_changes(db_session, world, field, value):
    profile, _ = await rp.promote(db_session, await _create(db_session), "a")
    setattr(profile, field, value)
    with pytest.raises(RuntimeProfileFrozenError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_retired_profile_never_changes_and_status_never_goes_back(db_session, world):
    profile = await rp.retire(db_session, await _create(db_session), "a", "x")
    profile.notes = "edited"
    with pytest.raises(RuntimeProfileFrozenError):
        await db_session.commit()
    await db_session.rollback()
    profile = await rp.get_profile(db_session, "EE-F-002_V1.0_RT_V1")
    profile.status = "DRAFT"
    with pytest.raises(RuntimeProfileFrozenError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_profiles_are_never_deleted_or_bulk_written(db_session, world):
    draft = await _create(db_session)
    await db_session.delete(draft)
    with pytest.raises(RuntimeProfileFrozenError):
        await db_session.commit()
    await db_session.rollback()
    for stmt in (update(RuntimeProfile).values(adapter_strength=0.9), sa.delete(RuntimeProfile)):
        with pytest.raises(RuntimeProfileFrozenError):
            await db_session.execute(stmt)


@pytest.mark.asyncio
async def test_draft_profile_can_change(db_session, world):
    draft = await _create(db_session)
    draft.notes = "Waiting for the reference set."
    await db_session.commit()
    assert (await rp.get_profile(db_session, draft.runtime_profile_id)).notes == "Waiting for the reference set."


# ========================== Strengths are data ====================

def _float_literals(source: str) -> list[float]:
    return [n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and isinstance(n.value, float)]


def test_no_strength_constant_in_code():
    sources = {
        "service": inspect.getsource(rp),
        "router": open(os.path.join(BACKEND, "app", "routers", "runtime_profiles_admin.py")).read(),
        "model": inspect.getsource(RuntimeProfile),
        "adapter status": inspect.getsource(training.set_adapter_status),
        "migration": open(MIGRATION).read(),
    }
    for name, source in sources.items():
        assert _float_literals(source) == [], name
    columns = RuntimeProfile.__table__.columns
    assert all(columns[c].default is None and columns[c].server_default is None
               for c in ("adapter_strength", "fallback_adapter_strength"))


# ========================== Seed ==================================

@pytest.mark.asyncio
async def test_seed_creates_a_reference_only_draft_and_is_idempotent(db_session, world):
    profile, created = await rp.seed_ee_f_002_runtime_profile(db_session, "admin@modelens.ai")
    assert (created, profile.runtime_profile_id, profile.status) == (True, "EE-F-002_V1.0_RT_V1", "DRAFT")
    assert (profile.default_strategy, profile.allowed_strategies) == ("REFERENCE_ONLY", ["REFERENCE_ONLY"])
    assert (profile.adapter_id, profile.adapter_strength, profile.fallback_adapter_strength,
            profile.reference_set_id, profile.fallback_retry_enabled) == (None, None, None, None, False)
    again, created = await rp.seed_ee_f_002_runtime_profile(db_session, "admin@modelens.ai")
    assert (created, again.id, again.status) == (False, profile.id, "DRAFT")
    assert len(await rp.list_profiles(db_session, EE)) == 1
    assert [e.action for e in await _audit(db_session)] == ["runtime_profile_seeded"]
    with pytest.raises(rp.RuntimeProfileNotFound):
        await rp.production_profile(db_session, EE, "1.0")


# ========================== Adapter status ========================

@pytest.mark.asyncio
async def test_adapter_status_walk_with_audit(client, db_session, world):
    await _adapter(db_session)
    admin, admin_id = world["h"]["admin"], world["users"]["admin"].id
    url = f"{ADAPTERS}/{ADAPTER}/status"
    evaluation = await client.post(url, json={"status": "EVALUATION", "reason": "Identity evaluation."}, headers=admin)
    assert evaluation.status_code == 200, evaluation.text
    assert evaluation.json()["status"] == "EVALUATION"
    production = await client.post(url, json={"status": "PRODUCTION"}, headers=admin)
    assert production.status_code == 409 and "PASSED training run" in production.json()["detail"]
    back = await client.post(url, json={"status": "EXPERIMENTAL"}, headers=admin)
    assert back.json()["status"] == "EXPERIMENTAL"
    archived = await client.post(url, json={"status": "ARCHIVED"}, headers=admin)
    assert archived.json()["status"] == "ARCHIVED"
    final = await client.post(url, json={"status": "EVALUATION"}, headers=admin)
    assert final.status_code == 409 and "none (final)" in final.json()["detail"]
    assert (await client.post(url, json={"status": "VALIDATION"}, headers=admin)).status_code == 422
    assert (await client.post(f"{ADAPTERS}/ADP-NOPE/status", json={"status": "EVALUATION"},
                              headers=admin)).status_code == 404
    entries = await _audit(db_session, "adapter_status_")
    assert [(e.details["from_status"], e.details["to_status"]) for e in entries] == [
        ("EXPERIMENTAL", "EVALUATION"), ("EVALUATION", "EXPERIMENTAL"), ("EXPERIMENTAL", "ARCHIVED")]
    assert entries[0].details["reason"] == "Identity evaluation."
    assert all(e.user_id == admin_id for e in entries)


@pytest.mark.asyncio
async def test_evaluation_needs_the_model_file_and_checksum(db_session, world):
    await _adapter(db_session, checksum=None)
    with pytest.raises(training.TrainingInvalid, match="checksum"):
        await training.set_adapter_status(db_session, ADAPTER, "EVALUATION", changed_by="a")
    await db_session.rollback()
    await _adapter(db_session, "ADP-WORKFLOW", kind="WORKFLOW", checksum=None, path=None)
    assert (await training.set_adapter_status(db_session, "ADP-WORKFLOW", "EVALUATION",
                                              changed_by="a")).status == "EVALUATION"


@pytest.mark.asyncio
async def test_adapter_of_a_production_profile_cannot_be_archived(db_session, world):
    adapter = await _adapter(db_session, status="PRODUCTION")
    await rp.promote(db_session, await _create(db_session, **PLUS), "a")
    with pytest.raises(training.TrainingConflict, match="EE-F-002_V1.0_RT_V1"):
        await training.set_adapter_status(db_session, ADAPTER, "ARCHIVED", changed_by="a")
    await db_session.refresh(adapter)
    assert adapter.status == "PRODUCTION"


@pytest.mark.asyncio
async def test_archived_adapter_cannot_be_promoted_by_a_run(db_session, world):
    db_session.add(ExperimentRun(run_id="RUN-CK", experiment_name="ck", character_id=EE, character_version="1.0",
                                 status="PASSED"))
    adapter = await _adapter(db_session, status="ARCHIVED")
    adapter.run_id = "RUN-CK"
    await db_session.commit()
    with pytest.raises(training.TrainingConflict, match="ARCHIVED"):
        await training.promote_run(db_session, "RUN-CK", adapter_id=ADAPTER, checkpoint_id=None, promoted_by="a")


# ========================== Character rows untouched ==============

CHARACTER_TABLES = ("character_registry_versions", "characters_v2", "character_identity_dna", "character_body_dna",
                    "canonical_assets", "character_reference_sets", "character_reference_set_items")


async def _character_rows(db):
    rows = {}
    for table in CHARACTER_TABLES:
        if table in models.Base.metadata.tables:
            result = await db.execute(sa.text(f"SELECT * FROM {table} ORDER BY id"))
            rows[table] = [tuple(r) for r in result.all()]
    return rows


@pytest.mark.asyncio
async def test_runtime_profile_and_adapter_writes_leave_character_rows_identical(db_session, world):
    await _adapter(db_session)
    ref = await _locked_set(db_session)
    before = await _character_rows(db_session)
    assert before["character_registry_versions"]
    await training.set_adapter_status(db_session, ADAPTER, "EVALUATION", changed_by="a")
    await rp.seed_ee_f_002_runtime_profile(db_session, "a")
    v2 = await _create(db_session, reference_set_id=ref.reference_set_id)
    await rp.promote(db_session, v2, "a")
    await rp.retire(db_session, await rp.get_profile(db_session, "EE-F-002_V1.0_RT_V1"), "a", "unused")
    db_session.expire_all()
    assert await _character_rows(db_session) == before


# ========================== Admin API =============================

ENDPOINTS = (
    ("post", BASE, {"character_version": "1.0"}),
    ("get", BASE, None),
    ("post", f"{BASE}/seed", None),
    ("get", f"{BASE}/EE-F-002_V1.0_RT_V1", None),
    ("post", f"{BASE}/EE-F-002_V1.0_RT_V1/promote", None),
    ("post", f"{BASE}/EE-F-002_V1.0_RT_V1/retire", {"reason": "x"}),
    ("post", f"{ADAPTERS}/{ADAPTER}/status", {"status": "EVALUATION"}),
)


@pytest.mark.asyncio
@pytest.mark.parametrize("method, path, body", ENDPOINTS)
async def test_every_endpoint_is_platform_admin_only(client, db_session, world, method, path, body):
    await _adapter(db_session)
    for headers, code in (({}, 401), (world["h"]["owner"], 403)):
        call = client.get(path, headers=headers) if method == "get" else client.post(path, json=body, headers=headers)
        assert (await call).status_code == code
    assert (await db_session.execute(select(RuntimeProfile))).scalars().all() == []
    await db_session.refresh((await db_session.execute(select(ModelArtifact))).scalars().one())
    assert (await db_session.execute(select(ModelArtifact.status))).scalar() == "EXPERIMENTAL"


@pytest.mark.asyncio
async def test_api_walk_with_409s(client, db_session, world):
    admin, admin_id = world["h"]["admin"], world["users"]["admin"].id
    await _adapter(db_session, status="EVALUATION")
    ref = await _locked_set(db_session)
    seeded = (await client.post(f"{BASE}/seed", headers=admin)).json()
    assert (seeded["created"], seeded["status"], seeded["allowed_strategies"]) == (True, "DRAFT", ["REFERENCE_ONLY"])
    assert (await client.post(f"{BASE}/seed", headers=admin)).json()["created"] is False

    created = await client.post(BASE, json={"character_version": "1.0", "reference_set_id": ref.reference_set_id,
                                            **PLUS}, headers=admin)
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["runtime_profile_id"], body["reference_set_id"], body["adapter_strength"],
            body["fallback_adapter_strength"], body["fallback_retry_enabled"]) == (
        "EE-F-002_V1.0_RT_V2", ref.reference_set_id, STRENGTH, FALLBACK, False)
    v2 = f"{BASE}/EE-F-002_V1.0_RT_V2"
    refused = await client.post(f"{v2}/promote", headers=admin)
    assert refused.status_code == 409 and "EVALUATION" in refused.json()["detail"]

    v1 = f"{BASE}/EE-F-002_V1.0_RT_V1"
    promoted = (await client.post(f"{v1}/promote", headers=admin)).json()
    assert (promoted["status"], promoted["replaced_runtime_profile_id"]) == ("PRODUCTION", None)
    again = await client.post(f"{v1}/promote", headers=admin)
    assert again.status_code == 409 and "only DRAFT profiles" in again.json()["detail"]
    listed = (await client.get(f"{BASE}?status=PRODUCTION", headers=admin)).json()
    assert [p["runtime_profile_id"] for p in listed["runtime_profiles"]] == ["EE-F-002_V1.0_RT_V1"]
    retired = await client.post(f"{v1}/retire", json={"reason": "Superseded."}, headers=admin)
    assert retired.json()["status"] == "RETIRED"
    final = await client.post(f"{v1}/retire", json={"reason": "again"}, headers=admin)
    assert final.status_code == 409 and "none (final)" in final.json()["detail"]
    assert [e.action for e in await _audit(db_session)] == [
        "runtime_profile_seeded", "runtime_profile_created", "runtime_profile_promoted", "runtime_profile_retired"]
    assert all(e.user_id == admin_id for e in await _audit(db_session))


@pytest.mark.asyncio
async def test_api_validation_errors(client, world):
    admin = world["h"]["admin"]
    no_strength = await client.post(BASE, json={"character_version": "1.0", **PLUS, "adapter_strength": None},
                                    headers=admin)
    assert no_strength.status_code == 400 and "no default strength" in no_strength.json()["detail"]
    for bad in ({"adapter_strength": 1.2}, {"allowed_strategies": ["LORA_ONLY"]}, {"default_strategy": "X"}):
        resp = await client.post(BASE, json={"character_version": "1.0", **PLUS, **bad}, headers=admin)
        assert resp.status_code == 422, bad
    assert (await client.get(f"{BASE}/EE-F-002_V1.0_RT_V9", headers=admin)).status_code == 404
    other = await client.post("/api/v1/admin/characters/EE-X-001/runtime-profiles/seed", headers=admin)
    assert other.status_code == 404


@pytest.mark.asyncio
async def test_customer_routes_are_untouched(client, db_session, world):
    await _adapter(db_session, status="PRODUCTION")
    await rp.promote(db_session, await _create(db_session, **PLUS), "a")
    for path in CUSTOMER_ROUTES:
        resp = await client.get(path, headers=world["h"]["owner"])
        assert resp.status_code in (200, 404, 422), path
        assert_customer_safe(resp.text)
        assert "RT_V" not in resp.text and "runtime_profile" not in resp.text and ADAPTER not in resp.text


# ========================== Migration =============================

def _migration():
    spec = importlib.util.spec_from_file_location("runtime_profiles_001", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def chain_db(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'chain.db'}")
    models.Base.metadata.create_all(
        engine, tables=[t for n, t in models.Base.metadata.tables.items() if n != "runtime_profiles"])
    yield engine
    engine.dispose()


def _run(engine, step):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(_migration(), step)()


def test_migration_matches_the_model_reruns_and_downgrades(chain_db):
    _run(chain_db, "upgrade")
    _run(chain_db, "upgrade")
    with chain_db.connect() as conn:
        assert table_differences(conn, "runtime_profiles", list(RuntimeProfile.__table__.columns)) == []
        indexes = {ix["name"] for ix in sa.inspect(conn).get_indexes("runtime_profiles")}
    assert {"uq_runtime_profile_production", "ix_runtime_profiles_character_id"} <= indexes
    _run(chain_db, "downgrade")
    with chain_db.connect() as conn:
        assert not sa.inspect(conn).has_table("runtime_profiles")
    _run(chain_db, "downgrade")  # nothing left to drop: still fine
    _run(chain_db, "upgrade")
    with chain_db.connect() as conn:
        assert table_differences(conn, "runtime_profiles", list(RuntimeProfile.__table__.columns)) == []


PROFILES = sa.table("runtime_profiles", *[sa.column(c) for c in (
    "runtime_profile_id", "character_id", "character_version", "version", "status", "allowed_strategies",
    "adapter_strength", "fallback_adapter_strength")])


def _row(name, version, status="DRAFT", **kw):
    return PROFILES.insert().values(runtime_profile_id=name, character_id=EE, character_version="1.0", version=version,
                                    status=status, allowed_strategies='["REFERENCE_ONLY"]', **kw)


def test_one_production_profile_per_character_version_in_the_database(chain_db):
    _run(chain_db, "upgrade")
    with chain_db.begin() as conn:
        conn.execute(_row("A", 1, "PRODUCTION"))
        conn.execute(_row("B", 2, "RETIRED"))
    with pytest.raises(IntegrityError):
        with chain_db.begin() as conn:
            conn.execute(_row("C", 3, "PRODUCTION"))


@pytest.mark.parametrize("strengths", [dict(adapter_strength=0), dict(adapter_strength=1.5),
                                       dict(adapter_strength=STRENGTH, fallback_adapter_strength=STRENGTH),
                                       dict(adapter_strength=STRENGTH, fallback_adapter_strength=1.2)])
def test_strength_checks_in_the_database(chain_db, strengths):
    _run(chain_db, "upgrade")
    with pytest.raises(IntegrityError):
        with chain_db.begin() as conn:
            conn.execute(_row("A", 1, **strengths))
    with chain_db.begin() as conn:
        conn.execute(_row("OK", 1, adapter_strength=STRENGTH, fallback_adapter_strength=FALLBACK))


def test_single_alembic_head_is_this_revision():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config(os.path.join(BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND, "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["runtime_profiles_001"]
    assert script.get_revision("runtime_profiles_001").down_revision == "reference_sets_001"
