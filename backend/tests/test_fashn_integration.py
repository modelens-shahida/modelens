"""Catalog generation through FASHN (app/services/fashn_client.py, app/services/fashn_catalog.py).

FASHN is faked (tests/fashn_fakes.py: no network, a test-only key). Covered:
* success: presigned input URLs (never our paths or public URLs), run + poll to completion, the
  output downloaded into our storage under the brand, linked to the job as an asset;
* Try-On Max with the job's model image; product-to-model without;
* failures (FASHN failed/canceled/time_out, 4xx, OutOfCredits, timeout, invalid output, storage
  failure): the item fails and is refunded exactly once; no mock output in production;
* 429 rate limits and 5xx are retried with backoff;
* cross-brand input paths never reach FASHN;
* customer responses never contain FASHN URLs, prediction ids, the key or signed URLs;
* the startup checklist refuses to boot Catalog in production without a key or S3.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

import app.models.db as models
from app.config import settings
from app.config_production import ProductionConfigError, check_config, run_startup_checks
from app.models.db import Asset, CatalogJob, CatalogJobItem, CreditTransaction, User
from app.services import fashn_catalog
from app.services.catalog_availability import CATALOG_GENERATION_FAILED
from app.services.storage import storage_service
from app.worker import _process_catalog_item_retry_async, _process_catalog_job_async, _process_single_catalog_item_async
from tests import fashn_fakes
from tests.fashn_fakes import OUTPUT_URL, PREDICTION_ID, TEST_KEY, api_error, status

pytestmark = pytest.mark.integration  # runs worker task bodies

SIGNATURE = "X-Amz-Signature=test-only-signature"


def _signed(key, expires_in):
    return f"https://modelens-test.s3.amazonaws.com/{key}?X-Amz-Expires={expires_in}&{SIGNATURE}"


@pytest.fixture
def production(monkeypatch):
    """Production with Catalog on, S3-style presigned URLs, and the fake FASHN."""
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "CATALOG_JOBS_ENABLED", True)
    monkeypatch.setattr(storage_service, "presigned_get_url", MagicMock(side_effect=_signed))
    return fashn_fakes.install(monkeypatch)


async def _stored_image(brand_id):
    return storage_service.save_file_bytes(f"tests/brand-{brand_id}/{uuid.uuid4().hex}.png", fashn_fakes.png())


async def _job(db, t, items=1, engine_mode="product_to_model", model_image=None, brand="brand", reserved=None):
    """A charged studio-quality catalog job (5 credits per item) of the brand's own stored images."""
    brand_id = t[brand].id
    editor = t["users"]["editor"] if brand == "brand" else t["users"]["nonmember"]
    reserved = reserved if reserved is not None else 5 * items
    user = await db.get(User, editor.id)
    user.credits = (user.credits or 0) - reserved
    paths = [await _stored_image(brand_id) for _ in range(items)]
    db.add_all([Asset(brand_id=brand_id, filename="p.png", storage_path=p, asset_type="image") for p in paths])
    job = CatalogJob(user_id=editor.id, brand_id=brand_id, status="queued", total_items=items,
                     generation_mode="studio_quality", engine_mode=engine_mode, resolution="2K", aspect_ratio="4:5",
                     pose="Catalog Standing", background="Soft Front Studio", credits_reserved=reserved,
                     meta={"model_image_path": model_image} if model_image else None)
    db.add(job)
    await db.commit()
    rows = [CatalogJobItem(job_id=job.id, sku_tag=f"SKU-{i}", status="queued", product_image_path=p)
            for i, p in enumerate(paths)]
    db.add_all(rows)
    await db.commit()
    return job.id, [r.id for r in rows], editor.id, paths


async def _work(db, worker, *args):
    db.expunge_all()
    with patch("app.worker.async_session_maker", models.async_session_maker):
        await worker(*args)


async def _reload(db, model, row_id):
    return (await db.execute(select(model).where(model.id == row_id).execution_options(populate_existing=True))
            ).scalar_one()


async def _credits(db, user_id):
    return (await db.execute(select(User.credits).where(User.id == user_id)
                             .execution_options(populate_existing=True))).scalar_one()


async def _refunds(db):
    return (await db.execute(select(CreditTransaction).where(
        CreditTransaction.transaction_type == "refund", CreditTransaction.reference_type == "catalog_job",
    ).execution_options(populate_existing=True))).scalars().all()


async def _generated_assets(db):
    return (await db.execute(select(Asset).where(Asset.asset_type == "generated")
                             .execution_options(populate_existing=True))).scalars().all()


# ========================== Success ===============================================

@pytest.mark.asyncio
async def test_product_to_model_success_polls_stores_and_links_the_output(db_session, test_data, production, capsys):
    fake = production
    job_id, [item_id], user_id, [path] = await _job(db_session, test_data)
    start = await _credits(db_session, user_id)

    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)

    run = fake.runs[0]
    assert run.headers["authorization"] == f"Bearer {TEST_KEY}"
    body = fake.run_json
    assert body["model_name"] == "product-to-model"
    assert body["inputs"]["product_image"].startswith("https://modelens-test.s3.amazonaws.com/")
    assert path not in body["inputs"]["product_image"]  # a signed URL of the key, not our path
    assert "X-Amz-Expires=900" in body["inputs"]["product_image"]
    assert {k: body["inputs"][k] for k in ("resolution", "generation_mode", "num_images", "aspect_ratio")} == \
        {"resolution": "2k", "generation_mode": "quality", "num_images": 1, "aspect_ratio": "4:5"}
    assert "model_image" not in body["inputs"]
    assert len(fake.polls) == 3 and all(p.url.path == f"/v1/status/{PREDICTION_ID}" for p in fake.polls)
    assert len(fake.downloads) == 1

    item = await _reload(db_session, CatalogJobItem, item_id)
    assert item.status == "qa_passed" and item.provider_job_id == PREDICTION_ID
    assert item.output_url.startswith(f"/uploads/brands/{test_data['brand'].id}/catalog/{job_id}/item-{item_id}-")
    assert storage_service.read_file_bytes(item.output_url[len("/uploads/"):]) == fake.output
    [asset] = await _generated_assets(db_session)
    assert (asset.brand_id, asset.storage_path, asset.meta["job_id"], asset.meta["item_id"]) == \
        (test_data["brand"].id, item.output_url, job_id, item_id)
    job = await _reload(db_session, CatalogJob, job_id)
    assert (job.status, job.completed_items, job.credits_consumed) == ("completed", 1, 5)
    assert await _credits(db_session, user_id) == start and await _refunds(db_session) == []
    out = capsys.readouterr().out
    assert TEST_KEY not in out and SIGNATURE not in out


@pytest.mark.asyncio
async def test_tryon_max_sends_the_model_image_as_a_signed_url(db_session, test_data, production):
    model_path = await _stored_image(test_data["brand"].id)
    job_id, [item_id], _, _ = await _job(db_session, test_data, engine_mode="tryon_max", model_image=model_path)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    inputs = production.run_json["inputs"]
    assert production.run_json["model_name"] == "tryon-max"
    assert inputs["model_image"].startswith("https://modelens-test.s3.amazonaws.com/") and SIGNATURE in inputs["model_image"]
    assert "aspect_ratio" not in inputs  # not a tryon-max input
    assert (await _reload(db_session, CatalogJobItem, item_id)).status == "qa_passed"


@pytest.mark.asyncio
async def test_rate_limits_and_server_errors_are_retried(db_session, test_data, production):
    production.run_replies = [api_error(429, "RateLimitExceeded"), api_error(503, "InternalServerError"),
                              (200, {"id": PREDICTION_ID, "error": None})]
    production.status_replies = [api_error(429, "ConcurrencyLimitExceeded"), status("processing"),
                                 status("completed", [OUTPUT_URL])]
    job_id, [item_id], _, _ = await _job(db_session, test_data)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    assert len(production.runs) == 3  # no id was issued for the refused runs: nothing ran twice
    assert (await _reload(db_session, CatalogJobItem, item_id)).status == "qa_passed"


# ========================== Failures: failed + refunded once =======================

FAILURES = {
    "fashn failed": lambda f: setattr(f, "status_replies", [status("processing"), status(
        "failed", error={"name": "ImageLoadError", "message": "Error loading model image: Invalid URL format"})]),
    "fashn canceled": lambda f: setattr(f, "status_replies", [status("canceled")]),
    "fashn time_out": lambda f: setattr(f, "status_replies", [status("time_out")]),
    "unauthorized": lambda f: setattr(f, "run_replies", [api_error(401, "UnauthorizedAccess")]),
    "bad request": lambda f: setattr(f, "run_replies", [api_error(400, "BadRequest")]),
    "out of credits": lambda f: setattr(f, "run_replies", [api_error(429, "OutOfCredits")]),
    "rate limited until the deadline": lambda f: setattr(f, "run_replies", [api_error(429, "RateLimitExceeded")] * 500),
    "polling timeout": lambda f: setattr(f, "status_replies", [status("processing")]),
    "no output": lambda f: setattr(f, "status_replies", [status("completed", [])]),
    "output not an image": lambda f: setattr(f, "output", b"<html>not an image</html>"),
    "output download fails": lambda f: setattr(f, "output_status", 403),
}


@pytest.mark.parametrize("case", list(FAILURES))
@pytest.mark.asyncio
async def test_any_fashn_failure_fails_the_item_and_refunds_it_once(db_session, test_data, production, case):
    FAILURES[case](production)
    job_id, [item_id], user_id, _ = await _job(db_session, test_data)
    start = await _credits(db_session, user_id)

    for _ in range(2):  # a redelivered task refunds nothing more
        await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)

    item = await _reload(db_session, CatalogJobItem, item_id)
    assert (item.status, item.error_message, item.output_url) == ("failed", CATALOG_GENERATION_FAILED, None)
    job = await _reload(db_session, CatalogJob, job_id)
    assert (job.status, job.completed_items, job.failed_items, job.credits_consumed) == ("failed", 0, 1, 0)
    assert await _credits(db_session, user_id) == start + 5
    assert [r.refund_key for r in await _refunds(db_session)] == [f"catalog_job:{job_id}:item:{item_id}"]
    assert await _generated_assets(db_session) == []
    if case == "unauthorized" or case == "bad request" or case == "out of credits":
        assert len(production.runs) == 1  # not retried


@pytest.mark.asyncio
async def test_storage_failure_fails_and_refunds_once(db_session, test_data, production, monkeypatch):
    job_id, [item_id], user_id, _ = await _job(db_session, test_data)
    start = await _credits(db_session, user_id)
    real_save = storage_service.save_file_bytes

    def save(name, data, *a):
        if name.startswith("brands/"):
            raise RuntimeError("bucket unavailable")
        return real_save(name, data, *a)

    monkeypatch.setattr(storage_service, "save_file_bytes", save)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    item = await _reload(db_session, CatalogJobItem, item_id)
    assert (item.status, item.error_message) == ("failed", CATALOG_GENERATION_FAILED)
    assert await _credits(db_session, user_id) == start + 5 and len(await _refunds(db_session)) == 1


@pytest.mark.asyncio
async def test_item_retry_after_a_failure_is_not_refunded_twice(db_session, test_data, production):
    production.status_replies = [status("failed", error={"name": "PipelineError", "message": "x"})]
    job_id, [item_id], user_id, _ = await _job(db_session, test_data)
    start = await _credits(db_session, user_id)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    await _work(db_session, _process_catalog_item_retry_async, item_id)  # fails again
    await _work(db_session, _process_single_catalog_item_async, MagicMock(), item_id, job_id)
    assert await _credits(db_session, user_id) == start + 5
    assert len(await _refunds(db_session)) == 1
    assert len(production.runs) == 3  # each attempt really ran
    assert (await _reload(db_session, CatalogJob, job_id)).failed_items == 1


@pytest.mark.asyncio
async def test_item_retry_that_succeeds_uses_fashn_and_settles_the_job(db_session, test_data, production):
    production.status_replies = [status("failed", error={"name": "PipelineError", "message": "x"})]
    job_id, [item_id], _, _ = await _job(db_session, test_data)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    production.status_replies = [status("completed", [OUTPUT_URL])]
    production._status_index = 0
    await _work(db_session, _process_catalog_item_retry_async, item_id)
    item = await _reload(db_session, CatalogJobItem, item_id)
    assert item.status == "qa_passed" and item.output_url.startswith("/uploads/brands/")
    job = await _reload(db_session, CatalogJob, job_id)
    assert (job.status, job.completed_items, job.failed_items) == ("completed", 1, 0)


@pytest.mark.asyncio
async def test_tryon_max_without_a_model_image_fails_without_calling_fashn(db_session, test_data, production):
    job_id, [item_id], user_id, _ = await _job(db_session, test_data, engine_mode="tryon_max")
    start = await _credits(db_session, user_id)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    production.assert_not_called()
    item = await _reload(db_session, CatalogJobItem, item_id)
    assert (item.status, item.error_message) == ("failed", "Try-On Max needs a model image.")
    assert await _credits(db_session, user_id) == start + 5


# ========================== Inputs: own storage, same brand, signed =================

@pytest.mark.parametrize("which", ["product", "model"])
@pytest.mark.asyncio
async def test_another_brands_image_never_reaches_fashn(db_session, test_data, production, which):
    theirs = await _stored_image(test_data["other_brand"].id)
    db_session.add(Asset(brand_id=test_data["other_brand"].id, filename="t.png", storage_path=theirs,
                         asset_type="image"))
    await db_session.commit()
    if which == "product":
        job_id, [item_id], user_id, _ = await _job(db_session, test_data)
        item = await db_session.get(CatalogJobItem, item_id)
        item.product_image_path = theirs
        await db_session.commit()
    else:
        job_id, [item_id], user_id, _ = await _job(db_session, test_data, engine_mode="tryon_max", model_image=theirs)
    start = await _credits(db_session, user_id)

    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)

    production.assert_not_called()
    storage_service.presigned_get_url.assert_not_called() if which == "product" else None
    item = await _reload(db_session, CatalogJobItem, item_id)
    label = "Product image" if which == "product" else "Model image"
    assert (item.status, item.error_message) == ("failed", f"{label} is not stored in this brand's ModeLens storage.")
    assert await _credits(db_session, user_id) == start + 5


@pytest.mark.asyncio
async def test_production_without_signed_urls_never_sends_a_public_url(db_session, test_data, production, monkeypatch):
    monkeypatch.setattr(storage_service, "presigned_get_url", MagicMock(return_value=None))  # local storage
    job_id, [item_id], _, _ = await _job(db_session, test_data)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    production.assert_not_called()
    assert (await _reload(db_session, CatalogJobItem, item_id)).error_message == CATALOG_GENERATION_FAILED


@pytest.mark.asyncio
async def test_outside_production_local_images_are_sent_inline(db_session, test_data, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    fake = fashn_fakes.install(monkeypatch)
    job_id, [item_id], _, _ = await _job(db_session, test_data)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    assert fake.run_json["inputs"]["product_image"].startswith("data:image/png;base64,")
    assert (await _reload(db_session, CatalogJobItem, item_id)).status == "qa_passed"


@pytest.mark.asyncio
async def test_production_without_a_key_never_saves_a_mock(db_session, test_data, production, monkeypatch):
    monkeypatch.setattr(settings, "FASHN_API_KEY", None)
    job_id, [item_id], user_id, _ = await _job(db_session, test_data)
    start = await _credits(db_session, user_id)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    production.assert_not_called()
    item = await _reload(db_session, CatalogJobItem, item_id)
    assert (item.status, item.output_url) == ("failed", None)
    assert await _credits(db_session, user_id) == start + 5 and await _generated_assets(db_session) == []


# ========================== Responses =============================================

@pytest.mark.asyncio
async def test_customer_responses_never_show_fashn_urls_or_internals(client, db_session, test_data, production):
    job_id, _, _, _ = await _job(db_session, test_data)
    await _work(db_session, _process_catalog_job_async, MagicMock(), job_id)
    res = await client.get(f"/api/v1/catalog-jobs/{job_id}", headers=test_data["get_headers"]("viewer"))
    assert res.status_code == 200
    text = res.text
    for leaked in ("fashn", PREDICTION_ID, TEST_KEY, "X-Amz-Signature", "amazonaws", "provider_job_id"):
        assert leaked not in text.lower() if leaked == "fashn" else leaked not in text, leaked
    assert res.json()["items"][0]["output_url"].startswith("/uploads/brands/")
    res = await client.get(f"/api/v1/catalog-jobs/{job_id}/export-zip", headers=test_data["get_headers"]("viewer"))
    assert res.status_code == 200 and OUTPUT_URL.encode() not in res.content


@pytest.mark.asyncio
async def test_direct_fashn_routes_are_503_in_production(client, test_data, production):
    for path in ("/api/v1/fashn/product-to-model", "/api/v1/fashn/try-on-max"):
        res = await client.post(path, json={}, headers=test_data["get_headers"]("owner"))
        assert res.status_code == 503, path
    production.assert_not_called()


# ========================== Create: engine mode and model image ===================

@pytest.mark.asyncio
async def test_create_validates_engine_mode_and_model_image(client, db_session, test_data, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    brand_id = test_data["brand"].id
    product = await _stored_image(brand_id)
    model = await _stored_image(brand_id)
    theirs = await _stored_image(test_data["other_brand"].id)
    db_session.add_all([Asset(brand_id=brand_id, filename="p.png", storage_path=product, asset_type="image"),
                        Asset(brand_id=brand_id, filename="m.png", storage_path=model, asset_type="image"),
                        Asset(brand_id=test_data["other_brand"].id, filename="t.png", storage_path=theirs,
                              asset_type="image")])
    owner = await db_session.get(User, test_data["users"]["owner"].id)
    owner.credits = 100
    await db_session.commit()
    headers = test_data["get_headers"]("owner")
    body = {"brand_id": brand_id, "products": [{"sku_tag": "A", "image_path": product}]}

    with patch("app.routers.catalog_jobs.process_catalog_job") as task:
        assert (await client.post("/api/v1/catalog-jobs", json={**body, "engine_mode": "magic"},
                                  headers=headers)).status_code == 422
        res = await client.post("/api/v1/catalog-jobs", json={**body, "engine_mode": "tryon_max"}, headers=headers)
        assert res.status_code == 422 and "model_image" in res.text
        res = await client.post("/api/v1/catalog-jobs", json={**body, "engine_mode": "tryon_max",
                                                               "model_image_path": theirs}, headers=headers)
        assert res.status_code == 422 and "model_image_path" in res.text
        res = await client.post("/api/v1/catalog-jobs", json={**body, "engine_mode": "tryon_max",
                                                               "model_image_path": model}, headers=headers)
        assert res.status_code == 201, res.text
        assert task.delay.call_count == 1
    job = await _reload(db_session, CatalogJob, res.json()["job_id"])
    assert (job.engine_mode, job.meta) == ("tryon_max", {"model_image_path": model})
    res = await client.post("/api/v1/catalog-jobs", headers=headers, data={
        "brand_id": str(brand_id), "fashn_mode": "tryon_max", "sku_0": "A"},
        files=[("products", ("p.png", fashn_fakes.png(), "image/png")),
               ("custom_model", ("m.png", fashn_fakes.png(), "image/png"))])
    assert res.status_code == 201, res.text
    job = await _reload(db_session, CatalogJob, res.json()["job_id"])
    assert job.meta["model_image_path"].startswith("/uploads/")


# ========================== Startup checklist =====================================

def test_catalog_on_in_production_without_a_key_or_s3_is_fatal(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "CATALOG_JOBS_ENABLED", False)
    monkeypatch.setattr(settings, "FASHN_API_KEY", None)
    assert not [i for i in check_config() if i.name == "FASHN_API_KEY"]

    monkeypatch.setattr(settings, "CATALOG_JOBS_ENABLED", True)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    [issue] = [i for i in check_config() if i.name == "FASHN_API_KEY"]
    assert issue.fatal is True
    with pytest.raises(ProductionConfigError):
        run_startup_checks()

    monkeypatch.setattr(settings, "FASHN_API_KEY", TEST_KEY)
    assert not [i for i in check_config() if i.name == "FASHN_API_KEY"]
    assert all(TEST_KEY not in str(i) for i in check_config())  # never logged
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    [storage] = [i for i in check_config() if i.name == "STORAGE_BACKEND" and i.fatal]
    assert storage.fatal is True


def test_fashn_settings_have_safe_defaults():
    from app.config import Settings
    fields = Settings.model_fields
    assert fields["FASHN_API_KEY"].default is None
    assert fields["FASHN_BASE_URL"].default == "https://api.fashn.ai"
    assert fields["CATALOG_JOBS_ENABLED"].default is False


def test_model_names_follow_the_engine_mode():
    assert fashn_catalog.model_name("tryon_max") == "tryon-max"
    assert fashn_catalog.model_name("product_to_model") == "product-to-model"
    assert fashn_catalog.model_name(None) == "product-to-model"
