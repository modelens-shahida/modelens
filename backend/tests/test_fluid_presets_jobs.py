"""Pins the current behaviour of /api/v1/fluid/presets and /api/v1/fluid/jobs
(LightingDomeSelector.jsx via lib/fluidApi.js)."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.services.fluid_service import APERTURES, FOCAL_LENGTHS, LIGHTING_PRESETS

PRESET_IDS = ["STUDIO_SOFT_DIFFUSE", "EDITORIAL_HARD_HIGH_KEY", "NATURAL_GOLDEN_HOUR",
              "DRAMATIC_CHIAROSCURO", "CYBERPUNK_NEON"]


def job_payload(**overrides):
    payload = {
        "preset_id": "NATURAL_GOLDEN_HOUR",
        "brand_id": 1,
        "source_asset_id": 7,
        "character_id": "EE-F-002",
        "focal_length_mm": 85,
        "aperture": 1.8,
        "prompt": "Sunset terrace",
        "generation_mode": "studio_quality",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_list_presets(client: AsyncClient, test_data: dict):
    res = await client.get("/api/v1/fluid/presets", headers=test_data["get_headers"]("viewer"))
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert [p["preset_id"] for p in data["presets"]] == PRESET_IDS
    assert data["total"] == 5
    assert data["focal_lengths"] == [35, 50, 85, 105]
    assert data["apertures"] == [1.4, 1.8, 2.8, 4.0, 5.6, 8.0]
    for preset in data["presets"]:
        assert {"preset_id", "name", "display_name", "family", "taxonomy_id", "description",
                "workflow_params", "recommended_for"} <= set(preset)


@pytest.mark.asyncio
async def test_get_preset(client: AsyncClient, test_data: dict):
    headers = test_data["get_headers"]("viewer")
    res = await client.get("/api/v1/fluid/presets/DRAMATIC_CHIAROSCURO", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json() == LIGHTING_PRESETS["DRAMATIC_CHIAROSCURO"]

    res = await client.get("/api/v1/fluid/presets/NOPE", headers=headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json()["detail"] == "Preset NOPE not found."


@pytest.mark.asyncio
async def test_presets_and_jobs_require_auth(client: AsyncClient):
    assert (await client.get("/api/v1/fluid/presets")).status_code == status.HTTP_401_UNAUTHORIZED
    assert (await client.get("/api/v1/fluid/presets/STUDIO_SOFT_DIFFUSE")).status_code == status.HTTP_401_UNAUTHORIZED
    assert (await client.post("/api/v1/fluid/jobs", json=job_payload())).status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_create_job_dispatches_with_workflow_params(client: AsyncClient, test_data: dict):
    editor = test_data["users"]["editor"]
    credits_before = editor.credits
    with patch("app.worker.run_fluid_generation_job.delay", return_value=SimpleNamespace(id="task-123")) as delay:
        res = await client.post("/api/v1/fluid/jobs", json=job_payload(), headers=test_data["get_headers"]("editor"))

    assert res.status_code == status.HTTP_202_ACCEPTED
    assert res.json() == {
        "task_id": "task-123",
        "status": "queued",
        "preset_id": "NATURAL_GOLDEN_HOUR",
        "preset_name": "Golden Hour",
        "focal_length_mm": 85,
        "aperture": "f/1.8",
        "taxonomy_id": "LGT-GH-001",
        "workflow_id": "WF-FLUID-001",
    }
    kwargs = delay.call_args.kwargs
    assert kwargs["brand_id"] == 1
    assert kwargs["user_id"] == editor.id
    assert kwargs["preset_id"] == "NATURAL_GOLDEN_HOUR"
    assert kwargs["source_asset_id"] == 7
    assert kwargs["character_id"] == "EE-F-002"
    assert kwargs["generation_mode"] == "studio_quality"
    assert kwargs["prompt"] == "Sunset terrace"
    params = kwargs["workflow_params"]
    assert params["workflow_id"] == "WF-FLUID-001"
    assert params["focal_length_mm"] == 85
    assert params["aperture"] == "f/1.8"
    assert params["depth_of_field"] == "shallow"
    assert params["color_temperature"] == 3800
    # Current behaviour: no credit charge on this endpoint.
    assert editor.credits == credits_before


@pytest.mark.asyncio
async def test_create_job_falls_back_to_mock_task_id_when_dispatch_fails(client: AsyncClient, test_data: dict):
    with patch("app.worker.run_fluid_generation_job.delay", side_effect=RuntimeError("broker down")):
        res = await client.post("/api/v1/fluid/jobs", json=job_payload(aperture=5.6),
                                headers=test_data["get_headers"]("editor"))
    assert res.status_code == status.HTTP_202_ACCEPTED
    assert res.json()["task_id"] == "mock_fluid_NATURAL_GOLDEN_HOUR"
    assert res.json()["aperture"] == "f/5.6"


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides, detail", [
    ({"preset_id": "NOPE"}, "Invalid preset: NOPE"),
    ({"focal_length_mm": 24}, f"Invalid focal length. Options: {FOCAL_LENGTHS}"),
    ({"aperture": 2.0}, f"Invalid aperture. Options: {APERTURES}"),
])
async def test_create_job_rejects_invalid_options(client: AsyncClient, test_data: dict, overrides, detail):
    with patch("app.worker.run_fluid_generation_job.delay") as delay:
        res = await client.post("/api/v1/fluid/jobs", json=job_payload(**overrides),
                                headers=test_data["get_headers"]("editor"))
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json()["detail"] == detail
    delay.assert_not_called()
