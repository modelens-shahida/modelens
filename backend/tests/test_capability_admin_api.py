"""Capability validation admin API (Character Runtime PR 2): platform-admin only, lifecycle over HTTP, 409 on
invalid transitions, audit log per action, customer routes unchanged."""
import pytest
from sqlalchemy import select

from app.models.db import AuditLog, CapabilityValidation
from app.services import capability_validations as cv
from test_capability_validations import CUSTOMER_ROUTES, assert_no_forbidden_terms
from test_production_dispatch import queue, world  # noqa: F401 (fixtures)

BASE = "/api/v1/admin/characters/EE-F-002/capabilities"
HAIR = f"{BASE}/HAIR/SOFT_WAVES"
REGISTER = {"character_version": "1.0", "capability_type": "HAIR", "capability_key": "SOFT_WAVES",
            "capability_version": 1, "customer_id": "hair_soft_waves", "group": "Polished", "sort_order": 10}
ALL_PASS = {"identity": "PASS", "face": "PASS", "body": "PASS", "product": "PASS"}
VALIDATE = {"capability_version": 1, "checks": ALL_PASS, "evidence": {"sample_production_ids": ["prd_val_001"]}}
ENDPOINTS = (
    ("post", BASE, REGISTER),
    ("get", BASE, None),
    ("post", f"{HAIR}/validation/start", {"capability_version": 1}),
    ("post", f"{HAIR}/validation", VALIDATE),
    ("post", f"{HAIR}/promote", {"capability_version": 1}),
    ("post", f"{HAIR}/retire", {"capability_version": 1, "reason": "x"}),
)


async def _call(client, headers, method, path, body=None):
    if method == "get":
        return await client.get(path, headers=headers)
    return await client.post(path, json=body, headers=headers)


async def _audit(db):
    rows = (await db.execute(select(AuditLog).where(AuditLog.action.like("capability_%"))
                             .order_by(AuditLog.id).execution_options(populate_existing=True))).scalars().all()
    return list(rows)


async def _registered(client, world, **overrides):
    resp = await client.post(BASE, json={**REGISTER, **overrides}, headers=world["h"]["admin"])
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _promoted(client, world, version=1, **promote):
    admin = world["h"]["admin"]
    if version == 1:
        await _registered(client, world)
    else:
        await _registered(client, world, capability_version=version)
    resp = await client.post(f"{HAIR}/validation", json={**VALIDATE, "capability_version": version}, headers=admin)
    assert resp.status_code == 200, resp.text
    resp = await client.post(f"{HAIR}/promote", json={"capability_version": version, **promote}, headers=admin)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ========================== Access ================================

@pytest.mark.asyncio
@pytest.mark.parametrize("method, path, body", ENDPOINTS)
async def test_every_endpoint_is_platform_admin_only(client, db_session, world, method, path, body):
    assert (await _call(client, {}, method, path, body)).status_code == 401
    for role in ("owner", "editor", "viewer", "other"):  # brand owners and members are not platform admins
        assert (await _call(client, world["h"][role], method, path, body)).status_code == 403, role
    assert (await db_session.execute(select(CapabilityValidation))).scalars().all() == []
    assert await _audit(db_session) == []


# ========================== Lifecycle =============================

@pytest.mark.asyncio
async def test_register_validate_promote_with_audit_trail(client, db_session, world):
    admin, admin_user = world["h"]["admin"], world["users"]["admin"]
    created = await _registered(client, world)
    assert {k: created[k] for k in ("character_id", "capability_type", "capability_key", "capability_version",
                                    "customer_id", "status", "group", "is_default", "recommended")} == {
        "character_id": "EE-F-002", "capability_type": "HAIR", "capability_key": "SOFT_WAVES",
        "capability_version": 1, "customer_id": "hair_soft_waves", "status": "REGISTERED", "group": "Polished",
        "is_default": False, "recommended": False}

    started = await client.post(f"{HAIR}/validation/start", json={"capability_version": 1}, headers=admin)
    assert started.status_code == 200 and started.json()["status"] == "VALIDATING"

    validated = await client.post(f"{HAIR}/validation", json=VALIDATE, headers=admin)
    assert validated.status_code == 200
    body = validated.json()
    assert (body["status"], body["validated_by"]) == ("VALIDATED", "platform-admin@modelens.ai")
    assert body["validated_at"]

    promoted = await client.post(f"{HAIR}/promote", json={"capability_version": 1, "is_default": True,
                                                         "recommended": True}, headers=admin)
    assert promoted.status_code == 200
    body = promoted.json()
    assert (body["status"], body["promoted_by"], body["replaced_version"]) == (
        "PROMOTED", "platform-admin@modelens.ai", None)
    assert body["promoted_at"]

    record = (await db_session.execute(select(CapabilityValidation)
                                       .execution_options(populate_existing=True))).scalars().one()
    assert record.validation == {"checks": ALL_PASS, "evidence": {"sample_production_ids": ["prd_val_001"]}}
    assert (record.is_default, record.recommended) == (True, True)
    # Same admin validated and promoted: allowed while the four-eyes rule is pending.
    assert record.validated_by == record.promoted_by

    entries = await _audit(db_session)
    assert [(e.action, e.details["from_status"], e.details["to_status"]) for e in entries] == [
        ("capability_registered", None, "REGISTERED"),
        ("capability_validation_started", "REGISTERED", "VALIDATING"),
        ("capability_validated", "VALIDATING", "VALIDATED"),
        ("capability_promoted", "VALIDATED", "PROMOTED"),
    ]
    for e in entries:
        assert e.user_id == admin_user.id and e.created_at
        assert e.details["actor_email"] == "platform-admin@modelens.ai"
        assert {k: e.details[k] for k in ("character_id", "character_version", "capability_type",
                                          "capability_key", "capability_version", "customer_id")} == {
            "character_id": "EE-F-002", "character_version": "1.0", "capability_type": "HAIR",
            "capability_key": "SOFT_WAVES", "capability_version": 1, "customer_id": "hair_soft_waves"}
    assert entries[2].details["checks"] == ALL_PASS
    assert (entries[3].details["is_default"], entries[3].details["replaced_version"]) == (True, None)


@pytest.mark.asyncio
async def test_failed_check_rejects_and_rework_needs_a_new_start(client, db_session, world):
    admin = world["h"]["admin"]
    await _registered(client, world)
    failed = {**VALIDATE, "checks": {**ALL_PASS, "body": "FAIL"}}
    resp = await client.post(f"{HAIR}/validation", json=failed, headers=admin)
    assert resp.status_code == 200 and resp.json()["status"] == "REJECTED"
    resp = await client.post(f"{HAIR}/validation", json=VALIDATE, headers=admin)
    assert resp.status_code == 409
    assert "REJECTED" in resp.json()["detail"] and "start validation again" in resp.json()["detail"]
    assert (await client.post(f"{HAIR}/validation/start", json={"capability_version": 1},
                              headers=admin)).json()["status"] == "VALIDATING"
    assert (await client.post(f"{HAIR}/validation", json=VALIDATE, headers=admin)).json()["status"] == "VALIDATED"
    actions = [e.action for e in await _audit(db_session)]
    assert actions == ["capability_registered", "capability_rejected", "capability_validation_started",
                       "capability_validated"]


@pytest.mark.asyncio
async def test_promoting_v2_retires_v1_and_audits_both(client, db_session, world):
    await _promoted(client, world)
    body = await _promoted(client, world, version=2)
    assert body["replaced_version"] == 1
    listed = (await client.get(f"{BASE}?type=HAIR", headers=world["h"]["admin"])).json()["capabilities"]
    assert [(c["capability_version"], c["status"]) for c in listed] == [(1, "RETIRED"), (2, "PROMOTED")]
    assert listed[0]["retire_reason"] == "Replaced by version 2."
    retired = [e for e in await _audit(db_session) if e.action == "capability_retired"]
    assert len(retired) == 1
    assert (retired[0].details["capability_version"], retired[0].details["from_status"],
            retired[0].details["to_status"], retired[0].details["replaced_by_version"]) == (1, "PROMOTED", "RETIRED", 2)


@pytest.mark.asyncio
async def test_retire_records_who_why_and_is_final(client, db_session, world):
    admin = world["h"]["admin"]
    await _promoted(client, world)
    resp = await client.post(f"{HAIR}/retire", json={"capability_version": 1, "reason": "Hand artefacts at 4K."},
                             headers=admin)
    assert resp.status_code == 200
    assert {k: resp.json()[k] for k in ("status", "retired_by", "retire_reason")} == {
        "status": "RETIRED", "retired_by": "platform-admin@modelens.ai", "retire_reason": "Hand artefacts at 4K."}
    again = await client.post(f"{HAIR}/retire", json={"capability_version": 1, "reason": "again"}, headers=admin)
    assert again.status_code == 409
    assert again.json()["detail"] == ("HAIR SOFT_WAVES v1 is RETIRED and cannot move to RETIRED. "
                                      "Allowed next statuses: none (final).")
    entry = (await _audit(db_session))[-1]
    assert (entry.action, entry.details["from_status"], entry.details["reason"]) == (
        "capability_retired", "PROMOTED", "Hand artefacts at 4K.")


@pytest.mark.asyncio
@pytest.mark.parametrize("setup, path, body, needle", [
    ("registered", "promote", {"capability_version": 1}, "is REGISTERED; only VALIDATED records can be promoted"),
    ("promoted", "promote", {"capability_version": 1}, "is PROMOTED; only VALIDATED records can be promoted"),
    ("promoted", "validation", VALIDATE, "is PROMOTED; validation results can be recorded only"),
    ("promoted", "validation/start", {"capability_version": 1},
     "is PROMOTED and cannot move to VALIDATING. Allowed next statuses: RETIRED."),
])
async def test_invalid_transitions_are_409_and_change_nothing(client, db_session, world, setup, path, body, needle):
    if setup == "registered":
        await _registered(client, world)
    else:
        await _promoted(client, world)
    before = [(e.id, e.action) for e in await _audit(db_session)]
    resp = await client.post(f"{HAIR}/{path}", json=body, headers=world["h"]["admin"])
    assert resp.status_code == 409
    assert needle in resp.json()["detail"]
    assert [(e.id, e.action) for e in await _audit(db_session)] == before
    record = (await db_session.execute(select(CapabilityValidation)
                                       .execution_options(populate_existing=True))).scalars().one()
    assert record.status == ("REGISTERED" if setup == "registered" else "PROMOTED")


# ========================== Register rules and lookups ============

@pytest.mark.asyncio
async def test_register_conflicts_are_409(client, db_session, world):
    await _registered(client, world)
    dup = await client.post(BASE, json=REGISTER, headers=world["h"]["admin"])
    assert dup.status_code == 409 and "already registered" in dup.json()["detail"]
    taken = await client.post(BASE, json={**REGISTER, "capability_key": "SLEEK_BUN"}, headers=world["h"]["admin"])
    assert taken.status_code == 409 and "hair_soft_waves is already used" in taken.json()["detail"]
    assert len(await _audit(db_session)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("override, code", [
    ({"capability_type": "NAILS"}, 422),
    ({"customer_id": "Hair Soft"}, 422),
    ({"capability_key": "bad key!"}, 422),
    ({"capability_version": 0}, 422),
    ({"character_version": "9.9"}, 404),
])
async def test_register_validation(client, world, override, code):
    resp = await client.post(BASE, json={**REGISTER, **override}, headers=world["h"]["admin"])
    assert resp.status_code == code, resp.text


@pytest.mark.asyncio
async def test_unknown_character_or_capability_is_404(client, world):
    admin = world["h"]["admin"]
    assert (await client.post("/api/v1/admin/characters/EE-X-999/capabilities/HAIR/SOFT_WAVES/promote",
                              json={"capability_version": 1}, headers=admin)).status_code == 404
    assert (await client.post(f"{HAIR}/promote", json={"capability_version": 1}, headers=admin)).status_code == 404
    assert (await client.post(f"{BASE}/NAILS/X/promote", json={"capability_version": 1},
                              headers=admin)).status_code == 422


@pytest.mark.asyncio
async def test_character_version_defaults_to_the_current_locked_version(client, world):
    await _registered(client, world)
    resp = await client.post(f"{HAIR}/validation", json={**VALIDATE, "character_version": None},
                             headers=world["h"]["admin"])
    assert resp.status_code == 200 and resp.json()["status"] == "VALIDATED"
    other = await client.post(f"{HAIR}/promote", json={"capability_version": 1, "character_version": "2.0"},
                              headers=world["h"]["admin"])
    assert other.status_code == 404


@pytest.mark.asyncio
async def test_list_filters_and_includes_backfilled_records(client, db_session, world):
    await cv.backfill_promoted(db_session)
    await _registered(client, world)
    admin = world["h"]["admin"]
    everything = (await client.get(BASE, headers=admin)).json()
    assert everything["total"] == len(everything["capabilities"]) > 1
    hair = (await client.get(f"{BASE}?type=HAIR", headers=admin)).json()["capabilities"]
    assert {(c["capability_key"], c["status"]) for c in hair} == {("CANONICAL", "PROMOTED"),
                                                                   ("SOFT_WAVES", "REGISTERED")}
    registered = (await client.get(f"{BASE}?status=REGISTERED", headers=admin)).json()["capabilities"]
    assert [c["capability_key"] for c in registered] == ["SOFT_WAVES"]
    assert (await client.get(f"{BASE}?character_version=2.0", headers=admin)).json()["total"] == 0
    assert (await client.get(f"{BASE}?type=NAILS", headers=admin)).status_code == 422


# ========================== Customers unchanged ===================

@pytest.mark.asyncio
async def test_admin_actions_leave_customer_responses_byte_identical(client, db_session, world):
    viewer = world["h"]["viewer"]
    before = {}
    for path in CUSTOMER_ROUTES:
        resp = await client.get(path, headers=viewer)
        assert resp.status_code == 200, path
        before[path] = resp.content
    await cv.backfill_promoted(db_session)
    await _promoted(client, world, is_default=True, recommended=True)
    await _registered(client, world, capability_type="POSE", capability_key="hand_on_hip",
                      customer_id="pose_hand_on_hip")
    retire = await client.post(f"{BASE}/SCENE/ENV-STU-0001/retire", json={"capability_version": 1, "reason": "x"},
                               headers=world["h"]["admin"])
    assert retire.status_code == 200
    for path in CUSTOMER_ROUTES:
        resp = await client.get(path, headers=viewer)
        assert resp.content == before[path], path
        assert_no_forbidden_terms(resp.text)
