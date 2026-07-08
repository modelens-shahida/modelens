import pytest
import json
import base64
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import AIJob, User, Asset, Character, CharacterVersion, GeneratedVideo
from app.worker import _process_workflow_job_async

class MockSessionContext:
    def __init__(self, session):
        self.session = session
    async def __aenter__(self):
        return self.session
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.mark.asyncio
async def test_workflow_endpoint_rbac(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    viewer_headers = test_data["get_headers"]("viewer")

    # Seed asset
    from sqlalchemy import text
    result = await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata)
        VALUES (:brand_id, 'Valid Asset', 'valid.png', '/uploads/valid.png', 'image', '{}')
        RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    valid_asset_id = result.fetchone()[0]

    # 1. Editor should succeed
    with patch("app.routers.jobs.process_workflow_job.delay") as mock_delay, \
         patch("app.routers.jobs.redis_client.set", new_callable=AsyncMock) as mock_redis_set:
        
        payload = {
            "brand_id": brand.id,
            "workflow_type": "flat_lay_to_model",
            "inputs": {
                "source_asset_id": valid_asset_id
            },
            "callback_url": "http://callback-url.com/cb"
        }

        res = await client.post("/api/v1/jobs/workflow", json=payload, headers=editor_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "pending"
        assert data["job_type"] == "workflow"
        assert data["inputs"]["workflow_type"] == "flat_lay_to_model"
        
        mock_delay.assert_called_once()
        mock_redis_set.assert_called_once()

    # 2. Viewer should be forbidden
    res = await client.post("/api/v1/jobs/workflow", json=payload, headers=viewer_headers)
    assert res.status_code == 403

    # 3. Invalid workflow type should be 400 Bad Request
    payload["workflow_type"] = "invalid_type"
    res = await client.post("/api/v1/jobs/workflow", json=payload, headers=editor_headers)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_flat_lay_to_model_execution(db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    editor_user = test_data["users"]["editor"]

    # Seed source asset
    source_asset = Asset(
        brand_id=brand.id,
        name="Source Hoodie Flat-lay",
        filename="hoodie.png",
        storage_path="/uploads/hoodie.png",
        asset_type="product_flat",
        meta={"status": "active"}
    )
    db_session.add(source_asset)

    # Seed character & character version
    character = Character(
        brand_id=brand.id,
        name="Hoodie Character Model",
        description="A mid-adult male model with curly hair",
        image_path="/characters/model.png"
    )
    db_session.add(character)
    await db_session.commit()

    char_version = CharacterVersion(
        character_id=character.id,
        version_number=1,
        prompt_trigger="athletic male model, blonde hair",
        reference_image_path="/characters/ref.png",
        validation_image_path="/characters/val.png",
        config_overrides={}
    )
    db_session.add(char_version)
    await db_session.commit()

    # Create job
    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        status="pending",
        job_type="workflow",
        inputs={
            "workflow_type": "flat_lay_to_model",
            "source_asset_id": source_asset.id,
            "character_id": character.id,
            "character_version_id": char_version.id,
            "background_style": "resort",
            "custom_background_prompt": "At a luxury pool resort"
        },
        outputs={}
    )
    db_session.add(job)
    await db_session.commit()

    mock_image_bytes = b"mock_generated_png_bytes"
    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker._generate_image", new=AsyncMock(return_value=mock_image_bytes)) as mock_gen, \
         patch("app.worker.redis_client.set", new_callable=AsyncMock), \
         patch("app.worker.dispatch_webhook.delay"):

        await _process_workflow_job_async(job.id)

    # Verify job state
    await db_session.refresh(job)
    assert job.status == "completed"
    assert job.asset_id is not None
    assert job.outputs["urls"] is not None

    # Verify generated asset
    res = await db_session.execute(select(Asset).where(Asset.id == job.asset_id))
    generated_asset = res.scalars().first()
    assert generated_asset is not None
    assert generated_asset.asset_type == "image"
    assert "flat-lay" in generated_asset.meta["prompt"]
    assert "athletic male model, blonde hair" in generated_asset.meta["prompt"]
    assert "At a luxury pool resort" in generated_asset.meta["prompt"]


@pytest.mark.asyncio
async def test_video_generation_execution(db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    editor_user = test_data["users"]["editor"]

    # Seed source asset
    source_asset = Asset(
        brand_id=brand.id,
        name="Source Hoodie Fit",
        filename="hoodie.png",
        storage_path="/uploads/hoodie.png",
        asset_type="image",
        meta={"status": "active"}
    )
    db_session.add(source_asset)
    await db_session.commit()

    # Create job
    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        status="pending",
        job_type="workflow",
        inputs={
            "workflow_type": "video_generation",
            "source_asset_id": source_asset.id,
            "motion_type": "cinematic",
            "duration_seconds": 6
        },
        outputs={}
    )
    db_session.add(job)
    await db_session.commit()

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker.redis_client.set", new_callable=AsyncMock), \
         patch("app.worker.dispatch_webhook.delay"):

        await _process_workflow_job_async(job.id)

    # Verify job state
    await db_session.refresh(job)
    assert job.status == "completed"
    assert job.asset_id is not None
    assert job.outputs["video_url"] is not None

    # Verify GeneratedVideo record
    v_res = await db_session.execute(select(GeneratedVideo).where(GeneratedVideo.job_id == job.id))
    video_rec = v_res.scalars().first()
    assert video_rec is not None
    assert video_rec.motion_type == "cinematic"
    assert video_rec.duration_seconds == 6
    assert video_rec.source_asset_id == source_asset.id

    # Verify Asset record
    a_res = await db_session.execute(select(Asset).where(Asset.id == job.asset_id))
    video_asset = a_res.scalars().first()
    assert video_asset is not None
    assert video_asset.asset_type == "video"
    assert video_asset.meta["video_id"] == video_rec.id


@pytest.mark.asyncio
async def test_workflow_credit_billing_and_refund(db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    editor_user = test_data["users"]["editor"]

    starting_credits = editor_user.credits
    editor_user.credits -= 1
    db_session.add(editor_user)
    await db_session.commit()

    # Create job that will fail (no source asset provided)
    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        status="pending",
        job_type="workflow",
        inputs={
            "workflow_type": "flat_lay_to_model"
            # Missing source_asset_id
        },
        outputs={}
    )
    db_session.add(job)
    await db_session.commit()

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker.redis_client.set", new_callable=AsyncMock), \
         patch("app.worker.dispatch_webhook.delay"):

        await _process_workflow_job_async(job.id, retries=3, max_retries=3)

    await db_session.refresh(job)
    assert job.status == "failed"
    assert "source_asset_id" in job.error_message

    # Verify credit refund
    await db_session.refresh(editor_user)
    assert editor_user.credits == starting_credits


# ========================== Input Validation Tests ================

@pytest.mark.asyncio
async def test_workflow_job_invalid_source_asset_not_found(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """source_asset_id that doesn't exist should return 404 before credit deduction."""
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_headers = test_data["get_headers"]("editor")

    with patch("app.routers.jobs.process_workflow_job.delay"), \
         patch("app.routers.jobs.redis_client.set", new_callable=AsyncMock):

        res = await client.post("/api/v1/jobs/workflow", json={
            "brand_id": brand.id,
            "workflow_template_id": workflow.id,
            "workflow_type": "background_replacement",
            "inputs": {"source_asset_id": 99999}
        }, headers=editor_headers)

        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_workflow_job_asset_wrong_brand(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """source_asset_id belonging to a different brand should return 400."""
    from sqlalchemy import text
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_headers = test_data["get_headers"]("editor")

    result = await db_session.execute(text("""
        INSERT INTO brands (name, owner_id, tier, monthly_credit_quota, credits_used_this_month)
        VALUES ('Other Brand', :owner_id, 'free', 100, 0) RETURNING id
    """), {"owner_id": test_data["users"]["owner"].id})
    await db_session.commit()
    other_brand_id = result.fetchone()[0]

    result = await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata)
        VALUES (:brand_id, 'Other Asset', 'other.png', '/uploads/other.png', 'image', '{}')
        RETURNING id
    """), {"brand_id": other_brand_id})
    await db_session.commit()
    other_asset_id = result.fetchone()[0]

    with patch("app.routers.jobs.process_workflow_job.delay"), \
         patch("app.routers.jobs.redis_client.set", new_callable=AsyncMock):

        res = await client.post("/api/v1/jobs/workflow", json={
            "brand_id": brand.id,
            "workflow_template_id": workflow.id,
            "workflow_type": "background_replacement",
            "inputs": {"source_asset_id": other_asset_id}
        }, headers=editor_headers)

        assert res.status_code == 400
        assert "does not belong to brand" in res.json()["detail"]


@pytest.mark.asyncio
async def test_workflow_job_valid_asset_succeeds(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """source_asset_id belonging to correct brand should succeed."""
    from sqlalchemy import text
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_headers = test_data["get_headers"]("editor")

    result = await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata)
        VALUES (:brand_id, 'Valid Asset', 'valid.png', '/uploads/valid.png', 'image', '{}')
        RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    valid_asset_id = result.fetchone()[0]

    with patch("app.routers.jobs.process_workflow_job.delay"), \
         patch("app.routers.jobs.redis_client.set", new_callable=AsyncMock):

        res = await client.post("/api/v1/jobs/workflow", json={
            "brand_id": brand.id,
            "workflow_template_id": workflow.id,
            "workflow_type": "background_replacement",
            "inputs": {"source_asset_id": valid_asset_id}
        }, headers=editor_headers)

        assert res.status_code == 201


# ========================== Character Validation Tests ============

@pytest.mark.asyncio
async def test_workflow_job_invalid_character_not_found(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """character_id that doesn't exist should return 404 before credit deduction."""
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_headers = test_data["get_headers"]("editor")

    with patch("app.routers.jobs.process_workflow_job.delay"), \
         patch("app.routers.jobs.redis_client.set", new_callable=AsyncMock):

        res = await client.post("/api/v1/jobs/workflow", json={
            "brand_id": brand.id,
            "workflow_template_id": workflow.id,
            "workflow_type": "flat_lay_to_model",
            "inputs": {"character_id": 99999}
        }, headers=editor_headers)

        assert res.status_code == 404
        assert "character" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_workflow_job_character_wrong_brand(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """character_id belonging to a different brand should return 400."""
    from sqlalchemy import text
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_headers = test_data["get_headers"]("editor")

    # Create another brand and character under it
    result = await db_session.execute(text("""
        INSERT INTO brands (name, owner_id, tier, monthly_credit_quota, credits_used_this_month)
        VALUES ('Other Brand 2', :owner_id, 'free', 100, 0) RETURNING id
    """), {"owner_id": test_data["users"]["owner"].id})
    await db_session.commit()
    other_brand_id = result.fetchone()[0]

    result = await db_session.execute(text("""
        INSERT INTO characters (brand_id, name, description, image_path)
        VALUES (:brand_id, 'Other Char', 'desc', '/uploads/other_char.png')
        RETURNING id
    """), {"brand_id": other_brand_id})
    await db_session.commit()
    other_char_id = result.fetchone()[0]

    with patch("app.routers.jobs.process_workflow_job.delay"), \
         patch("app.routers.jobs.redis_client.set", new_callable=AsyncMock):

        res = await client.post("/api/v1/jobs/workflow", json={
            "brand_id": brand.id,
            "workflow_template_id": workflow.id,
            "workflow_type": "flat_lay_to_model",
            "inputs": {"character_id": other_char_id}
        }, headers=editor_headers)

        assert res.status_code == 400
        assert "does not belong to brand" in res.json()["detail"]


@pytest.mark.asyncio
async def test_workflow_job_invalid_character_version(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """character_version_id not associated with character_id should return 404."""
    from sqlalchemy import text
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_headers = test_data["get_headers"]("editor")

    result = await db_session.execute(text("""
        INSERT INTO characters (brand_id, name, description, image_path)
        VALUES (:brand_id, 'Version Test Char', 'desc', '/uploads/vtc.png')
        RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    char_id = result.fetchone()[0]

    with patch("app.routers.jobs.process_workflow_job.delay"), \
         patch("app.routers.jobs.redis_client.set", new_callable=AsyncMock):

        res = await client.post("/api/v1/jobs/workflow", json={
            "brand_id": brand.id,
            "workflow_template_id": workflow.id,
            "workflow_type": "flat_lay_to_model",
            "inputs": {"character_id": char_id, "character_version_id": 99999}
        }, headers=editor_headers)

        assert res.status_code == 404
        assert "version" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_workflow_job_valid_character_and_version_succeeds(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Valid character and version from correct brand should succeed."""
    from sqlalchemy import text
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_headers = test_data["get_headers"]("editor")

    result = await db_session.execute(text("""
        INSERT INTO characters (brand_id, name, description, image_path)
        VALUES (:brand_id, 'Valid Char', 'desc', '/uploads/valid_char.png')
        RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    char_id = result.fetchone()[0]

    from datetime import datetime
    result = await db_session.execute(text("""
        INSERT INTO character_versions (character_id, version_number, config_overrides, created_at)
        VALUES (:char_id, 1, '{}', :created_at) RETURNING id
    """), {"char_id": char_id, "created_at": datetime.utcnow()})
    await db_session.commit()
    version_id = result.fetchone()[0]

    with patch("app.routers.jobs.process_workflow_job.delay"), \
         patch("app.routers.jobs.redis_client.set", new_callable=AsyncMock):

        res = await client.post("/api/v1/jobs/workflow", json={
            "brand_id": brand.id,
            "workflow_template_id": workflow.id,
            "workflow_type": "flat_lay_to_model",
            "inputs": {"character_id": char_id, "character_version_id": version_id}
        })
        assert res.status_code == 401 # Test request without headers returns 401

        res = await client.post("/api/v1/jobs/workflow", json={
            "brand_id": brand.id,
            "workflow_template_id": workflow.id,
            "workflow_type": "flat_lay_to_model",
            "inputs": {"character_id": char_id, "character_version_id": version_id}
        }, headers=editor_headers)
        assert res.status_code == 201


@pytest.mark.asyncio
async def test_workflow_job_does_not_fail_on_first_retry(db_session: AsyncSession, test_data: dict):
    """Workflow job should not mark as failed or refund credits on first retry attempt."""
    brand = test_data["brand"]
    editor_user = test_data["users"]["editor"]

    starting_credits = editor_user.credits
    editor_user.credits -= 1
    db_session.add(editor_user)
    await db_session.commit()

    # Create job that will fail (no source asset provided)
    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        status="pending",
        job_type="workflow",
        inputs={
            "workflow_type": "flat_lay_to_model"
        },
        outputs={}
    )
    db_session.add(job)
    await db_session.commit()

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker.redis_client.set", new_callable=AsyncMock), \
         patch("app.worker.dispatch_webhook.delay"):

        try:
            await _process_workflow_job_async(job.id, retries=0, max_retries=3)
        except Exception:
            pass

    await db_session.refresh(job)
    assert job.status != "failed"

    await db_session.refresh(editor_user)
    assert editor_user.credits == starting_credits - 1
