"""Rosanne Studio is disabled in production.

Rosanne: POST /api/v1/rosanne/generate reserved brand credits and then marked
the job completed from a mock ComfyUI run, charging for images that were never
made. In production with ROSANNE_JOBS_ENABLED off it answers 503 for every
caller before anything is reserved, written or dispatched; the dispatcher never
marks a mock completed in production and fails + refunds the job once instead.
Outside production nothing changes.

Everything is mocked: no network.
"""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.config_production import check_config
from app.models.db import Brand, CatalogJob, CreditTransaction
from app.routers.rosanne_pipeline import _dispatch_rosanne_workflow
from app.services.rosanne_availability import ROSANNE_DISABLED, ROSANNE_GENERATION_FAILED

pytestmark = pytest.mark.integration  # runs the Rosanne dispatcher

MESSAGE = "Rosanne Studio is undergoing scheduled pipeline upgrades. Please check back shortly."
ROSANNE_URL = "/api/v1/rosanne/generate"
ROSANNE_BODY = {"product_id": "GAR-TEST-001", "character_id": "EE-F-002", "quality_mode": "quality",
                "num_images": 1}


@pytest.fixture(autouse=True)
def outside_production(monkeypatch):
    """Tests opt into production with the ``production`` fixture."""
    monkeypatch.setattr(settings, "APP_ENV", "development")


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")


@pytest.fixture
def dispatcher():
    with patch("app.routers.rosanne_pipeline._dispatch_rosanne_workflow", new_callable=AsyncMock) as dispatch:
        yield dispatch


async def _brand_credits(db_session, brand_id):
    return (await db_session.execute(select(Brand.credits).where(Brand.id == brand_id)
                                     .execution_options(populate_existing=True))).scalar_one()


async def _count(db_session, model):
    return (await db_session.execute(select(func.count(model.id)))).scalar()


async def _job(db_session, job_id):
    return (await db_session.execute(select(CatalogJob).where(CatalogJob.job_id == job_id)
                                     .execution_options(populate_existing=True))).scalar_one()


async def _refunds(db_session):
    return (await db_session.execute(select(CreditTransaction).where(
        CreditTransaction.transaction_type == "refund").execution_options(populate_existing=True))).scalars().all()


def _headers(test_data, platform_admin_headers, role):
    return platform_admin_headers if role == "platform_admin" else test_data["get_headers"](role)


# ========================== Rosanne: routes =====================================

@pytest.mark.parametrize("role", ["owner", "admin", "editor", "viewer", "nonmember", "platform_admin"])
@pytest.mark.asyncio
async def test_rosanne_generate_in_production_is_503_before_anything(
        client, db_session, test_data, platform_admin_headers, production, dispatcher, role):
    brands = {b: await _brand_credits(db_session, b) for b in (await db_session.execute(select(Brand.id))).scalars()}
    before = (await _count(db_session, CatalogJob), await _count(db_session, CreditTransaction))

    res = await client.post(ROSANNE_URL, json=ROSANNE_BODY, headers=_headers(test_data, platform_admin_headers, role))

    assert (res.status_code, res.json()) == (503, {"detail": MESSAGE})
    dispatcher.assert_not_called()
    assert (await _count(db_session, CatalogJob), await _count(db_session, CreditTransaction)) == before
    assert {b: await _brand_credits(db_session, b) for b in brands} == brands


@pytest.mark.parametrize("app_env", ["", "staging-eu"])
@pytest.mark.asyncio
async def test_rosanne_is_disabled_when_app_env_is_missing_or_unknown(client, test_data, monkeypatch, app_env):
    monkeypatch.setattr(settings, "APP_ENV", app_env)
    monkeypatch.setattr(settings, "TESTING", False)
    res = await client.post(ROSANNE_URL, json=ROSANNE_BODY, headers=test_data["get_headers"]("owner"))
    assert (res.status_code, res.json()) == (503, {"detail": MESSAGE})


@pytest.mark.asyncio
async def test_unauthenticated_rosanne_generate_is_still_401(client, production):
    assert (await client.post(ROSANNE_URL, json=ROSANNE_BODY)).status_code == 401


@pytest.mark.parametrize("app_env,flag", [("development", False), ("production", True)])
@pytest.mark.asyncio
async def test_rosanne_generate_works_outside_production_or_when_enabled(
        client, db_session, test_data, dispatcher, monkeypatch, app_env, flag):
    monkeypatch.setattr(settings, "APP_ENV", app_env)
    monkeypatch.setattr(settings, "ROSANNE_JOBS_ENABLED", flag)
    brand = await db_session.get(Brand, test_data["brand"].id)
    brand.credits = 100
    await db_session.commit()
    res = await client.post(ROSANNE_URL, json=ROSANNE_BODY, headers=test_data["get_headers"]("owner"))
    assert res.status_code == 201, res.text
    dispatcher.assert_called_once()


@pytest.mark.asyncio
async def test_rosanne_read_routes_keep_working_in_production(client, test_data, production):
    owner = test_data["get_headers"]("owner")
    for method, url, kwargs in [
        ("get", "/api/v1/rosanne/config", {}),
        ("get", "/api/v1/rosanne/pose-presets", {}),
        ("post", "/api/v1/rosanne/estimate", {"json": ROSANNE_BODY}),
        ("post", "/api/v1/rosanne/check", {"json": ROSANNE_BODY}),
        ("get", "/api/v1/rosanne/jobs/unknown-job", {}),
    ]:
        res = await getattr(client, method)(url, headers=owner, **kwargs)
        assert res.status_code != 503, url


# ========================== Rosanne: dispatcher =================================

async def _reserved_rosanne_job(client, db_session, test_data, dispatcher):
    """A Rosanne job created (and its credits reserved) before the gate, not yet dispatched."""
    brand = await db_session.get(Brand, test_data["brand"].id)
    brand.credits = 100
    await db_session.commit()
    res = await client.post(ROSANNE_URL, json=ROSANNE_BODY, headers=test_data["get_headers"]("owner"))
    assert res.status_code == 201, res.text
    _, kwargs = dispatcher.call_args
    return kwargs, res.json()["credits_reserved"]


@pytest.mark.parametrize("flag,message", [(False, ROSANNE_DISABLED), (True, ROSANNE_GENERATION_FAILED)])
@pytest.mark.asyncio
async def test_queued_rosanne_job_in_production_fails_and_refunds_once_never_completes(
        client, db_session, test_data, dispatcher, monkeypatch, flag, message):
    kwargs, reserved = await _reserved_rosanne_job(client, db_session, test_data, dispatcher)
    brand_id = kwargs["brand_id"]
    after_reserve = await _brand_credits(db_session, brand_id)
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "ROSANNE_JOBS_ENABLED", flag)

    for _ in range(3):  # dispatched, then run again: one refund
        db_session.expunge_all()
        await _dispatch_rosanne_workflow(**kwargs)

    job = await _job(db_session, kwargs["job_id"])
    assert (job.status, job.error_message, job.completed_skus or 0) == ("failed", message, 0)
    assert await _brand_credits(db_session, brand_id) == after_reserve + reserved
    refunds = await _refunds(db_session)
    assert [r.refund_key for r in refunds] == [f"generation:{kwargs['job_id']}"]
    reservation = (await db_session.execute(select(CreditTransaction).where(
        CreditTransaction.reference_id == kwargs["job_id"], CreditTransaction.transaction_type == "reserved",
    ).execution_options(populate_existing=True))).scalar_one()
    assert reservation.status == "refunded"


@pytest.mark.asyncio
async def test_outside_production_the_mock_rosanne_completion_is_unchanged(client, db_session, test_data, dispatcher):
    kwargs, _ = await _reserved_rosanne_job(client, db_session, test_data, dispatcher)
    db_session.expunge_all()
    await _dispatch_rosanne_workflow(**kwargs)
    assert (await _job(db_session, kwargs["job_id"])).status == "completed"
    assert await _refunds(db_session) == []


def test_rosanne_message_is_exact():
    assert ROSANNE_DISABLED == MESSAGE


def test_rosanne_jobs_are_off_by_default():
    from app.config import Settings
    assert Settings.model_fields["ROSANNE_JOBS_ENABLED"].default is False


def test_startup_warns_but_does_not_fail_when_rosanne_is_enabled_in_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert not [i for i in check_config() if i.name == "ROSANNE_JOBS_ENABLED"]
    monkeypatch.setattr(settings, "ROSANNE_JOBS_ENABLED", True)
    [issue] = [i for i in check_config() if i.name == "ROSANNE_JOBS_ENABLED"]
    assert issue.fatal is False
