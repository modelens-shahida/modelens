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


@pytest.mark.asyncio
async def test_run_production_writes_telemetry_to_ai_jobs_outputs():
    """run_production writes telemetry and credits to ai_jobs.outputs."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.services.production_dispatch import run_production
    from app.models.db import AIJob

    mock_db = AsyncMock()

    mock_job = AIJob(
        id=101,
        job_type="production",
        status="queued",
        inputs={},
        outputs={},
    )
    mock_production = MagicMock()
    mock_production.production_id = "prd_test_123"
    mock_production.runtime_profile = {
        "params": {"count": 1, "aspect_ratio": "4:5", "resolution": "2K"},
        "layers": {
            "pose": {},
            "scene": {
                "location": {"display_name": "Studio"},
                "lighting": {"preset_id": "LGT_01"},
            },
        },
    }
    mock_production.estimated_credits = 8

    mock_db.get = AsyncMock(return_value=mock_job)

    with patch(
        "app.services.production_dispatch._first",
        AsyncMock(return_value=mock_production),
    ), patch(
        "app.services.production_dispatch.credits_sync_service.finalize_credits",
        AsyncMock(),
    ) as mock_finalize, patch(
        "app.services.generation_pipeline.GenerationJobManager"
    ) as mock_mgr_cls:

        mock_mgr = mock_mgr_cls.return_value
        mock_asset = MagicMock()
        mock_asset.id = 555
        mock_mgr.register_output_asset = AsyncMock(return_value=mock_asset)

        async def fake_generator(job, profile):
            return {
                "images": [b"test_image_bytes_12345"],
                "execution_id": "exec_comfy_999",
                "runtime_seconds": 1.25,
            }

        completed_job = await run_production(
            mock_db, 101, generate=fake_generator
        )

        assert completed_job.status == "completed"
        outputs = completed_job.outputs
        assert "images" in outputs and len(outputs["images"]) == 1
        assert outputs["images"][0]["asset_id"] == 555
        assert outputs["execution_ids"] == ["exec_comfy_999"]
        assert "execution_id" not in outputs
        assert outputs["runtime_seconds"] == 1.25
        assert outputs["output_size_bytes"] == len(b"test_image_bytes_12345")
        assert outputs["estimated_credits_used"] == 8
        assert "credits_used" not in outputs
        mock_finalize.assert_awaited_once_with("prd_test_123", mock_db)
