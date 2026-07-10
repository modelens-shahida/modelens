import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import Campaign, Character, CharacterVersion, AIJob


# ========================== Helper ===============================

async def create_test_campaign(db_session, brand_id, owner_id):
    campaign = Campaign(
        brand_id=brand_id,
        name="Test Generation Campaign",
        description="For testing",
    )
    db_session.add(campaign)
    await db_session.commit()
    await db_session.refresh(campaign)
    return campaign


async def create_test_character_with_version(db_session, brand_id):
    char = Character(
        brand_id=brand_id,
        name="Test Character",
        description="Test",
        image_path="/uploads/test.jpg",
    )
    db_session.add(char)
    await db_session.commit()
    await db_session.refresh(char)

    version = CharacterVersion(
        character_id=char.id,
        version_number=1,
        prompt_trigger="test_char_v1",
        mlflow_run_id="test_mlflow_run_123",
        config_overrides={},
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)
    return char, version


# ========================== Auth Tests ===========================

@pytest.mark.asyncio
async def test_generate_auth_required(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    res = await client.post(f"/api/v1/campaigns/1/generate", json={
        "character_id": 1, "character_version_id": 1
    })
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_generate_viewer_forbidden(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")
    campaign = await create_test_campaign(db_session, brand.id, test_data["users"]["owner"].id)

    res = await client.post(f"/api/v1/campaigns/{campaign.id}/generate",
        json={"character_id": 1, "character_version_id": 1},
        headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


# ========================== Generation Tests =====================

@pytest.mark.asyncio
async def test_generate_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Authorized generation should create parent and child jobs."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    campaign = await create_test_campaign(db_session, brand.id, test_data["users"]["owner"].id)
    char, version = await create_test_character_with_version(db_session, brand.id)

    with patch("app.routers.campaign_generation.process_campaign_generation") as mock_task:
        mock_task.delay = MagicMock()
        res = await client.post(f"/api/v1/campaigns/{campaign.id}/generate",
            json={
                "character_id": char.id,
                "character_version_id": version.id,
                "number_of_outputs": 2,
            },
            headers=owner_headers)

    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert "job_id" in data
    assert len(data["child_job_ids"]) == 2
    assert data["status"] == "queued"
    assert data["mlflow_run_id"] == "test_mlflow_run_123"


@pytest.mark.asyncio
async def test_generate_cross_tenant_asset_rejected(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Assets from another brand should be rejected."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    campaign = await create_test_campaign(db_session, brand.id, test_data["users"]["owner"].id)
    char, version = await create_test_character_with_version(db_session, brand.id)

    res = await client.post(f"/api/v1/campaigns/{campaign.id}/generate",
        json={
            "character_id": char.id,
            "character_version_id": version.id,
            "asset_ids": [99999],  # Non-existent asset
        },
        headers=owner_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_generate_invalid_character_version(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Invalid character version should return 404."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    campaign = await create_test_campaign(db_session, brand.id, test_data["users"]["owner"].id)
    char, version = await create_test_character_with_version(db_session, brand.id)

    res = await client.post(f"/api/v1/campaigns/{campaign.id}/generate",
        json={
            "character_id": char.id,
            "character_version_id": 99999,
        },
        headers=owner_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_generate_idempotency_protection(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Duplicate idempotency key should return 409."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    campaign = await create_test_campaign(db_session, brand.id, test_data["users"]["owner"].id)
    char, version = await create_test_character_with_version(db_session, brand.id)

    with patch("app.routers.campaign_generation.process_campaign_generation") as mock_task:
        mock_task.delay = MagicMock()
        await client.post(f"/api/v1/campaigns/{campaign.id}/generate",
            json={"character_id": char.id, "character_version_id": version.id, "idempotency_key": "test_key_123"},
            headers=owner_headers)

        res = await client.post(f"/api/v1/campaigns/{campaign.id}/generate",
            json={"character_id": char.id, "character_version_id": version.id, "idempotency_key": "test_key_123"},
            headers=owner_headers)

    assert res.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_cancel_generation(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Owner should be able to cancel a queued generation job."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    owner_user = test_data["users"]["owner"]

    job = AIJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="queued",
        job_type="campaign_generation",
        inputs={"campaign_id": 1},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    res = await client.post(f"/api/v1/generations/{job.id}/cancel",
        json={"reason": "Test cancellation"},
        headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_completed_job_returns_409(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Cannot cancel a completed job."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    owner_user = test_data["users"]["owner"]

    job = AIJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="completed",
        job_type="campaign_generation",
        inputs={"campaign_id": 1},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    res = await client.post(f"/api/v1/generations/{job.id}/cancel",
        json={},
        headers=owner_headers)
    assert res.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_get_generation_status(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Should return generation job status."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    owner_user = test_data["users"]["owner"]

    job = AIJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="queued",
        job_type="campaign_generation",
        inputs={"campaign_id": 1, "mlflow_run_id": "test_run"},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    res = await client.get(f"/api/v1/generations/{job.id}", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["job_id"] == job.id
    assert data["status"] == "queued"
    assert "progress" in data


@pytest.mark.asyncio
async def test_comfyui_mock_mode():
    """ComfyUI mock mode should return mock outputs."""
    from app.services.comfyui_service import ComfyUIService
    svc = ComfyUIService(mock_mode=True)
    prompt_id = await svc.submit_workflow({"test": True})
    assert "mock_prompt" in prompt_id
    result = await svc.poll_until_complete(prompt_id)
    assert result["status"] == "completed"
    assert len(result["outputs"]) > 0
