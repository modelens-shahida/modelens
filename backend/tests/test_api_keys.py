import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import APIKey
from app.middleware.auth import hash_api_key


# ========================== Auth Tests ============================

@pytest.mark.asyncio
async def test_api_keys_auth_required(client: AsyncClient):
    """Unauthenticated requests should return 401."""
    res = await client.get("/api/v1/api-keys")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    res = await client.post("/api/v1/api-keys", json={"name": "Test Key"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ========================== Key Generation Tests ==================

@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Creating an API key should return plaintext key and store hash."""
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post(
        "/api/v1/api-keys",
        json={"name": "My Test Key"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()

    assert "plaintext_key" in data
    assert data["plaintext_key"].startswith("ml_live_")
    assert data["name"] == "My Test Key"
    assert data["is_active"] is True

    # Verify hash is stored in DB
    key_hash = hash_api_key(data["plaintext_key"])
    stmt = select(APIKey).where(APIKey.key_hash == key_hash)
    result = await db_session.execute(stmt)
    db_key = result.scalars().first()
    assert db_key is not None
    assert db_key.name == "My Test Key"


@pytest.mark.asyncio
async def test_plaintext_key_not_returned_on_list(client: AsyncClient, test_data: dict):
    """List endpoint should never expose plaintext key or raw hash."""
    editor_headers = test_data["get_headers"]("editor")

    await client.post(
        "/api/v1/api-keys",
        json={"name": "Secret Key"},
        headers=editor_headers
    )

    res = await client.get("/api/v1/api-keys", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert len(data) >= 1

    for key in data:
        assert "plaintext_key" not in key
        assert "key_hash" not in key
        assert "masked_key" in key
        assert key["masked_key"].startswith("ml_live_****")


# ========================== Key Listing Tests =====================

@pytest.mark.asyncio
async def test_list_api_keys(client: AsyncClient, test_data: dict):
    """List should return all keys for the authenticated user."""
    editor_headers = test_data["get_headers"]("editor")

    await client.post("/api/v1/api-keys", json={"name": "Key 1"}, headers=editor_headers)
    await client.post("/api/v1/api-keys", json={"name": "Key 2"}, headers=editor_headers)

    res = await client.get("/api/v1/api-keys", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    names = [k["name"] for k in data]
    assert "Key 1" in names
    assert "Key 2" in names


# ========================== Key Deletion Tests ====================

@pytest.mark.asyncio
async def test_delete_api_key(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Deleting a key should remove it from the database."""
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post(
        "/api/v1/api-keys",
        json={"name": "Key To Delete"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    key_id = res.json()["id"]
    plaintext = res.json()["plaintext_key"]

    res = await client.delete(f"/api/v1/api-keys/{key_id}", headers=editor_headers)
    assert res.status_code == status.HTTP_204_NO_CONTENT

    # Verify key is removed from DB
    key_hash = hash_api_key(plaintext)
    stmt = select(APIKey).where(APIKey.key_hash == key_hash)
    result = await db_session.execute(stmt)
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_delete_nonexistent_key(client: AsyncClient, test_data: dict):
    """Deleting a non-existent key should return 404."""
    editor_headers = test_data["get_headers"]("editor")

    res = await client.delete("/api/v1/api-keys/99999", headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_cannot_delete_other_users_key(client: AsyncClient, test_data: dict):
    """User should not be able to delete another user's key."""
    editor_headers = test_data["get_headers"]("editor")
    owner_headers = test_data["get_headers"]("owner")

    res = await client.post(
        "/api/v1/api-keys",
        json={"name": "Owner Key"},
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    key_id = res.json()["id"]

    res = await client.delete(f"/api/v1/api-keys/{key_id}", headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


# ========================== Key Auth Tests ========================

@pytest.mark.asyncio
async def test_api_key_authentication(client: AsyncClient, test_data: dict):
    """X-API-Key header should authenticate requests successfully."""
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post(
        "/api/v1/api-keys",
        json={"name": "Auth Test Key"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    plaintext = res.json()["plaintext_key"]

    # Use the API key to access a protected endpoint
    res = await client.get(
        "/api/v1/api-keys",
        headers={"X-API-Key": plaintext}
    )
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_revoked_key_rejected(client: AsyncClient, test_data: dict):
    """After deletion, the key should no longer authenticate."""
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post(
        "/api/v1/api-keys",
        json={"name": "Revoke Test Key"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    key_id = res.json()["id"]
    plaintext = res.json()["plaintext_key"]

    # Delete the key
    await client.delete(f"/api/v1/api-keys/{key_id}", headers=editor_headers)

    # Now try using the deleted key
    res = await client.get(
        "/api/v1/api-keys",
        headers={"X-API-Key": plaintext}
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
