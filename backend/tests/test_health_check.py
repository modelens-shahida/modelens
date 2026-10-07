import asyncio
from contextlib import contextmanager

import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status
from httpx import AsyncClient

from app.main import app


# ========================== Helpers ===============================

@contextmanager
def dependencies(db_up=True, redis_up=True, db_error="Connection refused to db.internal:5432",
                 redis_error="Error connecting to redis://:hunter2@redis.internal:6379"):
    """Mock the DB session and Redis client the health router uses."""
    with patch("app.routers.health.async_session_maker") as mock_session, \
         patch("app.routers.health.aioredis.from_url") as mock_redis:
        if db_up:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
        else:
            mock_session.return_value.__aenter__.side_effect = Exception(db_error)

        redis = AsyncMock()
        if not redis_up:
            redis.ping.side_effect = Exception(redis_error)
        mock_redis.return_value = redis
        yield mock_session, redis


# ========================== Readiness: GET /api/v1/health ========

@pytest.mark.asyncio
async def test_health_check_all_healthy(client: AsyncClient):
    """Readiness should return 200 when all services are healthy."""
    with dependencies():
        res = await client.get("/api/v1/health")
    assert res.status_code == status.HTTP_200_OK
    assert res.json() == {"status": "healthy", "services": {"database": "healthy", "redis": "healthy"}}


@pytest.mark.asyncio
async def test_health_check_db_down(client: AsyncClient):
    """Readiness should return 503 naming the database when it is down."""
    with dependencies(db_up=False):
        res = await client.get("/api/v1/health")
    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = res.json()
    assert data["status"] == "unhealthy"
    assert data["services"] == {"database": "unhealthy", "redis": "healthy"}
    assert data["failing"] == ["database"]


@pytest.mark.asyncio
async def test_health_check_redis_down(client: AsyncClient):
    """Readiness should return 503 naming Redis when it is down, and still close the client."""
    with dependencies(redis_up=False) as (_, redis):
        res = await client.get("/api/v1/health")
    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = res.json()
    assert data["status"] == "unhealthy"
    assert data["services"] == {"database": "healthy", "redis": "unhealthy"}
    assert data["failing"] == ["redis"]
    redis.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_check_both_down(client: AsyncClient):
    """Readiness should return 503 naming both components when both are down."""
    with dependencies(db_up=False, redis_up=False):
        res = await client.get("/api/v1/health")
    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = res.json()
    assert data["status"] == "unhealthy"
    assert data["failing"] == ["database", "redis"]


@pytest.mark.asyncio
async def test_health_check_hides_internal_details(client: AsyncClient):
    """A failing check must not leak hostnames, connection strings or exception text."""
    with dependencies(db_up=False, redis_up=False):
        res = await client.get("/api/v1/health")
    body = res.text
    for leaked in ("db.internal", "redis.internal", "hunter2", "5432", "6379", "Connection refused",
                   "Error connecting", "Traceback"):
        assert leaked not in body


@pytest.mark.asyncio
async def test_health_check_hung_dependency_times_out(client: AsyncClient):
    """A dependency that never answers is reported unhealthy instead of hanging the probe."""
    async def never_answers():
        await asyncio.sleep(60)

    with dependencies() as (_, redis), patch("app.routers.health.CHECK_TIMEOUT_SECONDS", 0.05):
        redis.ping.side_effect = never_answers
        res = await asyncio.wait_for(client.get("/api/v1/health"), timeout=5)
    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert res.json()["failing"] == ["redis"]


@pytest.mark.asyncio
async def test_health_check_no_auth_required(client: AsyncClient):
    """Readiness should be accessible without authentication."""
    with dependencies():
        res = await client.get("/api/v1/health")
    assert res.status_code == status.HTTP_200_OK


# ========================== Liveness: GET /api/v1/health/live ====

@pytest.mark.asyncio
async def test_liveness_ok_when_dependencies_down(client: AsyncClient):
    """Liveness only reflects the process: 200 even with DB and Redis down, and neither is touched."""
    with dependencies(db_up=False, redis_up=False) as (mock_session, redis):
        res = await client.get("/api/v1/health/live")
    assert res.status_code == status.HTTP_200_OK
    assert res.json() == {"status": "alive"}
    mock_session.assert_not_called()
    redis.ping.assert_not_called()


@pytest.mark.asyncio
async def test_liveness_no_auth_required(client: AsyncClient):
    res = await client.get("/api/v1/health/live")
    assert res.status_code == status.HTTP_200_OK


# ========================== OpenAPI / exemptions ==================

def test_health_routes_have_no_auth_or_rate_limit_dependencies():
    """Neither probe may depend on auth or a RateLimiter."""
    routes = {r.path: r for r in app.routes if getattr(r, "path", "") in ("/api/v1/health", "/api/v1/health/live")}
    assert set(routes) == {"/api/v1/health", "/api/v1/health/live"}
    for route in routes.values():
        assert route.dependant.dependencies == []


def test_health_routes_in_openapi():
    paths = app.openapi()["paths"]
    readiness = paths["/api/v1/health"]["get"]
    liveness = paths["/api/v1/health/live"]["get"]
    assert readiness["operationId"] == "get_health_readiness"
    assert liveness["operationId"] == "get_health_liveness"
    assert "503" in readiness["responses"]
    assert "security" not in readiness and "security" not in liveness


@pytest.mark.asyncio
async def test_legacy_health_endpoint(client: AsyncClient):
    """Legacy /health endpoint should still return 200."""
    res = await client.get("/health")
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "healthy"
