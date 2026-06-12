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
