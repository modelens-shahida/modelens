import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import FixRequest, Asset


@pytest.mark.asyncio
async def test_create_fix_request_auth_required(client: AsyncClient, test_data: dict):
    """Creating a fix request should require authentication."""
    res = await client.post("/api/v1/fix-requests", json={
        "original_asset_id": 1,
        "requester_notes": "Please fix the cropping"
    })
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_create_fix_request_viewer_forbidden(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Viewer should not be able to create fix requests."""
    brand = test_data["brand"]
    viewer_headers = test_data["get_headers"]("viewer")

    asset = Asset(
        brand_id=brand.id,
        name="Test Asset",
        filename="test.jpg",
        storage_path="/uploads/test.jpg",
        asset_type="catalog",
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    res = await client.post("/api/v1/fix-requests", json={
        "original_asset_id": asset.id,
        "requester_notes": "Fix the background"
    }, headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_create_fix_request_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Editor should be able to create a fix request."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    asset = Asset(
        brand_id=brand.id,
        name="Test Asset",
        filename="test2.jpg",
        storage_path="/uploads/test2.jpg",
        asset_type="catalog",
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    res = await client.post("/api/v1/fix-requests", json={
        "original_asset_id": asset.id,
        "requester_notes": "Mannequin alignment is off"
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["review_status"] == "pending"
    assert data["requester_notes"] == "Mannequin alignment is off"

    result = await db_session.execute(select(FixRequest).where(FixRequest.id == data["id"]))
    assert result.scalars().first() is not None


@pytest.mark.asyncio
async def test_create_fix_request_asset_not_found(client: AsyncClient, test_data: dict):
    """Non-existent asset should return 404."""
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/fix-requests", json={
        "original_asset_id": 99999,
        "requester_notes": "Test notes"
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_list_fix_requests(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """List fix requests for a brand."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    asset = Asset(
        brand_id=brand.id,
        name="List Test Asset",
        filename="list_test.jpg",
        storage_path="/uploads/list_test.jpg",
        asset_type="catalog",
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    await client.post("/api/v1/fix-requests", json={
        "original_asset_id": asset.id,
        "requester_notes": "Test fix request"
    }, headers=editor_headers)

    res = await client.get(f"/api/v1/fix-requests?brand_id={brand.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) >= 1


@pytest.mark.asyncio
async def test_update_fix_request_editor_forbidden(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Editor should not be able to update fix request status."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    asset = Asset(
        brand_id=brand.id,
        name="Update Test Asset",
        filename="update_test.jpg",
        storage_path="/uploads/update_test.jpg",
        asset_type="catalog",
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    res = await client.post("/api/v1/fix-requests", json={
        "original_asset_id": asset.id,
        "requester_notes": "Test"
    }, headers=editor_headers)
    fix_id = res.json()["id"]

    res = await client.patch(f"/api/v1/fix-requests/{fix_id}", json={
        "review_status": "completed"
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_update_fix_request_owner_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Owner should be able to update fix request status."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    editor_headers = test_data["get_headers"]("editor")

    asset = Asset(
        brand_id=brand.id,
        name="Owner Update Test Asset",
        filename="owner_update.jpg",
        storage_path="/uploads/owner_update.jpg",
        asset_type="catalog",
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    res = await client.post("/api/v1/fix-requests", json={
        "original_asset_id": asset.id,
        "requester_notes": "Needs fixing"
    }, headers=editor_headers)
    fix_id = res.json()["id"]

    res = await client.patch(f"/api/v1/fix-requests/{fix_id}", json={
        "review_status": "completed",
        "reviewer_notes": "Fixed the alignment issue"
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["review_status"] == "completed"
    assert data["reviewer_notes"] == "Fixed the alignment issue"


@pytest.mark.asyncio
async def test_update_fix_request_invalid_status(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Invalid status should return 400."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    editor_headers = test_data["get_headers"]("editor")

    asset = Asset(
        brand_id=brand.id,
        name="Invalid Status Test Asset",
        filename="invalid_status.jpg",
        storage_path="/uploads/invalid_status.jpg",
        asset_type="catalog",
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    res = await client.post("/api/v1/fix-requests", json={
        "original_asset_id": asset.id,
        "requester_notes": "Test"
    }, headers=editor_headers)
    fix_id = res.json()["id"]

    res = await client.patch(f"/api/v1/fix-requests/{fix_id}", json={
        "review_status": "invalid_status_value"
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_update_fix_request_not_found(client: AsyncClient, test_data: dict):
    """Updating non-existent fix request should return 404."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.patch("/api/v1/fix-requests/99999", json={
        "review_status": "completed"
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND
