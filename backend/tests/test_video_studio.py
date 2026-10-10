"""Move Studio API: /api/v1/video presets and jobs (routers/video_projects.py)."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import delete, func, select

from app.models.db import AIJob, Asset, Brand, BrandMember, CreditTransaction

PRESETS = "/api/v1/video/presets"
JOBS = "/api/v1/video/jobs"
PRESET_IDS = {"MOT-WALK", "MOT-TURN", "MOT-FAB", "MOT-ORBIT"}


@pytest.fixture
def video_task():
    task = MagicMock()
    task.delay.return_value = MagicMock(id="celery-task-1")
    with patch("app.worker.run_video_generation_job", task):
        yield task


async def _asset(db_session, brand_id, **fields):
    asset = Asset(brand_id=brand_id, filename="look.png", storage_path="/uploads/look.png", asset_type="image",
                  **fields)
    db_session.add(asset)
    await db_session.commit()
    return asset


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
async def test_create_job_queues_the_worker_task(client, db_session, test_data, video_task):
    editor, brand = test_data["users"]["editor"], test_data["brand"]
    source = await _asset(db_session, brand.id)
    resp = await client.post(JOBS, json=_job(brand.id, source_asset_id=source.id, character_id="EE-F-002"),
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 202, resp.text
    assert resp.json() == {
        "task_id": "celery-task-1", "status": "queued", "preset_id": "MOT-WALK", "preset_name": "Catwalk Walk",
        "duration_seconds": 4, "aspect_ratio": "9:16", "total_frames": 96, "workflow_id": "WF-VIDEO-WALK-001",
    }
    video_task.delay.assert_called_once()
    kwargs = video_task.delay.call_args.kwargs
    assert (kwargs["brand_id"], kwargs["user_id"], kwargs["preset_id"]) == (brand.id, editor.id, "MOT-WALK")
    assert (kwargs["source_asset_id"], kwargs["character_id"]) == (source.id, "EE-F-002")
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


# ========================== Brand access ==========================

async def _side_effects(db_session):
    """Rows a video job could create or charge."""
    counts = [(await db_session.execute(select(func.count()).select_from(model))).scalar()
              for model in (AIJob, Asset, CreditTransaction)]
    credits = (await db_session.execute(select(Brand.id, Brand.credits).order_by(Brand.id))).all()
    return counts, credits


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "editor"])
async def test_owner_and_editors_can_create_jobs(client, test_data, video_task, role):
    resp = await client.post(JOBS, json=_job(test_data["brand"].id), headers=test_data["get_headers"](role))
    assert resp.status_code == 202, resp.text
    assert video_task.delay.call_args.kwargs["brand_id"] == test_data["brand"].id
    assert video_task.delay.call_args.kwargs["user_id"] == test_data["users"][role].id


@pytest.mark.asyncio
async def test_non_member_gets_403_and_nothing_is_queued(client, db_session, test_data, video_task):
    before = await _side_effects(db_session)
    # nonmember owns other_brand, but not test_data["brand"].
    resp = await client.post(JOBS, json=_job(test_data["brand"].id), headers=test_data["get_headers"]("nonmember"))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "You are not a member of this brand"
    video_task.delay.assert_not_called()
    assert await _side_effects(db_session) == before


@pytest.mark.asyncio
async def test_member_of_another_brand_gets_403(client, test_data, video_task):
    resp = await client.post(JOBS, json=_job(test_data["other_brand"].id), headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 403
    video_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_removed_member_gets_403(client, db_session, test_data, video_task):
    editor, brand = test_data["users"]["editor"], test_data["brand"]
    headers = test_data["get_headers"]("editor")
    assert (await client.post(JOBS, json=_job(brand.id), headers=headers)).status_code == 202

    await db_session.execute(delete(BrandMember).where(BrandMember.brand_id == brand.id,
                                                       BrandMember.user_id == editor.id))
    await db_session.commit()
    video_task.delay.reset_mock()
    before = await _side_effects(db_session)

    resp = await client.post(JOBS, json=_job(brand.id), headers=headers)
    assert resp.status_code == 403
    video_task.delay.assert_not_called()
    assert await _side_effects(db_session) == before


@pytest.mark.asyncio
async def test_missing_brand_returns_404(client, db_session, test_data, video_task):
    before = await _side_effects(db_session)
    resp = await client.post(JOBS, json=_job(999_999), headers=test_data["get_headers"]("owner"))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Brand not found"
    video_task.delay.assert_not_called()
    assert await _side_effects(db_session) == before


@pytest.mark.asyncio
async def test_brand_is_checked_before_the_preset(client, test_data, video_task):
    """An outsider learns nothing about presets or options from the error."""
    resp = await client.post(JOBS, json=_job(test_data["brand"].id, preset_id="MOT-NOPE"),
                             headers=test_data["get_headers"]("nonmember"))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_gets_403_and_nothing_is_queued(client, db_session, test_data, video_task):
    before = await _side_effects(db_session)
    resp = await client.post(JOBS, json=_job(test_data["brand"].id), headers=test_data["get_headers"]("viewer"))
    assert resp.status_code == 403
    assert "Requires at least 'editor' role" in resp.json()["detail"]
    video_task.delay.assert_not_called()
    assert await _side_effects(db_session) == before


# ========================== Source asset ==========================

@pytest.mark.asyncio
async def test_source_asset_of_another_brand_is_404(client, db_session, test_data, video_task):
    foreign = await _asset(db_session, test_data["other_brand"].id)
    before = await _side_effects(db_session)
    resp = await client.post(JOBS, json=_job(test_data["brand"].id, source_asset_id=foreign.id),
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Asset not found"
    video_task.delay.assert_not_called()
    assert await _side_effects(db_session) == before


@pytest.mark.asyncio
async def test_missing_or_deleted_source_asset_is_the_same_404(client, db_session, test_data, video_task):
    deleted = await _asset(db_session, test_data["brand"].id, deleted_at=datetime(2026, 1, 1))
    for asset_id in (999_999, deleted.id):
        resp = await client.post(JOBS, json=_job(test_data["brand"].id, source_asset_id=asset_id),
                                 headers=test_data["get_headers"]("editor"))
        assert (resp.status_code, resp.json()["detail"]) == (404, "Asset not found")
    video_task.delay.assert_not_called()
