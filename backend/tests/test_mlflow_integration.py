import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import Character, CharacterVersion


# ========================== Helper ===============================

async def create_test_character(db_session, brand_id, owner_id):
    char = Character(
        brand_id=brand_id,
        name="Test MLflow Character",
        description="For MLflow testing",
        image_path="/uploads/test.jpg",
    )
    db_session.add(char)
    await db_session.commit()
    await db_session.refresh(char)
    return char


# ========================== MLflow Integration Tests =============

@pytest.mark.asyncio
async def test_create_version_logs_to_mlflow(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Creating a character version should log to MLflow."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    char = await create_test_character(db_session, brand.id, test_data["users"]["owner"].id)

    mock_run = MagicMock()
    mock_run.info.run_id = "test_mlflow_run_id_123"
    mock_run.__enter__ = MagicMock(return_value=mock_run)
    mock_run.__exit__ = MagicMock(return_value=False)

    mock_mlflow = MagicMock()
    mock_mlflow.start_run.return_value = mock_run

    with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
        res = await client.post(
            f"/api/v1/characters/{char.id}/versions",
            json={
                "version_number": 1,
                "prompt_trigger": "test_char_v1",
                "config_overrides": {"learning_rate": "0.001"},
            },
            headers=editor_headers,
        )

    assert res.status_code == status.HTTP_201_CREATED
    mock_mlflow.set_experiment.assert_called_once_with(f"character_{char.id}")
    mock_mlflow.start_run.assert_called_once()


@pytest.mark.asyncio
async def test_create_version_stores_mlflow_run_id(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Character version should store mlflow_run_id in DB."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    char = await create_test_character(db_session, brand.id, test_data["users"]["owner"].id)

    mock_run = MagicMock()
    mock_run.info.run_id = "stored_run_id_456"
    mock_run.__enter__ = MagicMock(return_value=mock_run)
    mock_run.__exit__ = MagicMock(return_value=False)

    mock_mlflow = MagicMock()
    mock_mlflow.start_run.return_value = mock_run

    with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
        res = await client.post(
            f"/api/v1/characters/{char.id}/versions",
            json={"version_number": 1, "prompt_trigger": "test_v1"},
            headers=editor_headers,
        )

    assert res.status_code == status.HTTP_201_CREATED
    version_id = res.json()["id"]

    result = await db_session.execute(
        select(CharacterVersion).where(CharacterVersion.id == version_id)
    )
    version = result.scalars().first()
    assert version is not None
    assert version.mlflow_run_id == "stored_run_id_456"


@pytest.mark.asyncio
async def test_create_version_mlflow_offline_fallback(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """MLflow offline should not crash version creation."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    char = await create_test_character(db_session, brand.id, test_data["users"]["owner"].id)

    mock_mlflow = MagicMock()
    mock_mlflow.set_tracking_uri.side_effect = Exception("MLflow server unreachable")

    with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
        res = await client.post(
            f"/api/v1/characters/{char.id}/versions",
            json={"version_number": 1, "prompt_trigger": "offline_test"},
            headers=editor_headers,
        )

    # Should still create version successfully
    assert res.status_code == status.HTTP_201_CREATED
    version_id = res.json()["id"]

    result = await db_session.execute(
        select(CharacterVersion).where(CharacterVersion.id == version_id)
    )
    version = result.scalars().first()
    assert version is not None
    # mlflow_run_id should be None on failure
    assert version.mlflow_run_id is None


@pytest.mark.asyncio
async def test_create_version_logs_config_params(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Config overrides should be logged as MLflow parameters."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    char = await create_test_character(db_session, brand.id, test_data["users"]["owner"].id)

    mock_run = MagicMock()
    mock_run.info.run_id = "params_run_id"
    mock_run.__enter__ = MagicMock(return_value=mock_run)
    mock_run.__exit__ = MagicMock(return_value=False)

    mock_mlflow = MagicMock()
    mock_mlflow.start_run.return_value = mock_run

    config = {"learning_rate": "0.001", "batch_size": "4", "epochs": "10"}

    with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
        res = await client.post(
            f"/api/v1/characters/{char.id}/versions",
            json={"version_number": 1, "prompt_trigger": "test", "config_overrides": config},
            headers=editor_headers,
        )

    assert res.status_code == status.HTTP_201_CREATED
    # Verify log_param was called for config keys
    log_param_calls = [str(call) for call in mock_mlflow.log_param.call_args_list]
    assert any("learning_rate" in c for c in log_param_calls)


@pytest.mark.asyncio
async def test_create_version_auth_required(client: AsyncClient, test_data: dict):
    """Creating character version should require authentication."""
    res = await client.post("/api/v1/characters/1/versions", json={"version_number": 1})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_create_version_viewer_forbidden(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Viewer should not be able to create character versions."""
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")

    char = await create_test_character(db_session, brand.id, test_data["users"]["owner"].id)

    res = await client.post(
        f"/api/v1/characters/{char.id}/versions",
        json={"version_number": 1, "prompt_trigger": "test"},
        headers=viewer_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
