import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import WebhookSubscription, WebhookDeliveryLog, Notification


# ========================== Delivery Log Tests ====================

@pytest.mark.asyncio
async def test_delivery_logs_auth_required(client: AsyncClient, test_data: dict):
    """Delivery logs endpoint should require authentication."""
    res = await client.get("/api/v1/webhooks/1/delivery-logs")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_delivery_logs_viewer_forbidden(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Viewer should not be able to view delivery logs."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    viewer_headers = test_data["get_headers"]("viewer")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id,
        "url": "https://example.com/logs",
        "events": ["job.completed"]
    }, headers=owner_headers)
    sub_id = res.json()["id"]

    res = await client.get(f"/api/v1/webhooks/{sub_id}/delivery-logs", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_delivery_logs_owner_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Owner should be able to view delivery logs."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    sub = WebhookSubscription(
        brand_id=brand.id,
        url="https://example.com/owner-logs",
        events=["job.completed"],
        is_active=True,
        secret_token="ml_sec_test",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    log = WebhookDeliveryLog(
        subscription_id=sub.id,
        event_type="job.completed",
        payload={"type": "job.completed"},
        response_status=200,
        response_body="OK",
        execution_time_ms=150,
        status="success",
        attempt_number=1,
    )
    db_session.add(log)
    await db_session.commit()

    res = await client.get(f"/api/v1/webhooks/{sub.id}/delivery-logs", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert len(data) >= 1
    assert data[0]["status"] == "success"
    assert data[0]["event_type"] == "job.completed"


# ========================== Retry Endpoint Tests =================

@pytest.mark.asyncio
async def test_retry_auth_required(client: AsyncClient):
    """Retry endpoint should require authentication."""
    res = await client.post("/api/v1/webhooks/logs/1/retry")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_retry_viewer_forbidden(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Viewer should not be able to retry delivery."""
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")

    sub = WebhookSubscription(
        brand_id=brand.id,
        url="https://example.com/retry-test",
        events=["job.completed"],
        is_active=True,
        secret_token="ml_sec_test",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    log = WebhookDeliveryLog(
        subscription_id=sub.id,
        event_type="job.completed",
        payload={"type": "job.completed"},
        status="dead",
        attempt_number=5,
    )
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)

    res = await client.post(f"/api/v1/webhooks/logs/{log.id}/retry", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_retry_owner_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Owner should be able to retry a dead delivery."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    sub = WebhookSubscription(
        brand_id=brand.id,
        url="https://example.com/retry-owner",
        events=["job.completed"],
        is_active=True,
        secret_token="ml_sec_test",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    log = WebhookDeliveryLog(
        subscription_id=sub.id,
        event_type="job.completed",
        payload={"type": "job.completed"},
        status="dead",
        attempt_number=5,
    )
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)

    with patch("app.routers.webhooks.dispatch_webhook") as mock_task:
        mock_task.delay = MagicMock()
        res = await client.post(f"/api/v1/webhooks/logs/{log.id}/retry", headers=owner_headers)
        assert res.status_code == status.HTTP_202_ACCEPTED
        mock_task.delay.assert_called_once()


# ========================== DLQ & Notification Tests =============

@pytest.mark.asyncio
async def test_successful_delivery_logs_success_status():
    """Successful delivery should log success status."""
    from app.worker import _log_delivery
    with patch("app.worker.async_session_maker") as mock_session:
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db

        _log_delivery(1, {"type": "job.completed"}, 200, "OK", 100, "success", 1)
        mock_db.add.assert_called()


@pytest.mark.asyncio
async def test_dead_delivery_triggers_notification():
    """Dead delivery should trigger webhook_failed notification."""
    from app.worker import _trigger_webhook_failed_notification

    with patch("app.worker.async_session_maker") as mock_session:
        mock_db = AsyncMock()
        mock_sub = MagicMock()
        mock_sub.brand_id = 1
        mock_brand = MagicMock()
        mock_brand.owner_id = 1

        mock_db.execute.return_value.scalars.return_value.first.side_effect = [mock_sub, mock_brand]
        mock_session.return_value.__aenter__.return_value = mock_db

        with patch("app.worker._create_notification", new=AsyncMock()) as mock_notif:
            _trigger_webhook_failed_notification(1, "https://example.com/dead")


@pytest.mark.asyncio
async def test_delivery_log_not_found_returns_404(client: AsyncClient, test_data: dict):
    """Retry of non-existent log should return 404."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post("/api/v1/webhooks/logs/99999/retry", headers=owner_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND
