import pytest
import json
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import AIJob, User

@pytest.mark.asyncio
async def test_job_generation_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_headers = test_data["get_headers"]("editor")

    # Mock Celery delay to avoid actual queue execution
    with patch("app.routers.jobs.process_generation_job.delay") as mock_delay, \
         patch("app.routers.jobs.redis_client.set", new_callable=AsyncMock) as mock_redis_set:
        
        payload = {
            "brand_id": brand.id,
            "workflow_template_id": workflow.id,
            "inputs": {"urls": ["s3://my-bucket/input.jpg"]},
            "callback_url": "http://my-webhook.com/cb"
        }

        res = await client.post("/api/v1/jobs/generate", json=payload, headers=editor_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "pending"
        assert data["job_type"] == "generation"
        assert data["brand_id"] == brand.id
        assert data["workflow_template_id"] == workflow.id
        assert data["inputs"] == {"urls": ["s3://my-bucket/input.jpg"]}
        assert data["callback_url"] == "http://my-webhook.com/cb"

        # Verify credit deduction
        editor_user = test_data["users"]["editor"]
        db_res = await db_session.execute(select(User).where(User.id == editor_user.id))
        updated_user = db_res.scalars().first()
        assert updated_user.credits == 99  # Starts at 100, deducted by 1

        # Verify celery and redis were triggered
        mock_delay.assert_called_once()
        mock_redis_set.assert_called_once()


@pytest.mark.asyncio
async def test_job_generation_unauthorized(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    viewer_headers = test_data["get_headers"]("viewer")

    payload = {
        "brand_id": brand.id,
        "workflow_template_id": workflow.id,
        "inputs": {},
    }

    res = await client.post("/api/v1/jobs/generate", json=payload, headers=viewer_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_job_generation_insufficient_credits(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_user = test_data["users"]["editor"]
    editor_headers = test_data["get_headers"]("editor")

    # Set credits to 0
    editor_user.credits = 0
    db_session.add(editor_user)
    await db_session.commit()

    payload = {
        "brand_id": brand.id,
        "workflow_template_id": workflow.id,
        "inputs": {},
    }

    res = await client.post("/api/v1/jobs/generate", json=payload, headers=editor_headers)
    assert res.status_code == 400
    assert "Insufficient credits" in res.json()["detail"]


@pytest.mark.asyncio
async def test_job_status_polling_cache_hit(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_user = test_data["users"]["editor"]
    editor_headers = test_data["get_headers"]("editor")

    # Create dummy job in PostgreSQL (which will be bypassed on cache hit)
    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        workflow_template_id=workflow.id,
        status="pending",
        job_type="generation",
        inputs={},
        outputs={}
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # Mock Redis GET to return a cached "completed" state immediately
    cached_payload = {
        "id": job.id,
        "user_id": job.user_id,
        "brand_id": job.brand_id,
        "workflow_template_id": job.workflow_template_id,
        "asset_id": 12,
        "status": "completed",
        "job_type": "generation",
        "inputs": {},
        "outputs": {"urls": ["s3://completed.png"]},
        "callback_url": None,
        "error_message": None,
        "created_at": "2026-06-12T10:00:00",
        "updated_at": "2026-06-12T10:05:00"
    }

    with patch("app.routers.jobs.redis_client.get", new_callable=AsyncMock, return_value=json.dumps(cached_payload)):
        res = await client.get(f"/api/v1/jobs/{job.id}", headers=editor_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert data["asset_id"] == 12
        assert data["outputs"] == {"urls": ["s3://completed.png"]}


@pytest.mark.asyncio
async def test_job_status_polling_cache_miss(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_user = test_data["users"]["editor"]
    editor_headers = test_data["get_headers"]("editor")

    # Create dummy job in PostgreSQL
    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        workflow_template_id=workflow.id,
        status="processing",
        job_type="generation",
        inputs={"prompt": "beautiful jacket"},
        outputs={},
        callback_url="http://callback"
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # Mock Redis GET as cache miss (return None)
    with patch("app.routers.jobs.redis_client.get", new_callable=AsyncMock, return_value=None), \
         patch("app.routers.jobs.redis_client.set", new_callable=AsyncMock) as mock_redis_set:
        
        res = await client.get(f"/api/v1/jobs/{job.id}", headers=editor_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "processing"
        assert data["inputs"] == {"prompt": "beautiful jacket"}
        assert data["callback_url"] == "http://callback"

        # Verify it populates the cache after fetch
        mock_redis_set.assert_called_once()


# ========================== AI Generation Worker Tests ==============

@pytest.mark.asyncio
async def test_process_generation_job_success_with_mock_image(db_session: AsyncSession, test_data: dict):
    """
    Worker should generate an image (mocked), save it via storage_service,
    create an Asset, and mark the job completed.
    """
    from app.worker import _process_generation_job_async
    from app.models.db import AIJob, Asset

    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_user = test_data["users"]["editor"]

    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        workflow_template_id=workflow.id,
        status="pending",
        job_type="generation",
        inputs={"prompt": "A luxury editorial fashion shot, golden hour lighting"},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    fake_image_bytes = b"\x89PNG\r\n\x1a\nfakeimagebytes"

    class MockSessionContext:
        def __init__(self, session):
            self.session = session
        async def __aenter__(self):
            return self.session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker._generate_image", new=AsyncMock(return_value=fake_image_bytes)), \
         patch("app.worker.storage_service.save_file_bytes", return_value="/uploads/generated_test.png") as mock_save, \
         patch("app.worker.redis_client.set", new_callable=AsyncMock), \
         patch("app.worker.dispatch_webhook.delay"):

        await _process_generation_job_async(job.id)

    await db_session.refresh(job)
    assert job.status == "completed"
    assert job.asset_id is not None
    mock_save.assert_called_once()

    asset_result = await db_session.execute(select(Asset).where(Asset.id == job.asset_id))
    asset = asset_result.scalars().first()
    assert asset is not None
    assert asset.brand_id == brand.id
    assert asset.meta.get("generated_by_job") == job.id


@pytest.mark.asyncio
async def test_process_generation_job_failure_refunds_credit(db_session: AsyncSession, test_data: dict):
    """
    If image generation fails, the job should be marked failed and the
    user should be refunded 1 credit.
    """
    from app.worker import _process_generation_job_async
    from app.models.db import AIJob, User

    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_user = test_data["users"]["editor"]

    # Simulate a prior credit deduction (as generate_job endpoint normally does)
    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    starting_credits = user.credits
    user.credits -= 1
    await db_session.commit()

    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        workflow_template_id=workflow.id,
        status="pending",
        job_type="generation",
        inputs={"prompt": "This will fail"},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    class MockSessionContext:
        def __init__(self, session):
            self.session = session
        async def __aenter__(self):
            return self.session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker._generate_image", new=AsyncMock(side_effect=RuntimeError("Image generation failed"))), \
         patch("app.worker.redis_client.set", new_callable=AsyncMock), \
         patch("app.worker.dispatch_webhook.delay"):

        await _process_generation_job_async(job.id)

    await db_session.refresh(job)
    assert job.status == "failed"
    assert job.error_message is not None

    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    refunded_user = user_result.scalars().first()
    assert refunded_user.credits == starting_credits  # back to original after refund


@pytest.mark.asyncio
async def test_generate_image_mock_fallback_without_api_key(monkeypatch):
    """
    _generate_image should fall back to a mock placeholder image
    when OPENAI_API_KEY is not set, without raising.
    """
    from app.worker import _generate_image

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = await _generate_image("A test prompt")
    assert isinstance(result, bytes)
    assert len(result) > 0
