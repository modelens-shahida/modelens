"""Privileged admin actions: platform admins only.

* POST /api/v1/admin/settings changes settings for every brand, so only a
  platform admin/owner (users.role) may call it; brand admins/owners keep
  read access (GET, with their own brand-scoped metrics).
* POST /api/v1/ghost/batch/{job_id}/complete and /fail finalize or refund
  ledger credits. Nothing calls them in normal operation (no worker task
  processes ghost batches), so they are manual recovery tools for platform
  admins; brand members, including brand admins and owners, get 403.
"""
from unittest.mock import MagicMock

import celery.app.task
import pytest
from sqlalchemy import func, select

from app.middleware import rate_limit
from app.middleware.auth import create_access_token, hash_password
from app.models.db import Brand, CreditTransaction, GhostJob, Production, User


@pytest.fixture(autouse=True)
def ghost_batches_enabled(monkeypatch):
    """These tests cover batch behaviour when enabled; it is off by default (see test_ghost_batch_disabled.py)."""
    from app.config import settings
    monkeypatch.setattr(settings, "GHOST_BATCH_ENABLED", True)


SETTINGS = "/api/v1/admin/settings"
GHOST_BATCH = "/api/v1/ghost/batch"
PRODUCTION_FIELDS = {"productions_total", "productions_success", "productions_failed", "productions_retries",
                     "productions_in_progress", "productions_cancelled"}


@pytest.fixture
def queued(monkeypatch):
    """Every Celery .delay call (one shared mock for all tasks)."""
    delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr(celery.app.task.Task, "delay", delay)
    return delay


async def _platform_user(db_session, role: str) -> dict:
    user = User(email=f"platform-{role}@modelens.ai", hashed_password=hash_password("pw"), full_name="Platform",
                role=role)
    db_session.add(user)
    await db_session.commit()
    return {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}


async def _ledger(db_session):
    """Every credit transaction (status included) and every brand balance."""
    txns = (await db_session.execute(select(
        CreditTransaction.reference_id, CreditTransaction.transaction_type, CreditTransaction.status,
        CreditTransaction.amount).order_by(CreditTransaction.id))).all()
    brands = (await db_session.execute(select(Brand.id, Brand.credits).order_by(Brand.id))).all()
    return txns, brands


async def _limit() -> str:
    return await rate_limit.redis_client.get("settings:orchestrator_rate_limit")


# ========================== POST /admin/settings ==================

@pytest.mark.asyncio
@pytest.mark.parametrize("platform_role", ["admin", "owner"])
async def test_platform_admin_can_change_settings(client, db_session, platform_role):
    headers = await _platform_user(db_session, platform_role)
    resp = await client.post(SETTINGS, json={"orchestrator_rate_limit": 25}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "success", "orchestrator_rate_limit": 25}
    assert str(await _limit()) == "25"
    assert (await client.get(SETTINGS, headers=headers)).json()["orchestrator_rate_limit"] == 25


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "admin", "editor", "viewer", "nonmember"])
async def test_brand_roles_cannot_change_settings(client, test_data, role):
    """owner owns brand, admin is its admin member, nonmember owns other_brand."""
    before = await _limit()
    resp = await client.post(SETTINGS, json={"orchestrator_rate_limit": 999},
                             headers=test_data["get_headers"](role))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Platform admin role required."
    assert await _limit() == before


@pytest.mark.asyncio
async def test_settings_post_requires_login(client):
    assert (await client.post(SETTINGS, json={"orchestrator_rate_limit": 5})).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("role,brand", [("owner", "brand"), ("admin", "brand"), ("nonmember", "other_brand")])
async def test_brand_admins_keep_read_access_with_their_own_metrics(client, db_session, test_data, role, brand):
    other = {"brand": "other_brand", "other_brand": "brand"}[brand]
    for brand_key, count in ((brand, 1), (other, 2)):
        for i in range(count):
            db_session.add(Production(
                production_id=f"prd_{brand_key}_{i}", user_id=test_data["users"]["owner"].id,
                brand_id=test_data[brand_key].id, ai_job_id=None, request_hash="0" * 64, character_id="EE-F-002",
                character_version="1.0", product_type="garment", request={}, runtime_profile={},
                estimated_credits=4))
    await db_session.commit()

    resp = await client.get(SETTINGS, headers=test_data["get_headers"](role))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["orchestrator_rate_limit"], int)
    assert body["metrics"]["productions_total"] == 1  # own brand only (no job row -> failed)


@pytest.mark.asyncio
async def test_settings_response_has_no_campaign_fields(client, db_session):
    body = (await client.get(SETTINGS, headers=await _platform_user(db_session, "admin"))).json()
    assert set(body) == {"orchestrator_rate_limit", "metrics"}
    assert set(body["metrics"]) == PRODUCTION_FIELDS


@pytest.mark.asyncio
async def test_prometheus_no_longer_exposes_campaign_counters(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "campaigns_" not in resp.text


# ========================== Ghost batch /complete and /fail =======

async def _batch(client, test_data, queued) -> str:
    resp = await client.post(GHOST_BATCH, json={"brand_id": test_data["brand"].id, "items": [{"sku": "SKU-1"}]},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 201, resp.text
    queued.assert_not_called()  # no worker task picks ghost batches up
    return resp.json()["job_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["complete", "fail"])
@pytest.mark.parametrize("role", ["owner", "admin", "editor", "viewer", "nonmember"])
async def test_brand_roles_cannot_complete_or_fail_a_batch(client, db_session, test_data, queued, action, role):
    job_id = await _batch(client, test_data, queued)
    before = await _ledger(db_session)
    resp = await client.post(f"{GHOST_BATCH}/{job_id}/{action}", headers=test_data["get_headers"](role))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Platform admin role required."
    assert await _ledger(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["complete", "fail"])
async def test_callbacks_require_login(client, test_data, queued, action):
    job_id = await _batch(client, test_data, queued)
    assert (await client.post(f"{GHOST_BATCH}/{job_id}/{action}")).status_code == 401


@pytest.mark.asyncio
async def test_platform_admin_completes_a_batch(client, db_session, test_data, queued):
    job_id = await _batch(client, test_data, queued)
    brand_id = test_data["brand"].id
    assert (await db_session.execute(select(Brand.credits).where(Brand.id == brand_id))).scalar_one() == 96

    resp = await client.post(f"{GHOST_BATCH}/{job_id}/complete", headers=await _platform_user(db_session, "admin"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"
    txns, brands = await _ledger(db_session)
    assert txns == [(job_id, "reserved", "completed", -4)]
    assert dict(brands)[brand_id] == 96  # charged


@pytest.mark.asyncio
async def test_platform_admin_fails_a_batch_and_refunds_it(client, db_session, test_data, queued):
    job_id = await _batch(client, test_data, queued)
    brand_id = test_data["brand"].id

    resp = await client.post(f"{GHOST_BATCH}/{job_id}/fail", params={"reason": "GPU lost"},
                             headers=await _platform_user(db_session, "owner"))
    assert resp.status_code == 200, resp.text
    txns, brands = await _ledger(db_session)
    assert txns[0] == (job_id, "reserved", "refunded", -4)
    assert dict(brands)[brand_id] == 100  # refunded

    # A second refund of the same batch finds nothing pending.
    again = await client.post(f"{GHOST_BATCH}/{job_id}/fail", headers=await _platform_user(db_session, "admin"))
    assert again.status_code == 404
    assert dict((await _ledger(db_session))[1])[brand_id] == 100


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["complete", "fail"])
async def test_platform_admin_cannot_touch_other_generation_ids(client, db_session, test_data, action):
    """The ledger is shared by generation id; only ghost job ids may be finalized or refunded here."""
    db_session.add(CreditTransaction(brand_id=test_data["brand"].id, user_id=test_data["users"]["owner"].id,
                                     amount=-16, transaction_type="reserved", status="pending",
                                     reference_id="prd_other"))
    await db_session.commit()
    headers = await _platform_user(db_session, "admin")
    before = await _ledger(db_session)
    for job_id in ("prd_other", "no-such-job"):
        resp = await client.post(f"{GHOST_BATCH}/{job_id}/{action}", headers=headers)
        assert (resp.status_code, resp.json()["detail"]) == (404, "Ghost job not found.")
    assert await _ledger(db_session) == before
    assert (await db_session.execute(select(func.count()).select_from(GhostJob))).scalar() == 0
