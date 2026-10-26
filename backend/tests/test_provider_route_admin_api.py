"""Provider route admin API: platform-admin only, DRAFT on register, 409 on invalid transitions, audit log per
write, pack_live, and customer routes unchanged."""
import pytest
from sqlalchemy import select

from app.models.db import AuditLog, ProviderRoute
from app.services import capability_packs as pack_service
from test_capability_validations import CUSTOMER_ROUTES, assert_no_forbidden_terms
from test_production_dispatch import DISPATCH, _assert_customer_safe, _body, queue, world  # noqa: F401 (fixtures)

BASE = "/api/v1/admin/provider-routes"
ROUTE = f"{BASE}/RT-SHOES-01"
REGISTER = {"route_id": "RT-SHOES-01", "workflow_id": "WF-FOOTWEAR-TRYON", "quality_mode": "STUDIO_QUALITY",
            "provider_id": "PRV-COMFYUI", "model_id": "MDL-FLUX-01", "priority": 2, "meta": {"region": "eu"}}
REASON = {"reason": "Staging run passed QA."}
ENDPOINTS = (
    ("post", BASE, REGISTER),
    ("get", BASE, None),
    ("get", f"{BASE}/RT-GARMENT-01", None),
    ("post", f"{BASE}/RT-GARMENT-01/enable", REASON),
    ("post", f"{BASE}/RT-GARMENT-01/disable", REASON),
    ("post", f"{BASE}/RT-GARMENT-01/retire", REASON),
)


async def _call(client, headers, method, path, body=None):
    if method == "get":
        return await client.get(path, headers=headers)
    return await client.post(path, json=body, headers=headers)


async def _audit(db):
    rows = (await db.execute(select(AuditLog).where(AuditLog.action.like("provider_route_%"))
                             .order_by(AuditLog.id).execution_options(populate_existing=True))).scalars().all()
    return list(rows)


async def _route(db, route_id):
    return (await db.execute(select(ProviderRoute).where(ProviderRoute.route_id == route_id)
                             .execution_options(populate_existing=True))).scalars().one()


async def _registered(client, world, **overrides):
    resp = await client.post(BASE, json={**REGISTER, **overrides}, headers=world["h"]["admin"])
    assert resp.status_code == 201, resp.text
    return resp.json()


# ========================== Access ================================

@pytest.mark.asyncio
@pytest.mark.parametrize("method, path, body", ENDPOINTS)
async def test_every_endpoint_is_platform_admin_only(client, db_session, world, method, path, body):
    assert (await _call(client, {}, method, path, body)).status_code == 401
    for role in ("owner", "editor", "viewer", "other"):  # brand owners and members are not platform admins
        assert (await _call(client, world["h"][role], method, path, body)).status_code == 403, role
    routes = (await db_session.execute(select(ProviderRoute.route_id, ProviderRoute.status)
                                       .execution_options(populate_existing=True))).all()
    assert sorted(routes) == [("RT-GARMENT-01", "ACTIVE"), ("RT-GARMENT-DRAFT", "ACTIVE")]
    assert await _audit(db_session) == []


# ========================== Register ==============================

@pytest.mark.asyncio
async def test_register_creates_draft_with_audit(client, db_session, world):
    created = await _registered(client, world)
    assert {k: created[k] for k in REGISTER} == REGISTER
    assert (created["status"], created["fallback_route_id"]) == ("DRAFT", None)
    assert created["allowed_next_statuses"] == ["ACTIVE", "RETIRED"]
    assert created["pack_live"] is False  # no PRODUCTION pack uses WF-FOOTWEAR-TRYON
    assert created["created_at"]
    assert (await _route(db_session, "RT-SHOES-01")).status == "DRAFT"

    (entry,) = await _audit(db_session)
    assert entry.action == "provider_route_registered"
    assert entry.user_id == world["users"]["admin"].id and entry.created_at
    assert entry.details == {"actor_email": "platform-admin@modelens.ai", "route_id": "RT-SHOES-01",
                             "workflow_id": "WF-FOOTWEAR-TRYON", "quality_mode": "STUDIO_QUALITY",
                             "provider_id": "PRV-COMFYUI", "from_status": None, "to_status": "DRAFT"}


@pytest.mark.asyncio
async def test_register_with_existing_fallback(client, world):
    created = await _registered(client, world, workflow_id="WF-GARMENT-TRYON", fallback_route_id="RT-GARMENT-01")
    assert created["fallback_route_id"] == "RT-GARMENT-01"
    assert created["pack_live"] is True  # the garment pack is in PRODUCTION


@pytest.mark.asyncio
async def test_register_duplicate_is_409_without_audit(client, db_session, world):
    resp = await client.post(BASE, json={**REGISTER, "route_id": "RT-GARMENT-01"}, headers=world["h"]["admin"])
    assert resp.status_code == 409 and "already registered" in resp.json()["detail"]
    assert (await _route(db_session, "RT-GARMENT-01")).workflow_id == "WF-GARMENT-TRYON"
    assert await _audit(db_session) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback, message", [
    ("RT-NOPE", "not a registered route"),
    ("RT-SHOES-01", "cannot be the route itself"),
])
async def test_register_bad_fallback_is_400(client, db_session, world, fallback, message):
    resp = await client.post(BASE, json={**REGISTER, "fallback_route_id": fallback}, headers=world["h"]["admin"])
    assert resp.status_code == 400 and message in resp.json()["detail"]
    assert (await db_session.execute(select(ProviderRoute).where(ProviderRoute.route_id == "RT-SHOES-01"))
            ).scalars().first() is None
    assert await _audit(db_session) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides", [
    {"route_id": "rt garment"},
    {"route_id": "-RT"},
    {"route_id": "R" * 51},
    {"provider_id": "PRV/COMFYUI"},
    {"provider_id": ""},
    {"workflow_id": "WF GARMENT"},
    {"quality_mode": "turbo"},
    {"priority": 0},
    {"status": "ACTIVE"},  # register cannot choose the status
    {"avg_qa_score": 0.9},
])
async def test_register_rejects_invalid_or_extra_fields(client, db_session, world, overrides):
    resp = await client.post(BASE, json={**REGISTER, **overrides}, headers=world["h"]["admin"])
    assert resp.status_code == 422, overrides
    assert await _audit(db_session) == []


@pytest.mark.asyncio
async def test_register_requires_core_fields(client, world):
    for field in ("route_id", "workflow_id", "quality_mode", "provider_id"):
        body = {k: v for k, v in REGISTER.items() if k != field}
        assert (await client.post(BASE, json=body, headers=world["h"]["admin"])).status_code == 422, field


@pytest.mark.asyncio
async def test_register_accepts_tier_and_legacy_quality_names(client, world):
    for i, mode in enumerate(("fast_preview", "high_fidelity", "ultra_master", "FAST_DRAFT", "ULTRA_MASTER")):
        created = await _registered(client, world, route_id=f"RT-Q-{i}", quality_mode=mode)
        assert created["quality_mode"] == mode


# ========================== Lifecycle =============================

@pytest.mark.asyncio
async def test_enable_disable_reenable_retire_with_audit_trail(client, db_session, world):
    admin = world["h"]["admin"]
    await _registered(client, world)
    steps = (("enable", "ACTIVE", ["DISABLED", "RETIRED"]), ("disable", "DISABLED", ["ACTIVE", "RETIRED"]),
             ("enable", "ACTIVE", ["DISABLED", "RETIRED"]), ("retire", "RETIRED", []))
    for action, expected, allowed in steps:
        resp = await client.post(f"{ROUTE}/{action}", json=REASON, headers=admin)
        assert resp.status_code == 200, resp.text
        assert (resp.json()["status"], resp.json()["allowed_next_statuses"]) == (expected, allowed)
        assert (await _route(db_session, "RT-SHOES-01")).status == expected

    entries = await _audit(db_session)
    assert [(e.action, e.details["from_status"], e.details["to_status"]) for e in entries] == [
        ("provider_route_registered", None, "DRAFT"),
        ("provider_route_enabled", "DRAFT", "ACTIVE"),
        ("provider_route_disabled", "ACTIVE", "DISABLED"),
        ("provider_route_enabled", "DISABLED", "ACTIVE"),
        ("provider_route_retired", "ACTIVE", "RETIRED"),
    ]
    for e in entries:
        assert e.user_id == world["users"]["admin"].id
        assert (e.details["actor_email"], e.details["route_id"]) == ("platform-admin@modelens.ai", "RT-SHOES-01")
    assert all(e.details["reason"] == "Staging run passed QA." for e in entries[1:])


@pytest.mark.asyncio
async def test_draft_can_be_retired_directly(client, world):
    await _registered(client, world)
    resp = await client.post(f"{ROUTE}/retire", json=REASON, headers=world["h"]["admin"])
    assert resp.status_code == 200 and resp.json()["status"] == "RETIRED"


@pytest.mark.asyncio
@pytest.mark.parametrize("setup, action, current", [
    ((), "disable", "DRAFT"),
    (("enable",), "enable", "ACTIVE"),
    (("enable", "disable"), "disable", "DISABLED"),
    (("retire",), "enable", "RETIRED"),
    (("retire",), "disable", "RETIRED"),
    (("retire",), "retire", "RETIRED"),
])
async def test_invalid_transition_is_409_naming_allowed_next(client, db_session, world, setup, action, current):
    admin = world["h"]["admin"]
    await _registered(client, world)
    for step in setup:
        assert (await client.post(f"{ROUTE}/{step}", json=REASON, headers=admin)).status_code == 200
    before = len(await _audit(db_session))
    resp = await client.post(f"{ROUTE}/{action}", json=REASON, headers=admin)
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert f"is {current}" in detail and "Allowed next statuses:" in detail
    if current == "RETIRED":
        assert "none (final)" in detail
    assert (await _route(db_session, "RT-SHOES-01")).status == current
    assert len(await _audit(db_session)) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [None, "INACTIVE"])
async def test_legacy_status_can_be_disabled_then_enabled(client, db_session, world, legacy):
    admin = world["h"]["admin"]
    route = await _route(db_session, "RT-GARMENT-01")
    route.status = legacy
    await db_session.commit()
    path = f"{BASE}/RT-GARMENT-01"
    got = (await client.get(path, headers=admin)).json()
    assert (got["status"], got["allowed_next_statuses"]) == (legacy, ["DISABLED", "RETIRED"])
    resp = await client.post(f"{path}/enable", json=REASON, headers=admin)
    assert resp.status_code == 409 and f"is {legacy or 'unset'}" in resp.json()["detail"]
    assert (await client.post(f"{path}/disable", json=REASON, headers=admin)).json()["status"] == "DISABLED"
    assert (await client.post(f"{path}/enable", json=REASON, headers=admin)).json()["status"] == "ACTIVE"
    assert [e.details["from_status"] for e in await _audit(db_session)] == [legacy, "DISABLED"]


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{}, {"reason": ""}, {"reason": "x" * 1001}, {"reason": "ok", "status": "ACTIVE"}])
async def test_transition_requires_a_reason(client, db_session, world, body):
    for action in ("enable", "disable", "retire"):
        resp = await client.post(f"{BASE}/RT-GARMENT-01/{action}", json=body, headers=world["h"]["admin"])
        assert resp.status_code == 422, (action, body)
    assert (await _route(db_session, "RT-GARMENT-01")).status == "ACTIVE"
    assert await _audit(db_session) == []


@pytest.mark.asyncio
async def test_whitespace_reason_is_400(client, db_session, world):
    resp = await client.post(f"{BASE}/RT-GARMENT-01/disable", json={"reason": "   "}, headers=world["h"]["admin"])
    assert resp.status_code == 400 and "reason is required" in resp.json()["detail"]
    assert (await _route(db_session, "RT-GARMENT-01")).status == "ACTIVE"
    assert await _audit(db_session) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("method, suffix, body", [
    ("get", "", None), ("post", "/enable", REASON), ("post", "/disable", REASON), ("post", "/retire", REASON),
])
async def test_unknown_route_is_404(client, db_session, world, method, suffix, body):
    resp = await _call(client, world["h"]["admin"], method, f"{BASE}/RT-NOPE{suffix}", body)
    assert resp.status_code == 404 and "RT-NOPE not found" in resp.json()["detail"]
    assert await _audit(db_session) == []


# ========================== Reads =================================

@pytest.mark.asyncio
async def test_list_and_filters(client, db_session, world):
    admin = world["h"]["admin"]
    await _registered(client, world)
    listed = (await client.get(BASE, headers=admin)).json()
    assert listed["total"] == 3
    assert [r["route_id"] for r in listed["routes"]] == ["RT-SHOES-01", "RT-GARMENT-01", "RT-GARMENT-DRAFT"]
    by_id = {r["route_id"]: r for r in listed["routes"]}
    assert by_id["RT-GARMENT-01"]["pack_live"] is True and by_id["RT-SHOES-01"]["pack_live"] is False

    async def ids(query):
        resp = await client.get(f"{BASE}?{query}", headers=admin)
        assert resp.status_code == 200, resp.text
        return sorted(r["route_id"] for r in resp.json()["routes"])

    assert await ids("workflow_id=WF-GARMENT-TRYON") == ["RT-GARMENT-01", "RT-GARMENT-DRAFT"]
    assert await ids("status=DRAFT") == ["RT-SHOES-01"]
    assert await ids("status=ACTIVE&quality_mode=FAST_DRAFT") == ["RT-GARMENT-DRAFT"]
    assert await ids("status=RETIRED") == []
    assert (await client.get(f"{BASE}?status=LIVE", headers=admin)).status_code == 422


@pytest.mark.asyncio
async def test_get_shows_pack_live_and_does_not_require_it_to_enable(client, db_session, world):
    admin = world["h"]["admin"]
    path = f"{BASE}/RT-GARMENT-01"
    got = (await client.get(path, headers=admin)).json()
    assert (got["route_id"], got["provider_id"], got["pack_live"]) == ("RT-GARMENT-01", "PRV-COMFYUI", True)

    await pack_service.change_status(db_session, world["pack"].internal_key, "ARCHIVED", "admin")
    assert (await client.post(f"{path}/disable", json=REASON, headers=admin)).status_code == 200
    resp = await client.post(f"{path}/enable", json=REASON, headers=admin)
    assert resp.status_code == 200
    assert (resp.json()["status"], resp.json()["pack_live"]) == ("ACTIVE", False)


# ========================== Customer routes =======================

@pytest.mark.asyncio
async def test_admin_route_changes_leave_customer_routes_unchanged(client, world):
    admin, owner = world["h"]["admin"], world["h"]["owner"]
    before = {}
    for path in CUSTOMER_ROUTES:
        resp = await client.get(path, headers=owner)
        assert resp.status_code == 200, (path, resp.text)
        assert_no_forbidden_terms(resp.text)
        before[path] = resp.content
    await _registered(client, world)
    for action in ("enable", "disable", "retire"):
        assert (await client.post(f"{ROUTE}/{action}", json=REASON, headers=admin)).status_code == 200
    assert (await client.post(f"{BASE}/RT-GARMENT-DRAFT/disable", json=REASON, headers=admin)).status_code == 200
    for path in CUSTOMER_ROUTES:
        assert (await client.get(path, headers=owner)).content == before[path], path


@pytest.mark.asyncio
async def test_customer_production_responses_carry_no_route_fields(client, world, queue):
    admin, owner = world["h"]["admin"], world["h"]["owner"]
    for route_id in ("RT-GARMENT-01", "RT-GARMENT-DRAFT"):
        assert (await client.post(f"{BASE}/{route_id}/retire", json=REASON, headers=admin)).status_code == 200
    await _registered(client, world, route_id="RT-GARMENT-02", workflow_id="WF-GARMENT-TRYON")
    unavailable = await client.post(DISPATCH, json=_body(world), headers=owner)
    assert unavailable.status_code == 409
    _assert_customer_safe(unavailable.text)

    assert (await client.post(f"{BASE}/RT-GARMENT-02/enable", json=REASON, headers=admin)).status_code == 200
    dispatched = await client.post(DISPATCH, json=_body(world), headers=owner)
    assert dispatched.status_code == 202, dispatched.text
    _assert_customer_safe(dispatched.text)
    status = await client.get(f"/api/v1/productions/{dispatched.json()['production_id']}", headers=owner)
    assert status.status_code == 200
    _assert_customer_safe(status.text)
