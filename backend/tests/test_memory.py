import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


# ========================== Auth Tests ============================

@pytest.mark.asyncio
async def test_brand_memory_auth_required(client: AsyncClient, test_data: dict):
    """Brand memory without auth should return 401."""
    brand = test_data["brand"]
    res = await client.get(f"/api/v1/brands/{brand.id}/memory")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_campaign_memory_auth_required(client: AsyncClient):
    """Campaign memory without auth should return 401."""
    res = await client.get("/api/v1/campaigns/1/memory")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ========================== Brand Memory Tests ====================

@pytest.mark.asyncio
async def test_brand_memory_unauthorized_brand(client: AsyncClient, test_data: dict):
    """Brand memory for unauthorized brand should return 403."""
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/brands/9999/memory", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_brand_memory_empty(client: AsyncClient, test_data: dict):
    """Brand memory with no approved assets should return zeros."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(f"/api/v1/brands/{brand.id}/memory", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_assets"] == 0
    assert data["tag_frequency"] == {}


@pytest.mark.asyncio
async def test_brand_memory_with_approved_assets(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Brand memory should count approved assets and their tag frequencies."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # Insert approved asset
    result = await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata, status)
        VALUES (:brand_id, 'Approved Asset', 'approved.jpg', '/uploads/approved.jpg', 'image', '{}', 'approved')
        RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    asset_id = result.fetchone()[0]

    # Insert tags for the asset
    await db_session.execute(text("""
        INSERT INTO asset_tags (asset_id, tag) VALUES (:asset_id, :tag)
    """), {"asset_id": asset_id, "tag": "lighting:golden-hour"})
    await db_session.execute(text("""
        INSERT INTO asset_tags (asset_id, tag) VALUES (:asset_id, :tag)
    """), {"asset_id": asset_id, "tag": "mood:aspirational"})
    await db_session.commit()

    res = await client.get(f"/api/v1/brands/{brand.id}/memory", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_assets"] == 1
    assert data["tag_frequency"]["lighting:golden-hour"] == 1
    assert data["tag_frequency"]["mood:aspirational"] == 1


@pytest.mark.asyncio
async def test_brand_memory_excludes_draft_assets(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Brand memory should only count approved assets, not drafts."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # Insert draft asset
    await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata, status)
        VALUES (:brand_id, 'Draft Asset', 'draft.jpg', '/uploads/draft.jpg', 'image', '{}', 'draft')
    """), {"brand_id": brand.id})
    await db_session.commit()

    res = await client.get(f"/api/v1/brands/{brand.id}/memory", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_assets"] == 0


# ========================== Campaign Memory Tests =================

@pytest.mark.asyncio
async def test_campaign_memory_not_found(client: AsyncClient, test_data: dict):
    """Campaign memory for non-existent campaign should return 404."""
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/campaigns/99999/memory", headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_campaign_memory_empty(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Campaign memory with no linked assets should return zeros."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # Create a campaign
    result = await db_session.execute(text("""
        INSERT INTO campaigns (brand_id, name, description)
        VALUES (:brand_id, 'Test Campaign', 'Test')
        RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    campaign_id = result.fetchone()[0]

    res = await client.get(f"/api/v1/campaigns/{campaign_id}/memory", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_assets"] == 0
    assert data["tag_frequency"] == {}


@pytest.mark.asyncio
async def test_campaign_memory_with_assets(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Campaign memory should return tag frequencies for linked assets."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # Create campaign
    result = await db_session.execute(text("""
        INSERT INTO campaigns (brand_id, name, description)
        VALUES (:brand_id, 'Memory Campaign', 'Test')
        RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    campaign_id = result.fetchone()[0]

    # Create asset
    result = await db_session.execute(text("""
        INSERT INTO assets (brand_id, name, filename, storage_path, asset_type, metadata, status)
        VALUES (:brand_id, 'Campaign Asset', 'campaign.jpg', '/uploads/campaign.jpg', 'image', '{}', 'approved')
        RETURNING id
    """), {"brand_id": brand.id})
    await db_session.commit()
    asset_id = result.fetchone()[0]

    # Link asset to campaign
    await db_session.execute(text("""
        INSERT INTO campaign_assets (campaign_id, asset_id)
        VALUES (:campaign_id, :asset_id)
    """), {"campaign_id": campaign_id, "asset_id": asset_id})

    # Add tags
    await db_session.execute(text("""
        INSERT INTO asset_tags (asset_id, tag) VALUES (:asset_id, :tag)
    """), {"asset_id": asset_id, "tag": "location:studio"})
    await db_session.commit()

    res = await client.get(f"/api/v1/campaigns/{campaign_id}/memory", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_assets"] == 1
    assert data["tag_frequency"]["location:studio"] == 1
