import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, UTC
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import Invitation, BrandMember, User, Brand
from app.worker import send_invitation_email, _send_invitation_async


@pytest.mark.asyncio
async def test_create_invite_auth_required(client: AsyncClient):
    res = await client.post("/api/v1/brands/1/invites", json={"email": "new@brand.com", "role": "viewer"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_create_invite_role_checks(client: AsyncClient, test_data: dict):
    # Viewer should be forbidden
    viewer_headers = test_data["get_headers"]("viewer")
    res = await client.post(
        f"/api/v1/brands/{test_data['brand'].id}/invites",
        json={"email": "new@brand.com", "role": "viewer"},
        headers=viewer_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # Editor should be forbidden
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post(
        f"/api/v1/brands/{test_data['brand'].id}/invites",
        json={"email": "new@brand.com", "role": "viewer"},
        headers=editor_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # Admin should succeed
    admin_headers = test_data["get_headers"]("admin")
    with patch("app.worker.send_invitation_email.delay") as mock_delay:
        res = await client.post(
            f"/api/v1/brands/{test_data['brand'].id}/invites",
            json={"email": "new@brand.com", "role": "viewer"},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_201_CREATED
        assert res.json()["email"] == "new@brand.com"
        assert res.json()["role"] == "viewer"
        mock_delay.assert_called_once()


@pytest.mark.asyncio
async def test_create_invite_already_owner(client: AsyncClient, test_data: dict):
    admin_headers = test_data["get_headers"]("admin")
    owner_user = test_data["users"]["owner"]
    
    res = await client.post(
        f"/api/v1/brands/{test_data['brand'].id}/invites",
        json={"email": owner_user.email, "role": "viewer"},
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "already the brand owner" in res.json()["detail"]


@pytest.mark.asyncio
async def test_create_invite_already_member(client: AsyncClient, test_data: dict):
    admin_headers = test_data["get_headers"]("admin")
    editor_user = test_data["users"]["editor"]
    
    res = await client.post(
        f"/api/v1/brands/{test_data['brand'].id}/invites",
        json={"email": editor_user.email, "role": "viewer"},
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "already a member" in res.json()["detail"]


@pytest.mark.asyncio
async def test_create_invite_revokes_previous(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    admin_headers = test_data["get_headers"]("admin")
    brand_id = test_data["brand"].id
    email = "test-dup@brand.com"

    # Create an initial active invitation
    inv1 = Invitation(
        email=email,
        role="viewer",
        brand_id=brand_id,
        token="token-1",
        expires_at=datetime.now(UTC) + timedelta(days=7)
    )
    db_session.add(inv1)
    await db_session.commit()

    with patch("app.worker.send_invitation_email.delay"):
        res = await client.post(
            f"/api/v1/brands/{brand_id}/invites",
            json={"email": email, "role": "editor"},
            headers=admin_headers,
        )
        assert res.status_code == status.HTTP_201_CREATED

    # Reload first invitation to check if it's revoked
    await db_session.refresh(inv1)
    assert inv1.revoked_at is not None


@pytest.mark.asyncio
async def test_list_pending_invitations(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    admin_headers = test_data["get_headers"]("admin")
    brand_id = test_data["brand"].id

    # Create various invitations
    inv_pending = Invitation(email="pending@brand.com", role="viewer", brand_id=brand_id, token="t-pending", expires_at=datetime.now(UTC) + timedelta(days=7))
    inv_expired = Invitation(email="expired@brand.com", role="viewer", brand_id=brand_id, token="t-expired", expires_at=datetime.now(UTC) - timedelta(days=1))
    inv_revoked = Invitation(email="revoked@brand.com", role="viewer", brand_id=brand_id, token="t-revoked", expires_at=datetime.now(UTC) + timedelta(days=7), revoked_at=datetime.now(UTC))
    inv_accepted = Invitation(email="accepted@brand.com", role="viewer", brand_id=brand_id, token="t-accepted", expires_at=datetime.now(UTC) + timedelta(days=7), accepted_at=datetime.now(UTC))

    db_session.add_all([inv_pending, inv_expired, inv_revoked, inv_accepted])
    await db_session.commit()

    res = await client.get(f"/api/v1/brands/{brand_id}/invites", headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert len(data) == 1
    assert data[0]["email"] == "pending@brand.com"


@pytest.mark.asyncio
async def test_revoke_invitation_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    admin_headers = test_data["get_headers"]("admin")
    brand_id = test_data["brand"].id

    inv = Invitation(email="revoke-me@brand.com", role="viewer", brand_id=brand_id, token="t-rev-me", expires_at=datetime.now(UTC) + timedelta(days=7))
    db_session.add(inv)
    await db_session.commit()

    res = await client.delete(f"/api/v1/brands/{brand_id}/invites/{inv.id}", headers=admin_headers)
    assert res.status_code == status.HTTP_204_NO_CONTENT

    # Verify database state
    await db_session.refresh(inv)
    assert inv.revoked_at is not None


@pytest.mark.asyncio
async def test_revoke_invitation_not_found(client: AsyncClient, test_data: dict):
    admin_headers = test_data["get_headers"]("admin")
    res = await client.delete(f"/api/v1/brands/{test_data['brand'].id}/invites/99999", headers=admin_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_accept_invitation_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    # Invite nonmember
    nonmember = test_data["users"]["nonmember"]
    brand_id = test_data["brand"].id

    inv = Invitation(email=nonmember.email, role="editor", brand_id=brand_id, token="t-accept-success", expires_at=datetime.now(UTC) + timedelta(days=7))
    db_session.add(inv)
    await db_session.commit()

    nonmember_headers = test_data["get_headers"]("nonmember")
    res = await client.post("/api/v1/invites/accept", json={"token": "t-accept-success"}, headers=nonmember_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "success"
    assert res.json()["role"] == "editor"

    # Verify member created
    member_query = select(BrandMember).where(BrandMember.brand_id == brand_id, BrandMember.user_id == nonmember.id)
    member_result = await db_session.execute(member_query)
    member = member_result.scalars().first()
    assert member is not None
    assert member.role == "editor"

    # Verify invitation marked accepted
    await db_session.refresh(inv)
    assert inv.accepted_at is not None


@pytest.mark.asyncio
async def test_accept_invitation_invalid_token(client: AsyncClient, test_data: dict):
    headers = test_data["get_headers"]("nonmember")
    res = await client.post("/api/v1/invites/accept", json={"token": "t-invalid-token"}, headers=headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_accept_invitation_email_mismatch(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand_id = test_data["brand"].id
    inv = Invitation(email="different@brand.com", role="editor", brand_id=brand_id, token="t-diff-email", expires_at=datetime.now(UTC) + timedelta(days=7))
    db_session.add(inv)
    await db_session.commit()

    nonmember_headers = test_data["get_headers"]("nonmember")
    res = await client.post("/api/v1/invites/accept", json={"token": "t-diff-email"}, headers=nonmember_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "sent to a different email address" in res.json()["detail"]


@pytest.mark.asyncio
async def test_accept_invitation_expired(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    nonmember = test_data["users"]["nonmember"]
    brand_id = test_data["brand"].id
    inv = Invitation(email=nonmember.email, role="editor", brand_id=brand_id, token="t-exp", expires_at=datetime.now(UTC) - timedelta(days=1))
    db_session.add(inv)
    await db_session.commit()

    nonmember_headers = test_data["get_headers"]("nonmember")
    res = await client.post("/api/v1/invites/accept", json={"token": "t-exp"}, headers=nonmember_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "expired" in res.json()["detail"]


@pytest.mark.asyncio
async def test_accept_invitation_revoked(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    nonmember = test_data["users"]["nonmember"]
    brand_id = test_data["brand"].id
    inv = Invitation(email=nonmember.email, role="editor", brand_id=brand_id, token="t-rev", expires_at=datetime.now(UTC) + timedelta(days=7), revoked_at=datetime.now(UTC))
    db_session.add(inv)
    await db_session.commit()

    nonmember_headers = test_data["get_headers"]("nonmember")
    res = await client.post("/api/v1/invites/accept", json={"token": "t-rev"}, headers=nonmember_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "revoked" in res.json()["detail"]


@pytest.mark.asyncio
async def test_accept_invitation_already_accepted(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    nonmember = test_data["users"]["nonmember"]
    brand_id = test_data["brand"].id
    inv = Invitation(email=nonmember.email, role="editor", brand_id=brand_id, token="t-already", expires_at=datetime.now(UTC) + timedelta(days=7), accepted_at=datetime.now(UTC))
    db_session.add(inv)
    await db_session.commit()

    nonmember_headers = test_data["get_headers"]("nonmember")
    res = await client.post("/api/v1/invites/accept", json={"token": "t-already"}, headers=nonmember_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "already been accepted" in res.json()["detail"]


@pytest.mark.asyncio
async def test_accept_invitation_owner(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    owner = test_data["users"]["owner"]
    brand_id = test_data["brand"].id
    inv = Invitation(email=owner.email, role="editor", brand_id=brand_id, token="t-owner-accept", expires_at=datetime.now(UTC) + timedelta(days=7))
    db_session.add(inv)
    await db_session.commit()

    owner_headers = test_data["get_headers"]("owner")
    res = await client.post("/api/v1/invites/accept", json={"token": "t-owner-accept"}, headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["role"] == "owner"


@pytest.mark.asyncio
async def test_accept_invitation_existing_member(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    inv = Invitation(email=editor.email, role="admin", brand_id=brand_id, token="t-existing-accept", expires_at=datetime.now(UTC) + timedelta(days=7))
    db_session.add(inv)
    await db_session.commit()

    # Get editor membership row first
    member_query = select(BrandMember).where(BrandMember.brand_id == brand_id, BrandMember.user_id == editor.id)
    member_result = await db_session.execute(member_query)
    member = member_result.scalars().first()
    assert member.role == "editor"

    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/invites/accept", json={"token": "t-existing-accept"}, headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["role"] == "admin"

    # Reload and check role updated
    await db_session.refresh(member)
    assert member.role == "admin"


class MockSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_celery_task_sends_email(db_session: AsyncSession, test_data: dict):
    brand_id = test_data["brand"].id
    inv = Invitation(email="worker@brand.com", role="viewer", brand_id=brand_id, token="t-worker-email", expires_at=datetime.now(UTC) + timedelta(days=7))
    db_session.add(inv)
    await db_session.commit()

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker._send_email") as mock_send_email:
        await _send_invitation_async(inv.id, "Admin Name")
        mock_send_email.assert_called_once()
        kwargs = mock_send_email.call_args[1]
        assert kwargs["to_email"] == "worker@brand.com"
        assert "t-worker-email" in kwargs["html_content"]
