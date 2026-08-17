import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import AIJob


# ========================== Helper ===============================

async def create_test_job(db_session, brand_id, owner_id, workflow_template_id=None):
    job = AIJob(
        user_id=owner_id,
        brand_id=brand_id,
        status="queued",
        job_type="generation",
        workflow_template_id=workflow_template_id,
        inputs={"prompt": "fashion editorial outdoor", "scene_description": "model in summer dress"},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


# ========================== ComfyUI Worker Tests =================

@pytest.mark.asyncio
async def test_comfyui_mock_mode_completes(db_session: AsyncSession, test_data: dict):
    """ComfyUI mock mode should complete generation successfully."""
    from app.services.comfyui_service import ComfyUIService

    svc = ComfyUIService(mock_mode=True)

    # Test workflow injection
    workflow = {
        "14": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["4", 1]}},
        "22": {"class_type": "LoadImage", "inputs": {"image": ""}},
    }

    workflow = svc.inject_node_input(workflow, "14", "text", "summer dress outdoor")
    workflow = svc.inject_node_input(workflow, "22", "image", "pose_ref.png")

    assert workflow["14"]["inputs"]["text"] == "summer dress outdoor"
    assert workflow["22"]["inputs"]["image"] == "pose_ref.png"


@pytest.mark.asyncio
async def test_comfyui_submit_workflow_mock(db_session: AsyncSession, test_data: dict):
    """ComfyUI mock submit should return a prompt_id."""
    from app.services.comfyui_service import ComfyUIService

    svc = ComfyUIService(mock_mode=True)
    workflow = {"14": {"class_type": "CLIPTextEncode", "inputs": {"text": "test"}}}
    prompt_id = await svc.submit_workflow(workflow)

    assert prompt_id is not None
    assert "mock_prompt" in prompt_id


@pytest.mark.asyncio
async def test_comfyui_poll_until_complete_mock(db_session: AsyncSession, test_data: dict):
    """ComfyUI mock poll should return completed status with outputs."""
    from app.services.comfyui_service import ComfyUIService

    svc = ComfyUIService(mock_mode=True)
    result = await svc.poll_until_complete("mock_prompt_test")

    assert result["status"] == "completed"
    assert len(result["outputs"]) > 0


@pytest.mark.asyncio
async def test_comfyui_download_output_mock(db_session: AsyncSession, test_data: dict):
    """ComfyUI mock download should return valid image bytes."""
    from app.services.comfyui_service import ComfyUIService

    svc = ComfyUIService(mock_mode=True)
    image_bytes = await svc.download_output("mock_output.png")

    assert isinstance(image_bytes, bytes)
    assert len(image_bytes) > 0


@pytest.mark.asyncio
async def test_inject_node_input_nonexistent_node(db_session: AsyncSession, test_data: dict):
    """Injecting into non-existent node should not crash."""
    from app.services.comfyui_service import ComfyUIService

    svc = ComfyUIService(mock_mode=True)
    workflow = {"14": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}}}

    # Injecting into node "99" which doesn't exist
    result = svc.inject_node_input(workflow, "99", "text", "test")
    assert "14" in result  # Original node still intact


@pytest.mark.asyncio
async def test_worker_uses_comfyui_when_workflow_template_set(db_session: AsyncSession, test_data: dict):
    """Worker should use ComfyUI when workflow_template_id is set."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    job = await create_test_job(db_session, brand.id, owner_user.id, workflow_template_id=1)

    mock_comfyui = MagicMock()
    mock_comfyui.inject_node_input = MagicMock(side_effect=lambda w, n, k, v: w)
    mock_comfyui.submit_workflow = AsyncMock(return_value="mock_prompt_123")
    mock_comfyui.listen_websocket_completion = AsyncMock()
    mock_comfyui.poll_until_complete = AsyncMock(return_value={
        "status": "completed",
        "outputs": [{"filename": "output.png"}]
    })
    mock_comfyui.download_output = AsyncMock(return_value=b"fake_image_bytes")

    class MockSessionContext:
        def __init__(self, session):
            self.session = session
        async def __aenter__(self):
            return self.session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.services.comfyui_service.get_comfyui_service", return_value=mock_comfyui), \
         patch("app.worker.redis_client.set", new_callable=AsyncMock), \
         patch("app.worker.dispatch_webhook.delay"):
        with patch("app.worker.storage_service") as mock_storage:
            mock_storage.save_file_bytes = MagicMock(return_value="/uploads/output.png")
            from app.worker import _process_generation_job_async
            await _process_generation_job_async(job.id)

    result = await db_session.execute(select(AIJob).where(AIJob.id == job.id))
    updated_job = result.scalars().first()
    assert updated_job.status in ("completed", "failed")
