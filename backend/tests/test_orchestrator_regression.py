import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status
from httpx import AsyncClient

from app.middleware.auth import create_access_token, hash_password
from app.models.db import User

pytestmark = pytest.mark.integration


# ========================== Fixtures ==============================

@pytest.fixture(autouse=True)
def mock_redis_global():
    """Globally mock Redis client to avoid network connections and timeouts."""
    with patch("app.middleware.rate_limit.redis_client") as mock_redis:
        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_pipe.execute = AsyncMock(return_value=[None, 1, None, None])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        yield mock_redis, mock_pipe


# ========================== Orchestrator Tests =====================

@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint(client: AsyncClient):
    """Verify that the /metrics endpoint is exposed and returns Prometheus formatting."""
    res = await client.get("/metrics")
    assert res.status_code == status.HTTP_200_OK
    assert "# HELP" in res.text
    assert "campaigns_" not in res.text  # legacy campaign counters are gone


@pytest.mark.asyncio
async def test_admin_settings_get_unauthorized(client: AsyncClient):
    """Unauthorized requests to settings endpoint should be rejected."""
    res = await client.get("/api/v1/admin/settings")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_admin_settings_get_and_post(client: AsyncClient, db_session, test_data: dict, mock_redis_global):
    """Brand owners can read the settings; only platform admins can change them."""
    owner_headers = test_data["get_headers"]("owner")
    admin = User(email="platform-admin@modelens.ai", hashed_password=hash_password("pw"), full_name="Admin",
                 role="admin")
    db_session.add(admin)
    await db_session.commit()
    admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': admin.email})}"}
    mock_redis, mock_pipe = mock_redis_global

    # Mock Redis GET
    mock_redis.get = AsyncMock(return_value="15")
    mock_redis.set = AsyncMock(return_value=True)

    # Get settings
    res = await client.get("/api/v1/admin/settings", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["orchestrator_rate_limit"] == 15
    assert "metrics" in data

    # Post settings: a brand owner is refused, a platform admin is not
    res_post = await client.post("/api/v1/admin/settings", json={"orchestrator_rate_limit": 25}, headers=owner_headers)
    assert res_post.status_code == status.HTTP_403_FORBIDDEN
    mock_redis.set.assert_not_called()
    res_post = await client.post("/api/v1/admin/settings", json={"orchestrator_rate_limit": 25}, headers=admin_headers)
    assert res_post.status_code == status.HTTP_200_OK
    assert res_post.json()["orchestrator_rate_limit"] == 25
    mock_redis.set.assert_called_once_with("settings:orchestrator_rate_limit", "25")

