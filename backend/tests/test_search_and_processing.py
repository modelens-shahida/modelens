import json
import os
import hashlib
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import Asset, AssetTag, AIJob
from app.services.storage import storage_service
from app.worker import _process_asset_upload_async


@pytest.fixture
def mock_image_file():
    """Generates a small 1x1 pixel PNG file bytes."""
    import io
    from PIL import Image
    img = Image.new("RGBA", (1, 1), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_celery_asset_processing(
    client: AsyncClient, 
    db_session: AsyncSession, 
    test_data: dict, 
    mock_image_file: bytes
):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # 1. Create a mock local file
    unique_filename = "test_processing_file.png"
    storage_service.backend = "local"
    storage_service.save_file_bytes(unique_filename, mock_image_file)

    # 2. Add asset record in database with status='pending'
    asset = Asset(
        brand_id=brand.id,
        name="Test Process Image",
        filename="test_image.png",
        storage_path=f"/uploads/{unique_filename}",
        asset_type="image",
        meta={"status": "pending", "unique_filename": unique_filename}
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    # 3. Trigger async worker task processing directly with mocked database session maker
    from unittest.mock import patch

    class MockSessionContext:
        def __init__(self, session):
            self.session = session
        async def __aenter__(self):
            return self.session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    asset_id = asset.id

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)):
        await _process_asset_upload_async(asset_id)

    # 4. Verify asset was updated in DB
    db_session.expire(asset)
    res = await db_session.execute(select(Asset).where(Asset.id == asset_id))
    processed_asset = res.scalars().first()

    assert processed_asset.meta["status"] == "active"
    assert processed_asset.meta["sha256"] == hashlib.sha256(mock_image_file).hexdigest()
    assert processed_asset.meta["width"] == 1
    assert processed_asset.meta["height"] == 1
    assert "thumbnail_url" in processed_asset.meta
    assert "preview_url" in processed_asset.meta

    # Verify thumbnails are actually created on local storage
    thumb_name = os.path.basename(processed_asset.meta["thumbnail_url"])
    preview_name = os.path.basename(processed_asset.meta["preview_url"])
    assert storage_service.verify_file_exists(thumb_name)
    assert storage_service.verify_file_exists(preview_name)

    # Verify associated validation AIJob completed
    job_res = await db_session.execute(
        select(AIJob).where(AIJob.asset_id == asset_id, AIJob.job_type == "metadata_validation")
    )
    job = job_res.scalars().first()
    assert job is not None
    assert job.status == "completed"

    # Cleanup local test files
    for fname in [unique_filename, thumb_name, preview_name]:
        lpath = os.path.join("uploads", fname)
        if os.path.exists(lpath):
            os.remove(lpath)


@pytest.mark.asyncio
async def test_search_and_similarity_endpoints(
    client: AsyncClient, 
    db_session: AsyncSession, 
    test_data: dict
):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # 1. Create multiple assets with distinct names and metadata
    asset1 = Asset(
        brand_id=brand.id,
        name="Cool Denim Hoodie",
        filename="hoodie.jpg",
        storage_path="/uploads/hoodie.jpg",
        asset_type="image",
        meta={"status": "active", "style": "vintage"}
    )
    asset2 = Asset(
        brand_id=brand.id,
        name="Summer Sun Hat",
        filename="hat.jpg",
        storage_path="/uploads/hat.jpg",
        asset_type="image",
        meta={"status": "active", "style": "beachwear"}
    )
    db_session.add(asset1)
    db_session.add(asset2)
    await db_session.commit()
    await db_session.refresh(asset1)
    await db_session.refresh(asset2)

    # 2. Add embeddings for similarity testing (1536 dimensions)
    mock_emb1 = [0.1] * 1536
    mock_emb2 = [0.9] * 1536
    tag1 = AssetTag(asset_id=asset1.id, tag="vintage-denim", embedding=mock_emb1)
    tag2 = AssetTag(asset_id=asset2.id, tag="sun-beach", embedding=mock_emb2)
    db_session.add(tag1)
    db_session.add(tag2)
    await db_session.commit()

    # 3. Test Full-Text Search (FTS)
    res = await client.get(
        f"/api/v1/assets/search?q=Denim&brand_id={brand.id}",
        headers=editor_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "Cool Denim Hoodie"

    # Test FTS matching metadata
    res = await client.get(
        f"/api/v1/assets/search?q=beachwear&brand_id={brand.id}",
        headers=editor_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "Summer Sun Hat"

    # 4. Test Vector Similarity Search (ANN)
    # Search with a query vector close to mock_emb1 ([0.1] * 1536)
    query_vector = [0.12] * 1536
    payload = {
        "embedding": query_vector,
        "brand_id": brand.id,
        "limit": 5
    }
    res = await client.post(
        "/api/v1/assets/search/similar",
        json=payload,
        headers=editor_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    # First result should be "Cool Denim Hoodie" because [0.12]*1536 is much closer to [0.1]*1536 than [0.9]*1536
    assert data[0]["name"] == "Cool Denim Hoodie"
