import json

import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status
from httpx import AsyncClient, Response


# ========================== Generations proxy =====================
# /api/v1/generations/* is forwarded to the external templates service; the upstream call is mocked.

@pytest.fixture
def templates_upstream():
    """Patch the proxy's HTTP client; set .request.return_value to the templates service reply."""
    upstream = AsyncMock()
    upstream.__aenter__.return_value = upstream
    with patch("app.routers.templates_proxy.AsyncClient", return_value=upstream):
        yield upstream


def _upstream_json(status_code, body):
    return Response(status_code=status_code, json=body)


@pytest.mark.asyncio
async def test_cancel_generation(client: AsyncClient, test_data: dict, templates_upstream):
    """Cancel is forwarded to the templates service with the caller's identity and body."""
    owner = test_data["users"]["owner"]
    templates_upstream.request.return_value = _upstream_json(200, {"id": "gen_1", "status": "cancelled"})

    res = await client.post("/api/v1/generations/gen_1/cancel",
        json={"reason": "Test cancellation"},
        headers=test_data["get_headers"]("owner"))

    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "cancelled"
    templates_upstream.request.assert_called_once()
    sent = templates_upstream.request.call_args.kwargs
    assert sent["method"] == "POST"
    assert sent["url"].endswith("/v1/generations/gen_1/cancel")
    assert json.loads(sent["content"]) == {"reason": "Test cancellation"}
    assert sent["headers"]["X-User-Id"] == str(owner.id)


@pytest.mark.asyncio
async def test_cancel_completed_job_returns_409(client: AsyncClient, test_data: dict, templates_upstream):
    """The templates service's 409 for an already-finished job is passed through unchanged."""
    templates_upstream.request.return_value = _upstream_json(409, {"message": "Generation already completed"})

    res = await client.post("/api/v1/generations/gen_done/cancel",
        json={},
        headers=test_data["get_headers"]("owner"))

    assert res.status_code == status.HTTP_409_CONFLICT
    assert res.json() == {"message": "Generation already completed"}


@pytest.mark.asyncio
async def test_get_generation_status(client: AsyncClient, test_data: dict, templates_upstream):
    """Status reads are forwarded as GET and the upstream body is returned as-is."""
    body = {"id": "gen_1", "status": "queued", "progress": 0}
    templates_upstream.request.return_value = _upstream_json(200, body)

    res = await client.get("/api/v1/generations/gen_1", headers=test_data["get_headers"]("owner"))

    assert res.status_code == status.HTTP_200_OK
    assert res.json() == body
    sent = templates_upstream.request.call_args.kwargs
    assert sent["method"] == "GET"
    assert sent["url"].endswith("/v1/generations/gen_1")


@pytest.mark.slow  # mock-mode generation still waits on the app's simulated progress delays
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
