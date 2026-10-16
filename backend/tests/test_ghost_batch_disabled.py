"""Ghost batch creation is disabled until a batch worker exists.

POST /api/v1/ghost/batch reserved brand credits and saved a "queued" job that
no worker ever picks up. With GHOST_BATCH_ENABLED off (the default) it answers
503 for every caller before anything is validated, reserved or written.

Unchanged: single ghost jobs (and /ghost-jobs/batch, which queues ordinary
single jobs), estimate/check/rates, batch status, and the platform-admin
/complete and /fail recovery routes. GET /api/v1/ghost/batches/stuck lists the
batches still holding reserved credits, read-only.
"""
from unittest.mock import MagicMock

import celery
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.config import settings
from app.config_production import check_config
from app.middleware.auth import create_access_token, hash_password
from app.models.db import Asset, Brand, CreditTransaction, GhostJob, User

BATCH = "/api/v1/ghost/batch"
STUCK = "/api/v1/ghost/batches/stuck"
DISABLED = "Batch processing is temporarily unavailable. Please submit items as individual ghost jobs."
BRAND_ROLES = ["owner", "admin", "editor", "viewer", "nonmember"]


def _batch_body(brand_id):
    return {"brand_id": brand_id, "items": [{"sku": "SKU-1", "views": [{"view": "FRONT", "resolution": "2K"}]},
                                            {"sku": "SKU-2", "views": [{"view": "BACK", "resolution": "4K"}]}]}


@pytest.fixture
def queued(monkeypatch):
    """Every Celery .delay call."""
    delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr(celery.app.task.Task, "delay", delay)
    return delay


@pytest_asyncio.fixture
async def platform_admin(db_session):
    user = User(email="ghost-platform-admin@modelens.ai", hashed_password=hash_password("pw"),
                full_name="Platform Admin", role="admin")
    db_session.add(user)
    await db_session.commit()
    return {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}


async def _snapshot(db_session):
    """Row counts, balances and every ledger row."""
    jobs = (await db_session.execute(select(func.count()).select_from(GhostJob))).scalar()
    brands = (await db_session.execute(select(Brand.id, Brand.credits).order_by(Brand.id)
                                       .execution_options(populate_existing=True))).all()
    users = (await db_session.execute(select(User.id, User.credits).order_by(User.id)
                                      .execution_options(populate_existing=True))).all()
    ledger = (await db_session.execute(select(CreditTransaction.id, CreditTransaction.status, CreditTransaction.amount)
                                       .order_by(CreditTransaction.id)
                                       .execution_options(populate_existing=True))).all()
    return jobs, brands, users, ledger


async def _brand_credits(db_session, brand_id):
    return (await db_session.execute(select(Brand.credits).where(Brand.id == brand_id)
                                     .execution_options(populate_existing=True))).scalar_one()


@pytest_asyncio.fixture
async def stuck_batch(client, test_data, monkeypatch):
    """A batch created while batches were enabled (as before this change): 4 + 7 = 11 credits reserved."""
    monkeypatch.setattr(settings, "GHOST_BATCH_ENABLED", True)
    resp = await client.post(BATCH, json=_batch_body(test_data["brand"].id), headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 201, resp.text
    monkeypatch.setattr(settings, "GHOST_BATCH_ENABLED", False)
    return resp.json()["job_id"]



async def _garment(db_session, test_data):
    """A garment image asset of the test brand (single ghost jobs need one); its image_key."""
    db_session.add(Asset(brand_id=test_data["brand"].id, filename="garment.png", storage_path="/uploads/g.png",
                         asset_type="image"))
    await db_session.commit()
    return "/uploads/g.png"

# ========================== Disabled ==============================

def test_disabled_by_default():
    from app.config import Settings
    assert Settings.model_fields["GHOST_BATCH_ENABLED"].default is False
    assert settings.GHOST_BATCH_ENABLED is False


@pytest.mark.asyncio
@pytest.mark.parametrize("role", BRAND_ROLES + ["platform_admin"])
@pytest.mark.parametrize("body", ["valid", "invalid", "empty"])
async def test_batch_creation_is_503_for_everyone_and_changes_nothing(
        client, db_session, test_data, queued, platform_admin, role, body):
    headers = platform_admin if role == "platform_admin" else test_data["get_headers"](role)
    json_body = {"valid": _batch_body(test_data["brand"].id), "invalid": {"items": "nope"}, "empty": {}}[body]
    before = await _snapshot(db_session)
    resp = await client.post(BATCH, json=json_body, headers=headers)
    assert resp.status_code == 503, resp.text
    assert resp.json() == {"detail": DISABLED}
    assert await _snapshot(db_session) == before
    queued.assert_not_called()


@pytest.mark.asyncio
async def test_batch_creation_still_requires_login(client, db_session, test_data):
    before = await _snapshot(db_session)
    assert (await client.post(BATCH, json=_batch_body(test_data["brand"].id))).status_code == 401
    assert await _snapshot(db_session) == before


@pytest.mark.asyncio
async def test_documented_as_disabled(client):
    operation = (await client.get("/openapi.json")).json()["paths"][BATCH]["post"]
    assert "503" in operation["responses"]
    assert "disabled" in operation["description"].lower()


# ========================== Still working =========================

@pytest.mark.asyncio
async def test_single_ghost_job_still_reserves_and_queues(client, db_session, test_data, queued):
    user_id = test_data["users"]["editor"].id
    start = (await db_session.execute(select(User.credits).where(User.id == user_id))).scalar_one()
    garment = await _garment(db_session, test_data)
    resp = await client.post("/api/v1/ghost-jobs", json={"brand_id": test_data["brand"].id, "resolution": "4K",
                                                         "image_key": garment},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 201, resp.text
    assert resp.json()["credits_reserved"] == 7
    credits = (await db_session.execute(select(User.credits).where(User.id == user_id)
                                        .execution_options(populate_existing=True))).scalar_one()
    assert credits == start - 7
    queued.assert_called_once_with(resp.json()["job_id"])


@pytest.mark.asyncio
async def test_ghost_jobs_batch_of_single_jobs_still_works(client, db_session, test_data, queued):
    """/ghost-jobs/batch queues ordinary single jobs that the worker processes, so it stays on."""
    from app.models.db import Asset
    db_session.add(Asset(brand_id=test_data["brand"].id, filename="g.png", storage_path="/uploads/g.png",
                         asset_type="image"))
    await db_session.commit()
    jobs = [{"resolution": "1K", "image_key": "/uploads/g.png"}, {"resolution": "2K", "image_key": "/uploads/g.png"}]
    resp = await client.post("/api/v1/ghost-jobs/batch",
                             json={"brand_id": test_data["brand"].id, "jobs": jobs},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 201, resp.text
    assert resp.json()["total_credits_reserved"] == 6
    assert queued.call_count == 2


@pytest.mark.asyncio
async def test_estimate_check_and_rates_still_work(client, db_session, test_data):
    headers = test_data["get_headers"]("editor")
    body = _batch_body(test_data["brand"].id)
    before = await _snapshot(db_session)
    estimate = await client.post(f"{BATCH}/estimate", json={"items": body["items"]}, headers=headers)
    check = await client.post(f"{BATCH}/check", json=body, headers=headers)
    rates = await client.get("/api/v1/ghost/rates", headers=headers)
    assert (estimate.status_code, check.status_code, rates.status_code) == (200, 200, 200)
    assert estimate.json()["total_credits"] == 11
    assert await _snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "admin", "editor", "viewer"])
async def test_existing_batch_status_still_readable(client, test_data, stuck_batch, role):
    resp = await client.get(f"{BATCH}/{stuck_batch}", headers=test_data["get_headers"](role))
    assert resp.status_code == 200
    assert (resp.json()["status"], resp.json()["total_items"]) == ("queued", 2)


@pytest.mark.asyncio
async def test_admin_fail_still_refunds_a_stuck_batch(client, db_session, test_data, stuck_batch, platform_admin):
    brand_id = test_data["brand"].id
    held = await _brand_credits(db_session, brand_id)
    resp = await client.post(f"{BATCH}/{stuck_batch}/fail", params={"reason": "batch worker missing"},
                             headers=platform_admin)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "refunded"
    assert await _brand_credits(db_session, brand_id) == held + 11


@pytest.mark.asyncio
async def test_admin_complete_still_finalizes_a_batch(client, db_session, test_data, stuck_batch, platform_admin):
    brand_id = test_data["brand"].id
    held = await _brand_credits(db_session, brand_id)
    resp = await client.post(f"{BATCH}/{stuck_batch}/complete", headers=platform_admin)
    assert resp.status_code == 200, resp.text
    assert await _brand_credits(db_session, brand_id) == held


# ========================== Stuck batches listing =================

@pytest.mark.asyncio
async def test_stuck_listing_shows_pending_batches_and_changes_nothing(
        client, db_session, test_data, stuck_batch, platform_admin, queued):
    # A single ghost job is not a batch and must not be listed.
    resp = await client.post("/api/v1/ghost-jobs", json={"brand_id": test_data["brand"].id,
                                                         "image_key": await _garment(db_session, test_data)},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 201, resp.text
    before = await _snapshot(db_session)
    resp = await client.get(STUCK, headers=platform_admin)
    assert resp.status_code == 200
    body = resp.json()
    assert (body["total"], body["total_credits_reserved"]) == (1, 11)
    (batch,) = body["batches"]
    assert batch["job_id"] == stuck_batch
    assert (batch["brand_id"], batch["user_id"]) == (test_data["brand"].id, test_data["users"]["editor"].id)
    assert (batch["status"], batch["total_items"], batch["credits_reserved"]) == ("queued", 2, 11)
    assert batch["refund_url"] == f"{BATCH}/{stuck_batch}/fail"
    assert await _snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["fail", "complete"])
async def test_resolved_batches_leave_the_stuck_listing(client, stuck_batch, platform_admin, action):
    assert (await client.post(f"{BATCH}/{stuck_batch}/{action}", headers=platform_admin)).status_code == 200
    assert (await client.get(STUCK, headers=platform_admin)).json() == {
        "batches": [], "total": 0, "total_credits_reserved": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize("role", BRAND_ROLES)
async def test_stuck_listing_is_platform_admin_only(client, test_data, stuck_batch, role):
    resp = await client.get(STUCK, headers=test_data["get_headers"](role))
    assert resp.status_code == 403
    assert stuck_batch not in resp.text


@pytest.mark.asyncio
async def test_stuck_listing_requires_login(client):
    assert (await client.get(STUCK)).status_code == 401


# ========================== Flag on ===============================

@pytest.mark.asyncio
async def test_enabling_the_flag_restores_batch_creation(client, db_session, test_data, queued, monkeypatch):
    monkeypatch.setattr(settings, "GHOST_BATCH_ENABLED", True)
    brand_id = test_data["brand"].id
    start = await _brand_credits(db_session, brand_id)
    resp = await client.post(BATCH, json=_batch_body(brand_id), headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 201, resp.text
    assert (resp.json()["status"], resp.json()["total_credits_reserved"]) == ("queued", 11)
    assert await _brand_credits(db_session, brand_id) == start - 11
    queued.assert_not_called()  # still no worker for batches


def test_enabled_flag_is_a_startup_warning_not_fatal(monkeypatch):
    monkeypatch.setattr(settings, "GHOST_BATCH_ENABLED", True)
    issues = [i for i in check_config() if i.name == "GHOST_BATCH_ENABLED"]
    assert len(issues) == 1 and issues[0].fatal is False
    monkeypatch.setattr(settings, "GHOST_BATCH_ENABLED", False)
    assert not [i for i in check_config() if i.name == "GHOST_BATCH_ENABLED"]
