import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.models.db import WebhookSubscription, WebhookDeliveryLog


# ========================== Helper ===============================

async def create_test_subscription(db_session, brand_id):
    sub = WebhookSubscription(
        brand_id=brand_id,
        url="https://example.com/metrics-test",
        events=["job.completed"],
        is_active=True,
        secret_token="ml_sec_test",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


async def create_delivery_log(db_session, sub_id, status, response_status=200, exec_time=100):
    log = WebhookDeliveryLog(
        subscription_id=sub_id,
        event_type="job.completed",
        payload={"type": "job.completed"},
        response_status=response_status,
        response_body="OK",
        execution_time_ms=exec_time,
        status=status,
        attempt_number=1,
    )
    db_session.add(log)
    await db_session.commit()
    return log


# ========================== Auth Tests ===========================

@pytest.mark.asyncio
async def test_metrics_auth_required(client: AsyncClient):
    res = await client.get("/api/v1/webhooks/1/metrics")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_admin_metrics_auth_required(client: AsyncClient):
    res = await client.get("/api/v1/webhooks/admin/metrics")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_metrics_viewer_forbidden(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")
    sub = await create_test_subscription(db_session, brand.id)
    res = await client.get(f"/api/v1/webhooks/{sub.id}/metrics", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


# ========================== Metrics Tests ========================

@pytest.mark.asyncio
async def test_metrics_empty_logs(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Metrics with no logs should return zeros."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    sub = await create_test_subscription(db_session, brand.id)

    res = await client.get(f"/api/v1/webhooks/{sub.id}/metrics", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_deliveries"] == 0
    assert data["success_rate"] == 0.0
    assert data["failure_rate"] == 0.0
    assert data["avg_latency_ms"] == 0.0


@pytest.mark.asyncio
async def test_metrics_success_rate(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Success rate should be calculated correctly."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    sub = await create_test_subscription(db_session, brand.id)

    await create_delivery_log(db_session, sub.id, "success", 200, 100)
    await create_delivery_log(db_session, sub.id, "success", 200, 200)
    await create_delivery_log(db_session, sub.id, "failed", 503, 500)
    await create_delivery_log(db_session, sub.id, "dead", 503, 600)

    res = await client.get(f"/api/v1/webhooks/{sub.id}/metrics?time_range=30d", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_deliveries"] == 4
    assert data["success_rate"] == 50.0
    assert data["failure_rate"] == 50.0


@pytest.mark.asyncio
async def test_metrics_avg_latency(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Average latency should be calculated correctly."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    sub = await create_test_subscription(db_session, brand.id)

    await create_delivery_log(db_session, sub.id, "success", 200, 100)
    await create_delivery_log(db_session, sub.id, "success", 200, 300)

    res = await client.get(f"/api/v1/webhooks/{sub.id}/metrics?time_range=30d", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["avg_latency_ms"] == 200.0


@pytest.mark.asyncio
async def test_metrics_status_breakdown(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Status breakdown should count each status correctly."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    sub = await create_test_subscription(db_session, brand.id)

    await create_delivery_log(db_session, sub.id, "success", 200, 100)
    await create_delivery_log(db_session, sub.id, "retrying", 503, 200)
    await create_delivery_log(db_session, sub.id, "dead", 503, 300)

    res = await client.get(f"/api/v1/webhooks/{sub.id}/metrics?time_range=30d", headers=owner_headers)
    data = res.json()
    assert data["status_breakdown"]["success"] == 1
    assert data["status_breakdown"]["retrying"] == 1
    assert data["status_breakdown"]["dead"] == 1
    assert data["queue_health"]["retrying"] == 1
    assert data["queue_health"]["dead_letter_queue"] == 1


@pytest.mark.asyncio
async def test_metrics_status_code_distribution(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Status code distribution should group by HTTP response code."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    sub = await create_test_subscription(db_session, brand.id)

    await create_delivery_log(db_session, sub.id, "success", 200, 100)
    await create_delivery_log(db_session, sub.id, "success", 200, 100)
    await create_delivery_log(db_session, sub.id, "failed", 503, 200)

    res = await client.get(f"/api/v1/webhooks/{sub.id}/metrics?time_range=30d", headers=owner_headers)
    data = res.json()
    assert data["status_code_distribution"].get("200") == 2
    assert data["status_code_distribution"].get("503") == 1


@pytest.mark.asyncio
async def test_metrics_time_range_24h(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """time_range=24h should only include recent logs."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    sub = await create_test_subscription(db_session, brand.id)

    await create_delivery_log(db_session, sub.id, "success", 200, 100)

    res = await client.get(f"/api/v1/webhooks/{sub.id}/metrics?time_range=24h", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["time_range"] == "24h"


@pytest.mark.asyncio
async def test_admin_metrics_owner_success(client: AsyncClient, test_data: dict):
    """Owner should access admin metrics."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/webhooks/admin/metrics", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "total_deliveries" in data
    assert "success_rate" in data
    assert "queue_health" in data
