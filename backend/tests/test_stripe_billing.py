import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import User, CreditTransaction


# ========================== Checkout Tests ========================

@pytest.mark.asyncio
async def test_checkout_session_auth_required(client: AsyncClient):
    """Checkout session should require authentication."""
    res = await client.post("/api/v1/billing/checkout-session", json={
        "package": "lite", "frequency": "monthly"
    })
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_checkout_session_mock_mode(client: AsyncClient, test_data: dict):
    """In mock mode, should return mock session URL."""
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/billing/checkout-session", json={
        "package": "lite", "frequency": "monthly"
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "session_url" in data
    assert data["mock"] is True
    assert "lite" in data["session_url"]


@pytest.mark.asyncio
async def test_checkout_session_invalid_package(client: AsyncClient, test_data: dict):
    """Invalid package should return 400."""
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/billing/checkout-session", json={
        "package": "invalid", "frequency": "monthly"
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_checkout_session_invalid_frequency(client: AsyncClient, test_data: dict):
    """Invalid frequency should return 400."""
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/billing/checkout-session", json={
        "package": "pro", "frequency": "weekly"
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_checkout_session_all_packages(client: AsyncClient, test_data: dict):
    """All packages (lite, plus, pro) should work in mock mode."""
    editor_headers = test_data["get_headers"]("editor")
    for package in ["lite", "plus", "pro"]:
        res = await client.post("/api/v1/billing/checkout-session", json={
            "package": package, "frequency": "monthly"
        }, headers=editor_headers)
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["mock"] is True


@pytest.mark.asyncio
async def test_checkout_session_real_stripe_resolves_price_id(client: AsyncClient, test_data: dict):
    """With mock mode disabled, should pass resolved Stripe Price ID to Stripe Session."""
    editor_headers = test_data["get_headers"]("editor")
    
    mock_session = MagicMock()
    mock_session.id = "cs_real_123"
    mock_session.url = "https://checkout.stripe.com/pay/cs_real_123"
    
    with patch("app.routers.billing.settings") as mock_settings:
        mock_settings.STRIPE_MOCK_MODE = False
        mock_settings.STRIPE_API_KEY = "sk_test_key"
        mock_settings.STRIPE_PRICE_LITE_MONTHLY = "price_lite_monthly_real_id"
        mock_settings.STRIPE_SUCCESS_URL = "https://success"
        mock_settings.STRIPE_CANCEL_URL = "https://cancel"
        
        with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
            res = await client.post("/api/v1/billing/checkout-session", json={
                "package": "lite", "frequency": "monthly"
            }, headers=editor_headers)
            
            assert res.status_code == status.HTTP_200_OK
            assert res.json()["mock"] is False
            assert res.json()["session_url"] == "https://checkout.stripe.com/pay/cs_real_123"
            
            mock_create.assert_called_once()
            called_kwargs = mock_create.call_args[1]
            assert called_kwargs["line_items"][0]["price"] == "price_lite_monthly_real_id"


# ========================== Portal Tests =========================

@pytest.mark.asyncio
async def test_portal_session_auth_required(client: AsyncClient):
    """Portal session should require authentication."""
    res = await client.post("/api/v1/billing/portal-session")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_portal_session_mock_mode(client: AsyncClient, test_data: dict):
    """In mock mode, should return mock portal URL."""
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/billing/portal-session", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "portal_url" in data
    assert data["mock"] is True


# ========================== Webhook Tests ========================

@pytest.mark.asyncio
async def test_webhook_checkout_completed_provisions_credits(
    client: AsyncClient, db_session: AsyncSession, test_data: dict
):
    """checkout.session.completed should provision credits and log transaction."""
    editor_user = test_data["users"]["editor"]

    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    starting_credits = user.credits

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {
                    "user_id": str(editor_user.id),
                    "package": "plus",
                    "frequency": "monthly",
                }
            }
        }
    }

    res = await client.post(
        "/api/v1/stripe/webhook",
        content=json.dumps(event),
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["event_type"] == "checkout.session.completed"

    # Verify credits provisioned (plus = 250)
    await db_session.refresh(user)
    assert user.credits == starting_credits + 250

    # Verify CreditTransaction logged
    txn_result = await db_session.execute(
        select(CreditTransaction).where(
            CreditTransaction.user_id == editor_user.id,
            CreditTransaction.transaction_type == "top_up",
            CreditTransaction.reference_type == "purchase_invoice",
        )
    )
    assert txn_result.scalars().first() is not None


@pytest.mark.asyncio
async def test_webhook_lite_package_provisions_50_credits(
    client: AsyncClient, db_session: AsyncSession, test_data: dict
):
    """Lite package checkout should provision exactly 50 credits."""
    editor_user = test_data["users"]["editor"]
    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    starting_credits = user.credits

    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"user_id": str(editor_user.id), "package": "lite"}}}
    }
    res = await client.post("/api/v1/stripe/webhook", content=json.dumps(event),
                            headers={"Content-Type": "application/json"})
    assert res.status_code == status.HTTP_200_OK
    await db_session.refresh(user)
    assert user.credits == starting_credits + 50


@pytest.mark.asyncio
async def test_webhook_pro_package_provisions_1000_credits(
    client: AsyncClient, db_session: AsyncSession, test_data: dict
):
    """Pro package checkout should provision exactly 1000 credits."""
    editor_user = test_data["users"]["editor"]
    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    starting_credits = user.credits

    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"user_id": str(editor_user.id), "package": "pro"}}}
    }
    res = await client.post("/api/v1/stripe/webhook", content=json.dumps(event),
                            headers={"Content-Type": "application/json"})
    assert res.status_code == status.HTTP_200_OK
    await db_session.refresh(user)
    assert user.credits == starting_credits + 1000


@pytest.mark.asyncio
async def test_webhook_subscription_cancelled(client: AsyncClient, test_data: dict):
    """customer.subscription.deleted should return 200 and handle gracefully."""
    editor_user = test_data["users"]["editor"]
    event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"metadata": {"user_id": str(editor_user.id)}}}
    }
    res = await client.post("/api/v1/stripe/webhook", content=json.dumps(event),
                            headers={"Content-Type": "application/json"})
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["event_type"] == "customer.subscription.deleted"


@pytest.mark.asyncio
async def test_webhook_unknown_event_handled(client: AsyncClient):
    """Unknown event types should be handled gracefully."""
    event = {"type": "unknown.event", "data": {"object": {}}}
    res = await client.post("/api/v1/stripe/webhook", content=json.dumps(event),
                            headers={"Content-Type": "application/json"})
    assert res.status_code == status.HTTP_200_OK
