import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import Brand, CatalogJob, CreditTransaction


# ========================== Config Tests ========================

def test_rosanne_workflow_template_id():
    from app.routers.rosanne_pipeline import ROSANNE_WORKFLOW_TEMPLATE_ID
    assert ROSANNE_WORKFLOW_TEMPLATE_ID == "rosanne-v1"


def test_rosanne_identity_locks():
    from app.routers.rosanne_pipeline import ROSANNE_IDENTITY_LOCKS
    assert ROSANNE_IDENTITY_LOCKS["face_geometry"] is True
    assert ROSANNE_IDENTITY_LOCKS["skin_tone"] is True
    assert ROSANNE_IDENTITY_LOCKS["identity_markers"] is True


def test_rosanne_preset_params():
    from app.routers.rosanne_pipeline import ROSANNE_PRESET_PARAMS
    assert ROSANNE_PRESET_PARAMS["identity_strength"] == 0.82
    assert ROSANNE_PRESET_PARAMS["identity_strength_min"] == 0.70
    assert ROSANNE_PRESET_PARAMS["identity_strength_max"] == 0.90
    assert ROSANNE_PRESET_PARAMS["garment_preservation"] is True


def test_rosanne_pose_presets_defined():
    from app.routers.rosanne_pipeline import ROSANNE_POSE_PRESETS
    assert len(ROSANNE_POSE_PRESETS) > 0
    assert any(p["angle_code"] == "FRONT" for p in ROSANNE_POSE_PRESETS)
    assert any(p["angle_code"] == "L30" for p in ROSANNE_POSE_PRESETS)
    assert any(p["angle_code"] == "R30" for p in ROSANNE_POSE_PRESETS)


# ========================== Scene Prompt Tests ==================

def test_build_scene_prompt_basic():
    from app.routers.rosanne_pipeline import build_scene_prompt, RosanneScenePrompt
    prompt = build_scene_prompt(RosanneScenePrompt(character_id="EE-F-002"))
    assert "EE-F-002" in prompt
    assert "fashion" in prompt.lower()


def test_build_scene_prompt_with_environment():
    from app.routers.rosanne_pipeline import build_scene_prompt, RosanneScenePrompt
    prompt = build_scene_prompt(RosanneScenePrompt(
        character_id="EE-F-002",
        environment="luxury hotel lobby",
        lighting="soft daylight",
        mood="editorial",
    ))
    assert "luxury hotel lobby" in prompt
    assert "soft daylight" in prompt
    assert "editorial" in prompt


def test_build_scene_prompt_with_garment():
    from app.routers.rosanne_pipeline import build_scene_prompt, RosanneScenePrompt
    prompt = build_scene_prompt(RosanneScenePrompt(
        character_id="EE-F-002",
        garment_description="silk bias cut dress in burgundy",
    ))
    assert "silk bias cut dress" in prompt


# ========================== Credit Estimation Tests =============

@pytest.mark.asyncio
async def test_estimate_rosanne_credits_quality(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post(
        "/api/v1/rosanne/estimate?quality_mode=quality&num_images=1",
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["estimated_credits"] == 5
    assert data["workflow"] == "rosanne-v1"


@pytest.mark.asyncio
async def test_estimate_rosanne_credits_multi_images(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post(
        "/api/v1/rosanne/estimate?quality_mode=quality&num_images=2",
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["estimated_credits"] == 10


# ========================== Config Endpoint Tests ===============

@pytest.mark.asyncio
async def test_get_rosanne_config(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/rosanne/config", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["workflow_template_id"] == "rosanne-v1"
    assert "identity_locks" in data
    assert "preset_params" in data
    assert "pose_presets" in data


@pytest.mark.asyncio
async def test_get_rosanne_pose_presets(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/rosanne/pose-presets", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["pose_presets"]) > 0
    assert data["total"] > 0


# ========================== Scene Prompt Endpoint Tests =========

@pytest.mark.asyncio
async def test_build_scene_prompt_endpoint(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post(
        "/api/v1/rosanne/scene-prompt/build",
        json={
            "character_id": "EE-F-002",
            "environment": "luxury hotel",
            "lighting": "soft daylight",
            "mood": "editorial",
        },
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "scene_prompt" in data
    assert "EE-F-002" in data["scene_prompt"]
    assert data["prompt_length"] > 0


# ========================== Generation Tests ====================

@pytest.mark.asyncio
async def test_rosanne_generate_success(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    brand.credits = 100
    await db_session.commit()

    with patch("app.routers.rosanne_pipeline._dispatch_rosanne_workflow", new_callable=AsyncMock):
        res = await client.post(
            "/api/v1/rosanne/generate",
            json={
                "product_id": "GAR-TEST-001",
                "character_id": "EE-F-002",
                "character_version": "1.0",
                "pose_preset_id": "POSE-ROS-001",
                "quality_mode": "quality",
                "num_images": 1,
            },
            headers=owner_headers,
        )

    assert res.status_code == 201
    data = res.json()
    assert data["workflow_template_id"] == "rosanne-v1"
    assert data["character_id"] == "EE-F-002"
    assert data["identity_locks"]["face_geometry"] is True
    assert data["credits_reserved"] == 5
    assert "websocket_url" in data


@pytest.mark.asyncio
async def test_rosanne_generate_insufficient_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    brand.credits = 0
    await db_session.commit()

    res = await client.post(
        "/api/v1/rosanne/generate",
        json={
            "product_id": "GAR-TEST-001",
            "character_id": "EE-F-002",
            "quality_mode": "quality",
            "num_images": 1,
        },
        headers=owner_headers,
    )
    assert res.status_code == 402
    assert res.json()["detail"]["error"] == "insufficient_credits"


@pytest.mark.asyncio
async def test_rosanne_generate_with_custom_identity_strength(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    brand.credits = 100
    await db_session.commit()

    with patch("app.routers.rosanne_pipeline._dispatch_rosanne_workflow", new_callable=AsyncMock):
        res = await client.post(
            "/api/v1/rosanne/generate",
            json={
                "product_id": "GAR-TEST-001",
                "character_id": "EE-F-002",
                "identity_strength": 0.85,
                "quality_mode": "quality",
                "num_images": 1,
            },
            headers=owner_headers,
        )

    assert res.status_code == 201
    data = res.json()
    assert data["identity_strength"] == 0.85


@pytest.mark.asyncio
async def test_get_rosanne_job_status(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_user = test_data["users"]["owner"]
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    job = CatalogJob(
        job_id="rosanne_status_test",
        user_id=owner_user.id,
        brand_id=brand.id,
        status="queued",
        total_skus=1,
        quality_mode="quality",
        meta={
            "workflow_template_id": "rosanne-v1",
            "character_id": "EE-F-002",
            "identity_strength": 0.82,
            "credits_reserved": 5,
        }
    )
    db_session.add(job)
    await db_session.commit()

    res = await client.get("/api/v1/rosanne/jobs/rosanne_status_test", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["workflow_template_id"] == "rosanne-v1"
    assert data["character_id"] == "EE-F-002"
    assert data["identity_strength"] == 0.82
