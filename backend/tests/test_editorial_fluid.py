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


# ========================== Ownership & parent layers ============

OPERATIONS = {
    "apply-product": {"product_id": "prod_1"},
    "edit": {"prompt": "Brighten the jacket"},
    "model-swap": {"identity_prompt": "Short dark hair"},
    "reframe": {"aspect_ratio": "16:9"},
    "upscale": {"resolution": "4K"},
}


async def _seed_session(db_session: AsyncSession, user_id: int, session_id: str, layer_id: str) -> None:
    db_session.add(FluidSession(id=session_id, user_id=user_id, workspace_id="workspace_test",
                                name=f"Session {session_id}", model_id="model_01", aspect_ratio="4:5",
                                active_layer_id=layer_id))
    db_session.add(FluidLayer(id=layer_id, session_id=session_id, parent_layer_id=None,
                              operation="base_generation", provider="FASHN Product-to-Model",
                              provider_model="product-to-model", provider_job_id=f"job_{layer_id}",
                              image_url=f"https://cdn.modelens.ai/{layer_id}.png", aspect_ratio="4:5"))
    await db_session.commit()


async def _layer_count(db_session: AsyncSession, session_id: str) -> int:
    result = await db_session.execute(select(FluidLayer).where(FluidLayer.session_id == session_id))
    return len(result.scalars().all())


@pytest.mark.asyncio
async def test_other_users_session_is_not_found(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Another user's session behaves exactly like a missing one, for every endpoint."""
    await _seed_session(db_session, test_data["users"]["editor"].id, "session_editor", "layer_editor")
    viewer = test_data["get_headers"]("viewer")
    base = "/api/v1/editorial-sessions/session_editor"

    res = await client.get(base, headers=viewer)
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json()["detail"] == "Fluid Session 'session_editor' not found"
    assert (await client.get("/api/v1/editorial-sessions/session_missing", headers=viewer)).json()["detail"] == \
        "Fluid Session 'session_missing' not found"

    res = await client.post(f"{base}/generate", json={}, headers=viewer)
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json()["detail"] == "Fluid session 'session_editor' not found"

    for operation, payload in OPERATIONS.items():
        res = await client.post(f"{base}/layers/layer_editor/{operation}", json=payload, headers=viewer)
        assert res.status_code == status.HTTP_404_NOT_FOUND, operation
        assert res.json()["detail"] == "Fluid session 'session_editor' not found"

    res = await client.delete(base, headers=viewer)
    assert res.status_code == status.HTTP_404_NOT_FOUND

    listed = (await client.get("/api/v1/editorial-sessions", headers=viewer)).json()
    assert all(s["session_id"] != "session_editor" for s in listed)

    # Nothing changed for the owner.
    assert await _layer_count(db_session, "session_editor") == 1
    owner_view = await client.get(base, headers=test_data["get_headers"]("editor"))
    assert owner_view.status_code == status.HTTP_200_OK
    assert owner_view.json()["active_layer_id"] == "layer_editor"


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", list(OPERATIONS))
async def test_parent_layer_must_exist_in_the_session(client: AsyncClient, db_session: AsyncSession,
                                                      test_data: dict, operation):
    editor_id = test_data["users"]["editor"].id
    await _seed_session(db_session, editor_id, "session_a", "layer_a")
    await _seed_session(db_session, editor_id, "session_b", "layer_b")
    headers = test_data["get_headers"]("editor")

    for parent in ("layer_missing", "layer_b"):
        res = await client.post(f"/api/v1/editorial-sessions/session_a/layers/{parent}/{operation}",
                                json=OPERATIONS[operation], headers=headers)
        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert res.json()["detail"] == f"Layer '{parent}' not found in Fluid session 'session_a'"

    assert await _layer_count(db_session, "session_a") == 1


@pytest.mark.asyncio
async def test_fluid_operations_do_not_charge_credits(client: AsyncClient, db_session: AsyncSession,
                                                      test_data: dict):
    """Outputs are placeholders, so nothing is charged until there is a price list."""
    editor = test_data["users"]["editor"]
    editor.credits = 3
    await db_session.commit()
    headers = test_data["get_headers"]("editor")

    created = await client.post("/api/v1/editorial-sessions", json={"name": "Free session"}, headers=headers)
    assert created.status_code == status.HTTP_201_CREATED
    session_id = created.json()["session_id"]

    layer = (await client.post(f"/api/v1/editorial-sessions/{session_id}/generate", json={},
                               headers=headers)).json()
    for operation, payload in OPERATIONS.items():
        res = await client.post(f"/api/v1/editorial-sessions/{session_id}/layers/{layer['layer_id']}/{operation}",
                                json=payload, headers=headers)
        assert res.status_code == status.HTTP_200_OK, operation
        layer = res.json()

    await db_session.refresh(editor)
    assert editor.credits == 3


@pytest.mark.asyncio
async def test_frontend_flow_shapes(client: AsyncClient, test_data: dict):
    """The calls app/dashboard/fluid/page.jsx makes, with the fields it reads."""
    headers = test_data["get_headers"]("editor")
    created = await client.post("/api/v1/editorial-sessions", headers=headers, json={
        "name": "Page session", "scene_prompt": "Rooftop at dusk", "aspect_ratio": "3:4", "resolution": "2K",
    })
    assert created.status_code == status.HTTP_201_CREATED
    session_id = created.json()["session_id"]

    listed = (await client.get("/api/v1/editorial-sessions", headers=headers)).json()
    assert isinstance(listed, list)
    assert {"session_id", "name", "created_at"} <= set(listed[0])

    base = (await client.post(f"/api/v1/editorial-sessions/{session_id}/generate", json={},
                              headers=headers)).json()
    assert base["prompt"] == "Rooftop at dusk"

    session = (await client.get(f"/api/v1/editorial-sessions/{session_id}", headers=headers)).json()
    assert session["session_id"] == session_id
    assert [l["layer_id"] for l in session["layers"]] == [base["layer_id"]]
    assert {"layer_id", "operation", "image_url", "prompt"} <= set(session["layers"][0])
    assert session["active_layer_id"] == base["layer_id"]
