import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import AIJob, Asset
from app.services.generation_pipeline import (
    GenerationInputBuilder,
    GenerationJobManager,
    run_with_retries,
    PIPELINE_STAGES,
    JOB_TIMEOUT_SECONDS,
)
from app.services.comfyui_service import ComfyUIService


# ========================== Input Builder Tests ==================

def test_input_builder_scene_description():
    """Scene description should be injected into Node 14."""
    svc = ComfyUIService(mock_mode=True)
    builder = GenerationInputBuilder(svc)
    workflow = {"14": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}}}
    result = builder.build(workflow, scene_description="summer dress editorial")
    assert result["14"]["inputs"]["text"] == "summer dress editorial"


def test_input_builder_pose_filename():
    """Pose filename should be injected into Node 22."""
    svc = ComfyUIService(mock_mode=True)
    builder = GenerationInputBuilder(svc)
    workflow = {
        "14": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
        "22": {"class_type": "LoadImage", "inputs": {"image": ""}},
    }
    result = builder.build(workflow, pose_filename="catalog_pose_01.png")
    assert result["22"]["inputs"]["image"] == "catalog_pose_01.png"


def test_input_builder_extra_inputs():
    """Extra inputs should be injected into specified nodes."""
    svc = ComfyUIService(mock_mode=True)
    builder = GenerationInputBuilder(svc)
    workflow = {
        "14": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
        "99": {"class_type": "CustomNode", "inputs": {"strength": 0.5}},
    }
    result = builder.build(workflow, extra_inputs={"99": {"strength": 0.9}})
    assert result["99"]["inputs"]["strength"] == 0.9


def test_input_builder_preserves_unchanged_nodes():
    """Nodes not targeted should remain unchanged."""
    svc = ComfyUIService(mock_mode=True)
    builder = GenerationInputBuilder(svc)
    workflow = {
        "14": {"class_type": "CLIPTextEncode", "inputs": {"text": "original"}},
        "5": {"class_type": "KSampler", "inputs": {"steps": 30}},
    }
    result = builder.build(workflow)
    assert result["5"]["inputs"]["steps"] == 30


# ========================== Pipeline Stage Tests =================

def test_pipeline_stages_complete_is_100():
    assert PIPELINE_STAGES["completed"] == 100


def test_pipeline_stages_failed_is_0():
    assert PIPELINE_STAGES["failed"] == 0


def test_pipeline_stages_generating_is_positive():
    assert PIPELINE_STAGES["generating"] > 0


# ========================== Job Manager Tests ====================

@pytest.mark.asyncio
async def test_cancel_active_job(db_session: AsyncSession, test_data: dict):
    """Cancelling an active job should set status to cancelled."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    job = AIJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="generating",
        job_type="generation",
        inputs={"scene_description": "test"},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    manager = GenerationJobManager(db_session)
    result = await manager.cancel_job(job)
    assert result is True
    assert job.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_completed_job_returns_false(db_session: AsyncSession, test_data: dict):
    """Cancelling a completed job should return False."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    job = AIJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="completed",
        job_type="generation",
        inputs={},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()

    manager = GenerationJobManager(db_session)
    result = await manager.cancel_job(job)
    assert result is False


@pytest.mark.asyncio
async def test_generation_mock_mode_success(db_session: AsyncSession, test_data: dict):
    """Mock mode generation should complete successfully."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    job = AIJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="queued",
        job_type="generation",
        inputs={"scene_description": "editorial summer shoot"},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    manager = GenerationJobManager(db_session)

    result = await manager.run_with_timeout(
        job,
        {"scene_description": "editorial summer shoot"},
        timeout=30.0,
    )
    assert result is not None
    assert "image_bytes" in result
    assert isinstance(result["image_bytes"], bytes)


@pytest.mark.asyncio
async def test_generation_timeout_raises(db_session: AsyncSession, test_data: dict):
    """Generation that exceeds timeout should raise TimeoutError."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    job = AIJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="queued",
        job_type="generation",
        inputs={},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()

    manager = GenerationJobManager(db_session)

    async def slow_generation(*args, **kwargs):
        await asyncio.sleep(999)
        return {}

    with patch.object(manager, "_run_generation", slow_generation):
        with pytest.raises(asyncio.TimeoutError):
            await manager.run_with_timeout(job, {}, timeout=0.1)


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt(db_session: AsyncSession, test_data: dict):
    """Job should succeed on second attempt after first failure."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    job = AIJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="queued",
        job_type="generation",
        inputs={},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()

    manager = GenerationJobManager(db_session)
    call_count = 0

    async def flaky_generation(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Transient error")
        return {"image_bytes": b"fake_image", "outputs": [], "prompt_id": "mock"}

    with patch.object(manager, "run_with_timeout", flaky_generation):
        result = await run_with_retries(manager, job, {}, max_retries=2)

    assert call_count == 2
    assert result["image_bytes"] == b"fake_image"


@pytest.mark.asyncio
async def test_register_output_asset(db_session: AsyncSession, test_data: dict):
    """Output image should be registered as Asset linked to job."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    job = AIJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="completed",
        job_type="generation",
        inputs={},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    mock_storage = MagicMock()
    mock_storage.save_file_bytes = MagicMock(return_value="/uploads/output.png")

    manager = GenerationJobManager(db_session)
    asset = await manager.register_output_asset(
        db_session, job, b"fake_image_bytes", mock_storage
    )

    assert asset is not None
    assert asset.brand_id == brand.id
    assert job.asset_id == asset.id
    assert asset.asset_type == "generated"
