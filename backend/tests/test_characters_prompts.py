import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import Character, PromptTemplate

@pytest.mark.asyncio
async def test_characters_endpoints_auth_required(client: AsyncClient):
    # GET characters without auth should fail
    res = await client.get("/api/v1/characters")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # POST characters without auth should fail
    res = await client.post("/api/v1/characters", json={
        "brand_id": 1,
        "name": "Luxury Editorial",
        "description": "Premium luxury portrait theme",
        "image_path": "/uploads/luxury.png"
    })
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_characters_crud_access_control(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # 1. Create a character for our brand (should succeed)
    res = await client.post(
        "/api/v1/characters",
        json={
            "brand_id": brand.id,
            "name": "Mediterranean Escape Model",
            "description": "Sun-kissed commercial summer look",
            "image_path": "/uploads/med_summer.png"
        },
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["name"] == "Mediterranean Escape Model"
    assert data["brand_id"] == brand.id

    # Verify database record
    stmt = select(Character).where(Character.id == data["id"])
    result = await db_session.execute(stmt)
    char = result.scalars().first()
    assert char is not None
    assert char.name == "Mediterranean Escape Model"

    # 2. Try to create a character for an unauthorized brand ID (e.g. 9999) (should fail with 403)
    res = await client.post(
        "/api/v1/characters",
        json={
            "brand_id": 9999,
            "name": "Unauthorized Model",
            "description": "Hack test",
            "image_path": "/uploads/hack.png"
        },
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 3. List characters for our brand
    res = await client.get(f"/api/v1/characters?brand_id={brand.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    list_data = res.json()
    assert len(list_data) == 1
    assert list_data[0]["name"] == "Mediterranean Escape Model"

    # 4. Try to list characters for an unauthorized brand (should fail with 403)
    res = await client.get("/api/v1/characters?brand_id=9999", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_prompts_endpoints_auth_required(client: AsyncClient):
    # GET prompts without auth should fail
    res = await client.get("/api/v1/prompts")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_prompts_crud(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    # 1. Create a prompt template (should succeed since prompts are global resources)
    res = await client.post(
        "/api/v1/prompts",
        json={
            "name": "Luxury Lighting Prompt",
            "prompt_text": "Soft editorial studio lighting with gentle highlights, fashion look"
        },
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["name"] == "Luxury Lighting Prompt"
    assert data["prompt_text"] == "Soft editorial studio lighting with gentle highlights, fashion look"

    # Verify database record
    stmt = select(PromptTemplate).where(PromptTemplate.id == data["id"])
    result = await db_session.execute(stmt)
    prompt = result.scalars().first()
    assert prompt is not None
    assert prompt.name == "Luxury Lighting Prompt"

    # 2. List prompts
    res = await client.get("/api/v1/prompts", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    list_data = res.json()
    assert len(list_data) == 1
    assert list_data[0]["name"] == "Luxury Lighting Prompt"
