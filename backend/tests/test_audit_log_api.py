import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import AuditLog


@pytest.mark.asyncio
async def test_get_audit_logs_auth_required(client: AsyncClient, test_data: dict):
    """Audit logs endpoint should require authentication."""
    brand = test_data["brand"]
    res = await client.get(f"/api/v1/brands/{brand.id}/audit-logs")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_audit_logs_viewer_forbidden(client: AsyncClient, test_data: dict):
    """Viewer should not be able to view audit logs."""
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")
    res = await client.get(f"/api/v1/brands/{brand.id}/audit-logs", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_get_audit_logs_editor_forbidden(client: AsyncClient, test_data: dict):
    """Editor should not be able to view audit logs."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get(f"/api/v1/brands/{brand.id}/audit-logs", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_get_audit_logs_owner_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Owner should be able to view audit logs."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_headers = test_data["get_headers"]("owner")

    log = AuditLog(
        user_id=owner_user.id,
        brand_id=brand.id,
        action="api_key_created",
        details={"key_id": 1, "name": "Test Key"},
        client_ip="127.0.0.1",
    )
    db_session.add(log)
    await db_session.commit()

    res = await client.get(f"/api/v1/brands/{brand.id}/audit-logs", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert len(data) >= 1
    assert any(entry["action"] == "api_key_created" for entry in data)


@pytest.mark.asyncio
async def test_get_audit_logs_admin_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Admin should be able to view audit logs."""
    brand = test_data["brand"]
    admin_headers = test_data["get_headers"]("admin")

    res = await client.get(f"/api/v1/brands/{brand.id}/audit-logs", headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_get_audit_logs_pagination(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Audit logs should respect limit and offset."""
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_headers = test_data["get_headers"]("owner")

    for i in range(5):
        log = AuditLog(
            user_id=owner_user.id,
            brand_id=brand.id,
            action=f"test_action_{i}",
            details={"index": i},
        )
        db_session.add(log)
    await db_session.commit()

    res = await client.get(f"/api/v1/brands/{brand.id}/audit-logs?limit=3&offset=0", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) == 3
