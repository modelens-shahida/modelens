import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import FluidSession, FluidLayer, BrandModel, User

@pytest.mark.asyncio
async def test_create_editorial_session_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    headers = test_data["get_headers"]("editor")
    
    payload = {
        "workspace_id": "workspace_test",
        "name": "Summer Fashion Campaign",
        "model_id": "model_01",
        "model_prompt": "Female fashion model in neutral pose",
        "scene_prompt": "Cinematic lighting on a beach back-drop",
        "pose_reference_asset_id": "pose_asset_123",
        "background_asset_id": "background_asset_456",
        "product_ids": ["product_dress_01"],
        "aspect_ratio": "4:5",
        "resolution": "2K",
        "generation_mode": "QUALITY"
    }

    res = await client.post("/api/v1/editorial-sessions", json=payload, headers=headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["name"] == "Summer Fashion Campaign"
    assert data["session_id"] is not None
    assert data["workspace_id"] == "workspace_test"
    assert data["aspect_ratio"] == "4:5"
    assert len(data["layers"]) == 0

    # Verify session is persisted in db
    session_id = data["session_id"]
    result = await db_session.execute(select(FluidSession).where(FluidSession.id == session_id))
    session = result.scalar_one_or_none()
    assert session is not None
    assert session.name == "Summer Fashion Campaign"


@pytest.mark.asyncio
async def test_get_and_delete_editorial_session(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    headers = test_data["get_headers"]("editor")

    # Create session directly in DB
    session = FluidSession(
        id="session_test_123",
        user_id=test_data["users"]["editor"].id,
        workspace_id="workspace_test",
        name="Retrieve Campaign",
        model_id="model_01",
        aspect_ratio="1:1"
    )
    db_session.add(session)
    await db_session.commit()

    # Get session
    res = await client.get("/api/v1/editorial-sessions/session_test_123", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["name"] == "Retrieve Campaign"

    # Delete session
    res = await client.delete("/api/v1/editorial-sessions/session_test_123", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    
    # Confirm deletion from DB
    result = await db_session.execute(select(FluidSession).where(FluidSession.id == "session_test_123"))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_generate_base_layer(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    headers = test_data["get_headers"]("editor")

    # Create session
    session = FluidSession(
        id="session_gen_base",
        user_id=test_data["users"]["editor"].id,
        workspace_id="workspace_test",
        name="Base Gen Campaign",
        model_id="model_01",
        scene_prompt="Beachy background with sunset",
        aspect_ratio="4:5"
    )
    db_session.add(session)
    await db_session.commit()

    # Base Generate
    res = await client.post("/api/v1/editorial-sessions/session_gen_base/generate", json={
        "use_premium_creative_model": False
    }, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    layer_data = res.json()
    assert layer_data["layer_id"] is not None
    assert layer_data["operation"] == "base_generation"
    assert layer_data["provider"] == "FASHN Product-to-Model"
    assert layer_data["prompt"] == "Beachy background with sunset"

    # Verify layer is in DB
    result = await db_session.execute(select(FluidLayer).where(FluidLayer.id == layer_data["layer_id"]))
    layer = result.scalar_one_or_none()
    assert layer is not None


@pytest.mark.asyncio
async def test_non_destructive_layer_pipeline(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    headers = test_data["get_headers"]("editor")

    # Create session and base layer
    session = FluidSession(
        id="session_pipeline",
        user_id=test_data["users"]["editor"].id,
        workspace_id="workspace_test",
        name="Pipeline Campaign",
        model_id="model_01",
        aspect_ratio="4:5",
        active_layer_id="layer_base"
    )
    base_layer = FluidLayer(
        id="layer_base",
        session_id="session_pipeline",
        parent_layer_id=None,
        operation="base_generation",
        provider="FASHN Product-to-Model",
        provider_model="product-to-model",
        provider_job_id="job_base_1",
        image_url="https://cdn.modelens.ai/base.png",
        aspect_ratio="4:5"
    )
    db_session.add(session)
    db_session.add(base_layer)
    await db_session.commit()

    # 1. Apply Product
    res = await client.post("/api/v1/editorial-sessions/session_pipeline/layers/layer_base/apply-product", json={
        "product_id": "product_bag_02",
        "instructions": "Place bag in left hand"
    }, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    layer1 = res.json()
    assert layer1["parent_layer_id"] == "layer_base"
    assert layer1["operation"] == "apply_product"
    assert layer1["provider"] == "FASHN Try-On Max"

    # 2. Masked Edit (Inpaint)
    res = await client.post(f"/api/v1/editorial-sessions/session_pipeline/layers/{layer1['layer_id']}/edit", json={
        "prompt": "Move left arm slightly away",
        "mask_asset_id": "mask_arm_01",
        "use_gemini": True
    }, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    layer2 = res.json()
    assert layer2["parent_layer_id"] == layer1["layer_id"]
    assert layer2["operation"] == "edit"
    assert layer2["provider"] == "Gemini 3 Pro Image Inpaint"

    # 3. Model Swap
    res = await client.post(f"/api/v1/editorial-sessions/session_pipeline/layers/{layer2['layer_id']}/model-swap", json={
        "target_model_id": "brand_model_01",
        "identity_prompt": "Swap model identity"
    }, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    layer3 = res.json()
    assert layer3["parent_layer_id"] == layer2["layer_id"]
    assert layer3["operation"] == "model_swap"

    # 4. Reframe
    res = await client.post(f"/api/v1/editorial-sessions/session_pipeline/layers/{layer3['layer_id']}/reframe", json={
        "aspect_ratio": "16:9"
    }, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    layer4 = res.json()
    assert layer4["parent_layer_id"] == layer3["layer_id"]
    assert layer4["operation"] == "reframe"
    assert layer4["aspect_ratio"] == "16:9"

    # 5. Upscale
    res = await client.post(f"/api/v1/editorial-sessions/session_pipeline/layers/{layer4['layer_id']}/upscale", json={
        "resolution": "8K",
        "upscale_engine": "SeedVR2"
    }, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    layer5 = res.json()
    assert layer5["parent_layer_id"] == layer4["layer_id"]
    assert layer5["operation"] == "upscale"
    assert "8K" in layer5["prompt"]

    # Verify session retrieves all 6 layers ordered by creation date
    res = await client.get("/api/v1/editorial-sessions/session_pipeline", headers=headers)
    session_data = res.json()
    assert len(session_data["layers"]) == 6
    assert session_data["layers"][0]["layer_id"] == "layer_base"
    assert session_data["layers"][5]["layer_id"] == layer5["layer_id"]
    assert session_data["active_layer_id"] == layer5["layer_id"]


@pytest.mark.asyncio
async def test_list_editorial_sessions(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    headers = test_data["get_headers"]("editor")

    # Create session directly in DB
    session = FluidSession(
        id="session_list_test",
        user_id=test_data["users"]["editor"].id,
        workspace_id="workspace_test",
        name="List Campaign 1",
        model_id="model_01",
        aspect_ratio="1:1"
    )
    db_session.add(session)
    await db_session.commit()

    res = await client.get("/api/v1/editorial-sessions", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    sessions = res.json()
    assert len(sessions) >= 1
    assert any(s["name"] == "List Campaign 1" for s in sessions)


@pytest.mark.asyncio
async def test_brand_model_creation_and_listing(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    headers = test_data["get_headers"]("editor")

    # Create Brand Model
    res = await client.post("/api/v1/brand-models", json={
        "name": "Mia Private Model",
        "workspace_id": "workspace_test",
        "gender": "Female",
        "full_body_reference_asset_id": "asset_full_1",
        "portrait_reference_asset_id": "asset_portrait_1",
        "appearance_prompt": "Athletic female build",
        "rights_confirmed": True
    }, headers=headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["model_id"] is not None
    assert data["name"] == "Mia Private Model"

    # List Brand Models
    res = await client.get("/api/v1/brand-models", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    models = res.json()
    assert len(models) >= 1
    assert any(m["name"] == "Mia Private Model" for m in models)
