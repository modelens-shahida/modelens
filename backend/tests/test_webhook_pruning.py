import pytest
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.models.db import WebhookDeliveryLog, WebhookSubscription


# ========================== Helper ===============================

async def create_log(db_session, sub_id, days_old):
    """Create a WebhookDeliveryLog with a specific age."""
    created_at = datetime.utcnow() - timedelta(days=days_old)
    log = WebhookDeliveryLog(
        subscription_id=sub_id,
        event_type="job.completed",
        payload={"type": "job.completed"},
        response_status=200,
        response_body="OK",
        execution_time_ms=100,
        status="success",
        attempt_number=1,
    )
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)

    # Update created_at manually
    log.created_at = created_at
    await db_session.commit()
    return log


# ========================== Pruning Tests ========================

@pytest.mark.asyncio
async def test_prune_deletes_old_logs(db_session: AsyncSession, test_data: dict):
    """Logs older than retention window should be deleted."""
    from app.worker import _prune_webhook_logs_async

    brand = test_data["brand"]
    sub = WebhookSubscription(
        brand_id=brand.id,
        url="https://example.com/prune-test",
        events=["job.completed"],
        is_active=True,
        secret_token="ml_sec_test",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    # Create old log (40 days) - should be deleted
    old_log = await create_log(db_session, sub.id, days_old=40)
    # Create recent log (10 days) - should be preserved
    recent_log = await create_log(db_session, sub.id, days_old=10)

    with patch("app.worker.settings") as mock_settings:
        mock_settings.WEBHOOK_LOG_RETENTION_DAYS = 30
        mock_settings.WEBHOOK_LOG_PRUNE_BATCH_SIZE = 1000
        await _prune_webhook_logs_async()

    # Old log should be deleted
    old_result = await db_session.execute(
        select(WebhookDeliveryLog).where(WebhookDeliveryLog.id == old_log.id)
    )
    assert old_result.scalars().first() is None

    # Recent log should still exist
    recent_result = await db_session.execute(
        select(WebhookDeliveryLog).where(WebhookDeliveryLog.id == recent_log.id)
    )
    assert recent_result.scalars().first() is not None


@pytest.mark.asyncio
async def test_prune_preserves_recent_logs(db_session: AsyncSession, test_data: dict):
    """Logs within retention window should not be deleted."""
    from app.worker import _prune_webhook_logs_async

    brand = test_data["brand"]
    sub = WebhookSubscription(
        brand_id=brand.id,
        url="https://example.com/prune-preserve",
        events=["job.completed"],
        is_active=True,
        secret_token="ml_sec_test",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    # Create logs within retention window
    log1 = await create_log(db_session, sub.id, days_old=5)
    log2 = await create_log(db_session, sub.id, days_old=15)
    log3 = await create_log(db_session, sub.id, days_old=29)

    with patch("app.worker.settings") as mock_settings:
        mock_settings.WEBHOOK_LOG_RETENTION_DAYS = 30
        mock_settings.WEBHOOK_LOG_PRUNE_BATCH_SIZE = 1000
        await _prune_webhook_logs_async()

    # All logs should still exist
    for log in [log1, log2, log3]:
        result = await db_session.execute(
            select(WebhookDeliveryLog).where(WebhookDeliveryLog.id == log.id)
        )
        assert result.scalars().first() is not None


@pytest.mark.asyncio
async def test_prune_empty_table_no_error(db_session: AsyncSession, test_data: dict):
    """Pruning with no logs should not raise errors."""
    from app.worker import _prune_webhook_logs_async

    with patch("app.worker.settings") as mock_settings:
        mock_settings.WEBHOOK_LOG_RETENTION_DAYS = 30
        mock_settings.WEBHOOK_LOG_PRUNE_BATCH_SIZE = 1000
        # Should complete without error
        await _prune_webhook_logs_async()


@pytest.mark.asyncio
async def test_prune_configurable_retention(db_session: AsyncSession, test_data: dict):
    """Pruning should respect custom retention window."""
    from app.worker import _prune_webhook_logs_async

    brand = test_data["brand"]
    sub = WebhookSubscription(
        brand_id=brand.id,
        url="https://example.com/prune-config",
        events=["job.completed"],
        is_active=True,
        secret_token="ml_sec_test",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    # 15-day old log
    log = await create_log(db_session, sub.id, days_old=15)

    # With 7-day retention, 15-day log should be deleted
    with patch("app.worker.settings") as mock_settings:
        mock_settings.WEBHOOK_LOG_RETENTION_DAYS = 7
        mock_settings.WEBHOOK_LOG_PRUNE_BATCH_SIZE = 1000
        await _prune_webhook_logs_async()

    result = await db_session.execute(
        select(WebhookDeliveryLog).where(WebhookDeliveryLog.id == log.id)
    )
    assert result.scalars().first() is None


def test_pruning_task_registered_in_beat():
    """Pruning task should be registered in Celery Beat schedule."""
    from app.worker import celery_app
    beat_schedule = celery_app.conf.beat_schedule
    assert "prune-webhook-delivery-logs-daily" in beat_schedule
    assert beat_schedule["prune-webhook-delivery-logs-daily"]["task"] == "app.worker.prune_old_webhook_delivery_logs"
    assert beat_schedule["prune-webhook-delivery-logs-daily"]["schedule"] == 86400
