"""POST /api/v1/ghost-jobs/batch links each item's uploaded image to its own job.

Ghost Studio uploads every batch image first with POST /api/v1/assets (the same
storage_service.save_file_bytes path a single ghost job's upload uses) and then
sends the batch with each item's storage_path as image_key. The route used to
drop image_key; now each job gets a GhostJobAsset with the item's image, like a
single job. Items are validated before anything is charged or written, and the
batch is one transaction, so a failure leaves no credits charged and no rows.

Storage and the Celery dispatch are mocked; nothing reaches the network.
"""
from unittest.mock import MagicMock, patch

import celery.app.task
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.models.db import Asset, Brand, GhostJob, GhostJobAsset, User
from app.services.storage import storage_service

BATCH = "/api/v1/ghost-jobs/batch"
SINGLE = "/api/v1/ghost-jobs"
# Fields the worker (_process_ghost_job_async) reads from the job.
WORKER_FIELDS = ("user_id", "brand_id", "status", "garment_type", "view", "aspect_ratio", "resolution",
                 "preserve_print", "preserve_seams", "generation_mode", "credits_reserved", "credits_consumed",
                 "progress", "product_hint")


@pytest.fixture
def queued(monkeypatch):
    """Every Celery .delay call."""
    delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr(celery.app.task.Task, "delay", delay)
    return delay


@pytest.fixture
def stored():
    """storage_service writes (the batch route must not write files itself)."""
    with patch.object(storage_service, "save_file_bytes", return_value="/uploads/single-upload.png") as save:
        yield save


async def _image(db_session, brand_id, name, **fields):
    asset = Asset(brand_id=brand_id, filename=name, storage_path=f"/uploads/{name}",
                  asset_type=fields.pop("asset_type", "image"), **fields)
    db_session.add(asset)
    await db_session.commit()
    return asset


@pytest_asyncio.fixture
async def garments(db_session, test_data):
    """Three uploaded garment images in the test brand, as POST /api/v1/assets stores them."""
    brand_id = test_data["brand"].id
    return [await _image(db_session, brand_id, name) for name in ("dress.png", "top.jpg", "coat.webp")]


async def _snapshot(db_session):
    jobs = (await db_session.execute(select(func.count()).select_from(GhostJob))).scalar()
    links = (await db_session.execute(select(func.count()).select_from(GhostJobAsset))).scalar()
    users = (await db_session.execute(select(User.id, User.credits).order_by(User.id)
                                      .execution_options(populate_existing=True))).all()
    brands = (await db_session.execute(select(Brand.id, Brand.credits).order_by(Brand.id)
                                       .execution_options(populate_existing=True))).all()
    return jobs, links, users, brands


async def _links(db_session, job_id):
    return (await db_session.execute(select(GhostJobAsset).where(GhostJobAsset.job_id == job_id)
                                     .order_by(GhostJobAsset.id))).scalars().all()


def _item(asset=None, **fields):
    item = {"resolution": "2K", "garment_type": "dress", "view": "front", **fields}
    if asset is not None:
        item["image_key"] = asset.storage_path
    return item


# ========================== Images linked =========================

@pytest.mark.asyncio
async def test_each_item_image_is_linked_to_its_own_job(client, db_session, test_data, garments, queued, stored):
    items = [_item(garments[0], garment_type="dress"),
             _item(garments[1], garment_type="top", resolution="1K"),
             {"resolution": "4K", "garment_type": "coat", "asset_id": garments[2].id}]  # by asset_id
    resp = await client.post(BATCH, json={"brand_id": test_data["brand"].id, "jobs": items},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["batch_size"], body["total_credits_reserved"]) == (3, 4 + 2 + 7)

    for job_id, asset, garment_type in zip(body["job_ids"], garments, ("dress", "top", "coat")):
        job = (await db_session.execute(select(GhostJob).where(GhostJob.id == job_id))).scalar_one()
        assert job.garment_type == garment_type
        (link,) = await _links(db_session, job_id)
        assert (link.asset_id, link.image_path) == (asset.id, asset.storage_path)
    assert sorted(c.args[0] for c in queued.call_args_list) == sorted(body["job_ids"])
    stored.assert_not_called()  # images were stored by the upload; nothing is written again


@pytest.mark.asyncio
async def test_batch_job_matches_a_single_job_for_the_worker(client, db_session, test_data, garments, queued, stored):
    headers = test_data["get_headers"]("editor")
    brand_id = test_data["brand"].id
    common = {"resolution": "2K", "garment_type": "top", "view": "back", "aspect_ratio": "4:5",
              "generation_mode": "studio", "product_hint": "linen shirt"}
    single = await client.post(SINGLE, headers=headers, files={"image": ("shirt.png", b"png-bytes", "image/png")},
                               data={"brand_id": str(brand_id), **common,
                                     "preserve_print": "true", "preserve_seams": "true"})
    assert single.status_code == 201, single.text
    batch = await client.post(BATCH, headers=headers,
                              json={"brand_id": brand_id, "jobs": [{**common, "image_key": garments[1].storage_path}]})
    assert batch.status_code == 201, batch.text

    single_job = (await db_session.execute(select(GhostJob).where(GhostJob.id == single.json()["job_id"]))).scalar_one()
    batch_job = (await db_session.execute(select(GhostJob).where(GhostJob.id == batch.json()["job_ids"][0]))).scalar_one()
    assert {f: getattr(batch_job, f) for f in WORKER_FIELDS} == {f: getattr(single_job, f) for f in WORKER_FIELDS}

    (single_link,) = await _links(db_session, single_job.id)
    (batch_link,) = await _links(db_session, batch_job.id)
    # Same storage layout (storage_service.save_file_bytes); the batch link also names the uploaded asset.
    assert single_link.image_path.startswith("/uploads/") and batch_link.image_path.startswith("/uploads/")
    assert batch_link.asset_id == garments[1].id
    assert [c.args[0] for c in queued.call_args_list] == [single_job.id, batch_job.id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_worker_processes_a_batch_job_with_its_image(client, db_session, test_data, garments, queued):
    import app.models.db as models
    from app.models.db import AssetRelationship, GhostOutput
    from app.worker import _process_ghost_job_async

    resp = await client.post(BATCH, json={"brand_id": test_data["brand"].id, "jobs": [_item(garments[0])]},
                             headers=test_data["get_headers"]("editor"))
    job_id = resp.json()["job_ids"][0]
    db_session.expunge_all()
    with patch("app.worker.async_session_maker", models.async_session_maker), \
         patch("app.worker.storage_service.save_file_bytes", return_value="/uploads/ghost_out.png"):
        await _process_ghost_job_async(MagicMock(), job_id)

    job = (await db_session.execute(select(GhostJob).where(GhostJob.id == job_id))).scalar_one()
    assert job.status == "completed"
    output = (await db_session.execute(select(GhostOutput).where(GhostOutput.job_id == job_id))).scalar_one()
    rel = (await db_session.execute(select(AssetRelationship)
                                    .where(AssetRelationship.target_asset_id == output.asset_id))).scalar_one()
    assert (rel.source_asset_id, rel.relationship_type) == (garments[0].id, "REL-DERIVED-FROM")


# ========================== Validation ============================

@pytest_asyncio.fixture
async def bad_images(db_session, test_data):
    """Images an item must not use: another brand's, deleted, not an image, unsupported format."""
    from datetime import datetime
    other = Brand(name="Other Brand", owner_id=test_data["users"]["nonmember"].id)
    db_session.add(other)
    await db_session.commit()
    brand_id = test_data["brand"].id
    return {
        "other_brand": await _image(db_session, other.id, "foreign.png"),
        "deleted": await _image(db_session, brand_id, "deleted.png", deleted_at=datetime.utcnow()),
        "not_image": await _image(db_session, brand_id, "specs.pdf", asset_type="document"),
        "bad_format": await _image(db_session, brand_id, "garment.gif"),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("bad,expected", [
    ("missing", "jobs[1]: an image is required"),
    ("unknown_key", "jobs[1]: image_key was not found in this brand."),
    ("unknown_id", "jobs[1]: asset 999999 was not found in this brand."),
    ("other_brand", "jobs[1]: image_key was not found in this brand."),
    ("deleted", "jobs[1]: image_key was not found in this brand."),
    ("not_image", "jobs[1]: image_key is not a JPEG, PNG, WebP or HEIC image."),
    ("bad_format", "jobs[1]: image_key is not a JPEG, PNG, WebP or HEIC image."),
])
async def test_one_bad_item_rejects_the_whole_batch(
        client, db_session, test_data, garments, bad_images, queued, stored, bad, expected):
    bad_item = {
        "missing": _item(),
        "unknown_key": _item(image_key="/uploads/never-uploaded.png"),
        "unknown_id": _item(asset_id=999_999),
    }.get(bad) or _item(bad_images[bad])
    before = await _snapshot(db_session)
    resp = await client.post(BATCH, json={"brand_id": test_data["brand"].id,
                                          "jobs": [_item(garments[0]), bad_item, _item(garments[1])]},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 422, resp.text
    assert expected in resp.json()["detail"]
    assert "jobs[0]" not in resp.json()["detail"] and "jobs[2]" not in resp.json()["detail"]
    assert await _snapshot(db_session) == before
    queued.assert_not_called()
    stored.assert_not_called()


@pytest.mark.asyncio
async def test_every_bad_item_is_named(client, db_session, test_data, garments, queued):
    resp = await client.post(BATCH, json={"brand_id": test_data["brand"].id,
                                          "jobs": [_item(), _item(garments[0]), _item(asset_id=999_999)]},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 422
    assert "jobs[0]: an image is required" in resp.json()["detail"]
    assert "jobs[2]: asset 999999 was not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_insufficient_credits_still_402_after_images_check(client, db_session, test_data, garments, queued):
    editor = (await db_session.execute(select(User).where(User.id == test_data["users"]["editor"].id))).scalar_one()
    editor.credits = 5
    await db_session.commit()
    before = await _snapshot(db_session)
    resp = await client.post(BATCH, json={"brand_id": test_data["brand"].id,
                                          "jobs": [_item(garments[0]), _item(garments[1])]},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 402
    assert await _snapshot(db_session) == before
    queued.assert_not_called()


# ========================== Failure mid-batch =====================

@pytest.mark.asyncio
async def test_failure_mid_batch_charges_nothing_and_leaves_nothing(
        client, db_session, test_data, garments, queued, stored, monkeypatch):
    from app.routers import ghost_jobs
    real_link = ghost_jobs.GhostJobAsset
    calls = []

    def failing_link(**fields):
        calls.append(fields)
        if len(calls) == 2:
            raise RuntimeError("storage link failed")
        return real_link(**fields)

    monkeypatch.setattr(ghost_jobs, "GhostJobAsset", failing_link)
    before = await _snapshot(db_session)
    try:
        resp = await client.post(BATCH, json={"brand_id": test_data["brand"].id,
                                              "jobs": [_item(g) for g in garments]},
                                 headers=test_data["get_headers"]("editor"))
        assert resp.status_code == 500
    except RuntimeError as exc:  # the test client re-raises unhandled app errors
        assert "storage link failed" in str(exc)
    assert len(calls) == 2
    db_session.expire_all()
    assert await _snapshot(db_session) == before
    queued.assert_not_called()
    stored.assert_not_called()


# ========================== Auth ==================================

@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["viewer", "nonmember"])
async def test_brand_role_still_enforced(client, db_session, test_data, garments, queued, role):
    before = await _snapshot(db_session)
    resp = await client.post(BATCH, json={"brand_id": test_data["brand"].id, "jobs": [_item(garments[0])]},
                             headers=test_data["get_headers"](role))
    assert resp.status_code == 403
    assert await _snapshot(db_session) == before
    queued.assert_not_called()


@pytest.mark.asyncio
async def test_role_is_checked_before_images(client, test_data, queued):
    """A caller without access learns nothing about the brand's assets."""
    resp = await client.post(BATCH, json={"brand_id": test_data["brand"].id,
                                          "jobs": [_item(image_key="/uploads/whatever.png")]},
                             headers=test_data["get_headers"]("nonmember"))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_login_required(client, test_data, garments):
    resp = await client.post(BATCH, json={"brand_id": test_data["brand"].id, "jobs": [_item(garments[0])]})
    assert resp.status_code == 401


# ========================== Single job unchanged ==================

@pytest.mark.asyncio
async def test_single_job_still_saves_its_upload(client, db_session, test_data, queued, stored):
    resp = await client.post(SINGLE, headers=test_data["get_headers"]("editor"),
                             files={"image": ("dress.png", b"png-bytes", "image/png")},
                             data={"brand_id": str(test_data["brand"].id), "resolution": "1K"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["credits_reserved"] == 2
    stored.assert_called_once()
    (link,) = await _links(db_session, resp.json()["job_id"])
    assert (link.asset_id, link.image_path) == (None, "/uploads/single-upload.png")
    queued.assert_called_once_with(resp.json()["job_id"])


@pytest.mark.asyncio
async def test_single_job_without_image_still_allowed(client, test_data, queued, stored):
    resp = await client.post(SINGLE, json={"brand_id": test_data["brand"].id, "resolution": "1K"},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 201
    stored.assert_not_called()
