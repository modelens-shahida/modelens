import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import CharacterVersion, AIJob, Character


# ========================== MLflow Worker Tests ===================

@pytest.mark.asyncio
async def test_training_job_logs_to_mlflow(db_session: AsyncSession, test_data: dict):
    """Worker should log training run to MLflow and store run_id in CharacterVersion."""
    from app.worker import _process_training_job_async

    brand = test_data["brand"]
    editor_user = test_data["users"]["editor"]

    # Create a character
    character = Character(
        brand_id=brand.id,
        name="Test Character",
        description="Test",
        trigger_word="test_char",
    )
    db_session.add(character)
    await db_session.commit()
    await db_session.refresh(character)

    # Create training job
    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        status="pending",
        job_type="training",
        inputs={
            "character_id": character.id,
            "training_assets": [],
            "hyperparameters": {"learning_rate": 0.001, "batch_size": 4},
            "version_number": 1,
        },
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    mock_run = MagicMock()
    mock_run.info.run_id = "mock_run_id_12345"

    mock_mlflow = MagicMock()
    mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=mock_run)
    mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

    with patch("app.worker.asyncio.sleep", new=AsyncMock()), \
         patch.dict("sys.modules", {"mlflow": mock_mlflow}):
        await _process_training_job_async(job.id, retries=0, max_retries=3)

    await db_session.refresh(job)
    assert job.status == "completed"

    # Verify CharacterVersion was created
    result = await db_session.execute(
        select(CharacterVersion).where(CharacterVersion.character_id == character.id)
    )
    version = result.scalars().first()
    assert version is not None


@pytest.mark.asyncio
async def test_training_mlflow_failure_is_non_fatal(db_session: AsyncSession, test_data: dict):
    """MLflow logging failure should not fail the training job."""
    from app.worker import _process_training_job_async

    brand = test_data["brand"]
    editor_user = test_data["users"]["editor"]

    character = Character(
        brand_id=brand.id,
        name="Test Character 2",
        description="Test",
        trigger_word="test_char_2",
    )
    db_session.add(character)
    await db_session.commit()
    await db_session.refresh(character)

    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        status="pending",
        job_type="training",
        inputs={
            "character_id": character.id,
            "training_assets": [],
            "hyperparameters": {},
            "version_number": 1,
        },
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # MLflow raises exception
    mock_mlflow = MagicMock()
    mock_mlflow.set_tracking_uri.side_effect = Exception("MLflow unavailable")

    with patch("app.worker.asyncio.sleep", new=AsyncMock()), \
         patch.dict("sys.modules", {"mlflow": mock_mlflow}):
        await _process_training_job_async(job.id, retries=0, max_retries=3)

    await db_session.refresh(job)
    # Job should still complete even if MLflow fails
    assert job.status == "completed"


# ========================== Metrics API Tests ====================

@pytest.mark.asyncio
async def test_get_metrics_auth_required(client: AsyncClient, test_data: dict):
    """Metrics endpoint should require authentication."""
    res = await client.get("/api/v1/characters/versions/1/metrics")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_metrics_viewer_forbidden(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Viewer should not be able to view training metrics."""
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")

    character = Character(
        brand_id=brand.id,
        name="Metrics Test Character",
        description="Test",
        trigger_word="metrics_char",
    )
    db_session.add(character)
    await db_session.commit()
    await db_session.refresh(character)

    version = CharacterVersion(
        character_id=character.id,
        version_number=1,
        mlflow_run_id="test_run_id",
        config_overrides={},
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)

    res = await client.get(f"/api/v1/characters/versions/{version.id}/metrics", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_get_metrics_no_mlflow_run(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Version without mlflow_run_id should return message."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    character = Character(
        brand_id=brand.id,
        name="No MLflow Character",
        description="Test",
        trigger_word="no_mlflow",
    )
    db_session.add(character)
    await db_session.commit()
    await db_session.refresh(character)

    version = CharacterVersion(
        character_id=character.id,
        version_number=1,
        mlflow_run_id=None,
        config_overrides={},
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)

    res = await client.get(f"/api/v1/characters/versions/{version.id}/metrics", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["mlflow_run_id"] is None
    assert "No MLflow run" in res.json()["message"]


@pytest.mark.asyncio
async def test_get_metrics_owner_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Owner should be able to retrieve MLflow metrics."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    character = Character(
        brand_id=brand.id,
        name="Owner Metrics Character",
        description="Test",
        trigger_word="owner_metrics",
    )
    db_session.add(character)
    await db_session.commit()
    await db_session.refresh(character)

    version = CharacterVersion(
        character_id=character.id,
        version_number=1,
        mlflow_run_id="mock_run_id_xyz",
        config_overrides={},
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)

    mock_run = MagicMock()
    mock_run.data.params = {"learning_rate": "0.001"}
    mock_run.data.metrics = {"train_loss": 0.25, "val_loss": 0.30}
    mock_run.info.artifact_uri = "mlflow-artifacts:/1/mock_run_id_xyz/artifacts"
    mock_run.info.status = "FINISHED"

    mock_client = MagicMock()
    mock_client.get_run.return_value = mock_run

    mock_mlflow = MagicMock()
    mock_mlflow.tracking.MlflowClient.return_value = mock_client

    with patch.dict("sys.modules", {"mlflow": mock_mlflow, "mlflow.tracking": mock_mlflow.tracking}):
        res = await client.get(f"/api/v1/characters/versions/{version.id}/metrics", headers=owner_headers)

    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["mlflow_run_id"] == "mock_run_id_xyz"
