"""Move Studio API: /api/v1/video presets and jobs (routers/video_projects.py)."""
from unittest.mock import MagicMock, patch

import pytest

PRESETS = "/api/v1/video/presets"
JOBS = "/api/v1/video/jobs"
PRESET_IDS = {"MOT-WALK", "MOT-TURN", "MOT-FAB", "MOT-ORBIT"}


@pytest.fixture
def video_task():
    task = MagicMock()
    task.delay.return_value = MagicMock(id="celery-task-1")
    with patch("app.worker.run_video_generation_job", task):
        yield task


def _job(brand, **overrides):
    body = {"preset_id": "MOT-WALK", "brand_id": brand, "duration_seconds": 4, "aspect_ratio": "9:16"}
    body.update(overrides)
    return body


# ========================== Presets ===============================

@pytest.mark.asyncio
async def test_list_presets(client, test_data):
    resp = await client.get(PRESETS, headers=test_data["get_headers"]("viewer"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    assert {p["preset_id"] for p in body["presets"]} == PRESET_IDS
    for preset in body["presets"]:
        assert preset["display_name"] and preset["duration_options"] and preset["aspect_ratios"]


@pytest.mark.asyncio
async def test_get_preset(client, test_data):
    resp = await client.get(f"{PRESETS}/MOT-TURN", headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 200
    body = resp.json()
    assert (body["preset_id"], body["display_name"]) == ("MOT-TURN", "360° Spin")
    assert body["duration_options"] == [4, 6, 8]


@pytest.mark.asyncio
async def test_unknown_preset_returns_404(client, test_data):
    resp = await client.get(f"{PRESETS}/MOT-NOPE", headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 404
    assert "MOT-NOPE" in resp.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,url", [("get", PRESETS), ("get", f"{PRESETS}/MOT-WALK"), ("post", JOBS)])
async def test_video_endpoints_require_login(client, test_data, method, url):
    kwargs = {"json": _job(test_data["brand"].id)} if method == "post" else {}
    resp = await getattr(client, method)(url, **kwargs)
    assert resp.status_code == 401


# ========================== Jobs ==================================

@pytest.mark.asyncio
async def test_create_job_queues_the_worker_task(client, test_data, video_task):
    editor, brand = test_data["users"]["editor"], test_data["brand"]
    resp = await client.post(JOBS, json=_job(brand.id, source_asset_id=7, character_id="EE-F-002"),
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 202, resp.text
    assert resp.json() == {
        "task_id": "celery-task-1", "status": "queued", "preset_id": "MOT-WALK", "preset_name": "Catwalk Walk",
        "duration_seconds": 4, "aspect_ratio": "9:16", "total_frames": 96, "workflow_id": "WF-VIDEO-WALK-001",
    }
    video_task.delay.assert_called_once()
    kwargs = video_task.delay.call_args.kwargs
    assert (kwargs["brand_id"], kwargs["user_id"], kwargs["preset_id"]) == (brand.id, editor.id, "MOT-WALK")
    assert (kwargs["source_asset_id"], kwargs["character_id"]) == (7, "EE-F-002")
    params = kwargs["workflow_params"]
    assert (params["width"], params["height"], params["fps"], params["total_frames"]) == (1080, 1920, 24, 96)
    assert params["motion_type"] == "walk_forward"


@pytest.mark.asyncio
async def test_create_job_when_queue_unavailable_still_answers(client, test_data, video_task):
    video_task.delay.side_effect = RuntimeError("broker down")
    resp = await client.post(JOBS, json=_job(test_data["brand"].id), headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 202
    assert resp.json()["task_id"] == "mock_video_MOT-WALK"


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,message", [
    ({"preset_id": "MOT-NOPE"}, "Invalid preset: MOT-NOPE"),
    ({"preset_id": "MOT-TURN", "duration_seconds": 2}, "Invalid duration for MOT-TURN"),
    ({"preset_id": "MOT-FAB", "aspect_ratio": "1:1"}, "Invalid aspect ratio for MOT-FAB"),
])
async def test_create_job_rejects_options_the_preset_does_not_offer(client, test_data, video_task, overrides,
                                                                    message):
    resp = await client.post(JOBS, json=_job(test_data["brand"].id, **overrides),
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 400
    assert message in resp.json()["detail"]
    video_task.delay.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides", [{"duration_seconds": 1}, {"duration_seconds": 9}, {"brand_id": None},
                                       {"preset_id": None}])
async def test_create_job_validates_the_body(client, test_data, video_task, overrides):
    resp = await client.post(JOBS, json=_job(test_data["brand"].id, **overrides),
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 422
    video_task.delay.assert_not_called()
