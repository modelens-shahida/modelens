import json
import os
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta, UTC
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.models.db import Asset, AssetTag
from app.services.storage import storage_service
from app.worker import process_asset_upload

class MockSessionContext:
    def __init__(self, session):
        self.session = session
    async def __aenter__(self):
        return self.session
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.fixture(autouse=True)
def mock_external_deps(monkeypatch):
    """Fixture to mock storage existence verification and Celery task dispatch."""
    # Mock file existence check to always return True for tests
    monkeypatch.setattr(storage_service, "verify_file_exists", lambda name: True)
    
    # Mock celery task .delay call
    mock_delay = MagicMock()
    monkeypatch.setattr(process_asset_upload, "delay", mock_delay)
    
    return mock_delay


@pytest.mark.asyncio
async def test_upload_url_local_backend(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    
    # Set backend to local storage
    storage_service.backend = "local"
    
    payload = {
        "filename": "product_shot.png",
        "brand_id": brand.id,
        "asset_type": "image",
        "metadata_json": json.dumps({"category": "furniture"})
    }
    
    res = await client.post("/api/v1/assets/upload-url", json=payload, headers=editor_headers)
    assert res.status_code == 200
    data = res.json()
    
    assert "asset_id" in data
    assert "upload_url" in data
    assert "upload-mock" in data["upload_url"]  # Local endpoint
    assert data["method"] == "PUT"


@pytest.mark.asyncio
async def test_upload_url_s3_backend(client: AsyncClient, test_data: dict, monkeypatch):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    
    # Set config to S3 storage
    storage_service.backend = "s3"
    storage_service.bucket = "test-bucket"
    
    # Mock S3 client generate_presigned_url call
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-bucket/mock-filename.png"
    monkeypatch.setattr(storage_service, "_s3_client", mock_s3)
    
    payload = {
        "filename": "s3_shot.png",
        "brand_id": brand.id,
        "asset_type": "image"
    }
    
    try:
        res = await client.post("/api/v1/assets/upload-url", json=payload, headers=editor_headers)
        assert res.status_code == 200
        data = res.json()
        
        assert "asset_id" in data
        assert data["upload_url"] == "https://s3.amazonaws.com/test-bucket/mock-filename.png"
        assert data["method"] == "PUT"
    finally:
        # Restore defaults
        storage_service.backend = "local"
        storage_service.bucket = None


@pytest.mark.asyncio
async def test_mock_local_put_endpoint(client: AsyncClient):
    # Test uploading raw binary content directly to the mock endpoint
    binary_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."
    unique_filename = "test-mock-upload.png"
    
    res = await client.put(
        f"/api/v1/assets/upload-mock/{unique_filename}",
        content=binary_data,
        headers={"Content-Type": "application/octet-stream"}
    )
    
    assert res.status_code == 200
    assert res.json()["message"] == "Mock file upload successful"
    
    # Verify local file was created
    local_path = f"uploads/{unique_filename}"
    assert os.path.exists(local_path)
    
    # Cleanup file
    if os.path.exists(local_path):
        os.remove(local_path)


@pytest.mark.asyncio
async def test_confirm_upload_and_tagging(
    client: AsyncClient, 
    db_session: AsyncSession, 
    test_data: dict, 
    mock_external_deps
):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    mock_delay = mock_external_deps
    
    # 1. Create a pending asset record first via the upload-url endpoint
    payload = {
        "filename": "jeans.jpg",
        "brand_id": brand.id,
        "asset_type": "image",
        "metadata_json": json.dumps({
            "category": "apparel",
            "tags": ["denim", "blue", "slim-fit"]
        })
    }
    
    res = await client.post("/api/v1/assets/upload-url", json=payload, headers=editor_headers)
    assert res.status_code == 200
    asset_id = res.json()["asset_id"]
    
    # Verify asset is stored as pending
    asset_query = select(Asset).where(Asset.id == asset_id)
    db_res = await db_session.execute(asset_query)
    asset = db_res.scalars().first()
    assert asset is not None
    assert asset.meta["status"] == "pending"

    # 2. Confirm the upload
    confirm_payload = {"asset_id": asset_id}
    res = await client.post("/api/v1/assets/confirm", json=confirm_payload, headers=editor_headers)
    assert res.status_code == 200
    assert res.json()["asset"]["status"] == "active"
    
    # 3. Verify asset is updated to active in DB
    db_session.expire(asset)
    db_res = await db_session.execute(asset_query)
    asset = db_res.scalars().first()
    assert asset.meta["status"] == "active"
    
    # 4. Verify tags are extracted and saved
    tags_query = select(AssetTag).where(AssetTag.asset_id == asset_id)
    tags_res = await db_session.execute(tags_query)
    tags = [t.tag for t in tags_res.scalars().all()]
    
    # Assert category ('apparel') and tags list ('denim', 'blue', 'slim-fit') were added as database tags
    assert "apparel" in tags
    assert "denim" in tags
    assert "blue" in tags
    assert "slim-fit" in tags
    assert len(tags) == 4
    
    # 5. Verify Celery task process_asset_upload was triggered
    mock_delay.assert_called_once_with(asset_id)


# ========================== Asset Deletion Tests ===================

@pytest.mark.asyncio
async def test_delete_asset_owner_success(client: AsyncClient, db_session: AsyncSession, test_data: dict, monkeypatch):
    """Owner should be able to soft delete an asset; files not removed immediately, and DB row marked soft-deleted."""
    brand = test_data["brand"]
    brand_id = brand.id
    owner_headers = test_data["get_headers"]("owner")
    editor_headers = test_data["get_headers"]("editor")

    deleted_files = []
    monkeypatch.setattr(
        storage_service,
        "delete_file",
        lambda filename: deleted_files.append(filename) or True
    )

    # Create an asset via upload-url + confirm flow
    payload = {
        "filename": "to_delete.png",
        "brand_id": brand_id,
        "asset_type": "image",
        "metadata_json": json.dumps({
            "category": "apparel",
            "tags": ["denim"]
        })
    }
    res = await client.post("/api/v1/assets/upload-url", json=payload, headers=editor_headers)
    assert res.status_code == 200
    asset_id = res.json()["asset_id"]

    res = await client.post("/api/v1/assets/confirm", json={"asset_id": asset_id}, headers=editor_headers)
    assert res.status_code == 200

    # Manually set thumbnail metadata to simulate processed asset
    asset_result = await db_session.execute(select(Asset).where(Asset.id == asset_id))
    asset = asset_result.scalars().first()
    updated_meta = dict(asset.meta)
    updated_meta["thumbnail_256"] = "/uploads/thumb_256_to_delete.png"
    updated_meta["thumbnail_512"] = "/uploads/thumb_512_to_delete.png"
    asset.meta = updated_meta
    await db_session.commit()

    # Delete as owner
    res = await client.delete(f"/api/v1/assets/{asset_id}", headers=owner_headers)
    assert res.status_code == 204

    # Confirm DB row is NOT gone, but has deleted_at set
    db_session.expire(asset)
    result = await db_session.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalars().first()
    assert asset is not None
    assert asset.deleted_at is not None

    # Confirm tags are not cascade-deleted yet
    db_session.expire_all()
    tag_result = await db_session.execute(select(AssetTag).where(AssetTag.asset_id == asset_id))
    assert len(tag_result.scalars().all()) > 0

    # Confirm NO files were requested for deletion (since deletion is soft)
    assert len(deleted_files) == 0

    # Confirm the asset is hidden from normal list endpoint
    list_res = await client.get(f"/api/v1/assets?brand_id={brand_id}", headers=owner_headers)
    assert list_res.status_code == 200
    asset_ids = [a["id"] for a in list_res.json()]
    assert asset_id not in asset_ids


@pytest.mark.asyncio
async def test_delete_asset_forbidden_for_editor_and_viewer(client: AsyncClient, test_data: dict, monkeypatch):
    """Editor and viewer roles should receive 403 Forbidden when deleting an asset."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    viewer_headers = test_data["get_headers"]("viewer")

    monkeypatch.setattr(storage_service, "delete_file", lambda filename: True)

    payload = {
        "filename": "protected_asset.png",
        "brand_id": brand.id,
        "asset_type": "image",
        "metadata_json": json.dumps({})
    }
    res = await client.post("/api/v1/assets/upload-url", json=payload, headers=editor_headers)
    assert res.status_code == 200
    asset_id = res.json()["asset_id"]

    res = await client.post("/api/v1/assets/confirm", json={"asset_id": asset_id}, headers=editor_headers)
    assert res.status_code == 200

    # Editor cannot delete
    res = await client.delete(f"/api/v1/assets/{asset_id}", headers=editor_headers)
    assert res.status_code == 403

    # Viewer cannot delete
    res = await client.delete(f"/api/v1/assets/{asset_id}", headers=viewer_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_delete_nonexistent_asset_returns_404(client: AsyncClient, test_data: dict):
    """Deleting a non-existent asset should return 404."""
    owner_headers = test_data["get_headers"]("owner")

    res = await client.delete("/api/v1/assets/999999", headers=owner_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_trash_and_restore_asset(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Verify listing trash, restoring a soft-deleted asset, and access controls."""
    brand = test_data["brand"]
    brand_id = brand.id
    owner_headers = test_data["get_headers"]("owner")
    editor_headers = test_data["get_headers"]("editor")
    viewer_headers = test_data["get_headers"]("viewer")

    # 1. Create and confirm an asset
    payload = {
        "filename": "trash_test.png",
        "brand_id": brand_id,
        "asset_type": "image",
        "metadata_json": json.dumps({})
    }
    res = await client.post("/api/v1/assets/upload-url", json=payload, headers=editor_headers)
    assert res.status_code == 200
    asset_id = res.json()["asset_id"]

    res = await client.post("/api/v1/assets/confirm", json={"asset_id": asset_id}, headers=editor_headers)
    assert res.status_code == 200

    # 2. Soft-delete the asset
    res = await client.delete(f"/api/v1/assets/{asset_id}", headers=owner_headers)
    assert res.status_code == 204

    # 3. Retrieve trash (viewer role minimum)
    res = await client.get(f"/api/v1/assets/trash?brand_id={brand_id}", headers=viewer_headers)
    assert res.status_code == 200
    trash_ids = [a["id"] for a in res.json()]
    assert asset_id in trash_ids

    # 4. Attempt to restore with viewer (should fail with 403)
    res = await client.post(f"/api/v1/assets/{asset_id}/restore", headers=viewer_headers)
    assert res.status_code == 403

    # 5. Restore with editor (should succeed)
    res = await client.post(f"/api/v1/assets/{asset_id}/restore", headers=editor_headers)
    assert res.status_code == 200
    assert res.json()["message"] == "Asset restored successfully."

    # 6. Verify it is no longer in trash, but back in active assets list
    res = await client.get(f"/api/v1/assets/trash?brand_id={brand_id}", headers=viewer_headers)
    assert res.status_code == 200
    trash_ids = [a["id"] for a in res.json()]
    assert asset_id not in trash_ids

    res = await client.get(f"/api/v1/assets?brand_id={brand_id}", headers=viewer_headers)
    assert res.status_code == 200
    active_ids = [a["id"] for a in res.json()]
    assert asset_id in active_ids


@pytest.mark.asyncio
async def test_worker_purge_deleted_assets(db_session: AsyncSession, test_data: dict, monkeypatch):
    """Test the daily Celery task that permanently purges soft-deleted assets older than 30 days."""
    brand = test_data["brand"]
    brand_id = brand.id

    # Mock storage_service delete_file
    deleted_files = []
    monkeypatch.setattr(
        storage_service,
        "delete_file",
        lambda filename: deleted_files.append(filename) or True
    )

    # 1. Create two assets: one deleted 31 days ago (should be purged), one deleted 5 days ago (should not be purged)
    asset_to_purge = Asset(
        brand_id=brand_id,
        name="old_deleted.png",
        filename="old_deleted.png",
        storage_path="uploads/old_deleted.png",
        asset_type="image",
        deleted_at=datetime.now(UTC) - timedelta(days=31),
        meta={"unique_filename": "old_deleted.png", "status": "active", "thumbnail_256": "thumb_256_old.png"}
    )
    asset_to_keep = Asset(
        brand_id=brand_id,
        name="recent_deleted.png",
        filename="recent_deleted.png",
        storage_path="uploads/recent_deleted.png",
        asset_type="image",
        deleted_at=datetime.now(UTC) - timedelta(days=5),
        meta={"unique_filename": "recent_deleted.png", "status": "active", "thumbnail_256": "thumb_256_recent.png"}
    )
    db_session.add(asset_to_purge)
    db_session.add(asset_to_keep)
    await db_session.commit()
    await db_session.refresh(asset_to_purge)
    await db_session.refresh(asset_to_keep)

    asset_to_purge_id = asset_to_purge.id
    asset_to_keep_id = asset_to_keep.id

    # Seed tags for the purged asset to test cascade delete
    tag1 = AssetTag(asset_id=asset_to_purge_id, tag="old")
    db_session.add(tag1)
    await db_session.commit()

    # 2. Trigger worker purge task with mocked async_session_maker
    from app.worker import _purge_deleted_assets_async
    db_session.expire_all()
    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)):
        await _purge_deleted_assets_async()

    # 3. Verify asset_to_purge is completely gone from DB
    db_session.expire_all()
    res_purged = await db_session.execute(select(Asset).where(Asset.id == asset_to_purge_id))
    assert res_purged.scalars().first() is None

    # Verify its tags are cascade deleted
    res_tags = await db_session.execute(select(AssetTag).where(AssetTag.asset_id == asset_to_purge_id))
    assert len(res_tags.scalars().all()) == 0

    # Verify its files are purged from storage (main + thumbnail)
    assert "old_deleted.png" in deleted_files
    assert "thumb_256_old.png" in deleted_files

    # 4. Verify asset_to_keep still exists in DB
    res_keep = await db_session.execute(select(Asset).where(Asset.id == asset_to_keep_id))
    assert res_keep.scalars().first() is not None
    assert "recent_deleted.png" not in deleted_files
