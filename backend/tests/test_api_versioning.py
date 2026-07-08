import pytest
from fastapi import status
from httpx import AsyncClient


# ========================== Path-Based Versioning Tests ==========

@pytest.mark.asyncio
async def test_v1_brands_accessible(client: AsyncClient, test_data: dict):
    """v1 brands endpoint should be accessible."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/brands", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_v2_brands_fallback_to_v1(client: AsyncClient, test_data: dict):
    """v2 brands endpoint should fall back to v1."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v2/brands", headers=owner_headers)
    # Should return 200 via fallback to v1
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_v2_assets_fallback_to_v1(client: AsyncClient, test_data: dict):
    """v2 assets endpoint should fall back to v1."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v2/assets", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_v2_search_fallback_to_v1(client: AsyncClient, test_data: dict):
    """v2 search endpoint should fall back to v1."""
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    res = await client.get(f"/api/v2/search/faceted?brand_id={brand.id}", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_v2_health_fallback(client: AsyncClient):
    """v2 health endpoint should fall back to v1."""
    from unittest.mock import patch, AsyncMock
    with patch("app.routers.health.async_session_maker") as mock_session, \
         patch("app.routers.health.aioredis.from_url") as mock_redis:

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db

        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping = AsyncMock(return_value=True)
        mock_redis_instance.aclose = AsyncMock()
        mock_redis.return_value = mock_redis_instance

        res = await client.get("/api/v2/health")
        assert res.status_code == status.HTTP_200_OK


# ========================== Header-Based Versioning Tests ========

@pytest.mark.asyncio
async def test_accept_version_header_v1(client: AsyncClient, test_data: dict):
    """Accept-Version: 1.0 should use v1 endpoints."""
    owner_headers = test_data["get_headers"]("owner")
    owner_headers["Accept-Version"] = "1.0"
    res = await client.get("/api/v1/brands", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_accept_version_header_v2(client: AsyncClient, test_data: dict):
    """Accept-Version: 2.0 on v1 path should still work via fallback."""
    owner_headers = test_data["get_headers"]("owner")
    owner_headers["Accept-Version"] = "2.0"
    res = await client.get("/api/v1/brands", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK


# ========================== Response Header Tests ================

@pytest.mark.asyncio
async def test_v1_response_includes_version_header(client: AsyncClient, test_data: dict):
    """v1 responses should include X-API-Version header."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/brands", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.headers.get("X-API-Version") == "1.0"


@pytest.mark.asyncio
async def test_v2_response_includes_version_and_fallback_header(client: AsyncClient, test_data: dict):
    """v2 fallback responses should include X-API-Version and X-API-Fallback headers."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v2/brands", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.headers.get("X-API-Version") == "2.0"
    assert res.headers.get("X-API-Fallback") == "v1"


# ========================== Auth Required Tests ==================

@pytest.mark.asyncio
async def test_v2_auth_required_still_enforced(client: AsyncClient):
    """v2 fallback should still enforce authentication."""
    res = await client.get("/api/v2/brands")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_v1_and_v2_same_data(client: AsyncClient, test_data: dict):
    """v1 and v2 should return same data via fallback."""
    owner_headers = test_data["get_headers"]("owner")
    res_v1 = await client.get("/api/v1/brands", headers=owner_headers)
    res_v2 = await client.get("/api/v2/brands", headers=owner_headers)
    assert res_v1.status_code == status.HTTP_200_OK
    assert res_v2.status_code == status.HTTP_200_OK
    assert res_v1.json() == res_v2.json()
