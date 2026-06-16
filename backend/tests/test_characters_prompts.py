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


@pytest.mark.asyncio
async def test_get_character_by_id(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post(
        "/api/v1/characters",
        json={"brand_id": brand.id, "name": "Test Character", "description": "Test desc", "image_path": "/uploads/test.png"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    character_id = res.json()["id"]

    res = await client.get(f"/api/v1/characters/{character_id}", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["id"] == character_id

    res = await client.get("/api/v1/characters/99999", headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_update_character_access_control_extended(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    viewer_headers = test_data["get_headers"]("viewer")

    res = await client.post(
        "/api/v1/characters",
        json={"brand_id": brand.id, "name": "Original Name", "description": "Original desc", "image_path": "/uploads/orig.png"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    character_id = res.json()["id"]

    res = await client.patch(f"/api/v1/characters/{character_id}", json={"name": "Updated Name"}, headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["name"] == "Updated Name"

    res = await client.patch(f"/api/v1/characters/{character_id}", json={"name": "Hacked"}, headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN

    res = await client.patch("/api/v1/characters/99999", json={"name": "Ghost"}, headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_character_access_control_extended(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post(
        "/api/v1/characters",
        json={"brand_id": brand.id, "name": "To Delete", "description": "Delete me", "image_path": "/uploads/del.png"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    character_id = res.json()["id"]

    res = await client.delete(f"/api/v1/characters/{character_id}", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN

    res = await client.delete(f"/api/v1/characters/{character_id}", headers=owner_headers)
    assert res.status_code == status.HTTP_204_NO_CONTENT

    res = await client.delete(f"/api/v1/characters/{character_id}", headers=owner_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_prompt_by_id_extended(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post(
        "/api/v1/prompts",
        json={"name": "Test Prompt", "prompt_text": "Golden hour lighting"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    prompt_id = res.json()["id"]

    res = await client.get(f"/api/v1/prompts/{prompt_id}", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["id"] == prompt_id

    res = await client.get("/api/v1/prompts/99999", headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_update_and_delete_prompt_extended(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post(
        "/api/v1/prompts",
        json={"name": "Original Prompt", "prompt_text": "Original text"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    prompt_id = res.json()["id"]

    res = await client.patch(f"/api/v1/prompts/{prompt_id}", json={"name": "Updated Prompt"}, headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["name"] == "Updated Prompt"

    res = await client.patch("/api/v1/prompts/99999", json={"name": "Ghost"}, headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND

    res = await client.delete(f"/api/v1/prompts/{prompt_id}", headers=editor_headers)
    assert res.status_code == status.HTTP_204_NO_CONTENT

    res = await client.delete("/api/v1/prompts/99999", headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND
