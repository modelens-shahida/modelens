import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import CatalogJob, CatalogJobItem, CatalogOutput


# ========================== Helper ===============================

def make_products(n=3):
    return [{"sku_tag": f"SKU-{i+1}", "image_path": f"/uploads/product_{i+1}.jpg"} for i in range(n)]


# ========================== Auth Tests ===========================

@pytest.mark.asyncio
async def test_create_catalog_job_auth_required(client: AsyncClient):
    res = await client.post("/api/v1/catalog-jobs", json={"brand_id": 1, "products": make_products()})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ========================== Credit Tests =========================

@pytest.mark.asyncio
async def test_create_catalog_job_insufficient_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_user.credits = 0
    await db_session.commit()

    with patch("app.routers.catalog_jobs.process_catalog_job") as mock_task:
        mock_task.delay = MagicMock()
        res = await client.post(
            "/api/v1/catalog-jobs",
            json={"brand_id": brand.id, "products": make_products(3), "generation_mode": "studio_quality"},
            headers=owner_headers,
        )
    assert res.status_code == status.HTTP_402_PAYMENT_REQUIRED


@pytest.mark.asyncio
async def test_create_catalog_job_deducts_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_user.credits = 100
    await db_session.commit()

    with patch("app.routers.catalog_jobs.process_catalog_job") as mock_task:
        mock_task.delay = MagicMock()
        res = await client.post(
            "/api/v1/catalog-jobs",
            json={"brand_id": brand.id, "products": make_products(2), "generation_mode": "studio_quality"},
            headers=owner_headers,
        )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["total_items"] == 2
    assert data["credits_reserved"] == 10  # 2 items x 5 credits


@pytest.mark.asyncio
async def test_create_catalog_job_fast_draft_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_user.credits = 100
    await db_session.commit()

    with patch("app.routers.catalog_jobs.process_catalog_job") as mock_task:
        mock_task.delay = MagicMock()
        res = await client.post(
            "/api/v1/catalog-jobs",
            json={"brand_id": brand.id, "products": make_products(3), "generation_mode": "fast_draft"},
            headers=owner_headers,
        )
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["credits_reserved"] == 6  # 3 items x 2 credits


# ========================== CRUD Tests ==========================

@pytest.mark.asyncio
async def test_create_catalog_job_success(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_user.credits = 100
    await db_session.commit()

    with patch("app.routers.catalog_jobs.process_catalog_job") as mock_task:
        mock_task.delay = MagicMock()
        res = await client.post(
            "/api/v1/catalog-jobs",
            json={"brand_id": brand.id, "products": make_products(2)},
            headers=owner_headers,
        )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert "job_id" in data
    assert data["total_items"] == 2
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_get_catalog_job(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_user.credits = 100
    await db_session.commit()

    with patch("app.routers.catalog_jobs.process_catalog_job") as mock_task:
        mock_task.delay = MagicMock()
        create_res = await client.post(
            "/api/v1/catalog-jobs",
            json={"brand_id": brand.id, "products": make_products(2)},
            headers=owner_headers,
        )
    job_id = create_res.json()["job_id"]

    res = await client.get(f"/api/v1/catalog-jobs/{job_id}", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["job_id"] == job_id
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_catalog_job_not_found(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/catalog-jobs/99999", headers=owner_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


# ========================== Cancel Tests ========================

@pytest.mark.asyncio
async def test_cancel_catalog_job(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_user.credits = 100
    await db_session.commit()

    with patch("app.routers.catalog_jobs.process_catalog_job") as mock_task:
        mock_task.delay = MagicMock()
        create_res = await client.post(
            "/api/v1/catalog-jobs",
            json={"brand_id": brand.id, "products": make_products(2)},
            headers=owner_headers,
        )
    job_id = create_res.json()["job_id"]

    res = await client.post(f"/api/v1/catalog-jobs/{job_id}/cancel", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_completed_job_fails(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_headers = test_data["get_headers"]("owner")

    job = CatalogJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="completed",
        total_items=1,
        credits_reserved=5,
        credits_consumed=5,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    res = await client.post(f"/api/v1/catalog-jobs/{job.id}/cancel", headers=owner_headers)
    assert res.status_code == status.HTTP_409_CONFLICT


# ========================== Retry Tests =========================

@pytest.mark.asyncio
async def test_retry_catalog_job(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]
    owner_headers = test_data["get_headers"]("owner")

    job = CatalogJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="failed",
        total_items=2,
        credits_reserved=10,
        credits_consumed=0,
    )
    db_session.add(job)
    await db_session.flush()

    item = CatalogJobItem(job_id=job.id, sku_tag="SKU-1", status="failed")
    db_session.add(item)
    await db_session.commit()

    with patch("app.routers.catalog_jobs.process_catalog_job") as mock_task:
        mock_task.delay = MagicMock()
        res = await client.post(f"/api/v1/catalog-jobs/{job.id}/retry", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK


# ========================== Worker Tests ========================

@pytest.mark.asyncio
async def test_catalog_worker_mock_mode(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    job = CatalogJob(
        user_id=owner_user.id,
        brand_id=brand.id,
        status="queued",
        total_items=1,
        credits_reserved=5,
        credits_consumed=0,
        generation_mode="studio_quality",
        engine_mode="product_to_model",
    )
    db_session.add(job)
    await db_session.flush()

    item = CatalogJobItem(
        job_id=job.id,
        sku_tag="SKU-TEST",
        product_image_path="/uploads/test.jpg",
        status="queued",
    )
    db_session.add(item)
    await db_session.commit()

    from app.worker import _process_catalog_job_async

    class MockTask:
        request = MagicMock()
        request.retries = 0

    await _process_catalog_job_async(MockTask(), job.id)

    result = await db_session.execute(select(CatalogJob).where(CatalogJob.id == job.id))
    updated_job = result.scalars().first()
    assert updated_job.status in ("completed", "partially_completed", "failed")
