import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import Brand, CreditTransaction


# ========================== Threshold Tests ======================

def test_alert_levels_defined():
    from app.routers.low_credit_alerts import ALERT_LEVELS
    assert "critical" in ALERT_LEVELS
    assert "low" in ALERT_LEVELS
    assert "warning" in ALERT_LEVELS


def test_critical_threshold():
    from app.routers.low_credit_alerts import DEFAULT_CRITICAL_THRESHOLD
    assert DEFAULT_CRITICAL_THRESHOLD == 5


def test_low_threshold():
    from app.routers.low_credit_alerts import DEFAULT_LOW_CREDIT_THRESHOLD
    assert DEFAULT_LOW_CREDIT_THRESHOLD == 20


# ========================== Alert Status Tests ===================

@pytest.mark.asyncio
async def test_alert_status_sufficient_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    brand.credits = 100
    await db_session.commit()

    res = await client.get("/api/v1/credits/alerts/status", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["current_balance"] == 100
    assert data["alert_level"] is None
    assert data["is_critical"] is False
    assert data["is_low"] is False
    assert data["can_generate"] is True


@pytest.mark.asyncio
async def test_alert_status_low_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    brand.credits = 15
    await db_session.commit()

    res = await client.get("/api/v1/credits/alerts/status", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["alert_level"] == "low"
    assert data["is_low"] is True
    assert data["is_critical"] is False


@pytest.mark.asyncio
async def test_alert_status_critical_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    brand.credits = 3
    await db_session.commit()

    res = await client.get("/api/v1/credits/alerts/status", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["alert_level"] == "critical"
    assert data["is_critical"] is True
    assert data["can_generate"] is True


@pytest.mark.asyncio
async def test_alert_status_zero_credits(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    brand.credits = 0
    await db_session.commit()

    res = await client.get("/api/v1/credits/alerts/status", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["can_generate"] is False
    assert data["is_critical"] is True


# ========================== Alert Check Tests ====================

@pytest.mark.asyncio
async def test_manual_alert_check_low(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    brand.credits = 10
    await db_session.commit()

    with patch("app.routers.low_credit_alerts.check_and_trigger_alerts", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = {
            "brand_id": brand.id,
            "current_balance": 10,
            "alert_level": "low",
            "threshold_breached": 20,
            "email_sent": True,
            "webhook_triggered": True,
        }

        res = await client.post("/api/v1/credits/alerts/check", headers=owner_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["alert_level"] == "low"


# ========================== Threshold Config Tests ===============

@pytest.mark.asyncio
async def test_get_thresholds(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/credits/alerts/thresholds", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "thresholds" in data
    assert "defaults" in data
    assert data["defaults"]["critical"] == 5
    assert data["defaults"]["low"] == 20


# ========================== History Tests =======================

@pytest.mark.asyncio
async def test_alert_history(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    # Create some transactions
    txn = CreditTransaction(
        user_id=owner_user.id,
        brand_id=brand.id,
        transaction_type="deduction",
        amount=-10,
        description="Test deduction",
        reference_id="test_ref",
        status="completed",
    )
    db_session.add(txn)
    await db_session.commit()

    res = await client.get("/api/v1/credits/alerts/history", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "history" in data
    assert data["total"] >= 1
