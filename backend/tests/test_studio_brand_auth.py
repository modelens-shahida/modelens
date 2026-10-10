"""Brand authorization on Ghost, Ghost Batch, Sketch and Catalog job creation.

Every creation endpoint takes the brand from the request. The caller must own
it or be a member with the editor role or higher (viewer -> 403, non-member ->
403, unknown brand -> 404), and a source asset must belong to that brand (else
404, also when it exists in another brand). A rejected request stores no
upload, creates no job, asset or ledger row, queues nothing and charges no
credits.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import celery.app.task
import pytest
from sqlalchemy import func, select

from app.models.db import (
    AIJob, Asset, Brand, CatalogJob, CatalogJobItem, CreditTransaction, GhostJob, GhostJobAsset, SketchJob,
    SketchJobReference, User,
)
from app.services.storage import storage_service

ROW_MODELS = (GhostJob, GhostJobAsset, SketchJob, SketchJobReference, CatalogJob, CatalogJobItem, Asset,
              CreditTransaction, AIJob)

# name -> (url, JSON body for a brand, status on success)
ENDPOINTS = {
    "ghost": ("/api/v1/ghost-jobs", lambda b: {"brand_id": b, "resolution": "1K"}, 201),
    "ghost_jobs_batch": ("/api/v1/ghost-jobs/batch", lambda b: {"brand_id": b, "jobs": [{"resolution": "1K"}]}, 201),
    "ghost_volumetric": ("/api/v1/ghost-jobs/volumetric",
                         lambda b: {"brand_id": b, "views": ["FRONT"], "resolution": "1K"}, 202),
    "ghost_batch": ("/api/v1/ghost/batch", lambda b: {"brand_id": b, "items": [{"sku": "SKU-1"}]}, 201),
    "ghost_batch_check": ("/api/v1/ghost/batch/check", lambda b: {"brand_id": b, "items": [{"sku": "SKU-1"}]}, 200),
    "sketch_jobs": ("/api/v1/sketch-jobs", lambda b: {"brand_id": b, "generation_mode": "fast_draft"}, 201),
    "sketch_studio": ("/api/v1/sketch/jobs", lambda b: {"brand_id": b, "generation_mode": "fast_draft"}, 202),
    "catalog_jobs": ("/api/v1/catalog-jobs", lambda b: {
        "brand_id": b, "generation_mode": "fast_draft",
        "products": [{"sku_tag": "SKU-1", "image_path": "/uploads/sku-1.png"}]}, 201),
}
ALL = sorted(ENDPOINTS)
REQUIRED_BRAND = ["ghost", "ghost_jobs_batch", "ghost_volumetric", "ghost_batch", "ghost_batch_check",
                  "sketch_studio", "catalog_jobs"]


@pytest.fixture
def queued(monkeypatch):
    """Every Celery .delay call (one shared mock for all tasks)."""
    delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr(celery.app.task.Task, "delay", delay)
    return delay


@pytest.fixture
def stored():
    with patch.object(storage_service, "save_file_bytes", return_value="/uploads/saved.png") as save:
        yield save


async def _snapshot(db_session):
    counts = [(await db_session.execute(select(func.count()).select_from(m))).scalar() for m in ROW_MODELS]
    users = (await db_session.execute(select(User.id, User.credits).order_by(User.id))).all()
    brands = (await db_session.execute(select(Brand.id, Brand.credits).order_by(Brand.id))).all()
    return counts, users, brands


async def _asset(db_session, brand_id, **fields):
    asset = Asset(brand_id=brand_id, filename="sketch.png", storage_path="/uploads/sketch.png", asset_type="image",
                  **fields)
    db_session.add(asset)
    await db_session.commit()
    return asset


async def _post(client, test_data, name, role, brand_id, **overrides):
    url, body, _ = ENDPOINTS[name]
    return await client.post(url, json={**body(brand_id), **overrides}, headers=test_data["get_headers"](role))


async def _assert_rejected(client, db_session, test_data, queued, stored, name, role, brand_id, code, **overrides):
    before = await _snapshot(db_session)
    resp = await _post(client, test_data, name, role, brand_id, **overrides)
    assert resp.status_code == code, (name, resp.text)
    queued.assert_not_called()
    stored.assert_not_called()
    assert await _snapshot(db_session) == before, name
    return resp


# ========================== Roles =================================

@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "editor"])
@pytest.mark.parametrize("name", ALL)
async def test_owner_and_editor_allowed(client, test_data, queued, stored, name, role):
    resp = await _post(client, test_data, name, role, test_data["brand"].id)
    assert resp.status_code == ENDPOINTS[name][2], resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ALL)
async def test_viewer_gets_403(client, db_session, test_data, queued, stored, name):
    resp = await _assert_rejected(client, db_session, test_data, queued, stored, name, "viewer",
                                  test_data["brand"].id, 403)
    assert "Requires at least 'editor' role" in resp.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ALL)
async def test_non_member_gets_403(client, db_session, test_data, queued, stored, name):
    # nonmember owns other_brand, but has no role in test_data["brand"].
    resp = await _assert_rejected(client, db_session, test_data, queued, stored, name, "nonmember",
                                  test_data["brand"].id, 403)
    assert resp.json()["detail"] == "You are not a member of this brand"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ALL)
async def test_member_of_another_brand_gets_403(client, db_session, test_data, queued, stored, name):
    await _assert_rejected(client, db_session, test_data, queued, stored, name, "editor",
                           test_data["other_brand"].id, 403)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ALL)
async def test_missing_brand_gets_404(client, db_session, test_data, queued, stored, name):
    resp = await _assert_rejected(client, db_session, test_data, queued, stored, name, "owner", 999_999, 404)
    assert resp.json()["detail"] == "Brand not found"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", REQUIRED_BRAND)
async def test_missing_brand_id_gets_422(client, db_session, test_data, queued, stored, name):
    url, body, _ = ENDPOINTS[name]
    payload = body(test_data["brand"].id)
    payload.pop("brand_id")
    before = await _snapshot(db_session)
    resp = await client.post(url, json=payload, headers=test_data["get_headers"]("owner"))
    assert resp.status_code == 422, resp.text
    assert {"loc": ["body", "brand_id"], "type": "missing"}.items() <= resp.json()["detail"][0].items()
    queued.assert_not_called()
    assert await _snapshot(db_session) == before


# ========================== Source assets =========================

@pytest.mark.asyncio
@pytest.mark.parametrize("name,field", [("ghost_volumetric", "source_asset_id"), ("sketch_studio", "sketch_asset_id")])
async def test_source_asset_must_belong_to_the_brand(client, db_session, test_data, queued, stored, name, field):
    brand = test_data["brand"]
    foreign = await _asset(db_session, test_data["other_brand"].id)
    deleted = await _asset(db_session, brand.id, deleted_at=datetime(2026, 1, 1))
    for asset_id in (foreign.id, deleted.id, 999_999):  # all answer the same 404
        resp = await _assert_rejected(client, db_session, test_data, queued, stored, name, "editor", brand.id, 404,
                                      **{field: asset_id})
        assert resp.json()["detail"] == "Asset not found"

    own = await _asset(db_session, brand.id)
    resp = await _post(client, test_data, name, "editor", brand.id, **{field: own.id})
    assert resp.status_code == ENDPOINTS[name][2], resp.text
    assert queued.call_args.kwargs[field] == own.id


# ========================== Multipart uploads =====================

def _form_post(client, test_data, role, url, data, files):
    return client.post(url, data=data, files=files, headers=test_data["get_headers"](role))


@pytest.mark.asyncio
async def test_ghost_form_requires_brand_id(client, db_session, test_data, queued, stored):
    before = await _snapshot(db_session)
    for data in ({}, {"brand_id": ""}):
        resp = await _form_post(client, test_data, "owner", "/api/v1/ghost-jobs", {"resolution": "1K", **data},
                                {"image": ("front.png", b"img", "image/png")})
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"][0]["loc"] == ["body", "brand_id"]
    resp = await _form_post(client, test_data, "owner", "/api/v1/ghost-jobs", {"brand_id": "abc"},
                            {"image": ("front.png", b"img", "image/png")})
    assert resp.status_code == 422
    stored.assert_not_called()
    queued.assert_not_called()
    assert await _snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("url,file_field", [("/api/v1/ghost-jobs", "image"), ("/api/v1/sketch-jobs", "sketches"),
                                            ("/api/v1/catalog-jobs", "products")])
async def test_rejected_upload_is_not_stored(client, db_session, test_data, queued, stored, url, file_field):
    files = {file_field: ("front.png", b"img", "image/png")}
    before = await _snapshot(db_session)
    for role, brand_id, code in (("viewer", test_data["brand"].id, 403), ("nonmember", test_data["brand"].id, 403),
                                 ("owner", 999_999, 404)):
        resp = await _form_post(client, test_data, role, url, {"brand_id": str(brand_id)}, files)
        assert resp.status_code == code, (role, resp.text)
    stored.assert_not_called()
    queued.assert_not_called()
    assert await _snapshot(db_session) == before

    resp = await _form_post(client, test_data, "editor", url, {"brand_id": str(test_data["brand"].id)}, files)
    assert resp.status_code == 201, resp.text
    stored.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("url,file_field", [("/api/v1/sketch-jobs", "sketches"), ("/api/v1/catalog-jobs", "products")])
async def test_default_brand_still_needs_editor(client, db_session, test_data, queued, stored, url, file_field):
    """Sketch and catalog jobs fall back to the caller's first brand; the role check applies to it too."""
    files = {file_field: ("front.png", b"img", "image/png")}
    before = await _snapshot(db_session)
    resp = await _form_post(client, test_data, "viewer", url, {}, files)  # viewer's only brand
    assert resp.status_code == 403
    stored.assert_not_called()
    assert await _snapshot(db_session) == before

    resp = await _form_post(client, test_data, "editor", url, {}, files)
    assert resp.status_code == 201, resp.text
    job_model = SketchJob if "sketch" in url else CatalogJob
    job = (await db_session.execute(select(job_model))).scalars().one()
    assert job.brand_id == test_data["brand"].id


# ========================== Ghost batch jobs ======================

async def _ghost_batch(client, test_data):
    resp = await _post(client, test_data, "ghost_batch", "editor", test_data["brand"].id)
    assert resp.status_code == 201, resp.text
    return resp.json()["job_id"]


@pytest.mark.asyncio
async def test_ghost_batch_charges_the_requested_brand(client, db_session, test_data, queued, stored):
    brand_id, other_id = test_data["brand"].id, test_data["other_brand"].id
    job_id = await _ghost_batch(client, test_data)
    job_brand = (await db_session.execute(select(GhostJob.brand_id).where(GhostJob.job_id == job_id))).scalar_one()
    assert job_brand == brand_id
    txn = (await db_session.execute(
        select(CreditTransaction.brand_id, CreditTransaction.reference_id, CreditTransaction.amount))).one()
    assert tuple(txn) == (brand_id, job_id, -4)
    assert (await db_session.execute(select(Brand.credits).where(Brand.id == other_id))).scalar_one() == 100


@pytest.mark.asyncio
async def test_ghost_batch_job_is_only_visible_to_its_brand(client, test_data, queued, stored):
    job_id = await _ghost_batch(client, test_data)
    url = f"/api/v1/ghost/batch/{job_id}"
    for role in ("owner", "editor", "viewer"):
        assert (await client.get(url, headers=test_data["get_headers"](role))).status_code == 200
    resp = await client.get(url, headers=test_data["get_headers"]("nonmember"))
    assert (resp.status_code, resp.json()["detail"]) == (404, "Ghost job not found.")


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["complete", "fail"])
async def test_ghost_batch_callbacks_need_an_editor_of_the_jobs_brand(client, db_session, test_data, queued, stored,
                                                                      action):
    job_id = await _ghost_batch(client, test_data)
    url = f"/api/v1/ghost/batch/{job_id}/{action}"
    before = await _snapshot(db_session)
    for role in ("viewer", "nonmember"):
        resp = await client.post(url, headers=test_data["get_headers"](role))
        assert (resp.status_code, resp.json()["detail"]) == (404, "Ghost job not found.")
    assert await _snapshot(db_session) == before

    resp = await client.post(url, headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["complete", "fail"])
async def test_ghost_batch_callbacks_ignore_other_generation_ids(client, db_session, test_data, queued, stored,
                                                                 action):
    """Refunds go through the shared ledger by generation id; only ghost batch jobs may be touched here."""
    brand = test_data["brand"]
    db_session.add(CreditTransaction(brand_id=brand.id, user_id=test_data["users"]["owner"].id, amount=-16,
                                     transaction_type="reserved", status="pending", reference_id="prd_other"))
    await db_session.commit()
    before = await _snapshot(db_session)
    resp = await client.post(f"/api/v1/ghost/batch/prd_other/{action}", headers=test_data["get_headers"]("owner"))
    assert (resp.status_code, resp.json()["detail"]) == (404, "Ghost job not found.")
    assert await _snapshot(db_session) == before
