import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import Asset, AssetTag
from app.services.ai_tagging_service import generate_ai_tags, get_fallback_tags


# ========================== AI Tagging Service Tests =============

@pytest.mark.asyncio
async def test_fallback_tags_returned_on_no_api_key():
    """Should return fallback tags when no OpenAI key configured."""
    with patch("app.services.ai_tagging_service.logger"):
        with patch.dict("os.environ", {}):
            from app.services.ai_tagging_service import get_fallback_tags
            tags = get_fallback_tags("catalog")
            assert isinstance(tags, list)
            assert len(tags) > 0


@pytest.mark.asyncio
async def test_fallback_tags_on_openai_error():
    """Should return fallback tags when OpenAI call fails."""
    mock_openai = MagicMock()
    mock_openai.AsyncOpenAI.side_effect = Exception("API error")

    with patch.dict("sys.modules", {"openai": mock_openai}):
        tags = await generate_ai_tags(b"fake_image_bytes", "catalog")
        assert isinstance(tags, list)
        assert len(tags) > 0


@pytest.mark.asyncio
async def test_ai_tags_generated_successfully():
    """Should parse AI-generated tags from OpenAI response."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "summer dress, denim, outdoor, casual, fashion"

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    mock_openai = MagicMock()
    mock_openai.AsyncOpenAI.return_value = mock_client

    with patch.dict("sys.modules", {"openai": mock_openai}):
        with patch("app.services.ai_tagging_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-real-key"
            tags = await generate_ai_tags(b"fake_bytes", "catalog")

    assert isinstance(tags, list)
    assert len(tags) <= 5


def test_fallback_tags_max_4():
    """Fallback tags should return max 4 tags."""
    tags = get_fallback_tags("catalog")
    assert len(tags) <= 4


# ========================== Tag API Tests ========================

@pytest.mark.asyncio
async def test_get_asset_tags_auth_required(client: AsyncClient, test_data: dict):
    """Get tags should require authentication."""
    res = await client.get("/api/v1/assets/1/tags")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_add_tag_to_asset(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Should be able to add a tag to an asset."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    asset = Asset(
        brand_id=brand.id,
        name="Tag Test Asset",
        filename="tag_test.jpg",
        storage_path="/uploads/tag_test.jpg",
        asset_type="catalog",
        status="active",
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    res = await client.post(
        f"/api/v1/assets/{asset.id}/tags?tag=summer+dress",
        headers=owner_headers,
    )
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["tag"] == "summer dress"


@pytest.mark.asyncio
async def test_add_duplicate_tag_returns_409(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Adding a duplicate tag should return 409."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    asset = Asset(
        brand_id=brand.id,
        name="Dup Tag Asset",
        filename="dup.jpg",
        storage_path="/uploads/dup.jpg",
        asset_type="catalog",
        status="active",
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    await client.post(f"/api/v1/assets/{asset.id}/tags?tag=denim", headers=owner_headers)
    res = await client.post(f"/api/v1/assets/{asset.id}/tags?tag=denim", headers=owner_headers)
    assert res.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_get_tags_returns_list(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Get tags should return list of tags."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    asset = Asset(
        brand_id=brand.id,
        name="List Tags Asset",
        filename="list.jpg",
        storage_path="/uploads/list.jpg",
        asset_type="catalog",
        status="active",
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    tag = AssetTag(asset_id=asset.id, tag="outdoor")
    db_session.add(tag)
    await db_session.commit()

    res = await client.get(f"/api/v1/assets/{asset.id}/tags", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert isinstance(res.json(), list)
    assert any(t["tag"] == "outdoor" for t in res.json())


@pytest.mark.asyncio
async def test_delete_tag(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Should be able to delete a tag from an asset."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    asset = Asset(
        brand_id=brand.id,
        name="Delete Tag Asset",
        filename="del.jpg",
        storage_path="/uploads/del.jpg",
        asset_type="catalog",
        status="active",
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    tag = AssetTag(asset_id=asset.id, tag="to-delete")
    db_session.add(tag)
    await db_session.commit()
    await db_session.refresh(tag)

    res = await client.delete(f"/api/v1/assets/{asset.id}/tags/{tag.id}", headers=owner_headers)
    assert res.status_code == status.HTTP_204_NO_CONTENT

    result = await db_session.execute(select(AssetTag).where(AssetTag.id == tag.id))
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_delete_nonexistent_tag_returns_404(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Deleting non-existent tag should return 404."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    asset = Asset(
        brand_id=brand.id,
        name="No Tag Asset",
        filename="notag.jpg",
        storage_path="/uploads/notag.jpg",
        asset_type="catalog",
        status="active",
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    res = await client.delete(f"/api/v1/assets/{asset.id}/tags/99999", headers=owner_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND
