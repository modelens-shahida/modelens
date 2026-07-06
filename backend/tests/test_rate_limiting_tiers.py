import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import Brand
from app.middleware.rate_limit import TIER_LIMITS, invalidate_brand_tier_cache


# ========================== Tier Definition Tests ================

def test_tier_limits_defined():
    """All three tiers should be defined with correct keys."""
    for tier in ["free", "growth", "enterprise"]:
        assert tier in TIER_LIMITS
        assert "rpm" in TIER_LIMITS[tier]
        assert "rpd" in TIER_LIMITS[tier]
        assert "monthly_credits" in TIER_LIMITS[tier]


def test_tier_limits_ascending():
    """Higher tiers should have higher limits."""
    assert TIER_LIMITS["growth"]["rpm"] > TIER_LIMITS["free"]["rpm"]
    assert TIER_LIMITS["enterprise"]["rpm"] > TIER_LIMITS["growth"]["rpm"]
    assert TIER_LIMITS["enterprise"]["monthly_credits"] > TIER_LIMITS["growth"]["monthly_credits"]


# ========================== Credit Quota Tests ===================

@pytest.mark.asyncio
async def test_credit_quota_exhausted_returns_402(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Brand with exhausted monthly credits should get 402 on credit-consuming endpoints."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # Set brand credits_used_this_month to exceed quota
    result = await db_session.execute(select(Brand).where(Brand.id == brand.id))
    b = result.scalars().first()
    b.monthly_credit_quota = 10
    b.credits_used_this_month = 10
    await db_session.commit()

    # Invalidate cache
    await invalidate_brand_tier_cache(brand.id)

    # Mock the rate limiter to trigger credit check
    from app.middleware.rate_limit import _get_brand_tier_cached
    with patch("app.middleware.rate_limit._get_brand_tier_cached", new=AsyncMock(return_value={
        "tier": "free",
        "monthly_credit_quota": 10,
        "credits_used_this_month": 10,
    })):
        with patch("app.middleware.rate_limit._resolve_identifier", new=AsyncMock(return_value=("user", "1", brand.id))):
            from app.middleware.rate_limit import RateLimiter
            limiter = RateLimiter(check_credit_quota=True)
            from fastapi import Request
            mock_request = MagicMock()
            mock_request.headers = {"authorization": "Bearer test"}
            mock_request.url.path = "/api/v1/jobs/generate"
            mock_request.client.host = "127.0.0.1"

            with pytest.raises(Exception) as exc_info:
                await limiter(mock_request)
            assert "402" in str(exc_info.value.status_code) or exc_info.value.status_code == 402


@pytest.mark.asyncio
async def test_credit_quota_not_exhausted_passes(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Brand with available credits should not get 402."""
    brand = test_data["brand"]

    result = await db_session.execute(select(Brand).where(Brand.id == brand.id))
    b = result.scalars().first()
    b.monthly_credit_quota = 100
    b.credits_used_this_month = 50
    await db_session.commit()

    await invalidate_brand_tier_cache(brand.id)

    with patch("app.middleware.rate_limit._get_brand_tier_cached", new=AsyncMock(return_value={
        "tier": "free",
        "monthly_credit_quota": 100,
        "credits_used_this_month": 50,
    })):
        with patch("app.middleware.rate_limit._resolve_identifier", new=AsyncMock(return_value=("user", "1", brand.id))):
            with patch("app.middleware.rate_limit.redis_client") as mock_redis:
                mock_pipe = AsyncMock()
                mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
                mock_pipe.__aexit__ = AsyncMock(return_value=None)
                mock_pipe.execute = AsyncMock(return_value=[None, 1, None, None])
                mock_redis.pipeline.return_value = mock_pipe

                from app.middleware.rate_limit import RateLimiter
                from fastapi import Request
                mock_request = MagicMock()
                mock_request.headers = {"authorization": "Bearer test"}
                mock_request.url.path = "/api/v1/jobs/generate"
                mock_request.client.host = "127.0.0.1"

                limiter = RateLimiter(check_credit_quota=True)
                # Should not raise 402
                await limiter(mock_request)


# ========================== Cache Invalidation Tests =============

@pytest.mark.asyncio
async def test_cache_invalidation():
    """Cache invalidation should delete Redis key."""
    with patch("app.middleware.rate_limit.redis_client") as mock_redis:
        mock_redis.delete = AsyncMock()
        await invalidate_brand_tier_cache(1)
        mock_redis.delete.assert_called_once_with("brand_tier:1")


# ========================== Monthly Reset Tests ==================

@pytest.mark.asyncio
async def test_monthly_reset_resets_all_brands(db_session: AsyncSession, test_data: dict):
    """Monthly reset should set credits_used_this_month to 0 for all brands."""
    from app.worker import _reset_monthly_brand_credits_async

    brand = test_data["brand"]
    result = await db_session.execute(select(Brand).where(Brand.id == brand.id))
    b = result.scalars().first()
    b.credits_used_this_month = 500
    await db_session.commit()

    with patch("app.worker.async_session_maker") as mock_session:
        mock_db = AsyncMock()
        mock_brand = MagicMock()
        mock_brand.credits_used_this_month = 500
        mock_db.execute.return_value.scalars.return_value.all.side_effect = [
            [mock_brand], []
        ]
        mock_session.return_value.__aenter__.return_value = mock_db
        await _reset_monthly_brand_credits_async()
        assert mock_brand.credits_used_this_month == 0


def test_monthly_reset_task_in_beat():
    """Monthly reset task should be in Celery Beat schedule."""
    from app.worker import celery_app
    assert "reset-monthly-brand-credits" in celery_app.conf.beat_schedule


# ========================== Rate Limit Header Tests ==============

@pytest.mark.asyncio
async def test_rate_limit_headers_on_429():
    """429 response should include rate limit headers."""
    with patch("app.middleware.rate_limit._resolve_identifier", new=AsyncMock(return_value=("ip", "127.0.0.1", None))):
        with patch("app.middleware.rate_limit.redis_client") as mock_redis:
            mock_pipe = AsyncMock()
            mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
            mock_pipe.__aexit__ = AsyncMock(return_value=None)
            mock_pipe.execute = AsyncMock(return_value=[None, 999, None, None])
            mock_redis.pipeline.return_value = mock_pipe

            from app.middleware.rate_limit import RateLimiter
            limiter = RateLimiter(requests_limit=10, window_seconds=60)

            mock_request = MagicMock()
            mock_request.headers = {}
            mock_request.url.path = "/api/v1/test"
            mock_request.client.host = "127.0.0.1"

            with pytest.raises(Exception) as exc_info:
                await limiter(mock_request)

            assert exc_info.value.status_code == 429
            assert "X-RateLimit-Limit" in exc_info.value.headers
            assert "Retry-After" in exc_info.value.headers
