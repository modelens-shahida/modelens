import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


# ========================== Characters Pagination ==================

@pytest.mark.asyncio
async def test_characters_pagination_default(client: AsyncClient, test_data: dict):
    """Characters list should support default pagination."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # Create 3 characters
    for i in range(3):
        await client.post("/api/v1/characters", json={
            "brand_id": brand.id,
            "name": f"Character {i}",
            "description": "Test",
            "image_path": f"/uploads/char{i}.png"
        }, headers=editor_headers)

    res = await client.get(f"/api/v1/characters?brand_id={brand.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) <= 20


@pytest.mark.asyncio
async def test_characters_pagination_limit(client: AsyncClient, test_data: dict):
    """Characters list should respect limit parameter."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    for i in range(5):
        await client.post("/api/v1/characters", json={
            "brand_id": brand.id,
            "name": f"Paginated Char {i}",
            "description": "Test",
            "image_path": f"/uploads/pchar{i}.png"
        }, headers=editor_headers)

    res = await client.get(
        f"/api/v1/characters?brand_id={brand.id}&limit=2&offset=0",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) <= 2


@pytest.mark.asyncio
async def test_characters_pagination_offset(client: AsyncClient, test_data: dict):
    """Characters list should respect offset parameter."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(
        f"/api/v1/characters?brand_id={brand.id}&limit=20&offset=1000",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json() == []


@pytest.mark.asyncio
async def test_characters_pagination_max_limit(client: AsyncClient, test_data: dict):
    """Characters list should reject limit > 100."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(
        f"/api/v1/characters?brand_id={brand.id}&limit=200",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ========================== Prompts Pagination ====================

@pytest.mark.asyncio
async def test_prompts_pagination_limit(client: AsyncClient, test_data: dict):
    """Prompts list should respect limit parameter."""
    editor_headers = test_data["get_headers"]("editor")

    for i in range(5):
        await client.post("/api/v1/prompts", json={
            "name": f"Prompt {i}",
            "prompt_text": f"Test prompt text {i}"
        }, headers=editor_headers)

    res = await client.get("/api/v1/prompts?limit=2&offset=0", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) <= 2


@pytest.mark.asyncio
async def test_prompts_pagination_offset(client: AsyncClient, test_data: dict):
    """Prompts list with high offset should return empty."""
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get("/api/v1/prompts?limit=20&offset=1000", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json() == []


@pytest.mark.asyncio
async def test_prompts_pagination_max_limit(client: AsyncClient, test_data: dict):
    """Prompts list should reject limit > 100."""
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get("/api/v1/prompts?limit=500", headers=editor_headers)
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ========================== Assets Pagination ====================

@pytest.mark.asyncio
async def test_assets_pagination(client: AsyncClient, test_data: dict):
    """Assets list should support pagination."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(
        f"/api/v1/assets?brand_id={brand.id}&limit=5&offset=0",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) <= 5


@pytest.mark.asyncio
async def test_assets_pagination_max_limit(client: AsyncClient, test_data: dict):
    """Assets list should reject limit > 100."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(
        f"/api/v1/assets?brand_id={brand.id}&limit=200",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ========================== Jobs Pagination ======================

@pytest.mark.asyncio
async def test_jobs_pagination(client: AsyncClient, test_data: dict):
    """Jobs list should support pagination."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(
        f"/api/v1/jobs?brand_id={brand.id}&limit=5&offset=0",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) <= 5


@pytest.mark.asyncio
async def test_jobs_pagination_max_limit(client: AsyncClient, test_data: dict):
    """Jobs list should reject limit > 100."""
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(
        f"/api/v1/jobs?brand_id={brand.id}&limit=200",
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
