import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import CreditTransaction, Brand, CatalogJob
from app.config import settings

INTERNAL_SECRET = getattr(settings, "INTERNAL_CALLBACK_SECRET", "modelens-internal-secret")
INTERNAL_HEADERS = {"x-internal-secret": INTERNAL_SECRET}


# ========================== Credit Estimation Tests ==============

def test_estimate_fashn_credits_standard_2k():
    from app.routers.fashn_workflow import estimate_fashn_credits
    assert estimate_fashn_credits("product-to-model", "2k", 1, "standard") == 2


def test_estimate_fashn_credits_quality_2k():
    from app.routers.fashn_workflow import estimate_fashn_credits
    assert estimate_fashn_credits("product-to-model", "2k", 1, "quality") == 4


def test_estimate_fashn_credits_quality_4k():
    from app.routers.fashn_workflow import estimate_fashn_credits
    assert estimate_fashn_credits("try-on-max", "4k", 1, "quality") == 7


def test_estimate_fashn_credits_multi_images():
    from app.routers.fashn_workflow import estimate_fashn_credits
    assert estimate_fashn_credits("product-to-model", "2k", 2, "quality") == 8


# ========================== Credit Check Tests ===================

@pytest.mark.asyncio
async def test_fashn_credit_check_sufficient(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post(
        "/api/v1/fashn/check",
        json={
            "mode": "product-to-model",
            "resolution": "2k",
            "num_images": 1,
            "generation_mode": "quality",
        },
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "sufficient" in data
    assert "balance" in data
    assert "required" in data


# ========================== Product-to-Model Tests ===============

@pytest.mark.asyncio
async def test_product_to_model_success(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]

    # Set sufficient credits
    brand.credits = 100
    await db_session.commit()

    mock_result = {
        "id": "fashn_test_001",
        "status": "completed",
        "output": [{"url": "https://example.com/output.png", "quality_score": 0.95}]
    }

    with patch("app.routers.fashn_workflow.fashn_service.generate_product_to_model", new_callable=AsyncMock) as mock_fashn:
        mock_fashn.return_value = mock_result

        res = await client.post(
            "/api/v1/fashn/product-to-model",
            json={
                "product_image_url": "https://example.com/product.png",
                "resolution": "2k",
                "generation_mode": "quality",
                "num_images": 1,
            },
            headers=owner_headers,
        )

    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "completed"
    assert data["mode"] == "product-to-model"
    assert data["credits_reserved"] == 4


@pytest.mark.asyncio
async def test_product_to_model_insufficient_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]

    # Set insufficient credits
    brand.credits = 0
    await db_session.commit()

    res = await client.post(
        "/api/v1/fashn/product-to-model",
        json={
            "product_image_url": "https://example.com/product.png",
            "resolution": "4k",
            "generation_mode": "quality",
            "num_images": 1,
        },
        headers=owner_headers,
    )

    assert res.status_code == 402
    data = res.json()
    assert data["detail"]["error"] == "insufficient_credits"


# ========================== Try-On Max Tests ====================

@pytest.mark.asyncio
async def test_try_on_max_success(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]

    brand.credits = 100
    await db_session.commit()

    mock_result = {
        "id": "fashn_tryon_001",
        "status": "completed",
        "output": [{"url": "https://example.com/tryon.png", "quality_score": 0.96}]
    }

    with patch("app.routers.fashn_workflow.fashn_service.generate_try_on_max", new_callable=AsyncMock) as mock_fashn:
        mock_fashn.return_value = mock_result

        res = await client.post(
            "/api/v1/fashn/try-on-max",
            json={
                "product_image_url": "https://example.com/product.png",
                "model_image_url": "https://example.com/model.png",
                "resolution": "2k",
                "generation_mode": "quality",
                "num_images": 1,
            },
            headers=owner_headers,
        )

    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "completed"
    assert data["mode"] == "try-on-max"
    assert data["credits_reserved"] == 4


# ========================== Webhook Tests =======================

@pytest.mark.asyncio
async def test_webhook_complete_finalizes_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    txn = CreditTransaction(
        user_id=owner_user.id,
        brand_id=brand.id,
        transaction_type="reserved",
        amount=-4,
        description="FASHN test reservation",
        reference_id="fashn_webhook_test",
        status="pending",
    )
    db_session.add(txn)
    await db_session.commit()

    res = await client.post(
        "/api/v1/fashn/webhook",
        json={
            "job_id": "fashn_webhook_test",
            "status": "completed",
            "output": [{"url": "https://example.com/result.png"}]
        },
        headers=INTERNAL_HEADERS,
    )

    assert res.status_code == 200
    assert res.json()["status"] == "finalized"


@pytest.mark.asyncio
async def test_webhook_fail_refunds_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    initial_credits = brand.credits or 0

    txn = CreditTransaction(
        user_id=owner_user.id,
        brand_id=brand.id,
        transaction_type="reserved",
        amount=-4,
        description="FASHN test reservation for fail",
        reference_id="fashn_fail_test",
        status="pending",
    )
    db_session.add(txn)
    await db_session.commit()

    res = await client.post(
        "/api/v1/fashn/webhook",
        json={
            "job_id": "fashn_fail_test",
            "status": "failed",
            "error": "FASHN provider timeout"
        },
        headers=INTERNAL_HEADERS,
    )

    assert res.status_code == 200
    assert res.json()["status"] == "refunded"

    await db_session.refresh(brand)
    assert (brand.credits or 0) == initial_credits + 4


@pytest.mark.asyncio
async def test_webhook_requires_secret(client: AsyncClient):
    res = await client.post(
        "/api/v1/fashn/webhook",
        json={"job_id": "test", "status": "completed"},
    )
    assert res.status_code == 403
