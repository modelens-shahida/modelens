"""Catalog Studio is disabled in production until its try-on pipeline is rebuilt.

The Catalog worker never reached FASHN (Settings declares no FASHN_API_KEY), so
every job saved a mock output as a success and was charged for it. Now:

* in production with CATALOG_JOBS_ENABLED off, every Catalog create/retry route
  answers 503 for every caller before anything is reserved, written, uploaded
  or queued; reads, exports and cancel keep working;
* a Catalog job or item the worker picks up meanwhile is failed and refunded
  once, without calling FASHN or saving an output;
* in production the worker never saves a mock output, flag on or off;
* outside production nothing changes.

Everything is mocked: no network, fake keys only.
"""
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image
from sqlalchemy import func, select

import app.models.db as models
from app.config import settings
from app.config_production import check_config
from app.models.db import Asset, CatalogJob, CatalogJobItem, CreditTransaction, User
from app.services.catalog_availability import CATALOG_DISABLED, CATALOG_GENERATION_FAILED
from app.services.storage import storage_service
from app.worker import (
    _process_catalog_item_retry_async, _process_catalog_job_async, _process_single_catalog_item_async,
)

pytestmark = pytest.mark.integration  # runs worker task bodies

MESSAGE = "Catalog Studio is undergoing scheduled try-on pipeline upgrades. Please check back shortly."
MINE = "/uploads/brand/catalog-product.png"
URL = "/api/v1/catalog-jobs"
FASHN_OUTPUT = "https://cdn.fashn.ai/out/1.png"


def _png():
    out = io.BytesIO()
    Image.new("RGB", (16, 12), (120, 40, 200)).save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "CATALOG_JOBS_ENABLED", True)


@pytest.fixture
def dispatch():
    with patch("app.routers.catalog_jobs.process_catalog_job") as job_task, \
            patch("app.routers.catalog_jobs.process_catalog_item") as item_task, \
            patch.object(storage_service, "save_file_bytes", return_value=MINE) as save:
        yield job_task, item_task, save


class _SettingsWithFashnKey:
    """The real settings plus a FASHN key (Settings declares none, see app.config.catalog_fashn_key)."""
    FASHN_API_KEY = "fashn-test-key"

    def __getattr__(self, name):
        return getattr(settings, name)


def _fake_fashn(response=None, error=None):
    client = MagicMock()
    if error is not None:
        client.post = AsyncMock(side_effect=error)
    else:
        reply = MagicMock()
        reply.json.return_value = response
        client.post = AsyncMock(return_value=reply)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.fixture
def fashn():
    """No FASHN key (as in Railway) and a fake HTTP client that records any request; none is sent."""
    client = _fake_fashn({"id": "fashn-run-1", "output": [FASHN_OUTPUT]})
    with patch("httpx.AsyncClient", return_value=client):
        yield client.post


@pytest.fixture
def fashn_key(monkeypatch):
    monkeypatch.setattr("app.config.settings", _SettingsWithFashnKey())


async def _user_credits(db_session, user_id):
    return (await db_session.execute(select(User.credits).where(User.id == user_id)
                                     .execution_options(populate_existing=True))).scalar_one()


async def _reload(db_session, model, row_id):
    return (await db_session.execute(select(model).where(model.id == row_id)
                                     .execution_options(populate_existing=True))).scalar_one()


async def _refunds(db_session):
    return (await db_session.execute(select(CreditTransaction).where(
        CreditTransaction.transaction_type == "refund", CreditTransaction.reference_type == "catalog_job",
    ).execution_options(populate_existing=True))).scalars().all()


async def _outputs(db_session):
    return (await db_session.execute(select(Asset).where(Asset.asset_type == "generated")
                                     .execution_options(populate_existing=True))).scalars().all()


async def _counts(db_session):
    count = lambda model: select(func.count(model.id))  # noqa: E731
    return tuple([(await db_session.execute(count(m))).scalar() for m in (CatalogJob, CatalogJobItem,
                                                                           CreditTransaction, Asset)])


async def _catalog_job(db_session, test_data, items=2, job_status="queued", item_status="queued", reserved=10):
    """A charged studio-quality catalog job (5 credits per item) whose items use a brand asset."""
    editor = test_data["users"]["editor"]
    user = await db_session.get(User, editor.id)
    user.credits = (user.credits or 0) - reserved
    db_session.add(Asset(brand_id=test_data["brand"].id, filename="p.png", storage_path=MINE, asset_type="image"))
    job = CatalogJob(user_id=editor.id, brand_id=test_data["brand"].id, status=job_status, total_items=items,
                     failed_items=items if item_status == "failed" else 0,
                     generation_mode="studio_quality", credits_reserved=reserved)
    db_session.add(job)
    await db_session.commit()
    rows = [CatalogJobItem(job_id=job.id, sku_tag=f"SKU-{i}", status=item_status, product_image_path=MINE)
            for i in range(items)]
    db_session.add_all(rows)
    await db_session.commit()
    return job.id, [r.id for r in rows], editor.id


async def _work(db_session, worker, *args):
    db_session.expunge_all()
    with patch("app.worker.async_session_maker", models.async_session_maker):
        await worker(*args)


# ========================== Routes ===============================================

def _requests(brand_id, job_id, item_id):
    return [
        (URL, {"json": {"brand_id": brand_id, "products": [{"sku_tag": "A", "image_path": MINE}]}}),
        (URL, {"data": {"brand_id": str(brand_id), "sku_0": "A"},
               "files": {"products": ("p.png", _png(), "image/png")}}),
        (f"{URL}/{job_id}/retry", {}),
        (f"{URL}/{job_id}/items/{item_id}/retry", {}),
    ]


@pytest.mark.parametrize("role", ["owner", "admin", "editor", "viewer", "nonmember", "platform_admin"])
@pytest.mark.asyncio
async def test_catalog_create_and_retry_in_production_are_503_before_anything(
        client, db_session, test_data, platform_admin_headers, production, dispatch, role):
    job_id, [item_id, _], _ = await _catalog_job(db_session, test_data, job_status="failed", item_status="failed")
    headers = platform_admin_headers if role == "platform_admin" else test_data["get_headers"](role)
    credits = {u: await _user_credits(db_session, u) for u in (await db_session.execute(select(User.id))).scalars()}
    before = await _counts(db_session)

    for url, kwargs in _requests(test_data["brand"].id, job_id, item_id):
        res = await client.post(url, headers=headers, **kwargs)
        assert (res.status_code, res.json()) == (503, {"detail": MESSAGE}), url

    job_task, item_task, save = dispatch
    job_task.delay.assert_not_called()
    item_task.delay.assert_not_called()
    save.assert_not_called()
    assert await _counts(db_session) == before
    assert {u: await _user_credits(db_session, u) for u in credits} == credits
    assert (await _reload(db_session, CatalogJob, job_id)).status == "failed"
    assert (await _reload(db_session, CatalogJobItem, item_id)).status == "failed"


@pytest.mark.parametrize("app_env", ["", "staging-eu"])
@pytest.mark.asyncio
async def test_catalog_is_disabled_when_app_env_is_missing_or_unknown(client, test_data, monkeypatch, app_env):
    monkeypatch.setattr(settings, "APP_ENV", app_env)
    monkeypatch.setattr(settings, "TESTING", False)
    res = await client.post(URL, json={"brand_id": test_data["brand"].id}, headers=test_data["get_headers"]("owner"))
    assert (res.status_code, res.json()) == (503, {"detail": MESSAGE})


@pytest.mark.asyncio
async def test_unauthenticated_catalog_creation_is_still_401(client, production):
    assert (await client.post(URL, json={})).status_code == 401


@pytest.mark.parametrize("app_env,flag", [("development", False), ("production", True)])
@pytest.mark.asyncio
async def test_catalog_routes_work_outside_production_or_when_enabled(
        client, db_session, test_data, dispatch, monkeypatch, app_env, flag):
    monkeypatch.setattr(settings, "APP_ENV", app_env)
    monkeypatch.setattr(settings, "CATALOG_JOBS_ENABLED", flag)
    job_id, [item_id, _], _ = await _catalog_job(db_session, test_data, job_status="failed", item_status="failed")
    owner = test_data["get_headers"]("owner")
    owner_user = await db_session.get(User, test_data["users"]["owner"].id)
    owner_user.credits = 100
    await db_session.commit()

    res = await client.post(URL, headers=owner, json={
        "brand_id": test_data["brand"].id, "products": [{"sku_tag": "A", "image_path": MINE}]})
    assert res.status_code == 201, res.text
    res = await client.post(f"{URL}/{job_id}/items/{item_id}/retry", headers=test_data["get_headers"]("editor"))
    assert res.status_code == 200, res.text
    res = await client.post(f"{URL}/{job_id}/retry", headers=test_data["get_headers"]("editor"))
    assert res.status_code == 200, res.text
    job_task, item_task, _ = dispatch
    assert job_task.delay.call_count == 2 and item_task.delay.call_count == 1


@pytest.mark.asyncio
async def test_catalog_reads_exports_and_cancel_keep_working_in_production(client, db_session, test_data, production):
    job_id, _, user_id = await _catalog_job(db_session, test_data)
    start = await _user_credits(db_session, user_id)
    editor = test_data["get_headers"]("editor")
    res = await client.get(f"{URL}/{job_id}", headers=editor)
    assert (res.status_code, res.json()["status"]) == (200, "queued")
    assert (await client.get(f"{URL}/marketplaces", headers=editor)).status_code == 200
    assert (await client.get(f"{URL}/{job_id}/export-zip", headers=editor)).status_code != 503
    res = await client.post(f"{URL}/{job_id}/cancel", headers=editor)
    assert (res.status_code, res.json()["credits_refunded"]) == (200, 10)
    assert await _user_credits(db_session, user_id) == start + 10


# ========================== Worker in production ================================

@pytest.mark.asyncio
async def test_queued_catalog_job_in_production_fails_and_refunds_once_without_fashn(
        db_session, test_data, production, fashn, fashn_key):
    job_id, item_ids, user_id = await _catalog_job(db_session, test_data)
    start = await _user_credits(db_session, user_id)

    for _ in range(3):  # picked up, then redelivered twice
        await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)

    fashn.assert_not_called()
    job = await _reload(db_session, CatalogJob, job_id)
    assert (job.status, job.error_message, job.completed_items, job.failed_items) == ("failed", MESSAGE, 0, 2)
    for item_id in item_ids:
        item = await _reload(db_session, CatalogJobItem, item_id)
        assert (item.status, item.error_message, item.output_url) == ("failed", MESSAGE, None)
    assert await _user_credits(db_session, user_id) == start + 10
    assert len(await _refunds(db_session)) == 1
    assert await _outputs(db_session) == []


@pytest.mark.parametrize("worker", ["item_retry", "single_item"])
@pytest.mark.asyncio
async def test_queued_catalog_item_in_production_fails_and_refunds_once(
        db_session, test_data, production, fashn, worker):
    job_id, [item_id], user_id = await _catalog_job(db_session, test_data, items=1, reserved=5)
    start = await _user_credits(db_session, user_id)
    task = MagicMock()
    for _ in range(2):
        if worker == "item_retry":
            await _work(db_session, _process_catalog_item_retry_async, item_id)
        else:
            await _work(db_session, _process_single_catalog_item_async, task, item_id, job_id)

    task.retry.assert_not_called()
    fashn.assert_not_called()
    item = await _reload(db_session, CatalogJobItem, item_id)
    assert (item.status, item.error_message, item.output_url) == ("failed", MESSAGE, None)
    assert await _user_credits(db_session, user_id) == start + 5
    assert len(await _refunds(db_session)) == 1
    assert await _outputs(db_session) == []


@pytest.mark.parametrize("case", ["no key", "fashn error", "no output"])
@pytest.mark.asyncio
async def test_production_never_saves_a_mock_output_even_when_enabled(
        db_session, test_data, production, enabled, monkeypatch, capsys, case):
    if case != "no key":
        monkeypatch.setattr("app.config.settings", _SettingsWithFashnKey())
    client = _fake_fashn(error=RuntimeError("boom")) if case == "fashn error" else _fake_fashn({"id": "x", "output": []})
    job_id, item_ids, user_id = await _catalog_job(db_session, test_data)
    start = await _user_credits(db_session, user_id)

    with patch("httpx.AsyncClient", return_value=client):
        for _ in range(2):
            await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)

    assert client.post.called == (case != "no key")
    for item_id in item_ids:
        item = await _reload(db_session, CatalogJobItem, item_id)
        assert (item.status, item.error_message, item.output_url) == ("failed", CATALOG_GENERATION_FAILED, None)
    job = await _reload(db_session, CatalogJob, job_id)
    assert (job.status, job.completed_items, job.failed_items, job.credits_consumed) == ("failed", 0, 2, 0)
    assert await _user_credits(db_session, user_id) == start + 10
    assert len(await _refunds(db_session)) == 2  # one per item, each once
    assert await _outputs(db_session) == []
    assert "cdn.example.com" not in capsys.readouterr().out


@pytest.mark.parametrize("worker", ["item_retry", "single_item"])
@pytest.mark.asyncio
async def test_production_item_tasks_never_save_their_mock_even_when_enabled(
        db_session, test_data, production, enabled, fashn, worker):
    job_id, [item_id], user_id = await _catalog_job(db_session, test_data, items=1, reserved=5)
    start = await _user_credits(db_session, user_id)
    if worker == "item_retry":
        await _work(db_session, _process_catalog_item_retry_async, item_id)
    else:
        await _work(db_session, _process_single_catalog_item_async, MagicMock(), item_id, job_id)
    item = await _reload(db_session, CatalogJobItem, item_id)
    assert (item.status, item.error_message, item.output_url) == ("failed", CATALOG_GENERATION_FAILED, None)
    assert await _user_credits(db_session, user_id) == start + 5
    assert await _outputs(db_session) == []


@pytest.mark.asyncio
async def test_production_with_the_flag_and_a_working_fashn_still_generates(
        db_session, test_data, production, enabled, fashn, fashn_key):
    job_id, item_ids, user_id = await _catalog_job(db_session, test_data)
    start = await _user_credits(db_session, user_id)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    assert fashn.call_count == 2
    assert fashn.call_args.kwargs["json"]["inputs"]["product_image"] == MINE
    assert (await _reload(db_session, CatalogJob, job_id)).status == "completed"
    assert {a.storage_path for a in await _outputs(db_session)} == {FASHN_OUTPUT}
    assert await _user_credits(db_session, user_id) == start


@pytest.mark.asyncio
async def test_outside_production_the_mock_output_is_unchanged(db_session, test_data, monkeypatch, fashn):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    job_id, item_ids, _ = await _catalog_job(db_session, test_data)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    fashn.assert_not_called()
    assert (await _reload(db_session, CatalogJob, job_id)).status == "completed"
    item = await _reload(db_session, CatalogJobItem, item_ids[0])
    assert item.output_url == f"https://cdn.example.com/catalog/mock_{item.id}.png"


# ========================== Settings ============================================

def test_catalog_message_is_exact():
    assert CATALOG_DISABLED == MESSAGE


def test_catalog_jobs_are_off_by_default():
    from app.config import Settings
    assert Settings.model_fields["CATALOG_JOBS_ENABLED"].default is False


def test_startup_warns_but_does_not_fail_when_catalog_is_enabled_without_fashn(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert not [i for i in check_config() if i.name == "CATALOG_JOBS_ENABLED"]
    monkeypatch.setattr(settings, "CATALOG_JOBS_ENABLED", True)
    [issue] = [i for i in check_config() if i.name == "CATALOG_JOBS_ENABLED"]
    assert issue.fatal is False
    monkeypatch.setattr("app.config.settings", _SettingsWithFashnKey())
    assert not [i for i in check_config() if i.name == "CATALOG_JOBS_ENABLED"]
