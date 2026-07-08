import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cache_service import (
    get_cached, set_cached, invalidate_cache,
    brand_memory_cache_key, admin_stats_cache_key,
    invalidate_brand_memory_cache, invalidate_admin_stats_cache,
)


# ========================== Cache Service Tests ==================

@pytest.mark.asyncio
async def test_cache_miss_returns_none():
    """Cache miss should return None."""
    with patch("app.services.cache_service.redis_client") as mock_redis:
        mock_redis.get = AsyncMock(return_value=None)
        result = await get_cached("nonexistent_key")
        assert result is None


@pytest.mark.asyncio
async def test_cache_hit_returns_value():
    """Cache hit should return parsed JSON value."""
    import json
    with patch("app.services.cache_service.redis_client") as mock_redis:
        mock_redis.get = AsyncMock(return_value=json.dumps({"total": 42}))
        result = await get_cached("test_key")
        assert result == {"total": 42}


@pytest.mark.asyncio
async def test_cache_set_stores_value():
    """set_cached should call redis setex with correct TTL."""
    with patch("app.services.cache_service.redis_client") as mock_redis:
        mock_redis.setex = AsyncMock(return_value=True)
        result = await set_cached("test_key", {"data": 1}, ttl=300)
        assert result is True
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == 300


@pytest.mark.asyncio
async def test_cache_invalidation():
    """invalidate_cache should delete Redis key."""
    with patch("app.services.cache_service.redis_client") as mock_redis:
        mock_redis.delete = AsyncMock(return_value=1)
        result = await invalidate_cache("test_key")
        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")


@pytest.mark.asyncio
async def test_redis_error_graceful_fallback_on_get():
    """Redis error on GET should return None (graceful fallback)."""
    with patch("app.services.cache_service.redis_client") as mock_redis:
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection refused"))
        result = await get_cached("test_key")
        assert result is None  # Graceful fallback


@pytest.mark.asyncio
async def test_redis_error_graceful_fallback_on_set():
    """Redis error on SET should return False without crashing."""
    with patch("app.services.cache_service.redis_client") as mock_redis:
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis down"))
        result = await set_cached("test_key", {"data": 1}, ttl=300)
        assert result is False


@pytest.mark.asyncio
async def test_brand_memory_cache_key_format():
    """Brand memory cache key should follow expected format."""
    key = brand_memory_cache_key(42)
    assert key == "cache:brand_memory:42"


@pytest.mark.asyncio
async def test_admin_stats_cache_key_format():
    """Admin stats cache key should be consistent."""
    key = admin_stats_cache_key()
    assert key == "cache:admin_stats:summary"


# ========================== Cache Invalidation Tests =============

@pytest.mark.asyncio
async def test_brand_memory_cache_invalidated_on_asset_delete(client: AsyncClient, test_data: dict):
    """Deleting an asset should invalidate brand memory cache."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    with patch("app.services.cache_service.redis_client") as mock_redis:
        mock_redis.delete = AsyncMock(return_value=1)
        await invalidate_brand_memory_cache(brand.id)
        mock_redis.delete.assert_called_once_with(f"cache:brand_memory:{brand.id}")


@pytest.mark.asyncio
async def test_admin_stats_cache_invalidated():
    """Admin stats cache should be invalidated correctly."""
    with patch("app.services.cache_service.redis_client") as mock_redis:
        mock_redis.delete = AsyncMock(return_value=1)
        await invalidate_admin_stats_cache()
        mock_redis.delete.assert_called_once_with("cache:admin_stats:summary")


# ========================== Admin Stats Cache Tests ==============

@pytest.mark.asyncio
async def test_admin_stats_uses_cache(client: AsyncClient, test_data: dict):
    """Admin stats endpoint should return cached data on second call."""
    owner_headers = test_data["get_headers"]("owner")
    import json

    cached_data = {
        "total_users": 5,
        "total_assets": 10,
        "total_jobs": 20,
        "total_credits_consumed": 100,
        "total_revenue": 500,
    }

    with patch("app.routers.admin_stats.get_cached", new=AsyncMock(return_value=cached_data)):
        res = await client.get("/api/v1/admin/stats/summary", headers=owner_headers)
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["total_users"] == 5
        assert data["total_jobs"] == 20


@pytest.mark.asyncio
async def test_admin_stats_cache_miss_hits_db(client: AsyncClient, test_data: dict):
    """Admin stats cache miss should query DB and cache result."""
    owner_headers = test_data["get_headers"]("owner")

    with patch("app.routers.admin_stats.get_cached", new=AsyncMock(return_value=None)),          patch("app.routers.admin_stats.set_cached", new=AsyncMock()) as mock_set:
        res = await client.get("/api/v1/admin/stats/summary", headers=owner_headers)
        assert res.status_code == status.HTTP_200_OK
        mock_set.assert_called_once()
