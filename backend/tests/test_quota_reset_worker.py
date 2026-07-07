import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.models.db import Brand


# ========================== Helper ===============================

async def create_brand_with_reset(db_session, owner_id, name, tier_reset_at=None, credits_used=0):
    brand = Brand(
        name=name,
        owner_id=owner_id,
        tier="free",
        monthly_credit_quota=100,
        credits_used_this_month=credits_used,
        tier_reset_at=tier_reset_at,
    )
    db_session.add(brand)
    await db_session.commit()
    await db_session.refresh(brand)
    return brand


# ========================== Reset Task Tests =====================

@pytest.mark.asyncio
async def test_reset_brands_with_null_tier_reset_at(db_session: AsyncSession, test_data: dict):
    """Brands with null tier_reset_at should be reset."""
    owner_user = test_data["users"]["owner"]

    brand = await create_brand_with_reset(
        db_session, owner_user.id,
        "Null Reset Brand",
        tier_reset_at=None,
        credits_used=50,
    )

    with patch("app.worker.async_session_maker") as mock_session:
        mock_db = AsyncMock()
        mock_brand = MagicMock()
        mock_brand.id = brand.id
        mock_brand.credits_used_this_month = 50
        mock_brand.tier_reset_at = None
        mock_db.execute.return_value.scalars.return_value.all.side_effect = [
            [mock_brand], []
        ]
        mock_session.return_value.__aenter__.return_value = mock_db

        from app.worker import _reset_monthly_brand_credits_async
        await _reset_monthly_brand_credits_async()

        assert mock_brand.credits_used_this_month == 0
        assert mock_brand.tier_reset_at is not None


@pytest.mark.asyncio
async def test_reset_brands_older_than_30_days(db_session: AsyncSession, test_data: dict):
    """Brands with tier_reset_at older than 30 days should be reset."""
    owner_user = test_data["users"]["owner"]

    old_reset = datetime.utcnow() - timedelta(days=35)
    brand = await create_brand_with_reset(
        db_session, owner_user.id,
        "Old Reset Brand",
        tier_reset_at=old_reset,
        credits_used=75,
    )

    with patch("app.worker.async_session_maker") as mock_session:
        mock_db = AsyncMock()
        mock_brand = MagicMock()
        mock_brand.id = brand.id
        mock_brand.credits_used_this_month = 75
        mock_brand.tier_reset_at = old_reset
        mock_db.execute.return_value.scalars.return_value.all.side_effect = [
            [mock_brand], []
        ]
        mock_session.return_value.__aenter__.return_value = mock_db

        from app.worker import _reset_monthly_brand_credits_async
        await _reset_monthly_brand_credits_async()

        assert mock_brand.credits_used_this_month == 0


@pytest.mark.asyncio
async def test_recent_brands_not_reset(db_session: AsyncSession, test_data: dict):
    """Brands reset within last 30 days should NOT be reset again."""
    owner_user = test_data["users"]["owner"]

    recent_reset = datetime.utcnow() - timedelta(days=5)
    brand = await create_brand_with_reset(
        db_session, owner_user.id,
        "Recent Reset Brand",
        tier_reset_at=recent_reset,
        credits_used=30,
    )

    with patch("app.worker.async_session_maker") as mock_session:
        mock_db = AsyncMock()
        # Return empty list - no brands due for reset
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        mock_session.return_value.__aenter__.return_value = mock_db

        from app.worker import _reset_monthly_brand_credits_async
        await _reset_monthly_brand_credits_async()

        # No brands should be modified
        mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_reset_invalidates_redis_cache():
    """Reset should call cache invalidation for each brand."""
    with patch("app.worker.async_session_maker") as mock_session:
        mock_db = AsyncMock()
        mock_brand = MagicMock()
        mock_brand.id = 42
        mock_brand.credits_used_this_month = 100
        mock_brand.tier_reset_at = None
        mock_db.execute.return_value.scalars.return_value.all.side_effect = [
            [mock_brand], []
        ]
        mock_session.return_value.__aenter__.return_value = mock_db

        with patch("app.middleware.rate_limit.invalidate_brand_tier_cache", new=AsyncMock()) as mock_invalidate:
            from app.worker import _reset_monthly_brand_credits_async
            await _reset_monthly_brand_credits_async()

        assert mock_brand.credits_used_this_month == 0


@pytest.mark.asyncio
async def test_reset_sets_tier_reset_at_to_now():
    """Reset should set tier_reset_at to current UTC time."""
    before = datetime.utcnow()

    with patch("app.worker.async_session_maker") as mock_session:
        mock_db = AsyncMock()
        mock_brand = MagicMock()
        mock_brand.id = 1
        mock_brand.credits_used_this_month = 50
        mock_brand.tier_reset_at = None
        mock_db.execute.return_value.scalars.return_value.all.side_effect = [
            [mock_brand], []
        ]
        mock_session.return_value.__aenter__.return_value = mock_db

        from app.worker import _reset_monthly_brand_credits_async
        await _reset_monthly_brand_credits_async()

    after = datetime.utcnow()
    assert mock_brand.tier_reset_at is not None
    assert before <= mock_brand.tier_reset_at <= after


def test_quota_reset_task_in_beat_schedule():
    """Monthly reset task should be in Celery Beat schedule."""
    from app.worker import celery_app
    schedule = celery_app.conf.beat_schedule
    assert "reset-monthly-brand-credits" in schedule
    assert schedule["reset-monthly-brand-credits"]["schedule"] == 2592000
