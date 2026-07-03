import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.models.db import User, CreditTransaction


@pytest.mark.asyncio
async def test_low_credit_triggers_warning_email(db_session: AsyncSession, test_data: dict):
    """Dropping below 20 credits should trigger warning email task."""
    from app.routers.credits import _trigger_low_credit_warning_if_needed

    editor_user = test_data["users"]["editor"]
    result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = result.scalars().first()
    user.credits = 15
    user.last_low_credit_warning_at = None
    await db_session.commit()
    await db_session.refresh(user)

    with patch("app.routers.credits.send_low_credit_warning_email") as mock_task:
        mock_task.delay = MagicMock()
        await _trigger_low_credit_warning_if_needed(db_session, user)
        await db_session.commit()
        mock_task.delay.assert_called_once_with(user.id)


@pytest.mark.asyncio
async def test_low_credit_7_day_cooldown_enforced(db_session: AsyncSession, test_data: dict):
    """Warning should NOT be triggered if last warning was within 7 days."""
    from app.routers.credits import _trigger_low_credit_warning_if_needed

    editor_user = test_data["users"]["editor"]
    result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = result.scalars().first()
    user.credits = 10
    user.last_low_credit_warning_at = datetime.utcnow() - timedelta(days=3)
    await db_session.commit()
    await db_session.refresh(user)

    with patch("app.routers.credits.send_low_credit_warning_email") as mock_task:
        mock_task.delay = MagicMock()
        await _trigger_low_credit_warning_if_needed(db_session, user)
        mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_low_credit_warning_after_7_days(db_session: AsyncSession, test_data: dict):
    """Warning SHOULD be triggered if last warning was more than 7 days ago."""
    from app.routers.credits import _trigger_low_credit_warning_if_needed

    editor_user = test_data["users"]["editor"]
    result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = result.scalars().first()
    user.credits = 10
    user.last_low_credit_warning_at = datetime.utcnow() - timedelta(days=8)
    await db_session.commit()
    await db_session.refresh(user)

    with patch("app.routers.credits.send_low_credit_warning_email") as mock_task:
        mock_task.delay = MagicMock()
        await _trigger_low_credit_warning_if_needed(db_session, user)
        await db_session.commit()
        mock_task.delay.assert_called_once_with(user.id)


@pytest.mark.asyncio
async def test_top_up_resets_warning_state(db_session: AsyncSession, test_data: dict):
    """Purchasing credits above threshold should reset last_low_credit_warning_at."""
    from app.routers.credits import _trigger_low_credit_warning_if_needed

    editor_user = test_data["users"]["editor"]
    result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = result.scalars().first()
    user.credits = 50
    user.last_low_credit_warning_at = datetime.utcnow() - timedelta(days=1)
    await db_session.commit()
    await db_session.refresh(user)

    with patch("app.routers.credits.send_low_credit_warning_email") as mock_task:
        mock_task.delay = MagicMock()
        await _trigger_low_credit_warning_if_needed(db_session, user)
        await db_session.commit()

    # Warning should not be triggered
    mock_task.delay.assert_not_called()

    # last_low_credit_warning_at should be reset to None
    await db_session.refresh(user)
    assert user.last_low_credit_warning_at is None


@pytest.mark.asyncio
async def test_no_warning_above_threshold(db_session: AsyncSession, test_data: dict):
    """No warning should be triggered when credits are above threshold."""
    from app.routers.credits import _trigger_low_credit_warning_if_needed

    editor_user = test_data["users"]["editor"]
    result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = result.scalars().first()
    user.credits = 100
    user.last_low_credit_warning_at = None
    await db_session.commit()
    await db_session.refresh(user)

    with patch("app.routers.credits.send_low_credit_warning_email") as mock_task:
        mock_task.delay = MagicMock()
        await _trigger_low_credit_warning_if_needed(db_session, user)
        mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_mock_purchase_triggers_reset(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Mock purchase should reset warning state when balance goes above threshold."""
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]

    result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = result.scalars().first()
    user.credits = 5
    user.last_low_credit_warning_at = datetime.utcnow() - timedelta(days=1)
    await db_session.commit()

    with patch("app.routers.credits.send_low_credit_warning_email") as mock_task:
        mock_task.delay = MagicMock()
        res = await client.post("/api/v1/credits/mock-purchase",
                               json={"package": "starter"},
                               headers=editor_headers)
        assert res.status_code == status.HTTP_201_CREATED

    await db_session.refresh(user)
    assert user.last_low_credit_warning_at is None
