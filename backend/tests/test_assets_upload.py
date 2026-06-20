import json
import os
from unittest.mock import MagicMock
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.models.db import Asset, AssetTag
from app.services.storage import storage_service
from app.worker import process_asset_upload

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
    """Owner should be able to delete an asset; files removed and DB row gone."""
    brand = test_data["brand"]
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
        "brand_id": brand.id,
        "asset_type": "image",
        "metadata_json": json.dumps({})
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

    # Confirm DB row is gone
    result = await db_session.execute(select(Asset).where(Asset.id == asset_id))
    assert result.scalars().first() is None

    # Confirm tags cascade-deleted
    tag_result = await db_session.execute(select(AssetTag).where(AssetTag.asset_id == asset_id))
    assert tag_result.scalars().all() == []

    # Confirm all 3 files were requested for deletion (main + 2 thumbnails)
    assert len(deleted_files) == 3


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
