import base64

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import GhostJob, GhostOutput, GhostJobAsset, User, Asset
from app.worker import _process_ghost_job_async

# A real 1x1 PNG: the worker reads and decodes each job image before generating.
GARMENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI6QAAAABJRU5ErkJggg==")


GARMENT_KEY = "/uploads/batch-garment.png"


@pytest_asyncio.fixture
async def garment(db_session: AsyncSession, test_data: dict):
    """An uploaded garment image in the test brand; batch items reference it by image_key."""
    asset = Asset(brand_id=test_data["brand"].id, filename="garment.png", storage_path=GARMENT_KEY,
                  asset_type="image")
    db_session.add(asset)
    await db_session.commit()
    return asset

@pytest.mark.asyncio
async def test_create_ghost_job_insufficient_credits(client: AsyncClient, db_session: AsyncSession, test_data: dict,
                                                     garment):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id

    # Set user credits to 1 (requires 4 for 2K)
    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    user.credits = 1
    await db_session.commit()

    res = await client.post("/api/v1/ghost-jobs", json={
        "brand_id": brand_id,
        "product_hint": "red silk dress",
        "garment_type": "dress",
        "view": "front",
        "aspect_ratio": "3:4",
        "resolution": "2K",
        "image_key": GARMENT_KEY,
    }, headers=editor_headers)

    assert res.status_code == status.HTTP_402_PAYMENT_REQUIRED
    assert "Insufficient credits" in res.json()["detail"]


@pytest.mark.asyncio
async def test_create_ghost_job_success(client: AsyncClient, db_session: AsyncSession, test_data: dict, garment):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    user.credits = 10
    await db_session.commit()
    starting_credits = user.credits

    with patch("app.routers.ghost_jobs.process_ghost_job.delay") as mock_celery:
        res = await client.post("/api/v1/ghost-jobs", json={
            "brand_id": brand_id,
            "product_hint": "red silk dress",
            "garment_type": "dress",
            "view": "front",
            "aspect_ratio": "3:4",
            "resolution": "2K", # costs 4 credits
            "image_key": GARMENT_KEY,
        }, headers=editor_headers)

        assert res.status_code == status.HTTP_201_CREATED
        data = res.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        assert data["credits_reserved"] == 4

        mock_celery.assert_called_once_with(data["job_id"])

        # Check DB updates
        db_session.expire_all()
        user_result = await db_session.execute(select(User).where(User.id == editor_id))
        user = user_result.scalars().first()
        assert user.credits == starting_credits - 4

        job_result = await db_session.execute(select(GhostJob).where(GhostJob.id == data["job_id"]))
        job = job_result.scalars().first()
        assert job is not None
        assert job.status == "queued"
        assert job.credits_reserved == 4


@pytest.mark.asyncio
async def test_get_ghost_job(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id

    job = GhostJob(
        user_id=editor_user.id,
        brand_id=brand_id,
        status="preprocessing",
        product_hint="test item",
        progress=15,
    )
    db_session.add(job)
    await db_session.commit()

    res = await client.get(f"/api/v1/ghost-jobs/{job.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "preprocessing"
    assert res.json()["progress"] == 15


@pytest.mark.asyncio
async def test_retry_ghost_job(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id

    job = GhostJob(
        user_id=editor_user.id,
        brand_id=brand_id,
        status="failed",
        error_message="some api error",
        progress=0,
    )
    db_session.add(job)
    await db_session.commit()

    with patch("app.routers.ghost_jobs.process_ghost_job.delay") as mock_celery:
        res = await client.post(f"/api/v1/ghost-jobs/{job.id}/retry", headers=editor_headers)
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["status"] == "queued"

        mock_celery.assert_called_once_with(job.id)

        await db_session.refresh(job)
        assert job.status == "queued"
        assert job.error_message is None


@pytest.mark.asyncio
async def test_cancel_ghost_job(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    user.credits = 10
    await db_session.commit()
    starting_credits = user.credits

    job = GhostJob(
        user_id=editor_id,
        brand_id=brand_id,
        status="preprocessing",
        credits_reserved=4,
        progress=15,
    )
    db_session.add(job)
    await db_session.commit()

    res = await client.post(f"/api/v1/ghost-jobs/{job.id}/cancel", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "cancelled"

    await db_session.refresh(job)
    assert job.status == "cancelled"

    # Reload user and check refund
    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    assert user.credits == starting_credits + 4


class MockSessionContext:
    def __init__(self, session):
        self.session = session
    async def __aenter__(self):
        return self.session
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_process_ghost_job_celery_task(db_session: AsyncSession, test_data: dict):
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id

    job = GhostJob(
        user_id=editor_user.id,
        brand_id=brand_id,
        status="queued",
        product_hint="blue flower top",
        garment_type="top",
        view="front",
        aspect_ratio="3:4",
        resolution="2K",
        credits_reserved=4,
    )
    db_session.add(job)
    await db_session.commit()
    db_session.add(GhostJobAsset(job_id=job.id, image_path="/uploads/blue_flower_top.png"))
    await db_session.commit()

    # Mock storage and celery self retry
    mock_task_self = MagicMock()

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker.storage_service.read_file_bytes", return_value=GARMENT_PNG), \
         patch("app.worker.storage_service.save_file_bytes", return_value="/uploads/ghost_mock.png"):
        
        await _process_ghost_job_async(mock_task_self, job.id)

    # Check job completion status
    await db_session.refresh(job)
    assert job.status == "completed"
    assert job.progress == 100
    assert job.credits_consumed == 4

    # Verify output record
    out_result = await db_session.execute(select(GhostOutput).where(GhostOutput.job_id == job.id))
    output = out_result.scalars().first()
    assert output is not None
    assert output.output_url == "/uploads/ghost_mock.png"
    assert output.quality_score == 0.93
    assert output.fidelity_status == "passed"

    # Verify asset created
    asset_result = await db_session.execute(select(Asset).where(Asset.id == output.asset_id))
    asset = asset_result.scalars().first()
    assert asset is not None
    assert asset.asset_type == "generated"
    assert asset.status == "active"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_process_ghost_job_celery_task_failure(db_session: AsyncSession, test_data: dict):
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id

    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    user.credits = 10
    await db_session.commit()
    starting_credits = user.credits

    job = GhostJob(
        user_id=editor_user.id,
        brand_id=brand_id,
        status="queued",
        credits_reserved=4,
    )
    db_session.add(job)
    await db_session.commit()
    db_session.add(GhostJobAsset(job_id=job.id, image_path="/uploads/garment.png"))
    await db_session.commit()

    mock_task_self = MagicMock()
    mock_task_self.max_retries = 3
    mock_task_self.retry = MagicMock(side_effect=Exception("Task retry invoked"))

    async def attempt(retries):
        mock_task_self.request.retries = retries
        # Force storage_service to throw exception to simulate failure
        with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
             patch("app.worker.storage_service.read_file_bytes", return_value=GARMENT_PNG), \
             patch("app.worker.storage_service.save_file_bytes", side_effect=ValueError("Storage write error")):
            try:
                await _process_ghost_job_async(mock_task_self, job.id)
            except Exception as e:
                assert "Task retry invoked" in str(e)
        await db_session.refresh(job)
        user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
        return user_result.scalars().first().credits

    # A failed attempt with retries left: re-queued for the Celery retry, nothing refunded yet
    assert await attempt(0) == starting_credits
    assert job.status == "queued" and "Storage write error" in job.error_message
    assert mock_task_self.retry.call_count == 1

    # The last attempt fails too: the job fails and is refunded once
    assert await attempt(3) == starting_credits + 4
    assert job.status == "failed"
    assert "Storage write error" in job.error_message
    assert mock_task_self.retry.call_count == 1

# ========================== Batch Tests ==========================



@pytest.mark.asyncio
async def test_batch_create_success(client: AsyncClient, test_data: dict, db_session: AsyncSession, garment):
    """Batch creation should succeed and return list of job IDs."""
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_user.credits = 100
    await db_session.commit()

    with patch("app.routers.ghost_jobs.process_ghost_job") as mock_task:
        mock_task.delay = MagicMock()
        res = await client.post(
            "/api/v1/ghost-jobs/batch",
            json={
                "brand_id": brand.id,
                "jobs": [
                    {"resolution": "2K", "garment_type": "dress", "view": "front", "image_key": GARMENT_KEY},
                    {"resolution": "1K", "garment_type": "top", "view": "back", "image_key": GARMENT_KEY},
                ]
            },
            headers=owner_headers,
        )
    assert res.status_code == 201
    data = res.json()
    assert data["batch_size"] == 2
    assert len(data["job_ids"]) == 2
    assert data["total_credits_reserved"] == 6  # 2K=4 + 1K=2


@pytest.mark.asyncio
async def test_batch_insufficient_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession, garment):
    """Batch should fail with 402 if insufficient credits."""
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_user.credits = 3
    await db_session.commit()

    with patch("app.routers.ghost_jobs.process_ghost_job") as mock_task:
        mock_task.delay = MagicMock()
        res = await client.post(
            "/api/v1/ghost-jobs/batch",
            json={
                "brand_id": brand.id,
                "jobs": [
                    {"resolution": "4K", "image_key": GARMENT_KEY},
                    {"resolution": "4K", "image_key": GARMENT_KEY},
                ]
            },
            headers=owner_headers,
        )
    assert res.status_code == 402


@pytest.mark.asyncio
async def test_batch_empty_jobs_rejected(client: AsyncClient, test_data: dict):
    """Batch with empty jobs list should fail validation."""
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    res = await client.post(
        "/api/v1/ghost-jobs/batch",
        json={"brand_id": brand.id, "jobs": []},
        headers=owner_headers,
    )
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_batch_auth_required(client: AsyncClient, test_data: dict):
    """Batch endpoint requires authentication."""
    brand = test_data["brand"]
    res = await client.post(
        "/api/v1/ghost-jobs/batch",
        json={"brand_id": brand.id, "jobs": [{"resolution": "2K"}]},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_batch_credit_deduction(client: AsyncClient, test_data: dict, db_session: AsyncSession, garment):
    """Credits should be deducted atomically after batch creation."""
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_user.credits = 50
    await db_session.commit()

    with patch("app.routers.ghost_jobs.process_ghost_job") as mock_task:
        mock_task.delay = MagicMock()
        res = await client.post(
            "/api/v1/ghost-jobs/batch",
            json={
                "brand_id": brand.id,
                "jobs": [{"resolution": "2K", "image_key": GARMENT_KEY}, {"resolution": "2K", "image_key": GARMENT_KEY}]
            },
            headers=owner_headers,
        )
    assert res.status_code == 201
    await db_session.refresh(owner_user)
    assert (owner_user.credits or 0) == 42  # 50 - (4+4) = 42


# ========================== Worker: source assets =================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_process_ghost_job_with_source_assets_in_fresh_session(db_session: AsyncSession, test_data: dict):
    """The worker opens its own session, as in production: job.assets must not be lazy-loaded (MissingGreenlet)."""
    import app.models.db as models
    from app.models.db import AssetRelationship

    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    sources = [
        Asset(brand_id=brand_id, name=f"Source {i}", filename=f"src_{i}.png",
              storage_path=f"/uploads/src_{i}.png", asset_type="upload", status="active")
        for i in range(2)
    ]
    db_session.add_all(sources)
    await db_session.commit()

    job = GhostJob(user_id=editor_user.id, brand_id=brand_id, status="queued", garment_type="top",
                   view="front", credits_reserved=4)
    db_session.add(job)
    await db_session.commit()
    db_session.add_all([
        GhostJobAsset(job_id=job.id, asset_id=sources[0].id, image_path="/uploads/src_0.png"),
        GhostJobAsset(job_id=job.id, asset_id=sources[1].id, image_path="/uploads/src_1.png"),
        GhostJobAsset(job_id=job.id, asset_id=None, image_path="/uploads/unregistered.png"),
    ])
    await db_session.commit()
    job_id = job.id
    db_session.expunge_all()

    mock_task_self = MagicMock()
    with patch("app.worker.async_session_maker", models.async_session_maker), \
         patch("app.worker.storage_service.read_file_bytes", return_value=GARMENT_PNG), \
         patch("app.worker.storage_service.save_file_bytes", return_value="/uploads/ghost_mock.png"):
        await _process_ghost_job_async(mock_task_self, job_id)

    mock_task_self.retry.assert_not_called()
    job = (await db_session.execute(select(GhostJob).where(GhostJob.id == job_id))).scalars().one()
    assert job.status == "completed"
    assert job.error_message is None
    assert job.progress == 100
    assert job.credits_consumed == 4

    output = (await db_session.execute(select(GhostOutput).where(GhostOutput.job_id == job_id))).scalars().one()
    rels = (await db_session.execute(
        select(AssetRelationship).where(AssetRelationship.target_asset_id == output.asset_id)
    )).scalars().all()
    assert sorted((r.source_asset_id, r.relationship_type) for r in rels) == sorted(
        (s.id, "REL-DERIVED-FROM") for s in sources
    )


# ========================== Single job: the image is required ====

SINGLE_ROUTE = "/api/v1/ghost-jobs"


@pytest_asyncio.fixture
async def nothing_written(db_session: AsyncSession, test_data: dict):
    """Asserts afterwards that a rejected request reserved, stored, wrote and queued nothing."""
    from sqlalchemy import func
    from app.models.db import CreditTransaction
    from app.services.storage import storage_service

    async def snapshot():
        user_credits = (await db_session.execute(select(User.credits).where(
            User.id == test_data["users"]["editor"].id).execution_options(populate_existing=True))).scalar_one()
        counts = [(await db_session.execute(select(func.count()).select_from(m))).scalar()
                  for m in (GhostJob, GhostJobAsset, CreditTransaction)]
        return user_credits, counts

    before = await snapshot()
    with patch.object(storage_service, "save_file_bytes") as save, \
            patch("app.routers.ghost_jobs.process_ghost_job.delay") as queue:
        yield
    save.assert_not_called()
    queue.assert_not_called()
    assert await snapshot() == before


async def _other_brand_image(db_session, test_data):
    from app.models.db import Brand
    brand = Brand(name="Other Brand", owner_id=test_data["users"]["nonmember"].id)
    db_session.add(brand)
    await db_session.commit()
    asset = Asset(brand_id=brand.id, filename="o.png", storage_path="/uploads/other-brand.png", asset_type="image")
    db_session.add(asset)
    await db_session.commit()
    return asset


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [
    "json without image", "form without image", "image sent as text", "empty file", "not an image",
    "unsupported type", "unknown image_key", "unknown asset_id", "other brand's image_key",
    "other brand's asset_id", "asset that is not an image",
])
async def test_single_job_without_a_usable_image_is_422(client, db_session, test_data, nothing_written, case):
    brand_id = test_data["brand"].id
    headers = test_data["get_headers"]("editor")
    fields = {"brand_id": brand_id, "resolution": "2K"}
    if case == "json without image":
        res = await client.post(SINGLE_ROUTE, json=fields, headers=headers)
    elif case == "form without image":  # multipart, with some other file but no `image`
        res = await client.post(SINGLE_ROUTE, data={"brand_id": str(brand_id)},
                                files={"notes": ("n.txt", b"hi", "text/plain")}, headers=headers)
    elif case == "image sent as text":
        res = await client.post(SINGLE_ROUTE, data={"brand_id": str(brand_id), "image": "dress.png"},
                                files={"notes": ("n.txt", b"hi", "text/plain")}, headers=headers)
    elif case in ("empty file", "not an image", "unsupported type"):
        upload = {"empty file": ("dress.png", b""), "not an image": ("dress.png", b"<html>not a png</html>"),
                  "unsupported type": ("dress.gif", b"GIF89a\x01\x00\x01\x00\x00\x00\x00;")}[case]
        res = await client.post(SINGLE_ROUTE, data={"brand_id": str(brand_id)},
                                files={"image": (*upload, "image/png")}, headers=headers)
    else:
        if case.startswith("other brand"):
            other = await _other_brand_image(db_session, test_data)
            ref = {"image_key": other.storage_path} if "image_key" in case else {"asset_id": other.id}
        elif case == "asset that is not an image":
            doc = Asset(brand_id=brand_id, filename="spec.pdf", storage_path="/uploads/spec.pdf", asset_type="document")
            db_session.add(doc)
            await db_session.commit()
            ref = {"asset_id": doc.id}
        else:
            ref = {"image_key": "/uploads/nope.png"} if case == "unknown image_key" else {"asset_id": 999_999}
        res = await client.post(SINGLE_ROUTE, json={**fields, **ref}, headers=headers)
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, res.text
    detail = res.json()["detail"]
    assert isinstance(detail, str) and detail
    assert "other-brand" not in detail


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["dress.png", "dress.JPG", "dress.webp"])
async def test_single_job_with_an_uploaded_image_is_unchanged(client, db_session, test_data, filename):
    from io import BytesIO
    from PIL import Image as PILImage
    fmt = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP"}[filename.rsplit(".", 1)[1].lower()]
    out = BytesIO()
    PILImage.new("RGB", (4, 4)).save(out, format=fmt)
    from app.services.storage import storage_service
    with patch.object(storage_service, "save_file_bytes", return_value="/uploads/u.png") as save, \
            patch("app.routers.ghost_jobs.process_ghost_job.delay") as queue:
        res = await client.post(SINGLE_ROUTE, data={"brand_id": str(test_data["brand"].id), "resolution": "1K"},
                                files={"image": (filename, out.getvalue(), "image/png")},
                                headers=test_data["get_headers"]("editor"))
    assert res.status_code == 201, res.text
    assert save.call_args.args[1] == out.getvalue()
    queue.assert_called_once_with(res.json()["job_id"])
    link = (await db_session.execute(select(GhostJobAsset).where(GhostJobAsset.job_id == res.json()["job_id"])))
    assert [(l.asset_id, l.image_path) for l in link.scalars()] == [(None, "/uploads/u.png")]


@pytest.mark.asyncio
@pytest.mark.parametrize("by", ["image_key", "asset_id", "form asset_id"])
async def test_single_job_can_reference_an_uploaded_image_asset(client, db_session, test_data, garment, by):
    with patch("app.routers.ghost_jobs.process_ghost_job.delay"):
        if by == "form asset_id":
            res = await client.post(SINGLE_ROUTE, data={"brand_id": str(test_data["brand"].id),
                                                        "asset_id": str(garment.id)},
                                    files={"notes": ("n.txt", b"hi", "text/plain")},  # multipart
                                    headers=test_data["get_headers"]("editor"))
        else:
            ref = garment.storage_path if by == "image_key" else garment.id
            res = await client.post(SINGLE_ROUTE, json={"brand_id": test_data["brand"].id, by: ref},
                                    headers=test_data["get_headers"]("editor"))
    assert res.status_code == 201, res.text
    link = (await db_session.execute(select(GhostJobAsset).where(GhostJobAsset.job_id == res.json()["job_id"])))
    assert [(l.asset_id, l.image_path) for l in link.scalars()] == [(garment.id, GARMENT_KEY)]


@pytest.mark.asyncio
async def test_single_job_role_check_still_comes_first(client, test_data):
    res = await client.post(SINGLE_ROUTE, json={"brand_id": test_data["brand"].id},
                            headers=test_data["get_headers"]("viewer"))
    assert res.status_code == 403
