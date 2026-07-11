import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import Campaign, Character, CharacterVersion
from app.config import settings


# ========================== Fixtures ==============================

@pytest.fixture(autouse=True)
def mock_redis_global():
    """Globally mock Redis client to avoid network connections and timeouts."""
    with patch("app.middleware.rate_limit.redis_client") as mock_redis:
        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_pipe.execute = AsyncMock(return_value=[None, 1, None, None])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        yield mock_redis, mock_pipe


# ========================== Helpers ===============================

async def create_regression_campaign(db_session, brand_id):
    campaign = Campaign(
        brand_id=brand_id,
        name="Regression Campaign",
        description="For regression testing",
    )
    db_session.add(campaign)
    await db_session.commit()
    await db_session.refresh(campaign)
    return campaign


async def create_regression_character(db_session, brand_id):
    char = Character(
        brand_id=brand_id,
        name="Regression Character",
        description="Regression test character",
        image_path="/uploads/regression.jpg",
    )
    db_session.add(char)
    await db_session.commit()
    await db_session.refresh(char)

    version = CharacterVersion(
        character_id=char.id,
        version_number=1,
        prompt_trigger="regress_trigger",
        mlflow_run_id="regress_run_123",
        config_overrides={},
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)
    return char, version


# ========================== Orchestrator Tests =====================

@pytest.mark.asyncio
async def test_full_orchestrator_flow(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Verify campaign creation, generation triggering, and metrics tracking."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    
    # 1. Create a campaign
    campaign = await create_regression_campaign(db_session, brand.id)
    char, version = await create_regression_character(db_session, brand.id)

    # 2. Trigger generation
    with patch("app.worker.process_campaign_generation.delay") as mock_delay:
        res = await client.post(
            f"/api/v1/campaigns/{campaign.id}/generate",
            json={
                "character_id": char.id,
                "character_version_id": version.id,
                "number_of_outputs": 1,
                "idempotency_key": "unique_flow_key_123"
            },
            headers=owner_headers
        )
        assert res.status_code == status.HTTP_201_CREATED
        data = res.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        
        # Verify Celery delay was called
        mock_delay.assert_called_once_with(data["job_id"])


@pytest.mark.asyncio
async def test_orchestrator_idempotency(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Verify that duplicate requests with the same idempotency key are rejected with 409."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    campaign = await create_regression_campaign(db_session, brand.id)
    char, version = await create_regression_character(db_session, brand.id)

    idempotency_key = "idempotency_regression_key"

    with patch("app.worker.process_campaign_generation.delay") as mock_delay:
        # First call should succeed
        res1 = await client.post(
            f"/api/v1/campaigns/{campaign.id}/generate",
            json={
                "character_id": char.id,
                "character_version_id": version.id,
                "number_of_outputs": 1,
                "idempotency_key": idempotency_key
            },
            headers=owner_headers
        )
        assert res1.status_code == status.HTTP_201_CREATED

        # Second call with the same key should fail with 409
        res2 = await client.post(
            f"/api/v1/campaigns/{campaign.id}/generate",
            json={
                "character_id": char.id,
                "character_version_id": version.id,
                "number_of_outputs": 1,
                "idempotency_key": idempotency_key
            },
            headers=owner_headers
        )
        assert res2.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_orchestrator_throttling(client: AsyncClient, db_session: AsyncSession, test_data: dict, mock_redis_global):
    """Verify that orchestrator rate limit settings are respected and return 429 when exceeded."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    campaign = await create_regression_campaign(db_session, brand.id)
    char, version = await create_regression_character(db_session, brand.id)

    mock_redis, mock_pipe = mock_redis_global
    # Set execution return to a count higher than the limit (999)
    mock_pipe.execute = AsyncMock(return_value=[None, 999, None, None])

    res = await client.post(
        f"/api/v1/campaigns/{campaign.id}/generate",
        json={
            "character_id": char.id,
            "character_version_id": version.id,
            "number_of_outputs": 1,
            "idempotency_key": "throttle_key_regression"
        },
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint(client: AsyncClient):
    """Verify that the /metrics endpoint is exposed and returns Prometheus formatting."""
    res = await client.get("/metrics")
    assert res.status_code == status.HTTP_200_OK
    assert "campaigns_total" in res.text
