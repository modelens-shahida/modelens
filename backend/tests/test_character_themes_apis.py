import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ========================== Character Versions Tests ==============

@pytest.mark.asyncio
async def test_create_character_version_success(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/characters", json={
        "brand_id": brand.id, "name": "Version Test", "description": "Test", "image_path": "/uploads/v.png"
    }, headers=editor_headers)
    character_id = res.json()["id"]

    res = await client.post(f"/api/v1/characters/{character_id}/versions", json={
        "prompt_trigger": "luxury_v1",
        "config_overrides": {"lighting": "soft-studio"}
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["version_number"] == 1
    assert res.json()["config_overrides"]["lighting"] == "soft-studio"


@pytest.mark.asyncio
async def test_create_character_version_auto_increment(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/characters", json={
        "brand_id": brand.id, "name": "Auto Inc", "description": "Test", "image_path": "/uploads/ai.png"
    }, headers=editor_headers)
    character_id = res.json()["id"]

    r1 = await client.post(f"/api/v1/characters/{character_id}/versions", json={"prompt_trigger": "v1"}, headers=editor_headers)
    r2 = await client.post(f"/api/v1/characters/{character_id}/versions", json={"prompt_trigger": "v2"}, headers=editor_headers)
    assert r1.json()["version_number"] == 1
    assert r2.json()["version_number"] == 2


@pytest.mark.asyncio
async def test_create_character_version_viewer_forbidden(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")
    viewer_headers = test_data["get_headers"]("viewer")

    res = await client.post("/api/v1/characters", json={
        "brand_id": brand.id, "name": "Viewer Test", "description": "Test", "image_path": "/uploads/vt.png"
    }, headers=editor_headers)
    character_id = res.json()["id"]

    res = await client.post(f"/api/v1/characters/{character_id}/versions", json={"prompt_trigger": "fail"}, headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_create_character_version_not_found(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/characters/99999/versions", json={"prompt_trigger": "ghost"}, headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_list_character_versions(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/characters", json={
        "brand_id": brand.id, "name": "List Versions", "description": "Test", "image_path": "/uploads/lv.png"
    }, headers=editor_headers)
    character_id = res.json()["id"]

    await client.post(f"/api/v1/characters/{character_id}/versions", json={"prompt_trigger": "v1"}, headers=editor_headers)
    await client.post(f"/api/v1/characters/{character_id}/versions", json={"prompt_trigger": "v2"}, headers=editor_headers)

    res = await client.get(f"/api/v1/characters/{character_id}/versions", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) == 2


# ========================== Character Embeddings Tests ============

@pytest.mark.asyncio
async def test_create_character_embedding_success(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/characters", json={
        "brand_id": brand.id, "name": "Embed Char", "description": "Test", "image_path": "/uploads/ec.png"
    }, headers=editor_headers)
    character_id = res.json()["id"]

    res = await client.post(f"/api/v1/characters/{character_id}/versions", json={"prompt_trigger": "embed_v1"}, headers=editor_headers)
    version_id = res.json()["id"]

    res = await client.post(
        f"/api/v1/characters/{character_id}/versions/{version_id}/embeddings",
        json={"embedding": [0.1] * 1536, "tag": "luxury-editorial"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["tag"] == "luxury-editorial"


@pytest.mark.asyncio
async def test_create_character_embedding_wrong_dimensions(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/characters", json={
        "brand_id": brand.id, "name": "Wrong Dim", "description": "Test", "image_path": "/uploads/wd.png"
    }, headers=editor_headers)
    character_id = res.json()["id"]

    res = await client.post(f"/api/v1/characters/{character_id}/versions", json={"prompt_trigger": "wd_v1"}, headers=editor_headers)
    version_id = res.json()["id"]

    res = await client.post(
        f"/api/v1/characters/{character_id}/versions/{version_id}/embeddings",
        json={"embedding": [0.1] * 512, "tag": "wrong"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_character_embedding_version_not_found(client: AsyncClient, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/characters", json={
        "brand_id": brand.id, "name": "No Version", "description": "Test", "image_path": "/uploads/nv.png"
    }, headers=editor_headers)
    character_id = res.json()["id"]

    res = await client.post(
        f"/api/v1/characters/{character_id}/versions/99999/embeddings",
        json={"embedding": [0.1] * 1536, "tag": "ghost"},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND


# ========================== Theme Packages Tests ==================

@pytest.mark.asyncio
async def test_create_theme_package_success(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/themes", json={"name": "Pkg Theme", "theme_json": {}}, headers=editor_headers)
    theme_id = res.json()["id"]

    res = await client.post(f"/api/v1/themes/{theme_id}/packages", json={"location_name": "Mediterranean Coast"}, headers=editor_headers)
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["location_name"] == "Mediterranean Coast"


@pytest.mark.asyncio
async def test_create_theme_package_invalid_character(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/themes", json={"name": "Invalid Char Theme", "theme_json": {}}, headers=editor_headers)
    theme_id = res.json()["id"]

    res = await client.post(f"/api/v1/themes/{theme_id}/packages", json={"character_id": 99999}, headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_create_theme_package_not_found(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/themes/99999/packages", json={"location_name": "Ghost"}, headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_list_theme_packages(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    res = await client.post("/api/v1/themes", json={"name": "List Pkg Theme", "theme_json": {}}, headers=editor_headers)
    theme_id = res.json()["id"]

    await client.post(f"/api/v1/themes/{theme_id}/packages", json={"location_name": "Beach"}, headers=editor_headers)
    await client.post(f"/api/v1/themes/{theme_id}/packages", json={"location_name": "Studio"}, headers=editor_headers)

    res = await client.get(f"/api/v1/themes/{theme_id}/packages", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) == 2


@pytest.mark.asyncio
async def test_list_theme_packages_not_found(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/themes/99999/packages", headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND
