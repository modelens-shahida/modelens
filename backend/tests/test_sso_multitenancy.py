import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, UTC

from app.models.db import Brand, BrandMember, Invitation, User
from app.services.sso_service import (
    extract_email_domain,
    find_whitelisted_brand,
    auto_provision_member,
    accept_pending_invitation,
    handle_sso_login,
)


# ========================== Domain Utils Tests ===================

def test_extract_email_domain():
    assert extract_email_domain("user@example.com") == "example.com"
    assert extract_email_domain("user@BRAND.CO") == "brand.co"
    assert extract_email_domain("invalid") == ""


# ========================== Whitelist Tests ======================

@pytest.mark.asyncio
async def test_find_whitelisted_brand_match(db_session: AsyncSession, test_data: dict):
    """Should find brand when email domain is whitelisted."""
    brand = test_data["brand"]
    result = await db_session.execute(select(Brand).where(Brand.id == brand.id))
    b = result.scalars().first()
    b.domain_whitelist = ["testbrand.com", "example.com"]
    await db_session.commit()

    matched = await find_whitelisted_brand("user@example.com", db_session)
    assert matched is not None
    assert matched.id == brand.id


@pytest.mark.asyncio
async def test_find_whitelisted_brand_no_match(db_session: AsyncSession, test_data: dict):
    """Should return None when email domain is not whitelisted."""
    brand = test_data["brand"]
    result = await db_session.execute(select(Brand).where(Brand.id == brand.id))
    b = result.scalars().first()
    b.domain_whitelist = ["other.com"]
    await db_session.commit()

    matched = await find_whitelisted_brand("user@different.com", db_session)
    assert matched is None


@pytest.mark.asyncio
async def test_find_whitelisted_brand_null_whitelist(db_session: AsyncSession, test_data: dict):
    """Should return None when whitelist is null."""
    brand = test_data["brand"]
    result = await db_session.execute(select(Brand).where(Brand.id == brand.id))
    b = result.scalars().first()
    b.domain_whitelist = None
    await db_session.commit()

    matched = await find_whitelisted_brand("user@example.com", db_session)
    assert matched is None


# ========================== Auto-Provision Tests =================

@pytest.mark.asyncio
async def test_auto_provision_member_success(db_session: AsyncSession, test_data: dict):
    """Should provision user as viewer in brand."""
    brand = test_data["brand"]
    viewer_user = test_data["users"]["viewer"]

    # Remove existing membership first
    existing = await db_session.execute(
        select(BrandMember).where(
            BrandMember.brand_id == brand.id,
            BrandMember.user_id == viewer_user.id,
        )
    )
    m = existing.scalars().first()
    if m:
        await db_session.delete(m)
        await db_session.commit()

    result = await db_session.execute(select(Brand).where(Brand.id == brand.id))
    b = result.scalars().first()
    result_user = await db_session.execute(select(User).where(User.id == viewer_user.id))
    u = result_user.scalars().first()

    provisioned = await auto_provision_member(u, b, role="viewer", db=db_session)
    assert provisioned is True


@pytest.mark.asyncio
async def test_auto_provision_already_member(db_session: AsyncSession, test_data: dict):
    """Should return False if user is already a member."""
    brand = test_data["brand"]
    editor_user = test_data["users"]["editor"]

    result = await db_session.execute(select(Brand).where(Brand.id == brand.id))
    b = result.scalars().first()
    result_user = await db_session.execute(select(User).where(User.id == editor_user.id))
    u = result_user.scalars().first()

    provisioned = await auto_provision_member(u, b, role="viewer", db=db_session)
    assert provisioned is False


# ========================== Invitation Auto-Accept Tests =========

@pytest.mark.asyncio
async def test_accept_pending_invitation_success(db_session: AsyncSession, test_data: dict):
    """Should auto-accept pending invitation for matching email."""
    brand = test_data["brand"]
    viewer_user = test_data["users"]["viewer"]

    invite = Invitation(
        brand_id=brand.id,
        email=viewer_user.email,
        role="editor",
        token="sso_test_token_abc",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(invite)
    await db_session.commit()

    # Remove existing membership
    existing = await db_session.execute(
        select(BrandMember).where(
            BrandMember.brand_id == brand.id,
            BrandMember.user_id == viewer_user.id,
        )
    )
    m = existing.scalars().first()
    if m:
        await db_session.delete(m)
        await db_session.commit()

    result_user = await db_session.execute(select(User).where(User.id == viewer_user.id))
    u = result_user.scalars().first()

    member = await accept_pending_invitation(u, db_session)
    assert member is not None
    assert member.role == "editor"


@pytest.mark.asyncio
async def test_accept_expired_invitation_ignored(db_session: AsyncSession, test_data: dict):
    """Expired invitations should not be auto-accepted."""
    brand = test_data["brand"]
    viewer_user = test_data["users"]["viewer"]

    invite = Invitation(
        brand_id=brand.id,
        email=viewer_user.email,
        role="editor",
        token="expired_sso_token",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(invite)
    await db_session.commit()

    result_user = await db_session.execute(select(User).where(User.id == viewer_user.id))
    u = result_user.scalars().first()

    member = await accept_pending_invitation(u, db_session)
    assert member is None


# ========================== Auth Settings API Tests ==============

@pytest.mark.asyncio
async def test_update_domain_whitelist_owner(client: AsyncClient, test_data: dict):
    """Owner should be able to update domain whitelist."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.patch(
        f"/api/v1/brands/{brand.id}/auth-settings",
        json={"domain_whitelist": ["mycompany.com", "partner.org"]},
        headers=owner_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "mycompany.com" in data["domain_whitelist"]


@pytest.mark.asyncio
async def test_get_auth_settings(client: AsyncClient, test_data: dict):
    """Viewer should be able to read auth settings."""
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")

    res = await client.get(
        f"/api/v1/brands/{brand.id}/auth-settings",
        headers=viewer_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    assert "domain_whitelist" in res.json()


@pytest.mark.asyncio
async def test_update_domain_whitelist_viewer_forbidden(client: AsyncClient, test_data: dict):
    """Viewer should not be able to update auth settings."""
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")

    res = await client.patch(
        f"/api/v1/brands/{brand.id}/auth-settings",
        json={"domain_whitelist": ["hacker.com"]},
        headers=viewer_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_sso_login_endpoint_auto_registers_and_provisions(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """POST /api/v1/auth/sso-login should register a new user and generate JWT tokens."""
    brand = test_data["brand"]
    # Update brand whitelist
    result = await db_session.execute(select(Brand).where(Brand.id == brand.id))
    b = result.scalars().first()
    b.domain_whitelist = ["sso-company.com"]
    await db_session.commit()

    # Request SSO login for a non-existent user with matching whitelist domain
    res = await client.post(
        "/api/v1/auth/sso-login",
        json={
            "email": "newuser@sso-company.com",
            "full_name": "New SSO User",
            "provider": "google"
        }
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Verify user was created
    user_query = select(User).where(User.email == "newuser@sso-company.com")
    user_res = await db_session.execute(user_query)
    user = user_res.scalars().first()
    assert user is not None
    assert user.full_name == "New SSO User"

    # Verify user was auto-provisioned as Viewer in the brand
    member_query = select(BrandMember).where(
        BrandMember.brand_id == brand.id,
        BrandMember.user_id == user.id
    )
    m_result = await db_session.execute(member_query)
    member = m_result.scalars().first()
    assert member is not None
    assert member.role == "viewer"

