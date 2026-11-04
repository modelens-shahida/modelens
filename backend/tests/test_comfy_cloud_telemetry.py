import pytest
from pydantic import SecretStr
from app.config import Settings
from app.services.comfyui_service import ComfyUIService


def test_comfy_cloud_api_key_secret_str_masking():
    """COMFY_CLOUD_API_KEY must use SecretStr and be masked in repr."""
    key = "super_secret_comfy_key_123"
    s = Settings(COMFY_CLOUD_API_KEY=SecretStr(key))
    assert s.COMFY_CLOUD_API_KEY is not None
    assert s.COMFY_CLOUD_API_KEY.get_secret_value() == key
    assert key not in str(s.COMFY_CLOUD_API_KEY)
    assert key not in repr(s.COMFY_CLOUD_API_KEY)
    assert key not in repr(s)


def test_comfyui_service_headers_with_and_without_key():
    """ComfyUIService attaches Authorization only when key is given."""
    svc_no_auth = ComfyUIService(mock_mode=True)
    assert svc_no_auth._headers() == {}

    svc_auth = ComfyUIService(mock_mode=True, api_key="test_cloud_token")
    expected = {"Authorization": "Bearer test_cloud_token"}
    assert svc_auth._headers() == expected


@pytest.mark.asyncio
async def test_generation_pipeline_telemetry_fields():
    """GenerationJobManager run_with_timeout returns telemetry fields."""
    from unittest.mock import AsyncMock, MagicMock
    from app.services.generation_pipeline import GenerationJobManager

    mock_db = MagicMock()
    manager = GenerationJobManager(mock_db)

    # Mock the internal service
    manager.service.submit_workflow = AsyncMock(
        return_value="mock_exec_abc123"
    )
    manager.service.listen_websocket_completion = AsyncMock(
        return_value=None
    )
    manager.service.poll_until_complete = AsyncMock(
        return_value={"outputs": [{"filename": "out.png"}]}
    )
    manager.service.download_output = AsyncMock(
        return_value=b"fake_image_bytes"
    )
    manager.update_job_status = AsyncMock()

    mock_job = MagicMock()
    mock_job.id = 42

    result = await manager.run_with_timeout(
        mock_job, {"scene_description": "editorial"}
    )
    assert result["prompt_id"] == "mock_exec_abc123"
    assert result["execution_id"] == "mock_exec_abc123"
    assert "runtime_seconds" in result
    assert isinstance(result["runtime_seconds"], float)
    assert result["image_bytes"] == b"fake_image_bytes"
