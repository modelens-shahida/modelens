"""Production metrics on GET /api/v1/admin/settings (app/services/production_metrics.py)."""
import uuid

import pytest

from app.middleware.auth import create_access_token, hash_password
from app.models.db import AIJob, Production, User
from app.services import production_dispatch as dispatch_service
from app.services.production_metrics import production_metrics

from test_production_dispatch import DISPATCH, _body, queue, world  # noqa: F401 (fixtures)

SETTINGS = "/api/v1/admin/settings"
PRODUCTION_FIELDS = ("productions_total", "productions_success", "productions_failed", "productions_retries",
                     "productions_in_progress", "productions_cancelled")
CAMPAIGN_FIELDS = ("campaigns_total", "campaigns_success", "campaigns_failed", "campaigns_retries")


async def _production(db_session, brand_id, user_id, status, with_job=True):
    """A production whose ai_jobs row has ``status`` (or no ai_jobs row)."""
    job = None
    if with_job:
        job = AIJob(user_id=user_id, brand_id=brand_id, status=status, job_type="production", inputs={}, outputs={})
        db_session.add(job)
        await db_session.flush()
    db_session.add(Production(
        production_id=f"prd_{uuid.uuid4().hex}", user_id=user_id, brand_id=brand_id, ai_job_id=job and job.id,
        request_hash="0" * 64, character_id="EE-F-002", character_version="1.0", product_type="garment",
        request={}, runtime_profile={}, estimated_credits=4))
    await db_session.commit()


async def _productions(db_session, brand_id, user_id, statuses):
    for status in statuses:
        await _production(db_session, brand_id, user_id, status, with_job=status is not None)


# One of every status a production's ai_jobs row can have, plus a deleted job.
MIXED = ["completed", "completed", "completed", "failed", "timeout", None, "cancelled",
         "queued", "pending", "processing", "generating"]
MIXED_COUNTS = {"productions_total": 6, "productions_success": 3, "productions_failed": 3, "productions_retries": 0,
                "productions_in_progress": 4, "productions_cancelled": 1}


def _metrics(resp) -> dict:
    assert resp.status_code == 200, resp.text
    return resp.json()["metrics"]


def _productions_only(metrics: dict) -> dict:
    return {k: metrics[k] for k in PRODUCTION_FIELDS}


# ========================== Buckets ===============================

@pytest.mark.asyncio
async def test_no_productions_is_all_zero(db_session):
    assert await production_metrics(db_session) == dict.fromkeys(PRODUCTION_FIELDS, 0)


@pytest.mark.asyncio
async def test_each_status_lands_in_one_bucket(db_session, test_data):
    await _productions(db_session, test_data["brand"].id, test_data["users"]["owner"].id, MIXED)
    metrics = await production_metrics(db_session)
    assert metrics == MIXED_COUNTS
    assert metrics["productions_total"] == metrics["productions_success"] + metrics["productions_failed"]
    assert sum(metrics[k] for k in ("productions_total", "productions_in_progress",
                                    "productions_cancelled")) == len(MIXED)


@pytest.mark.asyncio
async def test_success_rate_ignores_cancelled_and_in_progress(db_session, test_data):
    brand, owner = test_data["brand"].id, test_data["users"]["owner"].id
    await _productions(db_session, brand, owner, ["completed"] * 3 + ["failed"])
    rate = lambda m: m["productions_success"] / m["productions_total"]  # noqa: E731 (what the frontend computes)
    assert rate(await production_metrics(db_session)) == 0.75

    await _productions(db_session, brand, owner, ["cancelled", "queued", "processing"])
    assert rate(await production_metrics(db_session)) == 0.75


@pytest.mark.asyncio
async def test_brand_filter(db_session, test_data):
    brand, other = test_data["brand"].id, test_data["other_brand"].id
    owner, nonmember = test_data["users"]["owner"].id, test_data["users"]["nonmember"].id
    await _productions(db_session, brand, owner, ["completed", "failed"])
    await _productions(db_session, other, nonmember, ["completed", "queued"])

    assert (await production_metrics(db_session, [brand]))["productions_failed"] == 1
    other_metrics = await production_metrics(db_session, [other])
    assert (other_metrics["productions_total"], other_metrics["productions_in_progress"]) == (1, 1)
    assert (await production_metrics(db_session, [brand, other]))["productions_total"] == 3
    assert await production_metrics(db_session, []) == dict.fromkeys(PRODUCTION_FIELDS, 0)


# ========================== Endpoint ==============================

@pytest.mark.asyncio
async def test_settings_return_production_and_campaign_fields(client, db_session, test_data):
    await _productions(db_session, test_data["brand"].id, test_data["users"]["owner"].id, MIXED)
    metrics = _metrics(await client.get(SETTINGS, headers=test_data["get_headers"]("owner")))
    assert _productions_only(metrics) == MIXED_COUNTS
    for field in PRODUCTION_FIELDS + CAMPAIGN_FIELDS:
        assert isinstance(metrics[field], int)


@pytest.mark.asyncio
async def test_platform_admin_sees_every_brand(client, db_session, test_data):
    admin = User(email="platform@modelens.ai", hashed_password=hash_password("pw"), full_name="Platform", role="admin")
    db_session.add(admin)
    await db_session.commit()
    await _productions(db_session, test_data["brand"].id, test_data["users"]["owner"].id, ["completed", "failed"])
    await _productions(db_session, test_data["other_brand"].id, test_data["users"]["nonmember"].id, ["completed"])

    headers = {"Authorization": f"Bearer {create_access_token({'sub': admin.email})}"}
    metrics = _metrics(await client.get(SETTINGS, headers=headers))
    assert (metrics["productions_total"], metrics["productions_success"]) == (3, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [
    ("owner", (2, 1, 1)),      # owns brand
    ("admin", (2, 1, 1)),      # admin member of brand
    ("nonmember", (1, 1, 0)),  # owns other_brand only
])
async def test_brand_admins_see_only_their_brands(client, db_session, test_data, role, expected):
    await _productions(db_session, test_data["brand"].id, test_data["users"]["owner"].id, ["completed", "failed"])
    await _productions(db_session, test_data["other_brand"].id, test_data["users"]["nonmember"].id, ["completed"])
    metrics = _metrics(await client.get(SETTINGS, headers=test_data["get_headers"](role)))
    assert (metrics["productions_total"], metrics["productions_success"], metrics["productions_failed"]) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["editor", "viewer"])
async def test_editors_and_viewers_still_get_403(client, test_data, role):
    resp = await client.get(SETTINGS, headers=test_data["get_headers"](role))
    assert resp.status_code == 403


# ========================== Real productions ======================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_dispatched_productions_move_through_the_buckets(client, db_session, world, queue, monkeypatch):
    from app.services.storage import storage_service
    monkeypatch.setattr(storage_service, "save_file_bytes", lambda name, data, *a: f"/uploads/{name}")
    for _ in range(3):
        assert (await client.post(DISPATCH, json=_body(world, count=1), headers=world["h"]["owner"])).status_code == 202
    settings_of = lambda: client.get(SETTINGS, headers=world["h"]["admin"])  # noqa: E731

    metrics = _metrics(await settings_of())
    assert (metrics["productions_total"], metrics["productions_in_progress"]) == (0, 3)

    async def ok(job, profile):
        return [b"png"]

    async def boom(job, profile):
        raise RuntimeError("provider down")

    await dispatch_service.run_production(db_session, queue[0], generate=ok)
    await dispatch_service.run_production(db_session, queue[1], generate=boom)
    metrics = _productions_only(_metrics(await settings_of()))
    assert metrics == {"productions_total": 2, "productions_success": 1, "productions_failed": 1,
                       "productions_retries": 0, "productions_in_progress": 1, "productions_cancelled": 0}
