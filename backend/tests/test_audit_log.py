import json
import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import AuditLog, APIKey, WebhookSubscription, Asset, BrandMember, User, AssetTag
from app.services.storage import storage_service
from app.worker import process_asset_upload

@pytest.fixture(autouse=True)
def mock_external_deps(monkeypatch):
    """Fixture to mock storage existence verification and Celery task dispatch."""
    # Mock file existence check to always return True for tests
    monkeypatch.setattr(storage_service, "verify_file_exists", lambda name: True)
    
    # Mock celery task .delay call
    mock_delay = MagicMock()
    monkeypatch.setattr(process_asset_upload, "delay", mock_delay)
    
    return mock_delay


@pytest.mark.asyncio
async def test_api_key_audit_logging(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    owner = test_data["users"]["owner"]
    owner_id = owner.id
    owner_headers = test_data["get_headers"]("owner")

    # 1. Create API key
    payload = {"name": "Audit Test Key"}
    res = await client.post("/api/v1/api-keys", json=payload, headers=owner_headers)
    assert res.status_code == 201
    key_id = res.json()["id"]

    # Verify audit log created
    res_logs = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "api_key_created",
            AuditLog.user_id == owner_id
        )
    )
    log = res_logs.scalars().first()
    assert log is not None
    assert log.details.get("key_id") == key_id
    assert log.details.get("name") == "Audit Test Key"
    assert log.client_ip is not None  # client IP captured from request

    # 2. Delete API key
    res = await client.delete(f"/api/v1/api-keys/{key_id}", headers=owner_headers)
    assert res.status_code == 204

    # Verify audit log created
    db_session.expire_all()
    res_logs_del = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "api_key_deleted",
            AuditLog.user_id == owner_id
        )
    )
    log_del = res_logs_del.scalars().first()
    assert log_del is not None
    assert log_del.details.get("key_id") == key_id
    assert log_del.details.get("name") == "Audit Test Key"
    assert log_del.client_ip is not None


@pytest.mark.asyncio
async def test_webhook_audit_logging(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    brand_id = brand.id
    owner = test_data["users"]["owner"]
    owner_id = owner.id
    owner_headers = test_data["get_headers"]("owner")

    # 1. Register webhook
    payload = {
        "brand_id": brand_id,
        "url": "https://example.com/webhook",
        "events": ["job.completed"]
    }
    res = await client.post("/api/v1/webhooks", json=payload, headers=owner_headers)
    assert res.status_code == 201
    webhook_id = res.json()["id"]

    # Verify audit log created
    res_logs = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "webhook_created",
            AuditLog.brand_id == brand_id
        )
    )
    log = res_logs.scalars().first()
    assert log is not None
    assert log.user_id == owner_id
    assert log.details.get("webhook_id") == webhook_id
    assert log.details.get("url") == "https://example.com/webhook"
    assert log.client_ip is not None

    # 2. Delete webhook
    res = await client.delete(f"/api/v1/webhooks/{webhook_id}", headers=owner_headers)
    assert res.status_code == 204

    # Verify audit log created
    db_session.expire_all()
    res_logs_del = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "webhook_deleted",
            AuditLog.brand_id == brand_id
        )
    )
    log_del = res_logs_del.scalars().first()
    assert log_del is not None
    assert log_del.user_id == owner_id
    assert log_del.details.get("webhook_id") == webhook_id
    assert log_del.client_ip is not None


@pytest.mark.asyncio
async def test_asset_audit_logging(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    brand_id = brand.id
    owner = test_data["users"]["owner"]
    owner_id = owner.id
    owner_headers = test_data["get_headers"]("owner")
    editor_headers = test_data["get_headers"]("editor")
    editor = test_data["users"]["editor"]
    editor_id = editor.id

    # 1. Create and confirm asset
    payload = {
        "filename": "audit_asset.png",
        "brand_id": brand_id,
        "asset_type": "image",
        "metadata_json": json.dumps({})
    }
    res = await client.post("/api/v1/assets/upload-url", json=payload, headers=editor_headers)
    assert res.status_code == 200
    asset_id = res.json()["asset_id"]

    res = await client.post("/api/v1/assets/confirm", json={"asset_id": asset_id}, headers=editor_headers)
    assert res.status_code == 200

    # 2. Delete asset (soft delete)
    res = await client.delete(f"/api/v1/assets/{asset_id}", headers=owner_headers)
    assert res.status_code == 204

    # Verify audit log created
    res_logs = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "asset_deleted",
            AuditLog.brand_id == brand_id
        )
    )
    log = res_logs.scalars().first()
    assert log is not None
    assert log.user_id == owner_id
    assert log.details.get("asset_id") == asset_id
    assert log.client_ip is not None

    # 3. Restore asset
    res = await client.post(f"/api/v1/assets/{asset_id}/restore", headers=editor_headers)
    assert res.status_code == 200

    # Verify audit log created
    db_session.expire_all()
    res_logs_rest = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "asset_restored",
            AuditLog.brand_id == brand_id
        )
    )
    log_rest = res_logs_rest.scalars().first()
    assert log_rest is not None
    assert log_rest.user_id == editor_id
    assert log_rest.details.get("asset_id") == asset_id
    assert log_rest.client_ip is not None


@pytest.mark.asyncio
async def test_brand_member_audit_logging(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    brand_id = brand.id
    owner = test_data["users"]["owner"]
    owner_id = owner.id
    owner_headers = test_data["get_headers"]("owner")
    nonmember = test_data["users"]["nonmember"]
    nonmember_id = nonmember.id

    # 1. Invite/add member
    payload = {
        "email": nonmember.email,
        "role": "viewer"
    }
    res = await client.post(f"/api/v1/brands/{brand_id}/members", json=payload, headers=owner_headers)
    assert res.status_code == 201

    # Verify audit log created
    res_logs = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "brand_member_added",
            AuditLog.brand_id == brand_id
        )
    )
    log = res_logs.scalars().first()
    assert log is not None
    assert log.user_id == owner_id
    assert log.details.get("invited_user_email") == nonmember.email
    assert log.details.get("role") == "viewer"
    assert log.client_ip is not None

    # 2. Remove member
    res = await client.delete(f"/api/v1/brands/{brand_id}/members/{nonmember_id}", headers=owner_headers)
    assert res.status_code == 204

    # Verify audit log created
    db_session.expire_all()
    res_logs_rem = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "brand_member_removed",
            AuditLog.brand_id == brand_id
        )
    )
    log_rem = res_logs_rem.scalars().first()
    assert log_rem is not None
    assert log_rem.user_id == owner_id
    assert log_rem.details.get("removed_user_id") == nonmember_id
    assert log_rem.client_ip is not None
