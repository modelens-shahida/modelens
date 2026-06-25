import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.db import AIJob, User, CharacterVersion


@pytest.mark.asyncio
async def test_train_character_auth_required(client: AsyncClient, test_data: dict):
    res = await client.post("/api/v1/characters/1/train", json={"training_assets": [1], "hyperparameters": {}})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_train_character_viewer_forbidden(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/characters", json={"brand_id": brand.id, "name": "RBAC Char", "description": "Test", "image_path": "/uploads/rbac.png"}, headers=editor_headers)
    character_id = res.json()["id"]

    res = await client.post(f"/api/v1/characters/{character_id}/train", json={"training_assets": [1], "hyperparameters": {}}, headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_train_character_not_found(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/characters/99999/train", json={"training_assets": [1], "hyperparameters": {}}, headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_train_character_invalid_asset(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/characters", json={"brand_id": brand.id, "name": "Invalid Asset Char", "description": "Test", "image_path": "/uploads/inv.png"}, headers=editor_headers)
    character_id = res.json()["id"]

    res = await client.post(f"/api/v1/characters/{character_id}/train", json={"training_assets": [99999], "hyperparameters": {}}, headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_train_character_non_image_asset(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/characters", json={"brand_id": brand.id, "name": "Non Image Char", "description": "Test", "image_path": "/uploads/ni.png"}, headers=editor_headers)
    character_id = res.json()["id"]

    result = await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata)
        VALUES (:brand_id, 'Video Asset', 'video.mp4', '/uploads/video.mp4', 'video', '{}') RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    video_asset_id = result.fetchone()[0]

    res = await client.post(f"/api/v1/characters/{character_id}/train", json={"training_assets": [video_asset_id], "hyperparameters": {}}, headers=editor_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "not an image" in res.json()["detail"]


@pytest.mark.asyncio
async def test_train_character_insufficient_credits(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]

    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    user.credits = 5
    await db_session.commit()

    res = await client.post("/api/v1/characters", json={"brand_id": brand.id, "name": "Low Credits Char", "description": "Test", "image_path": "/uploads/lc.png"}, headers=editor_headers)
    character_id = res.json()["id"]

    result = await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata)
        VALUES (:brand_id, 'Train Asset', 'train.png', '/uploads/train.png', 'image', '{}') RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    asset_id = result.fetchone()[0]

    res = await client.post(f"/api/v1/characters/{character_id}/train", json={"training_assets": [asset_id], "hyperparameters": {}}, headers=editor_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "credits" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_train_character_deducts_10_credits(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]

    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    starting_credits = user.credits

    res = await client.post("/api/v1/characters", json={"brand_id": brand.id, "name": "Credit Char", "description": "Test", "image_path": "/uploads/cc.png"}, headers=editor_headers)
    character_id = res.json()["id"]

    result = await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata)
        VALUES (:brand_id, 'Train Asset', 'ta.png', '/uploads/ta.png', 'image', '{}') RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    asset_id = result.fetchone()[0]

    with patch("app.routers.characters.process_training_job.delay"):
        res = await client.post(f"/api/v1/characters/{character_id}/train", json={"training_assets": [asset_id], "hyperparameters": {}}, headers=editor_headers)

    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["credits_remaining"] == starting_credits - 10


@pytest.mark.asyncio
async def test_training_job_success_creates_character_version(db_session: AsyncSession, test_data: dict):
    from app.worker import _process_training_job_async
    brand = test_data["brand"]
    editor_user = test_data["users"]["editor"]

    result = await db_session.execute(text("""
        INSERT INTO characters (brand_id, name, description, image_path)
        VALUES (:brand_id, 'Training Char', 'desc', '/uploads/tc.png') RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    char_id = result.fetchone()[0]

    result = await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata)
        VALUES (:brand_id, 'Train Img', 'ti.png', '/uploads/ti.png', 'image', '{"prompt": "luxury editorial"}') RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    asset_id = result.fetchone()[0]

    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        status="pending",
        job_type="character_training",
        inputs={"character_id": char_id, "version_number": 1, "training_assets": [asset_id], "hyperparameters": {"learning_rate": 0.0001}},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    with patch("app.worker.asyncio.sleep", new=AsyncMock()):
        await _process_training_job_async(job.id, retries=0, max_retries=3)

    await db_session.refresh(job)
    assert job.status == "completed"
    assert job.outputs.get("character_version_id") is not None

    version_result = await db_session.execute(select(CharacterVersion).where(CharacterVersion.character_id == char_id))
    assert version_result.scalars().first() is not None


@pytest.mark.asyncio
async def test_training_job_failure_refunds_credits(db_session: AsyncSession, test_data: dict):
    from app.worker import _process_training_job_async
    brand = test_data["brand"]
    editor_user = test_data["users"]["editor"]

    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    starting_credits = user.credits
    user.credits -= 10
    await db_session.commit()

    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        status="pending",
        job_type="character_training",
        inputs={"character_id": 99999, "training_assets": [], "version_number": 1, "hyperparameters": {}},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    with patch("app.worker.asyncio.sleep", new=AsyncMock(side_effect=RuntimeError("Training failed"))):
        await _process_training_job_async(job.id, retries=3, max_retries=3)

    await db_session.refresh(job)
    assert job.status == "failed"

    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    assert user_result.scalars().first().credits == starting_credits
