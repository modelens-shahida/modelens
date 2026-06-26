import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import WebhookSubscription, AIJob


@pytest.mark.asyncio
async def test_webhook_auth_required(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id, "url": "https://example.com/hook", "events": ["job.completed"]
    })
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_webhook_viewer_forbidden(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")
    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id, "url": "https://example.com/hook", "events": ["job.completed"]
    }, headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_webhook_editor_forbidden(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id, "url": "https://example.com/hook", "events": ["job.completed"]
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_webhook_viewer_cannot_delete(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    viewer_headers = test_data["get_headers"]("viewer")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id, "url": "https://example.com/del", "events": ["job.completed"]
    }, headers=owner_headers)
    webhook_id = res.json()["id"]

    res = await client.delete(f"/api/v1/webhooks/{webhook_id}", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_webhook_editor_cannot_delete(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id, "url": "https://example.com/del2", "events": ["job.failed"]
    }, headers=owner_headers)
    webhook_id = res.json()["id"]

    res = await client.delete(f"/api/v1/webhooks/{webhook_id}", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_register_webhook_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id, "url": "https://example.com/hook", "events": ["job.completed", "job.failed"]
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["brand_id"] == brand.id
    assert data["is_active"] is True
    assert "job.completed" in data["events"]

    result = await db_session.execute(select(WebhookSubscription).where(WebhookSubscription.id == data["id"]))
    assert result.scalars().first() is not None


@pytest.mark.asyncio
async def test_register_webhook_invalid_event(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id, "url": "https://example.com/hook", "events": ["invalid.event"]
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid events" in res.json()["detail"]


@pytest.mark.asyncio
async def test_list_webhooks(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    viewer_headers = test_data["get_headers"]("viewer")

    await client.post("/api/v1/webhooks", json={"brand_id": brand.id, "url": "https://example.com/h1", "events": ["job.completed"]}, headers=owner_headers)
    await client.post("/api/v1/webhooks", json={"brand_id": brand.id, "url": "https://example.com/h2", "events": ["job.failed"]}, headers=owner_headers)

    res = await client.get(f"/api/v1/webhooks?brand_id={brand.id}", headers=viewer_headers)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) >= 2


@pytest.mark.asyncio
async def test_list_webhooks_unauthorized_brand(client: AsyncClient, test_data: dict):
    viewer_headers = test_data["get_headers"]("viewer")
    res = await client.get("/api/v1/webhooks?brand_id=99999", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_delete_webhook_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.post("/api/v1/webhooks", json={"brand_id": brand.id, "url": "https://example.com/delete-me", "events": ["job.completed"]}, headers=owner_headers)
    webhook_id = res.json()["id"]

    res = await client.delete(f"/api/v1/webhooks/{webhook_id}", headers=owner_headers)
    assert res.status_code == status.HTTP_204_NO_CONTENT

    result = await db_session.execute(select(WebhookSubscription).where(WebhookSubscription.id == webhook_id))
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_delete_webhook_not_found(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.delete("/api/v1/webhooks/99999", headers=owner_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_worker_dispatches_brand_webhooks_on_job_completed(db_session: AsyncSession, test_data: dict):
    """Worker should dispatch webhooks to brand subscribers on job completion."""
    from app.worker import _process_generation_job_async

    brand = test_data["brand"]
    editor_user = test_data["users"]["editor"]

    subscription = WebhookSubscription(
        brand_id=brand.id,
        url="https://example.com/brand-hook",
        events=["job.completed"],
        is_active=True,
    )
    db_session.add(subscription)
    await db_session.commit()

    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        status="pending",
        job_type="generation",
        inputs={"prompt": "webhook test"},
        outputs={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    with patch("app.worker._generate_image", new=AsyncMock(return_value=b"\x89PNGfake")), \
         patch("app.worker.storage_service.save_file_bytes", return_value="/uploads/test.png"), \
         patch("app.worker.redis_client.set", new=AsyncMock()), \
         patch("app.worker.dispatch_webhook.delay") as mock_dispatch:

        await _process_generation_job_async(job.id, retries=0, max_retries=3)

    await db_session.refresh(job)
    assert job.status == "completed"

    dispatched_urls = [call.args[0] for call in mock_dispatch.call_args_list]
    assert "https://example.com/brand-hook" in dispatched_urls
