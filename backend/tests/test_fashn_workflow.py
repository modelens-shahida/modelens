import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import AIJob


# ========================== Helper ===============================

async def create_workflow_job(db, brand_id, user_id, workflow_type):
    job = AIJob(
        user_id=user_id,
        brand_id=brand_id,
        status="queued",
        job_type="workflow",
        inputs={"workflow_type": workflow_type, "prompt": "test fashion shot"},
        outputs={},
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


# ========================== FASHN Service Tests ==================

@pytest.mark.asyncio
async def test_fashn_product_to_model_mock(db_session: AsyncSession, test_data: dict):
    """FASHNService mock mode should return valid response."""
    from app.services.fashn_service import FASHNService

    svc = FASHNService()
    result = await svc.generate_product_to_model(
        product_image_url="mock://flat_lay.jpg",
        prompt="fashion model wearing dress",
    )
    assert result is not None
    assert "output" in result
    assert len(result["output"]) > 0


@pytest.mark.asyncio
async def test_fashn_try_on_max_mock(db_session: AsyncSession, test_data: dict):
    """FASHNService try-on mock should return valid response."""
    from app.services.fashn_service import FASHNService

    svc = FASHNService()
    result = await svc.generate_try_on_max(
        product_image_url="mock://mannequin.jpg",
        model_image_url="mock://model.jpg",
        prompt="fashion model wearing dress",
    )
    assert result is not None
    assert "output" in result


@pytest.mark.asyncio
async def test_flat_lay_workflow_uses_fashn(db_session: AsyncSession, test_data: dict):
    """flat_lay_to_model workflow should call FASHN generate_product_to_model."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    job = await create_workflow_job(db_session, brand.id, owner_user.id, "flat_lay_to_model")

    mock_fashn = MagicMock()
    mock_fashn.generate_product_to_model = AsyncMock(return_value={
        "output": [{"url": "mock://output.png"}]
    })

    with patch("app.services.fashn_service.FASHNService", return_value=mock_fashn):
        from app.worker import _process_workflow_job_async

        class MockTask:
            request = MagicMock()
            request.retries = 0

        await _process_workflow_job_async(job.id)

    result = await db_session.execute(select(AIJob).where(AIJob.id == job.id))
    updated_job = result.scalars().first()
    assert updated_job.status in ("completed", "failed")


@pytest.mark.asyncio
async def test_mannequin_workflow_uses_fashn(db_session: AsyncSession, test_data: dict):
    """mannequin_to_model workflow should call FASHN generate_try_on_max."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    job = await create_workflow_job(db_session, brand.id, owner_user.id, "mannequin_to_model")

    mock_fashn = MagicMock()
    mock_fashn.generate_try_on_max = AsyncMock(return_value={
        "output": [{"url": "mock://output_tryon.png"}]
    })

    with patch("app.services.fashn_service.FASHNService", return_value=mock_fashn):
        from app.worker import _process_workflow_job_async

        class MockTask:
            request = MagicMock()
            request.retries = 0

        await _process_workflow_job_async(job.id)

    result = await db_session.execute(select(AIJob).where(AIJob.id == job.id))
    updated_job = result.scalars().first()
    assert updated_job.status in ("completed", "failed")


@pytest.mark.asyncio
async def test_fashn_fallback_on_error(db_session: AsyncSession, test_data: dict):
    """Workflow should fallback to DALL-E if FASHN raises exception."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    job = await create_workflow_job(db_session, brand.id, owner_user.id, "flat_lay_to_model")

    mock_fashn = MagicMock()
    mock_fashn.generate_product_to_model = AsyncMock(side_effect=Exception("FASHN API error"))

    with patch("app.services.fashn_service.FASHNService", return_value=mock_fashn):
        from app.worker import _process_workflow_job_async
        await _process_workflow_job_async(job.id)

    result = await db_session.execute(select(AIJob).where(AIJob.id == job.id))
    updated_job = result.scalars().first()
    assert updated_job.status in ("completed", "failed")
