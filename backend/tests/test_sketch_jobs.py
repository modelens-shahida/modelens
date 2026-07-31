import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import SketchJob, SketchJobReference, SketchOutput, User, Asset
from app.worker import _process_sketch_job_async


@pytest.mark.asyncio
async def test_create_sketch_job_insufficient_credits(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id

    # Set user credits to 0
    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    user.credits = 0
    await db_session.commit()

    # Fast draft costs 1 credit
    res = await client.post("/api/v1/sketch-jobs", json={
        "brand_id": brand_id,
        "product_hint": "denim jacket",
        "generation_mode": "fast_draft",
    }, headers=editor_headers)

    assert res.status_code == status.HTTP_402_PAYMENT_REQUIRED
    assert "Insufficient credits" in res.json()["detail"]


@pytest.mark.asyncio
async def test_create_sketch_job_success_fast_draft(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    user.credits = 10
    await db_session.commit()
    starting_credits = user.credits

    with patch("app.routers.sketch_jobs.process_sketch_job.delay") as mock_celery:
        res = await client.post("/api/v1/sketch-jobs", json={
            "brand_id": brand_id,
            "product_hint": "denim jacket",
            "generation_mode": "fast_draft", # costs 1 credit
            "reference_image_paths": ["/uploads/sketch1.png"],
        }, headers=editor_headers)

        assert res.status_code == status.HTTP_201_CREATED
        data = res.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        assert data["credits_reserved"] == 1

        mock_celery.assert_called_once_with(data["job_id"])

        # Check DB updates
        db_session.expire_all()
        user_result = await db_session.execute(select(User).where(User.id == editor_id))
        user = user_result.scalars().first()
        assert user.credits == starting_credits - 1

        job_result = await db_session.execute(select(SketchJob).where(SketchJob.id == data["job_id"]))
        job = job_result.scalars().first()
        assert job is not None
        assert job.status == "queued"
        assert job.credits_reserved == 1

        # Check references
        refs_result = await db_session.execute(
            select(SketchJobReference).where(SketchJobReference.job_id == data["job_id"])
        )
        refs = refs_result.scalars().all()
        assert len(refs) == 1
        assert refs[0].image_path == "/uploads/sketch1.png"


@pytest.mark.asyncio
async def test_create_sketch_job_success_studio_quality(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    user.credits = 10
    await db_session.commit()
    starting_credits = user.credits

    with patch("app.routers.sketch_jobs.process_sketch_job.delay") as mock_celery:
        res = await client.post("/api/v1/sketch-jobs", json={
            "brand_id": brand_id,
            "product_hint": "leather boots",
            "generation_mode": "studio_quality", # costs 5 credits
            "reference_image_paths": ["/uploads/sketch2.png", "/uploads/sketch3.png"],
        }, headers=editor_headers)

        assert res.status_code == status.HTTP_201_CREATED
        data = res.json()
        assert data["credits_reserved"] == 5

        db_session.expire_all()
        user_result = await db_session.execute(select(User).where(User.id == editor_id))
        user = user_result.scalars().first()
        assert user.credits == starting_credits - 5


@pytest.mark.asyncio
async def test_get_sketch_job(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id

    job = SketchJob(
        user_id=editor_user.id,
        brand_id=brand_id,
        status="preprocessing",
        product_hint="running shoes",
        progress=15,
    )
    db_session.add(job)
    await db_session.commit()

    res = await client.get(f"/api/v1/sketch-jobs/{job.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["status"] == "preprocessing"
    assert data["progress"] == 15
    assert data["references"] == []


@pytest.mark.asyncio
async def test_retry_sketch_job(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id

    job = SketchJob(
        user_id=editor_user.id,
        brand_id=brand_id,
        status="failed",
        error_message="API connection timed out",
        progress=0,
    )
    db_session.add(job)
    await db_session.commit()

    with patch("app.routers.sketch_jobs.process_sketch_job.delay") as mock_celery:
        res = await client.post(f"/api/v1/sketch-jobs/{job.id}/retry", headers=editor_headers)
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["status"] == "queued"

        mock_celery.assert_called_once_with(job.id)

        await db_session.refresh(job)
        assert job.status == "queued"
        assert job.error_message is None


@pytest.mark.asyncio
async def test_cancel_sketch_job(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    user.credits = 10
    await db_session.commit()
    starting_credits = user.credits

    job = SketchJob(
        user_id=editor_id,
        brand_id=brand_id,
        status="queued",
        credits_reserved=5,
        progress=0,
    )
    db_session.add(job)
    await db_session.commit()

    res = await client.post(f"/api/v1/sketch-jobs/{job.id}/cancel", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "cancelled"

    await db_session.refresh(job)
    assert job.status == "cancelled"

    # Reload user and check credit refund
    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    assert user.credits == starting_credits + 5


class MockSessionContext:
    def __init__(self, session):
        self.session = session
    async def __aenter__(self):
        return self.session
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_process_sketch_job_celery_task_success(db_session: AsyncSession, test_data: dict):
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id

    job = SketchJob(
        user_id=editor_user.id,
        brand_id=brand_id,
        status="queued",
        product_hint="designer handbag",
        generation_mode="studio_quality",
        credits_reserved=5,
    )
    db_session.add(job)
    await db_session.commit()

    mock_task_self = MagicMock()

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker.storage_service.save_file_bytes", return_value="/uploads/sketch_mock_output.png"):
        
        await _process_sketch_job_async(mock_task_self, job.id)

    # Check job completion status
    await db_session.refresh(job)
    assert job.status == "completed"
    assert job.progress == 100
    assert job.credits_consumed == 5

    # Verify output record
    out_result = await db_session.execute(select(SketchOutput).where(SketchOutput.job_id == job.id))
    output = out_result.scalars().first()
    assert output is not None
    assert output.output_url == "/uploads/sketch_mock_output.png"
    assert output.quality_score == 0.91

    # Verify asset created
    asset_result = await db_session.execute(select(Asset).where(Asset.id == output.asset_id))
    asset = asset_result.scalars().first()
    assert asset is not None
    assert asset.asset_type == "generated"
    assert asset.status == "active"


@pytest.mark.asyncio
async def test_process_sketch_job_celery_task_failure(db_session: AsyncSession, test_data: dict):
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id

    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    user.credits = 10
    await db_session.commit()
    starting_credits = user.credits

    job = SketchJob(
        user_id=editor_user.id,
        brand_id=brand_id,
        status="queued",
        credits_reserved=5,
    )
    db_session.add(job)
    await db_session.commit()

    mock_task_self = MagicMock()
    mock_task_self.retry = MagicMock(side_effect=Exception("Task retry invoked"))

    # Force storage_service to throw exception to simulate failure
    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker.storage_service.save_file_bytes", side_effect=ValueError("Storage write error")):
        
        try:
            await _process_sketch_job_async(mock_task_self, job.id)
        except Exception as err:
            assert "Task retry invoked" in str(err)

    # Check job failure and credit refund
    await db_session.refresh(job)
    assert job.status == "failed"
    assert "Storage write error" in job.error_message

    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    assert user.credits == starting_credits + 5
