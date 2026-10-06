"""P3 Registry: admin-only writes and the model lifecycle on /models/{model_id}/promote."""
import re

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.main import app
from app.models.db import ModelArtifact, RuntimePromotion
from test_training_registry import (  # noqa: F401 (fixtures)
    BASE as TRAINING,
    _adapter,
    _headers,
    _passed_run,
    admin,
    seeded,
    users,
)


def _p3_write_routes():
    for route in app.routes:
        if isinstance(route, APIRoute) and "P3 Registry" in (route.tags or []):
            for method in route.methods - {"GET", "HEAD"}:
                yield method, route.path


P3_WRITE_ROUTES = sorted(_p3_write_routes())


async def _model(client, admin, model_id="P3-MODEL-1"):
    resp = await client.post("/api/v1/models", json={"model_id": model_id, "character_id": "EE-F-002"}, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _promote(client, headers, model_id, new_status):
    return await client.patch(f"/api/v1/models/{model_id}/promote", params={"new_status": new_status}, headers=headers)


async def _walk(client, admin, model_id, *statuses):
    for new_status in statuses:
        resp = await _promote(client, admin, model_id, new_status)
        assert resp.status_code == 200, resp.text


async def _status_of(db_session, model_id):
    db_session.expire_all()
    row = (await db_session.execute(select(ModelArtifact).where(ModelArtifact.model_id == model_id))).scalars().first()
    return row.status


# ========================== Admin only ============================

def test_p3_write_routes_discovered():
    assert P3_WRITE_ROUTES == sorted([
        ("POST", "/api/v1/datasets"),
        ("POST", "/api/v1/datasets/{dataset_id}/items"),
        ("POST", "/api/v1/datasets/{dataset_id}/freeze"),
        ("POST", "/api/v1/experiments"),
        ("POST", "/api/v1/experiments/{run_id}/metrics"),
        ("POST", "/api/v1/models"),
        ("PATCH", "/api/v1/models/{model_id}/promote"),
        ("POST", "/api/v1/rights"),
    ])


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", P3_WRITE_ROUTES)
async def test_non_admin_gets_403_on_every_write(client, users, method, path):
    url = re.sub(r"\{[^}]+\}", "X-1", path)
    resp = await client.request(method, url, json={}, params={"new_status": "VALIDATION"},
                                headers=_headers(users["customer"]))
    assert resp.status_code == 403, (method, path, resp.text)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", P3_WRITE_ROUTES)
async def test_unauthenticated_gets_401_on_every_write(client, method, path):
    url = re.sub(r"\{[^}]+\}", "X-1", path)
    resp = await client.request(method, url, json={}, params={"new_status": "VALIDATION"})
    assert resp.status_code == 401, (method, path, resp.text)


@pytest.mark.asyncio
async def test_customer_cannot_promote_and_status_is_unchanged(client, users, admin, db_session):
    await _model(client, admin)
    resp = await _promote(client, _headers(users["customer"]), "P3-MODEL-1", "VALIDATION")
    assert resp.status_code == 403
    assert await _status_of(db_session, "P3-MODEL-1") == "EXPERIMENTAL"


@pytest.mark.asyncio
async def test_reads_stay_open_to_logged_in_users(client, users, admin):
    await _model(client, admin)
    resp = await client.get("/api/v1/models", headers=_headers(users["customer"]))
    assert resp.status_code == 200
    assert [m["model_id"] for m in resp.json()["models"]] == ["P3-MODEL-1"]


@pytest.mark.asyncio
async def test_admin_writes_keep_their_response_shapes(client, admin):
    resp = await client.post("/api/v1/datasets", json={
        "dataset_id": "P3-DS-1", "display_name": "P3 set", "purpose": "DATA-PURPOSE-TRAIN"}, headers=admin)
    assert (resp.status_code, resp.json()) == (201, {"dataset_id": "P3-DS-1", "status": "created"})
    resp = await client.post("/api/v1/datasets/P3-DS-1/freeze", headers=admin)
    assert resp.status_code == 200 and resp.json()["status"] == "FROZEN"
    resp = await client.post("/api/v1/experiments", json={"run_id": "P3-RUN-1", "experiment_name": "p3"}, headers=admin)
    assert (resp.status_code, resp.json()) == (201, {"run_id": "P3-RUN-1", "status": "QUEUED"})
    assert await _model(client, admin) == {"model_id": "P3-MODEL-1", "status": "EXPERIMENTAL"}
    resp = await client.post("/api/v1/rights", json={
        "rights_id": "R-1", "resource_type": "asset", "resource_id": "1"}, headers=admin)
    assert (resp.status_code, resp.json()) == (201, {"rights_id": "R-1", "status": "created"})


# ========================== Lifecycle =============================

@pytest.mark.asyncio
async def test_admin_walks_plain_model_to_production(client, admin, db_session):
    await _model(client, admin)
    for new_status in ("VALIDATION", "APPROVED", "PRODUCTION"):
        resp = await _promote(client, admin, "P3-MODEL-1", new_status)
        assert (resp.status_code, resp.json()) == (200, {"model_id": "P3-MODEL-1", "status": new_status})
    db_session.expire_all()
    row = (await db_session.execute(select(ModelArtifact).where(ModelArtifact.model_id == "P3-MODEL-1"))).scalars().first()
    assert row.production_alias == "PROD-EE-F-002-P3-MODEL-1"
    await _walk(client, admin, "P3-MODEL-1", "DEPRECATED", "RETIRED")


@pytest.mark.asyncio
@pytest.mark.parametrize("path,target", [
    ((), "PRODUCTION"),                                 # EXPERIMENTAL -> PRODUCTION skips two steps
    ((), "APPROVED"),                                   # EXPERIMENTAL -> APPROVED skips VALIDATION
    (("VALIDATION",), "PRODUCTION"),                    # VALIDATION -> PRODUCTION skips APPROVED
    ((), "EXPERIMENTAL"),                               # same status
    ((), "DEPRECATED"),                                 # only PRODUCTION can be deprecated
    (("RETIRED",), "EXPERIMENTAL"),                     # RETIRED is final
    (("VALIDATION", "APPROVED", "PRODUCTION"), "APPROVED"),  # no going back from PRODUCTION
])
async def test_invalid_transition_is_409(client, admin, db_session, path, target):
    await _model(client, admin)
    await _walk(client, admin, "P3-MODEL-1", *path)
    before = await _status_of(db_session, "P3-MODEL-1")
    resp = await _promote(client, admin, "P3-MODEL-1", target)
    assert resp.status_code == 409, resp.text
    assert f"to {target}" in resp.json()["detail"]
    assert await _status_of(db_session, "P3-MODEL-1") == before


@pytest.mark.asyncio
async def test_validation_can_go_back_to_experimental(client, admin):
    await _model(client, admin)
    await _walk(client, admin, "P3-MODEL-1", "VALIDATION", "EXPERIMENTAL", "VALIDATION")


@pytest.mark.asyncio
async def test_unknown_status_is_400_and_unknown_model_is_404(client, admin):
    await _model(client, admin)
    assert (await _promote(client, admin, "P3-MODEL-1", "LIVE")).status_code == 400
    assert (await _promote(client, admin, "NOPE", "VALIDATION")).status_code == 404


# ========================== Training adapters =====================

@pytest.mark.asyncio
async def test_trained_adapter_cannot_be_set_to_production_here(client, admin, db_session, seeded):
    await _passed_run(client, admin)
    assert (await _adapter(client, admin)).status_code == 201
    # Earlier steps are fine; PRODUCTION is not.
    await _walk(client, admin, "ADP-ID-1", "VALIDATION", "APPROVED")
    resp = await _promote(client, admin, "ADP-ID-1", "PRODUCTION")
    assert resp.status_code == 409
    assert "/api/v1/admin/training/runs/RUN-1/promote" in resp.json()["detail"]
    assert await _status_of(db_session, "ADP-ID-1") == "APPROVED"
    assert (await db_session.execute(select(RuntimePromotion))).scalars().all() == []


@pytest.mark.asyncio
async def test_adapter_without_run_cannot_be_set_to_production_here(client, admin, db_session, seeded):
    resp = await _adapter(client, admin, adapter_id="ADP-WF", layer="POSE", kind="WORKFLOW", run_id=None,
                          checkpoint_id=None, reference={"workflow_id": "WF-POSE"})
    assert resp.status_code == 201, resp.text
    await _walk(client, admin, "ADP-WF", "VALIDATION", "APPROVED")
    resp = await _promote(client, admin, "ADP-WF", "PRODUCTION")
    assert resp.status_code == 409
    assert "/api/v1/admin/training/runs/{run_id}/promote" in resp.json()["detail"]
    assert await _status_of(db_session, "ADP-WF") == "APPROVED"


@pytest.mark.asyncio
async def test_training_promotion_still_works(client, admin, db_session, seeded):
    await _passed_run(client, admin)
    assert (await _adapter(client, admin)).status_code == 201
    resp = await client.post(f"{TRAINING}/runs/RUN-1/promote", json={"adapter_id": "ADP-ID-1"}, headers=admin)
    assert resp.status_code == 201, resp.text
    assert await _status_of(db_session, "ADP-ID-1") == "PRODUCTION"
    # Retiring a live adapter is still an admin step on the P3 lifecycle.
    await _walk(client, admin, "ADP-ID-1", "DEPRECATED")
