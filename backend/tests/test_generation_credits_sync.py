import pytest
import pytest_asyncio
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import User, Brand, CreditTransaction
from app.services.credits_sync_service import credits_sync_service

@pytest.mark.asyncio
async def test_generation_credits_sync_full_flow(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    owner_user = test_data["users"]["owner"]
    brand_id = test_data["brand"].id

    # 1. Check Credit Balance
    res = await client.get("/api/v1/credits/balance", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "balance" in data
    assert isinstance(data["balance"], int)

    # 2. Check Credit Rates
    res = await client.get("/api/v1/credits/rates", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "rates" in data

    # 3. Credit Estimate for Multi-Angle Batch
    res = await client.post("/api/v1/credits/estimate", json={
        "quality_mode": "STUDIO_QUALITY",
        "resolution": "2K",
        "angle_count": 4
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    estimate = res.json()
    assert estimate["estimated_credits"] == 16 # 4 credits * 4 angles

    # 4. Check If Sufficient Credits
    res = await client.post("/api/v1/credits/check", json={
        "quality_mode": "STUDIO_QUALITY",
        "resolution": "2K",
        "angle_count": 4
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    check_data = res.json()
    assert "sufficient" in check_data
    assert check_data["required"] == 16

    # 5. Reserve & Complete Callback
    await credits_sync_service.reserve_credits(
        brand_id=brand_id,
        user_id=owner_user.id,
        amount=16,
        generation_id="GEN-TEST-001",
        description="4-angle batch reservation",
        db=db_session
    )
    res = await client.post(
        "/api/v1/internal/generations/GEN-TEST-001/complete",
        json={"generation_id": "GEN-TEST-001"},
        headers={"x-internal-secret": "modelens-internal-secret"}
    )
    assert res.status_code == status.HTTP_200_OK

    # 6. Reserve & Failure / Refund Callback
    await credits_sync_service.reserve_credits(
        brand_id=brand_id,
        user_id=owner_user.id,
        amount=8,
        generation_id="GEN-TEST-FAIL-001",
        description="Failing job reservation",
        db=db_session
    )
    res = await client.post(
        "/api/v1/internal/generations/GEN-TEST-FAIL-001/fail",
        json={"generation_id": "GEN-TEST-FAIL-001", "reason": "GPU timeout"},
        headers={"x-internal-secret": "modelens-internal-secret"}
    )
    assert res.status_code == status.HTTP_200_OK

    # 7. Billing Summary
    res = await client.get("/api/v1/billing/summary", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    billing = res.json()
    assert "balance" in billing or "current_balance" in billing
