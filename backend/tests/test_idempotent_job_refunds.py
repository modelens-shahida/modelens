"""A job's credits are refunded at most once (app/services/job_refunds.py).

Worker attempts and Celery retries, cancels, admin /fail, internal
callbacks and concurrent attempts all refund a job once, by what it was
charged; a retry that succeeds is not refunded. The credit_transactions
refund_key unique index (migration job_refund_key_001) backs this up in the
database.

Everything is mocked: no network, fake keys only.
"""
import asyncio
import importlib.util
import os
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

import app.models.db as models
from app.config import settings
from app.models.db import (
    AIJob, Brand, CatalogJob, CatalogJobItem, CreditTransaction, GhostJob, GhostJobAsset, SketchJob, User,
)
from app.services import job_refunds
from app.services.credits_sync_service import credits_sync_service
from app.services.job_refunds import refund_job
from app.services.storage import storage_service
from app.worker import (
    _fail_or_requeue, _process_catalog_job_async, _process_generation_job_async, _process_ghost_job_async,
    _process_sketch_job_async,
)
from tests import gemini_fakes

pytestmark = pytest.mark.integration  # runs worker task bodies and a migration

INTERNAL = {"x-internal-secret": "modelens-internal-secret"}


@pytest.fixture(autouse=True)
def mock_image_outside_production(monkeypatch):
    """Non-production, no Gemini key: the ghost/sketch workers use their mock image."""
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)


@pytest.fixture
def garment_store():
    with patch.object(storage_service, "read_file_bytes", return_value=gemini_fakes.OUTPUT_PNG):
        yield


async def _user_credits(db_session, user_id):
    return (await db_session.execute(select(User.credits).where(User.id == user_id)
                                     .execution_options(populate_existing=True))).scalar_one()


async def _brand_credits(db_session, brand_id):
    return (await db_session.execute(select(Brand.credits).where(Brand.id == brand_id)
                                     .execution_options(populate_existing=True))).scalar_one()


async def _refunds(db_session, **where):
    stmt = select(CreditTransaction).where(CreditTransaction.transaction_type == "refund")
    for name, value in where.items():
        stmt = stmt.where(getattr(CreditTransaction, name) == value)
    return (await db_session.execute(stmt.execution_options(populate_existing=True))).scalars().all()


async def _reload(db_session, model, row_id):
    return (await db_session.execute(select(model).where(model.id == row_id)
                                     .execution_options(populate_existing=True))).scalar_one()


async def _charged_job(db_session, test_data, model, reserved=7, **fields):
    """A queued job whose credits were taken from the editor, as the creation routes do."""
    editor = test_data["users"]["editor"]
    user = await db_session.get(User, editor.id)
    user.credits = (user.credits or 0) - reserved
    job = model(user_id=editor.id, brand_id=test_data["brand"].id, status="queued", credits_reserved=reserved,
                **fields)
    db_session.add(job)
    await db_session.commit()
    if model is GhostJob:
        db_session.add(GhostJobAsset(job_id=job.id, image_path="/uploads/garment.png"))
        await db_session.commit()
    return job.id, editor.id


async def _attempt(db_session, worker, job_id, retries, max_retries=3):
    """One Celery attempt of a ghost/sketch task in its own session, as in production."""
    task = MagicMock()
    task.request.retries = retries
    task.max_retries = max_retries
    task.retry.side_effect = RuntimeError("retry scheduled")
    db_session.expunge_all()
    with patch("app.worker.async_session_maker", models.async_session_maker):
        try:
            await worker(task, job_id)
        except RuntimeError as e:
            assert str(e) == "retry scheduled"
    return task


# ========================== Worker attempts and retries =========================

@pytest.mark.parametrize("worker,model,kind", [
    (_process_ghost_job_async, GhostJob, "ghost_job"),
    (_process_sketch_job_async, SketchJob, "sketch_job"),
])
@pytest.mark.asyncio
async def test_job_failing_on_every_retry_is_refunded_exactly_once(
        db_session, test_data, garment_store, worker, model, kind):
    job_id, user_id = await _charged_job(db_session, test_data, model, reserved=7)
    start = await _user_credits(db_session, user_id)
    with patch.object(storage_service, "save_file_bytes", side_effect=OSError("disk full")):
        for retries in range(3):  # attempts with a Celery retry left: re-queued, nothing refunded
            task = await _attempt(db_session, worker, job_id, retries)
            task.retry.assert_called_once()
            job = await _reload(db_session, model, job_id)
            assert (job.status, job.error_message) == ("queued", "disk full")
            assert await _user_credits(db_session, user_id) == start
        task = await _attempt(db_session, worker, job_id, retries=3)  # the last attempt
        task.retry.assert_not_called()
        assert (await _reload(db_session, model, job_id)).status == "failed"
        assert await _user_credits(db_session, user_id) == start + 7
        await _attempt(db_session, worker, job_id, retries=3)  # a redelivered message: no second refund
    assert await _user_credits(db_session, user_id) == start + 7
    [row] = await _refunds(db_session, reference_type=kind)
    assert (row.amount, row.refund_key, row.reference_id) == (7, f"{kind}:{job_id}", str(job_id))


@pytest.mark.parametrize("worker,model", [(_process_ghost_job_async, GhostJob), (_process_sketch_job_async, SketchJob)])
@pytest.mark.asyncio
async def test_fail_then_succeed_is_not_refunded(db_session, test_data, garment_store, worker, model):
    job_id, user_id = await _charged_job(db_session, test_data, model, reserved=5)
    start = await _user_credits(db_session, user_id)
    with patch.object(storage_service, "save_file_bytes", side_effect=OSError("blip")):
        await _attempt(db_session, worker, job_id, retries=0)
    with patch.object(storage_service, "save_file_bytes", return_value="/uploads/out.png"):
        task = await _attempt(db_session, worker, job_id, retries=1)
    task.retry.assert_not_called()
    job = await _reload(db_session, model, job_id)
    assert (job.status, job.credits_consumed) == ("completed", 5)
    assert await _user_credits(db_session, user_id) == start
    assert await _refunds(db_session) == []


@pytest.mark.asyncio
async def test_ghost_gemini_failure_on_a_retry_refunds_once(db_session, test_data, garment_store, monkeypatch):
    """The PR #44 Gemini-only guard is gone: the shared helper covers it."""
    monkeypatch.setattr(settings, "APP_ENV", "production")
    gemini = gemini_fakes.install(monkeypatch)
    job_id, user_id = await _charged_job(db_session, test_data, GhostJob, reserved=4)
    start = await _user_credits(db_session, user_id)
    with patch.object(storage_service, "save_file_bytes", side_effect=OSError("blip")):
        await _attempt(db_session, _process_ghost_job_async, job_id, retries=0)  # retryable: no refund
    assert await _user_credits(db_session, user_id) == start
    gemini.generate_content.return_value = gemini_fakes.image_response(data=None, text="no image")
    for retries in (1, 2):  # Gemini failure: final; a redelivery of it does not refund again
        task = await _attempt(db_session, _process_ghost_job_async, job_id, retries=retries)
        task.retry.assert_not_called()
    assert (await _reload(db_session, GhostJob, job_id)).status == "failed"
    assert await _user_credits(db_session, user_id) == start + 4
    assert len(await _refunds(db_session, reference_type="ghost_job")) == 1


class _Session:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        pass


async def _run_ai_job(db_session, job_id, error, retries):
    with patch("app.worker.async_session_maker", return_value=_Session(db_session)), \
            patch("app.worker._generate_image", side_effect=error), \
            patch("app.worker.redis_client"), patch("app.worker._publish_brand_event"), \
            patch("app.worker.dispatch_webhook"), patch("app.worker._dispatch_brand_webhooks"):
        try:
            await _process_generation_job_async(job_id, retries=retries, max_retries=3)
        except RuntimeError:
            pass  # re-raised for Celery's autoretry


async def _ai_job(db_session, test_data):
    editor = test_data["users"]["editor"]
    job = AIJob(user_id=editor.id, brand_id=test_data["brand"].id, status="pending", job_type="generation",
                inputs={}, outputs={})
    db_session.add(job)
    await db_session.commit()
    return job.id, editor.id


@pytest.mark.asyncio
async def test_ai_job_retryable_failures_refund_once_on_the_last_attempt(db_session, test_data, monkeypatch):
    monkeypatch.setattr(settings, "COMFYUI_MOCK_MODE", False)
    job_id, user_id = await _ai_job(db_session, test_data)
    start = await _user_credits(db_session, user_id)
    for retries in range(3):
        await _run_ai_job(db_session, job_id, RuntimeError("GPU busy"), retries)
        assert (await _reload(db_session, AIJob, job_id)).status != "failed"
        assert await _user_credits(db_session, user_id) == start
    for _ in range(2):  # the last attempt, then a redelivery
        await _run_ai_job(db_session, job_id, RuntimeError("GPU busy"), 3)
    assert (await _reload(db_session, AIJob, job_id)).status == "failed"
    assert await _user_credits(db_session, user_id) == start + 1
    [row] = await _refunds(db_session, reference_type="job")
    assert row.refund_key == f"job:{job_id}"


@pytest.mark.asyncio
async def test_ai_job_error_celery_never_retries_is_final_at_once(db_session, test_data, monkeypatch):
    """Before: a ValueError on attempt 1 was re-raised, Celery did not retry it (not in autoretry_for),
    and the job stayed 'processing' with its credit kept. Now it fails and is refunded once."""
    monkeypatch.setattr(settings, "COMFYUI_MOCK_MODE", False)
    job_id, user_id = await _ai_job(db_session, test_data)
    start = await _user_credits(db_session, user_id)
    await _run_ai_job(db_session, job_id, ValueError("bad input"), retries=0)
    assert (await _reload(db_session, AIJob, job_id)).status == "failed"
    assert await _user_credits(db_session, user_id) == start + 1


# ========================== Cancels and the worker =============================

@pytest.mark.parametrize("url,model,kind", [
    ("/api/v1/ghost-jobs", GhostJob, "ghost_job"),
    ("/api/v1/sketch-jobs", SketchJob, "sketch_job"),
])
@pytest.mark.asyncio
async def test_double_cancel_refunds_once(client, db_session, test_data, url, model, kind):
    job_id, user_id = await _charged_job(db_session, test_data, model, reserved=7)
    start = await _user_credits(db_session, user_id)
    headers = test_data["get_headers"]("editor")
    first = await client.post(f"{url}/{job_id}/cancel", headers=headers)
    second = await client.post(f"{url}/{job_id}/cancel", headers=headers)
    assert (first.status_code, first.json()["credits_refunded"]) == (200, 7)
    assert second.status_code == 409
    assert await _user_credits(db_session, user_id) == start + 7
    assert len(await _refunds(db_session, reference_type=kind)) == 1


@pytest.mark.asyncio
async def test_cancel_then_worker_failure_refunds_once_and_stays_cancelled(client, db_session, test_data):
    job_id, user_id = await _charged_job(db_session, test_data, GhostJob, reserved=7)
    job = await db_session.get(GhostJob, job_id)
    job.status = "generating"  # the worker is mid-run
    await db_session.commit()
    start = await _user_credits(db_session, user_id)
    async with models.async_session_maker() as worker_db:
        running = await worker_db.get(GhostJob, job_id)  # the worker's copy: still "generating"
        res = await client.post(f"/api/v1/ghost-jobs/{job_id}/cancel", headers=test_data["get_headers"]("editor"))
        assert res.json()["credits_refunded"] == 7
        # The worker's attempt then fails on its last attempt
        await _fail_or_requeue(worker_db, running, "ghost_job", OSError("disk full"), final=True)
    job = await _reload(db_session, GhostJob, job_id)
    assert job.status == "cancelled"
    assert await _user_credits(db_session, user_id) == start + 7
    assert len(await _refunds(db_session, reference_type="ghost_job")) == 1


@pytest.mark.parametrize("worker,model", [(_process_ghost_job_async, GhostJob), (_process_sketch_job_async, SketchJob)])
@pytest.mark.asyncio
async def test_worker_skips_a_job_cancelled_while_queued(client, db_session, test_data, garment_store, worker, model):
    job_id, user_id = await _charged_job(db_session, test_data, model, reserved=7)
    url = "/api/v1/ghost-jobs" if model is GhostJob else "/api/v1/sketch-jobs"
    await client.post(f"{url}/{job_id}/cancel", headers=test_data["get_headers"]("editor"))
    after_cancel = await _user_credits(db_session, user_id)
    with patch.object(storage_service, "save_file_bytes", side_effect=OSError("disk full")) as save:
        await _attempt(db_session, worker, job_id, retries=3)
    save.assert_not_called()
    assert (await _reload(db_session, model, job_id)).status == "cancelled"
    assert await _user_credits(db_session, user_id) == after_cancel


# ========================== Catalog: per item, capped by the charge ============

@pytest.mark.asyncio
async def test_catalog_item_refunds_and_cancel_never_exceed_the_charge(client, db_session, test_data):
    job_id, user_id = await _charged_job(db_session, test_data, CatalogJob, reserved=10, total_items=2,
                                         generation_mode="studio_quality")
    items = [CatalogJobItem(job_id=job_id, sku_tag=f"S{i}", status="queued") for i in range(2)]
    db_session.add_all(items)
    await db_session.commit()
    first_item = items[0].id
    start = await _user_credits(db_session, user_id)

    async def run_worker():
        db_session.expunge_all()
        with patch("app.worker.async_session_maker", models.async_session_maker), \
                patch("app.worker._register_asset_version", side_effect=RuntimeError("version store down")):
            await _process_catalog_job_async(MagicMock(), job_id)

    await run_worker()  # both items fail: 5 + 5
    assert await _user_credits(db_session, user_id) == start + 10
    # A retried item that fails again is not refunded again
    item = await _reload(db_session, CatalogJobItem, first_item)
    item.status = "queued"
    job = await _reload(db_session, CatalogJob, job_id)
    job.status = "processing"
    await db_session.commit()
    await run_worker()
    assert await _user_credits(db_session, user_id) == start + 10
    job = await _reload(db_session, CatalogJob, job_id)
    job.status = "processing"
    await db_session.commit()
    # Cancelling refunds what is left of the charge: nothing
    res = await client.post(f"/api/v1/catalog-jobs/{job_id}/cancel", headers=test_data["get_headers"]("editor"))
    assert (res.status_code, res.json()["credits_refunded"]) == (200, 0)
    assert await _user_credits(db_session, user_id) == start + 10
    assert sum(r.amount for r in await _refunds(db_session, reference_type="catalog_job")) == 10


@pytest.mark.asyncio
async def test_refund_amount_is_what_the_job_reserved(db_session, test_data):
    job_id, user_id = await _charged_job(db_session, test_data, GhostJob, reserved=7)
    start = await _user_credits(db_session, user_id)
    job = await db_session.get(GhostJob, job_id)
    assert await refund_job(db_session, "ghost_job", job, "test", amount=50) == 7  # capped at the charge
    await db_session.commit()
    assert await refund_job(db_session, "ghost_job", job, "test") == 0
    await db_session.commit()
    assert await _user_credits(db_session, user_id) == start + 7
    [row] = await _refunds(db_session)
    assert (row.amount, row.user_id, row.brand_id, row.balance_after) == (7, user_id, test_data["brand"].id, start + 7)


# ========================== Brand reservations: admin /fail, callbacks ==========

async def _reservation(db_session, test_data, generation_id, amount=8):
    brand_id = test_data["brand"].id
    brand = await db_session.get(Brand, brand_id)
    brand.credits = 100
    db_session.add(GhostJob(user_id=test_data["users"]["owner"].id, brand_id=brand_id, job_id=generation_id,
                            status="queued", credits_reserved=amount))
    await db_session.commit()
    await credits_sync_service.reserve_credits(brand_id=brand_id, user_id=test_data["users"]["owner"].id,
                                               amount=amount, generation_id=generation_id, description="test",
                                               db=db_session)
    return brand_id


@pytest.mark.asyncio
async def test_admin_fail_twice_refunds_once(client, db_session, test_data, platform_admin_headers):
    brand_id = await _reservation(db_session, test_data, "ghost_batch_twice")
    reserved = await _brand_credits(db_session, brand_id)
    first = await client.post("/api/v1/ghost/batch/ghost_batch_twice/fail", headers=platform_admin_headers)
    second = await client.post("/api/v1/ghost/batch/ghost_batch_twice/fail", headers=platform_admin_headers)
    assert (first.status_code, first.json()["credits_refunded"]) == (200, 8)
    assert second.status_code == 404
    assert await _brand_credits(db_session, brand_id) == reserved + 8
    [row] = await _refunds(db_session, refund_key="generation:ghost_batch_twice")
    assert (row.amount, row.reference_id) == (8, "refund_ghost_batch_twice")


@pytest.mark.asyncio
async def test_internal_fail_callback_then_admin_fail_refunds_once(client, db_session, test_data,
                                                                   platform_admin_headers):
    brand_id = await _reservation(db_session, test_data, "gen_cb_1")
    reserved = await _brand_credits(db_session, brand_id)
    body = {"generation_id": "gen_cb_1", "reason": "GPU timeout"}
    assert (await client.post("/api/v1/internal/generations/gen_cb_1/fail", json=body, headers=INTERNAL)).status_code == 200
    assert (await client.post("/api/v1/internal/generations/gen_cb_1/fail", json=body, headers=INTERNAL)).status_code == 404
    assert (await client.post("/api/v1/ghost/batch/gen_cb_1/fail", headers=platform_admin_headers)).status_code == 404
    assert await _brand_credits(db_session, brand_id) == reserved + 8
    assert len(await _refunds(db_session, refund_key="generation:gen_cb_1")) == 1


@pytest.mark.asyncio
async def test_partial_refund_on_completion_is_capped_and_once(client, db_session, test_data):
    brand_id = await _reservation(db_session, test_data, "gen_partial", amount=8)
    reserved = await _brand_credits(db_session, brand_id)
    body = {"generation_id": "gen_partial", "credits_consumed": 5}
    assert (await client.post("/api/v1/internal/generations/gen_partial/complete", json=body,
                              headers=INTERNAL)).status_code == 200
    assert (await client.post("/api/v1/internal/generations/gen_partial/complete", json=body,
                              headers=INTERNAL)).status_code == 404
    assert await _brand_credits(db_session, brand_id) == reserved + 3
    [row] = await _refunds(db_session, refund_key="generation:gen_partial:partial")
    assert (row.amount, row.reference_id) == (3, "gen_partial")


# ========================== Concurrency and the database guarantee =============

@pytest.mark.asyncio
async def test_concurrent_refund_attempts_refund_once(db_session, test_data):
    job_id, user_id = await _charged_job(db_session, test_data, GhostJob, reserved=7)
    start = await _user_credits(db_session, user_id)

    async def attempt():
        async with models.async_session_maker() as session:
            job = await session.get(GhostJob, job_id)
            refunded = await refund_job(session, "ghost_job", job, "concurrent")
            await session.commit()
            return refunded

    results = await asyncio.gather(*(attempt() for _ in range(5)), return_exceptions=True)
    # SQLite has no row locks: losers are stopped by the unique refund_key (their transaction rolls
    # back) or find the refund already written. Postgres serializes them on the job row lock instead.
    assert [r for r in results if not isinstance(r, Exception) and r] == [7]
    assert all(isinstance(r, (IntegrityError, sa.exc.OperationalError)) or r in (0, 7) for r in results)
    assert await _user_credits(db_session, user_id) == start + 7
    assert len(await _refunds(db_session, reference_type="ghost_job")) == 1


@pytest.mark.asyncio
async def test_unique_refund_key_stops_a_second_refund_even_without_the_check(db_session, test_data, monkeypatch):
    job_id, user_id = await _charged_job(db_session, test_data, GhostJob, reserved=7)
    start = await _user_credits(db_session, user_id)
    job = await db_session.get(GhostJob, job_id)
    await refund_job(db_session, "ghost_job", job, "first")
    await db_session.commit()

    async def never_refunded(db, key):
        return False

    monkeypatch.setattr(job_refunds, "_already_refunded", never_refunded)
    monkeypatch.setattr(job_refunds, "refunded_so_far", lambda *a: asyncio.sleep(0, result=0))
    with pytest.raises(IntegrityError):
        await refund_job(db_session, "ghost_job", job, "second")
    await db_session.rollback()
    assert await _user_credits(db_session, user_id) == start + 7


# ========================== Migration job_refund_key_001 =======================

MIGRATION = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "alembic", "versions", "job_refund_key_001.py")

PRE_MIGRATION = """
CREATE TABLE credit_transactions (
    id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER, transaction_type VARCHAR(50),
    reference_type VARCHAR(50), reference_id VARCHAR(255), description VARCHAR(500)
);
INSERT INTO credit_transactions VALUES
    (1, 1, -1, 'spend', 'job', NULL, 'AI generation job credit deduction'),
    (2, 1, 1, 'refund', 'job', '17', 'Refund for failed generation job 17'),
    (3, 1, -8, 'reserved', NULL, 'gen_a', 'batch'),
    (4, 1, 8, 'refund', NULL, 'refund_gen_a', 'Auto refund: failed'),
    (5, 1, 8, 'refund', NULL, 'gen_b', 'Generation failed refund - gen_b'),
    (6, 1, 3, 'refund', NULL, 'gen_c', 'Partial refund for generation gen_c'),
    (7, 1, 5, 'refund', NULL, 'dlq_x_1', 'Auto DLQ refund - x job 1 failed'),
    (8, 1, 50, 'top_up', 'purchase_invoice', 'cs_1', 'Stripe');
"""


def _migration():
    spec = importlib.util.spec_from_file_location("job_refund_key_001", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def migration_db(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as conn:
        for statement in PRE_MIGRATION.split(";"):
            if statement.strip():
                conn.exec_driver_sql(statement)
    yield engine
    engine.dispose()


def _run(engine, step):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(_migration(), step)()


def _state(engine):
    with engine.connect() as conn:
        inspector = sa.inspect(conn)
        columns = {c["name"] for c in inspector.get_columns("credit_transactions")}
        indexes = {i["name"]: bool(i["unique"]) for i in inspector.get_indexes("credit_transactions")}
        rows = conn.exec_driver_sql("SELECT * FROM credit_transactions ORDER BY id").all()
    return columns, indexes, rows


def test_migration_revises_the_previous_head():
    module = _migration()
    assert (module.revision, module.down_revision) == ("job_refund_key_001", "stripe_customer_ledger_001")


def test_upgrade_adds_the_unique_key_and_backfills_unambiguous_refunds(migration_db):
    _run(migration_db, "upgrade")
    columns, indexes, _ = _state(migration_db)
    assert "refund_key" in columns and indexes["ix_credit_transactions_refund_key"] is True
    with migration_db.connect() as conn:
        keys = conn.exec_driver_sql("SELECT id, refund_key FROM credit_transactions ORDER BY id").all()
    assert keys == [(1, None), (2, "job:17"), (3, None), (4, "generation:gen_a"), (5, "generation:gen_b"),
                    (6, "generation:gen_c:partial"), (7, None), (8, None)]
    with pytest.raises(IntegrityError):
        with migration_db.begin() as conn:
            conn.exec_driver_sql("INSERT INTO credit_transactions (user_id, amount, refund_key) "
                                 "VALUES (1, 1, 'job:17')")


def test_upgrade_twice_is_a_no_op_and_downgrade_restores(migration_db):
    before = _state(migration_db)
    _run(migration_db, "upgrade")
    once = _state(migration_db)
    _run(migration_db, "upgrade")
    assert _state(migration_db) == once
    _run(migration_db, "downgrade")
    assert _state(migration_db) == before
    _run(migration_db, "upgrade")
    assert "refund_key" in _state(migration_db)[0]


@pytest.mark.parametrize("duplicate,listed", [
    ("(9, 1, 1, 'refund', 'job', '17', 'Refund for failed generation job 17')", r"job:17 \(2 rows, 2 credits\)"),
    ("(9, 1, 8, 'refund', NULL, 'gen_a', 'Generation failed refund - gen_a')", r"generation:gen_a \(2 rows, 16 credits\)"),
])
def test_duplicate_refunds_stop_the_upgrade_without_deleting(migration_db, duplicate, listed):
    with migration_db.begin() as conn:
        conn.exec_driver_sql(f"INSERT INTO credit_transactions VALUES {duplicate}")
    before = _state(migration_db)
    with pytest.raises(RuntimeError, match=listed + r".*nothing was deleted"):
        _run(migration_db, "upgrade")
    assert _state(migration_db) == before
