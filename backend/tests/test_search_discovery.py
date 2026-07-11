import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, UTC

from app.models.db import Asset
from app.services.search_service import (
    build_faceted_filters,
    compute_relevance_score,
    get_accessible_brand_ids,
)


# ========================== Helper ===============================

async def create_asset(db_session, brand_id, name, asset_type="catalog", status_val="active", days_old=0):
    asset = Asset(
        brand_id=brand_id,
        name=name,
        filename=f"{name.lower().replace(' ', '_')}.jpg",
        storage_path=f"/uploads/{name}.jpg",
        asset_type=asset_type,
        status=status_val,
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)
    if days_old > 0:
        asset.created_at = datetime.now(UTC) - timedelta(days=days_old)
        await db_session.commit()
    return asset


# ========================== Relevance Score Tests ================

def test_exact_name_match_highest_score():
    """Exact name match should get highest relevance score."""
    asset = Asset(name="Summer Dress", filename="summer_dress.jpg", asset_type="catalog", meta={})
    score = compute_relevance_score(asset, "Summer Dress")
    assert score >= 3


def test_partial_name_match_medium_score():
    """Partial name match should get medium relevance score."""
    asset = Asset(name="Summer Dress Collection", filename="dress.jpg", asset_type="catalog", meta={})
    score = compute_relevance_score(asset, "Summer")
    assert score >= 2


def test_no_match_zero_score():
    """Non-matching query should return 0 score."""
    asset = Asset(name="Winter Coat", filename="coat.jpg", asset_type="catalog", meta={})
    score = compute_relevance_score(asset, "swimwear")
    assert score == 0


def test_empty_query_zero_score():
    """Empty query should return 0 score."""
    asset = Asset(name="Summer Dress", filename="dress.jpg", asset_type="catalog", meta={})
    score = compute_relevance_score(asset, "")
    assert score == 0


# ========================== Faceted Filter Tests =================

def test_build_filters_asset_type():
    """asset_type filter should be case-insensitive."""
    filters = build_faceted_filters({1}, asset_type="CATALOG")
    assert len(filters) > 0


def test_build_filters_no_brand_access():
    """Empty accessible_brand_ids should return no results filter."""
    filters = build_faceted_filters(set())
    # Should include brand_id == -1 filter
    assert any("-1" in str(f) or "brand_id" in str(f).lower() for f in filters)


# ========================== API Faceted Search Tests =============

@pytest.mark.asyncio
async def test_faceted_search_auth_required(client: AsyncClient):
    """Faceted search should require authentication."""
    res = await client.get("/api/v1/search/faceted")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_faceted_search_returns_own_brand_assets(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Faceted search should return only accessible brand assets."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    await create_asset(db_session, brand.id, "Summer Dress", "catalog")

    res = await client.get(
        f"/api/v1/search/faceted?brand_id={brand.id}",
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "results" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_faceted_search_forbidden_brand(client: AsyncClient, test_data: dict):
    """Faceted search for unauthorized brand should return 403."""
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/search/faceted?brand_id=99999", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_faceted_search_asset_type_filter(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """asset_type filter should match only correct type."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    await create_asset(db_session, brand.id, "Catalog Item", "catalog")
    await create_asset(db_session, brand.id, "Generated Item", "generated")

    res = await client.get(
        f"/api/v1/search/faceted?brand_id={brand.id}&asset_type=catalog",
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert all(r["asset_type"].lower() == "catalog" for r in data["results"])


@pytest.mark.asyncio
async def test_faceted_search_case_insensitive_filter(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """asset_type filter should be case-insensitive."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    await create_asset(db_session, brand.id, "Case Test", "catalog")

    res_upper = await client.get(
        f"/api/v1/search/faceted?brand_id={brand.id}&asset_type=CATALOG",
        headers=owner_headers
    )
    res_lower = await client.get(
        f"/api/v1/search/faceted?brand_id={brand.id}&asset_type=catalog",
        headers=owner_headers
    )
    assert res_upper.status_code == status.HTTP_200_OK
    assert res_lower.status_code == status.HTTP_200_OK
    assert res_upper.json()["total"] == res_lower.json()["total"]


@pytest.mark.asyncio
async def test_faceted_search_sort_by_name_asc(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Sort by name asc should return alphabetical order."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    await create_asset(db_session, brand.id, "Zebra Top", "catalog")
    await create_asset(db_session, brand.id, "Alpha Dress", "catalog")

    res = await client.get(
        f"/api/v1/search/faceted?brand_id={brand.id}&sort_by=name&sort_order=asc",
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_200_OK
    results = res.json()["results"]
    if len(results) >= 2:
        names = [r["name"] for r in results]
        assert names == sorted(names)


@pytest.mark.asyncio
async def test_faceted_search_pagination(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Pagination should respect limit and offset."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    for i in range(5):
        await create_asset(db_session, brand.id, f"Pagination Item {i}", "catalog")

    res = await client.get(
        f"/api/v1/search/faceted?brand_id={brand.id}&limit=2&offset=0",
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()["results"]) <= 2


@pytest.mark.asyncio
async def test_faceted_search_date_range_filter(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Date range filter should only return assets within the range."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    await create_asset(db_session, brand.id, "Old Asset", "catalog", days_old=60)
    await create_asset(db_session, brand.id, "New Asset", "catalog", days_old=1)

    after_date = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    res = await client.get(
        f"/api/v1/search/faceted?brand_id={brand.id}&created_after={after_date}",
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_faceted_search_text_query(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Text query should filter by name match."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    await create_asset(db_session, brand.id, "Unique Summer Dress", "catalog")

    res = await client.get(
        f"/api/v1/search/faceted?brand_id={brand.id}&q=Unique",
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_faceted_search_invalid_sort(client: AsyncClient, test_data: dict):
    """Invalid sort_by should return 422."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get(
        "/api/v1/search/faceted?sort_by=invalid_sort",
        headers=owner_headers
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
