import pytest
import json
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import Brand, AIJob, CreditTransaction, WebhookSubscription, WebhookDeliveryLog


# ========================== Auth Tests ===========================

@pytest.mark.asyncio
async def test_export_auth_required(client: AsyncClient, test_data: dict):
    """Export endpoint should require authentication."""
    brand = test_data["brand"]
    res = await client.get(f"/api/v1/analytics/export?brand_id={brand.id}")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_export_viewer_forbidden(client: AsyncClient, test_data: dict):
    """Viewer should not be able to export analytics."""
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")
    res = await client.get(f"/api/v1/analytics/export?brand_id={brand.id}", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_export_editor_forbidden(client: AsyncClient, test_data: dict):
    """Editor should not be able to export analytics."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get(f"/api/v1/analytics/export?brand_id={brand.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_export_brand_not_found(client: AsyncClient, test_data: dict):
    """Non-existent brand should return 404."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/analytics/export?brand_id=99999", headers=owner_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


# ========================== JSON Export Tests ====================

@pytest.mark.asyncio
async def test_export_json_format(client: AsyncClient, test_data: dict):
    """JSON export should return correct content-type and structure."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.get(
        f"/api/v1/analytics/export?brand_id={brand.id}&format=json",
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert "application/json" in res.headers["content-type"]

    data = res.json()
    assert "brand_id" in data
    assert "brand_name" in data
    assert "tier" in data
    assert "webhook_delivery_stats" in data
    assert "job_stats" in data
    assert "quota_usage_last_30_days" in data
    assert "exported_at" in data


@pytest.mark.asyncio
async def test_export_json_webhook_stats_structure(client: AsyncClient, test_data: dict):
    """JSON export webhook stats should have all required fields."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.get(
        f"/api/v1/analytics/export?brand_id={brand.id}&format=json",
        headers=owner_headers
    )
    webhook_stats = res.json()["webhook_delivery_stats"]
    assert "success_count" in webhook_stats
    assert "failed_count" in webhook_stats
    assert "avg_latency_ms" in webhook_stats
    assert "max_latency_ms" in webhook_stats
    assert "min_latency_ms" in webhook_stats


@pytest.mark.asyncio
async def test_export_json_with_real_jobs(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """JSON export should include actual job stats."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    editor_user = test_data["users"]["editor"]

    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        status="completed",
        job_type="generation",
        inputs={},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()

    res = await client.get(
        f"/api/v1/analytics/export?brand_id={brand.id}&format=json",
        headers=owner_headers
    )
    data = res.json()
    assert data["job_stats"].get("completed", 0) >= 1


# ========================== CSV Export Tests ====================

@pytest.mark.asyncio
async def test_export_csv_format(client: AsyncClient, test_data: dict):
    """CSV export should return correct content-type and attachment header."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.get(
        f"/api/v1/analytics/export?brand_id={brand.id}&format=csv",
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert "text/csv" in res.headers["content-type"]
    assert "attachment" in res.headers.get("content-disposition", "")
    assert ".csv" in res.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_export_csv_contains_sections(client: AsyncClient, test_data: dict):
    """CSV export should contain all data sections."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.get(
        f"/api/v1/analytics/export?brand_id={brand.id}&format=csv",
        headers=owner_headers
    )
    csv_content = res.text
    assert "Brand" in csv_content
    assert "Webhook Delivery" in csv_content
    assert "Jobs" in csv_content


@pytest.mark.asyncio
async def test_export_invalid_format(client: AsyncClient, test_data: dict):
    """Invalid format should return 422."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.get(
        f"/api/v1/analytics/export?brand_id={brand.id}&format=xml",
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_export_admin_access(client: AsyncClient, test_data: dict):
    """Admin should be able to export analytics."""
    brand = test_data["brand"]
    admin_headers = test_data["get_headers"]("admin")

    res = await client.get(
        f"/api/v1/analytics/export?brand_id={brand.id}&format=json",
        headers=admin_headers
    )
    assert res.status_code == status.HTTP_200_OK
