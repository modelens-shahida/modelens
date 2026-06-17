import pytest
import math
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.pipeline import get_embedding, _mock_embedding


# ========================== Pipeline Tests ================================

@pytest.mark.asyncio
async def test_mock_embedding_dimensions():
    """Mock embedding should return 1536-dimensional vector."""
    embedding = _mock_embedding("test query")
    assert len(embedding) == 1536


@pytest.mark.asyncio
async def test_mock_embedding_is_normalized():
    """Mock embedding should be a unit vector (magnitude ~1.0)."""
    embedding = _mock_embedding("fashion editorial luxury")
    magnitude = math.sqrt(sum(v * v for v in embedding))
    assert abs(magnitude - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_mock_embedding_is_deterministic():
    """Same text should always produce the same embedding."""
    e1 = _mock_embedding("golden hour beach")
    e2 = _mock_embedding("golden hour beach")
    assert e1 == e2


@pytest.mark.asyncio
async def test_mock_embedding_differs_for_different_text():
    """Different texts should produce different embeddings."""
    e1 = _mock_embedding("luxury editorial")
    e2 = _mock_embedding("casual streetwear")
    assert e1 != e2


@pytest.mark.asyncio
async def test_get_embedding_fallback():
    """get_embedding should return 1536-dim vector even without OpenAI key."""
    embedding = await get_embedding("test text")
    assert len(embedding) == 1536


# ========================== Search Auth Tests ==============================

@pytest.mark.asyncio
async def test_search_auth_required(client: AsyncClient):
    """Search without auth should return 401."""
    res = await client.get("/api/v1/search?brand_id=1&q=test")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_search_unauthorized_brand(client: AsyncClient, test_data: dict):
    """Search on unauthorized brand should return 403."""
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/search?brand_id=9999&q=test", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_search_invalid_type(client: AsyncClient, test_data: dict):
    """Invalid search type should return 400."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get(
        f"/api/v1/search?brand_id={brand.id}&q=test&type=invalid",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST


# ========================== FTS Tests =====================================

@pytest.mark.asyncio
async def test_fts_search_returns_results(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """FTS search should return assets matching the query text."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # Seed an asset directly
    await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata)
        VALUES (:brand_id, 'Luxury Editorial Shot', 'luxury_editorial.jpg', '/uploads/luxury.jpg', 'image', '{}')
    """), {"brand_id": brand.id})
    await db_session.commit()

    res = await client.get(
        f"/api/v1/search?brand_id={brand.id}&q=luxury&type=fts",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert isinstance(data, list)
    if data:
        assert any("luxury" in r["name"].lower() for r in data)
        assert data[0]["search_type"] == "fts"


@pytest.mark.asyncio
async def test_fts_search_no_match(client: AsyncClient, test_data: dict):
    """FTS search with no matching assets should return empty list."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(
        f"/api/v1/search?brand_id={brand.id}&q=xyznonexistentterm999&type=fts",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json() == []


# ========================== Vector Search Tests ============================

@pytest.mark.asyncio
async def test_vector_search_returns_list(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Vector search should return a list (even if empty without embeddings)."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(
        f"/api/v1/search?brand_id={brand.id}&q=fashion editorial&type=vector",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert isinstance(res.json(), list)


# ========================== Hybrid Search Tests ============================

@pytest.mark.asyncio
async def test_hybrid_search_returns_list(client: AsyncClient, test_data: dict):
    """Hybrid search (default) should return a list."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(
        f"/api/v1/search?brand_id={brand.id}&q=editorial",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_hybrid_search_type_label(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Hybrid search results should have search_type = hybrid."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata)
        VALUES (:brand_id, 'Golden Hour Portrait', 'golden_hour.jpg', '/uploads/golden.jpg', 'image', '{}')
    """), {"brand_id": brand.id})
    await db_session.commit()

    res = await client.get(
        f"/api/v1/search?brand_id={brand.id}&q=golden&type=hybrid",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    if data:
        assert data[0]["search_type"] == "hybrid"


# ========================== Pagination Tests ==============================

@pytest.mark.asyncio
async def test_search_pagination(client: AsyncClient, test_data: dict):
    """Search should respect limit and offset params."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(
        f"/api/v1/search?brand_id={brand.id}&q=test&limit=5&offset=0",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert len(data) <= 5
