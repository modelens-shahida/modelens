import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_ghost_batch_rates(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/ghost/rates", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "ghost_rates" in data
    assert data["ghost_rates"]["1K"] == 2
    assert data["ghost_rates"]["2K"] == 4
    assert data["ghost_rates"]["4K"] == 7
    assert data["ghost_rates"]["8K"] == 10
    assert "volumetric_rates" in data


@pytest.mark.asyncio
async def test_ghost_batch_estimate_and_check(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    
    payload = {
        "items": [
            {
                "sku": "SKU-GHOST-01",
                "product_name": "Silk Blouse",
                "garment_type": "top",
                "views": [
                    {"view": "FRONT", "resolution": "2K"},
                    {"view": "BACK", "resolution": "2K"},
                    {"view": "TURNTABLE", "resolution": "2K"} # 2x base = 8
                ]
            }
        ],
        "quality_mode": "STUDIO_QUALITY"
    }

    # 1. Estimate
    res = await client.post("/api/v1/ghost/batch/estimate", json=payload, headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    # 4 (FRONT) + 4 (BACK) + 8 (TURNTABLE) = 16
    assert data["total_credits"] == 16
    assert data["total_items"] == 1

    # 2. Check
    res = await client.post("/api/v1/ghost/batch/check", json=payload, headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    check_data = res.json()
    assert "sufficient" in check_data
    assert check_data["required"] == 16


@pytest.mark.asyncio
async def test_ghost_batch_creation_and_callbacks(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")

    batch_payload = {
        "items": [
            {
                "sku": "SKU-DRESS-001",
                "product_name": "Evening Maxi Dress",
                "garment_type": "dress",
                "views": [
                    {"view": "FRONT", "resolution": "2K"},
                    {"view": "BACK", "resolution": "2K"}
                ]
            }
        ],
        "quality_mode": "STUDIO_QUALITY",
        "preserve_print": True,
        "preserve_construction": True,
        "project_name": "Summer Collection Ghost"
    }

    # 1. Create Ghost Batch Job
    res = await client.post("/api/v1/ghost/batch", json=batch_payload, headers=owner_headers)
    assert res.status_code == status.HTTP_201_CREATED
    job_data = res.json()
    assert "job_id" in job_data
    assert job_data["status"] == "queued"
    assert job_data["total_credits_reserved"] == 8 # 4 + 4
    job_id = job_data["job_id"]

    # 2. Get Ghost Batch Status
    res = await client.get(f"/api/v1/ghost/batch/{job_id}", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    status_data = res.json()
    assert status_data["job_id"] == job_id
    assert status_data["status"] == "queued"
    assert status_data["total_items"] == 1

    # 3. Complete Callback
    res = await client.post(f"/api/v1/ghost/batch/{job_id}/complete", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    complete_data = res.json()
    assert complete_data["status"] in ["finalized", "completed", "success"]
