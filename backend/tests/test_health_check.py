import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status
from httpx import AsyncClient


# ========================== Health Check Tests ===================

@pytest.mark.asyncio
async def test_health_check_all_healthy(client: AsyncClient):
    """Health check should return 200 when all services are healthy."""
    with patch("app.routers.health.async_session_maker") as mock_session,          patch("app.routers.health.aioredis.from_url") as mock_redis:

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db

        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping = AsyncMock(return_value=True)
        mock_redis_instance.aclose = AsyncMock()
        mock_redis.return_value = mock_redis_instance

        res = await client.get("/api/v1/health")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["status"] == "healthy"
        assert data["services"]["database"] == "healthy"
        assert data["services"]["redis"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_db_down(client: AsyncClient):
    """Health check should return 503 when database is down."""
    with patch("app.routers.health.async_session_maker") as mock_session,          patch("app.routers.health.aioredis.from_url") as mock_redis:

        mock_session.return_value.__aenter__.side_effect = Exception("Connection refused")

        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping = AsyncMock(return_value=True)
        mock_redis_instance.aclose = AsyncMock()
        mock_redis.return_value = mock_redis_instance

        res = await client.get("/api/v1/health")
        assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = res.json()
        assert data["status"] == "unhealthy"
        assert "unhealthy" in data["services"]["database"]
        assert data["services"]["redis"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_redis_down(client: AsyncClient):
    """Health check should return 503 when Redis is down."""
    with patch("app.routers.health.async_session_maker") as mock_session,          patch("app.routers.health.aioredis.from_url") as mock_redis:

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db

        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping.side_effect = Exception("Redis connection refused")
        mock_redis.return_value = mock_redis_instance

        res = await client.get("/api/v1/health")
        assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = res.json()
        assert data["status"] == "unhealthy"
        assert data["services"]["database"] == "healthy"
        assert "unhealthy" in data["services"]["redis"]


@pytest.mark.asyncio
async def test_health_check_both_down(client: AsyncClient):
    """Health check should return 503 when both DB and Redis are down."""
    with patch("app.routers.health.async_session_maker") as mock_session,          patch("app.routers.health.aioredis.from_url") as mock_redis:

        mock_session.return_value.__aenter__.side_effect = Exception("DB down")

        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping.side_effect = Exception("Redis down")
        mock_redis.return_value = mock_redis_instance

        res = await client.get("/api/v1/health")
        assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = res.json()
        assert data["status"] == "unhealthy"
        assert "unhealthy" in data["services"]["database"]
        assert "unhealthy" in data["services"]["redis"]


@pytest.mark.asyncio
async def test_health_check_no_auth_required(client: AsyncClient):
    """Health check should be accessible without authentication."""
    with patch("app.routers.health.async_session_maker") as mock_session,          patch("app.routers.health.aioredis.from_url") as mock_redis:

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db

        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping = AsyncMock(return_value=True)
        mock_redis_instance.aclose = AsyncMock()
        mock_redis.return_value = mock_redis_instance

        # No auth headers
        res = await client.get("/api/v1/health")
        assert res.status_code != status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_legacy_health_endpoint(client: AsyncClient):
    """Legacy /health endpoint should still return 200."""
    res = await client.get("/health")
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "healthy"
