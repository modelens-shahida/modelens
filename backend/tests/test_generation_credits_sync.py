import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import CreditTransaction, Brand
from app.config import settings

INTERNAL_SECRET = getattr(settings, "INTERNAL_CALLBACK_SECRET", "modelens-internal-secret")
INTERNAL_HEADERS = {"x-internal-secret": INTERNAL_SECRET}


# ========================== Credit Estimation Tests ==============

def test_estimate_credits_default():
    from app.routers.templates_proxy import estimate_credits
    assert estimate_credits({}) == 2


def test_estimate_credits_2k_2outputs():
    from app.routers.templates_proxy import estimate_credits
    assert estimate_credits({"outputCount": 2, "resolution": "2K"}) == 4


def test_estimate_credits_4k_1output():
    from app.routers.templates_proxy import estimate_credits
    assert estimate_credits({"outputCount": 1, "resolution": "4K"}) == 5


def test_estimate_credits_8k_2outputs():
    from app.routers.templates_proxy import estimate_credits
    assert estimate_credits({"outputCount": 2, "resolution": "8K"}) == 20


# ========================== Internal Callback Auth Tests =========

@pytest.mark.asyncio
async def test_complete_callback_requires_secret(client: AsyncClient):
    res = await client.post("/api/v1/internal/generations/gen_001/complete", json={"generation_id": "gen_001"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_fail_callback_requires_secret(client: AsyncClient):
    res = await client.post("/api/v1/internal/generations/gen_001/fail", json={"generation_id": "gen_001"})
    assert res.status_code == 403


# ========================== Complete Callback Tests ==============

@pytest.mark.asyncio
async def test_complete_callback_not_found(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post(
        "/api/v1/internal/generations/nonexistent_gen/complete",
        json={"generation_id": "nonexistent_gen"},
        headers=INTERNAL_HEADERS,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_complete_callback_finalizes_transaction(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    # Create pending transaction
    txn = CreditTransaction(
        user_id=owner_user.id,
        brand_id=brand.id,
        transaction_type="reserved",
        amount=-5,
        description="Test reservation",
        reference_id="gen_complete_test",
        status="pending",
    )
    db_session.add(txn)
    await db_session.commit()

    res = await client.post(
        "/api/v1/internal/generations/gen_complete_test/complete",
        json={"generation_id": "gen_complete_test"},
        headers=INTERNAL_HEADERS,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "completed"

    # Verify transaction status updated
    await db_session.refresh(txn)
    assert txn.status == "completed"


# ========================== Fail Callback Tests ==================

@pytest.mark.asyncio
async def test_fail_callback_refunds_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    initial_credits = brand.credits or 0

    # Create pending transaction
    txn = CreditTransaction(
        user_id=owner_user.id,
        brand_id=brand.id,
        transaction_type="reserved",
        amount=-10,
        description="Test reservation for fail",
        reference_id="gen_fail_test",
        status="pending",
    )
    db_session.add(txn)
    await db_session.commit()

    res = await client.post(
        "/api/v1/internal/generations/gen_fail_test/fail",
        json={"generation_id": "gen_fail_test", "reason": "Provider timeout"},
        headers=INTERNAL_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "refunded"
    assert data["credits_refunded"] == 10

    # Verify brand credits restored
    await db_session.refresh(brand)
    assert (brand.credits or 0) == initial_credits + 10


@pytest.mark.asyncio
async def test_fail_callback_not_found(client: AsyncClient):
    res = await client.post(
        "/api/v1/internal/generations/nonexistent_fail/fail",
        json={"generation_id": "nonexistent_fail"},
        headers=INTERNAL_HEADERS,
    )
    assert res.status_code == 404
