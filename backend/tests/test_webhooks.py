import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import WebhookSubscription, AIJob


class MockSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


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

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker._generate_image", new=AsyncMock(return_value=b"\x89PNGfake")), \
         patch("app.worker.storage_service.save_file_bytes", return_value="/uploads/test.png"), \
         patch("app.worker.redis_client.set", new=AsyncMock()), \
         patch("app.worker.dispatch_webhook.delay") as mock_dispatch:

        await _process_generation_job_async(job.id, retries=0, max_retries=3)

    await db_session.refresh(job)
    assert job.status == "completed"

    dispatched_urls = [call.args[0] for call in mock_dispatch.call_args_list]
    assert "https://example.com/brand-hook" in dispatched_urls


# ========================== WebhookLog Tests ======================

@pytest.mark.asyncio
async def test_webhook_logs_auth_required(client: AsyncClient, test_data: dict):
    """Webhook logs endpoint should require authentication."""
    res = await client.get("/api/v1/webhooks/1/logs")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_webhook_logs_viewer_forbidden(client: AsyncClient, test_data: dict):
    """Viewer should not be able to view webhook logs."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    viewer_headers = test_data["get_headers"]("viewer")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id,
        "url": "https://example.com/logs-test",
        "events": ["job.completed"]
    }, headers=owner_headers)
    webhook_id = res.json()["id"]

    res = await client.get(f"/api/v1/webhooks/{webhook_id}/logs", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_webhook_logs_owner_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Owner should be able to view webhook logs."""
    from app.models.db import WebhookSubscription, WebhookLog

    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    # Create subscription
    sub = WebhookSubscription(
        brand_id=brand.id,
        url="https://example.com/log-view",
        events=["job.completed"],
        is_active=True,
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    # Create a log entry
    log = WebhookLog(
        subscription_id=sub.id,
        event="job.completed",
        payload={"type": "job.completed", "job_id": 1},
        status_code=200,
        response_body="OK",
        attempt=1,
        is_success=True,
    )
    db_session.add(log)
    await db_session.commit()

    res = await client.get(f"/api/v1/webhooks/{sub.id}/logs", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert len(data) >= 1
    assert data[0]["event"] == "job.completed"
    assert data[0]["is_success"] is True


@pytest.mark.asyncio
async def test_webhook_dispatch_logs_success(db_session: AsyncSession, test_data: dict):
    """Successful webhook dispatch should log a success entry in WebhookLog."""
    from app.worker import dispatch_webhook
    from app.models.db import WebhookSubscription, WebhookLog
    from unittest.mock import patch, MagicMock

    brand = test_data["brand"]

    sub = WebhookSubscription(
        brand_id=brand.id,
        url="https://example.com/success-hook",
        events=["job.completed"],
        is_active=True,
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client, \
         patch("app.worker.is_safe_url", return_value=True):
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        with patch("app.worker.async_session_maker") as mock_session:
            from unittest.mock import AsyncMock
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None
            mock_db.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_db
            dispatch_webhook("https://example.com/success-hook", {"type": "job.completed"}, subscription_id=sub.id)

    # Verify mock_db.add was called (log was created)
    mock_db.add.assert_called()


# ========================== HMAC Signing Tests ====================

@pytest.mark.asyncio
async def test_register_webhook_returns_secret_token(client: AsyncClient, test_data: dict):
    """Registering a webhook should return a secret_token."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id,
        "url": "https://example.com/hmac-test",
        "events": ["job.completed"]
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert "secret_token" in data
    assert data["secret_token"].startswith("ml_sec_")


@pytest.mark.asyncio
async def test_rotate_secret_owner_success(client: AsyncClient, test_data: dict):
    """Owner should be able to rotate webhook secret."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    # Create webhook
    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id,
        "url": "https://example.com/rotate-test",
        "events": ["job.completed"]
    }, headers=owner_headers)
    webhook_id = res.json()["id"]
    original_secret = res.json()["secret_token"]

    # Rotate secret
    res = await client.post(f"/api/v1/webhooks/{webhook_id}/rotate-secret", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "secret_token" in data
    assert data["secret_token"].startswith("ml_sec_")
    assert data["secret_token"] != original_secret


@pytest.mark.asyncio
async def test_rotate_secret_viewer_forbidden(client: AsyncClient, test_data: dict):
    """Viewer should not be able to rotate webhook secret."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    viewer_headers = test_data["get_headers"]("viewer")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id,
        "url": "https://example.com/viewer-rotate",
        "events": ["job.completed"]
    }, headers=owner_headers)
    webhook_id = res.json()["id"]

    res = await client.post(f"/api/v1/webhooks/{webhook_id}/rotate-secret", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_rotate_secret_not_found(client: AsyncClient, test_data: dict):
    """Rotating secret for non-existent webhook should return 404."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post("/api/v1/webhooks/99999/rotate-secret", headers=owner_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_dispatch_webhook_includes_hmac_header(db_session, test_data: dict):
    """dispatch_webhook should include X-Modelens-Signature header."""
    from app.models.db import WebhookSubscription
    from unittest.mock import patch, MagicMock

    brand = test_data["brand"]
    sub = WebhookSubscription(
        brand_id=brand.id,
        url="https://example.com/hmac-hook",
        events=["job.completed"],
        is_active=True,
        secret_token="ml_sec_testsecret123",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"
    mock_response.raise_for_status = MagicMock()

    captured_headers = {}

    def mock_post(url, json=None, headers=None, timeout=None):
        captured_headers.update(headers or {})
        return mock_response

    with patch("httpx.Client") as mock_client, \
         patch("app.worker.is_safe_url", return_value=True), \
         patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)):
        mock_client.return_value.__enter__.return_value.post.side_effect = mock_post
        from app.worker import dispatch_webhook
        dispatch_webhook(
            "https://example.com/hmac-hook",
            {"type": "job.completed", "job_id": 1},
            subscription_id=sub.id
        )

    assert "X-Modelens-Signature" in captured_headers
    sig = captured_headers["X-Modelens-Signature"]
    assert sig.startswith("sha256=")
    assert "X-Modelens-Timestamp" in captured_headers
