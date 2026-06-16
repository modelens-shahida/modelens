import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import CampaignTheme


@pytest.mark.asyncio
async def test_themes_auth_required(client: AsyncClient):
    """Unauthenticated requests should return 401."""
    res = await client.get("/api/v1/themes")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    res = await client.post("/api/v1/themes", json={
        "name": "Test Theme",
        "theme_json": {}
    })
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_create_global_theme(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Creating a global theme (no brand_id) should succeed for any authenticated user."""
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post(
        "/api/v1/themes",
        json={
            "name": "Quiet Luxury",
            "description": "Minimal, elegant, high-end aesthetic",
            "theme_json": {
                "lighting": "soft-studio",
                "mood": "aspirational",
                "location": "studio"
            }
        },
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["name"] == "Quiet Luxury"
    assert data["brand_id"] is None

    stmt = select(CampaignTheme).where(CampaignTheme.id == data["id"])
    result = await db_session.execute(stmt)
    theme = result.scalars().first()
    assert theme is not None
    assert theme.name == "Quiet Luxury"


@pytest.mark.asyncio
async def test_create_brand_theme(client: AsyncClient, test_data: dict):
    """Creating a brand-specific theme should succeed for authorized users."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post(
        "/api/v1/themes",
        json={
            "name": "Mediterranean Escape",
            "description": "Coastal luxury summer campaign",
            "brand_id": brand.id,
            "theme_json": {
                "lighting": "golden-hour",
                "location": "nature-beach",
                "mood": "romantic"
            }
        },
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["brand_id"] == brand.id


@pytest.mark.asyncio
async def test_create_brand_theme_unauthorized(client: AsyncClient, test_data: dict):
    """Creating a theme for an unauthorized brand should return 403."""
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post(
        "/api/v1/themes",
        json={
            "name": "Hack Theme",
            "brand_id": 9999,
            "theme_json": {}
        },
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_list_themes(client: AsyncClient, test_data: dict):
    """Listing themes should return global themes. With brand_id, also returns brand themes."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # Create a global theme
    await client.post("/api/v1/themes", json={
        "name": "Global Theme",
        "theme_json": {"mood": "minimal"}
    }, headers=editor_headers)

    # Create a brand theme
    await client.post("/api/v1/themes", json={
        "name": "Brand Theme",
        "brand_id": brand.id,
        "theme_json": {"mood": "aspirational"}
    }, headers=editor_headers)

    # List global themes only
    res = await client.get("/api/v1/themes", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    names = [t["name"] for t in res.json()]
    assert "Global Theme" in names
    assert "Brand Theme" not in names

    # List with brand_id — should include both global and brand themes
    res = await client.get(f"/api/v1/themes?brand_id={brand.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    names = [t["name"] for t in res.json()]
    assert "Global Theme" in names
    assert "Brand Theme" in names


@pytest.mark.asyncio
async def test_get_theme_by_id(client: AsyncClient, test_data: dict):
    """GET by ID should return the theme or 404."""
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/themes", json={
        "name": "Test Get Theme",
        "theme_json": {}
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_201_CREATED
    theme_id = res.json()["id"]

    res = await client.get(f"/api/v1/themes/{theme_id}", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["id"] == theme_id

    res = await client.get("/api/v1/themes/99999", headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_update_theme_access_control(client: AsyncClient, test_data: dict):
    """PATCH requires editor role. Viewer should get 403. 404 for non-existent."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    viewer_headers = test_data["get_headers"]("viewer")

    res = await client.post("/api/v1/themes", json={
        "name": "Original Theme",
        "brand_id": brand.id,
        "theme_json": {"mood": "bold"}
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_201_CREATED
    theme_id = res.json()["id"]

    res = await client.patch(f"/api/v1/themes/{theme_id}", json={"name": "Updated Theme"}, headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["name"] == "Updated Theme"

    res = await client.patch(f"/api/v1/themes/{theme_id}", json={"name": "Hacked"}, headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN

    res = await client.patch("/api/v1/themes/99999", json={"name": "Ghost"}, headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_theme_access_control(client: AsyncClient, test_data: dict):
    """DELETE requires owner/admin. Editor should get 403. 404 for non-existent."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/themes", json={
        "name": "Theme To Delete",
        "brand_id": brand.id,
        "theme_json": {}
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_201_CREATED
    theme_id = res.json()["id"]

    res = await client.delete(f"/api/v1/themes/{theme_id}", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN

    res = await client.delete(f"/api/v1/themes/{theme_id}", headers=owner_headers)
    assert res.status_code == status.HTTP_204_NO_CONTENT

    res = await client.delete(f"/api/v1/themes/{theme_id}", headers=owner_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND
