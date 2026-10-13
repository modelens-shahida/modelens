"""Stripe checkout and billing portal against the production rules.

* Wherever production rules apply STRIPE_MOCK_MODE is ignored and the real
  Stripe client is called with STRIPE_SECRET_KEY; mock sessions only outside
  production.
* The checkout session metadata is exactly what the webhook reads: a signed
  checkout.session.completed built from it grants the package's credits once,
  and renewal invoices carry the same metadata through the subscription.
* Stripe errors become a clean 502 that leaks nothing and changes no credits.

The stripe library is patched; nothing reaches the network. Fake keys only.
"""
import hashlib
import hmac
import json
import logging
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import stripe
from sqlalchemy import select

from app.config import DEFAULT_STRIPE_SECRET_KEY, settings
from app.models.db import CreditTransaction, User
from app.services.stripe_client import PAYMENT_PROVIDER_ERROR

CHECKOUT = "/api/v1/billing/checkout-session"
PORTAL = "/api/v1/billing/portal-session"
WEBHOOK = "/api/v1/stripe/webhook"
FAKE_SECRET_KEY = "sk_live_fake_for_tests_only"
FAKE_WEBHOOK_SECRET = "whsec_fake_for_tests_only"
FAKE_PRICE = "price_fake_plus_monthly"


@pytest.fixture
def env(monkeypatch):
    """env(app_env, mock_mode, **settings overrides) with fake Stripe keys."""
    def set_env(app_env, mock_mode, **overrides):
        values = {"APP_ENV": app_env, "TESTING": False, "STRIPE_MOCK_MODE": mock_mode,
                  "STRIPE_SECRET_KEY": FAKE_SECRET_KEY, "STRIPE_WEBHOOK_SECRET": FAKE_WEBHOOK_SECRET,
                  "STRIPE_PRICE_PLUS_MONTHLY": FAKE_PRICE, **overrides}
        for name, value in values.items():
            monkeypatch.setattr(settings, name, value)
    return set_env


@pytest.fixture
def fake_stripe(monkeypatch):
    """Patch the Stripe calls; each records the API key that was set when it ran."""
    calls = SimpleNamespace(keys=[], customers=[])

    def recorder(result):
        def call(*args, **kwargs):
            calls.keys.append(stripe.api_key)
            return result
        return MagicMock(side_effect=call)

    calls.customer_list = recorder(SimpleNamespace(data=calls.customers))
    calls.checkout_create = recorder(SimpleNamespace(id="cs_fake_123", url="https://checkout.stripe.com/c/pay/cs_fake_123"))
    calls.portal_create = recorder(SimpleNamespace(url="https://billing.stripe.com/p/session/fake"))
    monkeypatch.setattr(stripe.Customer, "list", calls.customer_list)
    monkeypatch.setattr(stripe.checkout.Session, "create", calls.checkout_create)
    monkeypatch.setattr(stripe.billing_portal.Session, "create", calls.portal_create)
    monkeypatch.setattr(stripe, "api_key", None)
    return calls


async def _ledger(db_session):
    users = (await db_session.execute(select(User.id, User.credits).order_by(User.id)
                                      .execution_options(populate_existing=True))).all()
    txns = (await db_session.execute(select(CreditTransaction.id, CreditTransaction.amount)
                                     .order_by(CreditTransaction.id))).all()
    return users, txns


async def _credits(db_session, user_id):
    return (await db_session.execute(select(User.credits).where(User.id == user_id)
                                     .execution_options(populate_existing=True))).scalar_one()


def _signed(event: dict):
    payload = json.dumps(event).encode()
    timestamp = int(time.time())
    digest = hmac.new(FAKE_WEBHOOK_SECRET.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return payload, {"content-type": "application/json", "stripe-signature": f"t={timestamp},v1={digest}"}


async def _deliver(client, event):
    payload, headers = _signed(event)
    return await client.post(WEBHOOK, content=payload, headers=headers)


# ========================== Checkout ==============================

@pytest.mark.asyncio
@pytest.mark.parametrize("app_env", ["production", "prod", None, "qa"])
@pytest.mark.parametrize("mock_mode", [True, False])
async def test_production_rules_always_use_real_stripe(client, test_data, env, fake_stripe, app_env, mock_mode):
    env(app_env, mock_mode)
    user = test_data["users"]["editor"]
    resp = await client.post(CHECKOUT, json={"package": "plus", "frequency": "monthly"},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"session_url": "https://checkout.stripe.com/c/pay/cs_fake_123",
                           "session_id": "cs_fake_123", "mock": False}
    assert fake_stripe.keys == [FAKE_SECRET_KEY, FAKE_SECRET_KEY]
    kwargs = fake_stripe.checkout_create.call_args.kwargs
    assert kwargs["line_items"] == [{"price": FAKE_PRICE, "quantity": 1}]
    assert kwargs["customer_email"] == user.email and "customer" not in kwargs
    assert kwargs["client_reference_id"] == str(user.id)


@pytest.mark.asyncio
async def test_existing_customer_is_reused(client, test_data, env, fake_stripe):
    env("production", False)
    fake_stripe.customers.append(SimpleNamespace(id="cus_fake_1"))
    resp = await client.post(CHECKOUT, json={"package": "plus", "frequency": "monthly"},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 200
    kwargs = fake_stripe.checkout_create.call_args.kwargs
    assert kwargs["customer"] == "cus_fake_1" and "customer_email" not in kwargs
    fake_stripe.customer_list.assert_called_once_with(email=test_data["users"]["editor"].email, limit=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("app_env", ["development", "test", "local"])
async def test_mock_session_outside_production(client, test_data, env, fake_stripe, app_env):
    env(app_env, True)
    resp = await client.post(CHECKOUT, json={"package": "plus", "frequency": "annual"},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 200
    assert resp.json()["mock"] is True
    fake_stripe.checkout_create.assert_not_called()
    fake_stripe.customer_list.assert_not_called()


@pytest.mark.asyncio
async def test_mock_mode_off_outside_production_uses_real_stripe(client, test_data, env, fake_stripe):
    env("development", False)
    resp = await client.post(CHECKOUT, json={"package": "plus", "frequency": "monthly"},
                             headers=test_data["get_headers"]("editor"))
    assert resp.json()["mock"] is False
    assert fake_stripe.keys[-1] == FAKE_SECRET_KEY


@pytest.mark.asyncio
@pytest.mark.parametrize("package", ["lite", "plus", "pro"])
async def test_annual_checkout_uses_the_yearly_price(client, test_data, env, fake_stripe, package):
    env("production", False, **{f"STRIPE_PRICE_{package.upper()}_YEARLY": f"price_fake_{package}_yearly"})
    resp = await client.post(CHECKOUT, json={"package": package, "frequency": "annual"},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 200, resp.text
    assert fake_stripe.checkout_create.call_args.kwargs["line_items"][0]["price"] == f"price_fake_{package}_yearly"


@pytest.mark.asyncio
@pytest.mark.parametrize("key", [DEFAULT_STRIPE_SECRET_KEY, ""])
@pytest.mark.parametrize("url", [CHECKOUT, PORTAL])
async def test_default_key_in_production_is_not_sent(client, test_data, env, fake_stripe, key, url):
    env("production", True, STRIPE_SECRET_KEY=key)
    resp = await client.post(url, json={"package": "plus", "frequency": "monthly"},
                             headers=test_data["get_headers"]("editor"))
    assert (resp.status_code, resp.json()["detail"]) == (503, "Payments are not configured.")
    assert fake_stripe.keys == []


# ========================== Checkout -> webhook ===================

def _completed(session_kwargs, session_id="cs_fake_123"):
    return {"id": "evt_fake_checkout", "object": "event", "type": "checkout.session.completed",
            "data": {"object": {"id": session_id, "object": "checkout.session", "payment_status": "paid",
                                "client_reference_id": session_kwargs["client_reference_id"],
                                "metadata": session_kwargs["metadata"]}}}


def _invoice(subscription_metadata, invoice_id, billing_reason):
    return {"id": f"evt_{invoice_id}", "object": "event", "type": "invoice.payment_succeeded",
            "data": {"object": {"id": invoice_id, "object": "invoice", "billing_reason": billing_reason,
                                "parent": {"subscription_details": {"metadata": subscription_metadata}},
                                "lines": {"data": [{"metadata": subscription_metadata}]}}}}


@pytest.mark.asyncio
@pytest.mark.parametrize("frequency,expected", [("monthly", 250), ("annual", 3000)])
async def test_checkout_metadata_grants_credits_once_end_to_end(
        client, db_session, test_data, env, fake_stripe, frequency, expected):
    env("production", False, STRIPE_PRICE_PLUS_YEARLY="price_fake_plus_yearly")
    user_id = test_data["users"]["editor"].id
    start = await _credits(db_session, user_id)

    resp = await client.post(CHECKOUT, json={"package": "plus", "frequency": frequency},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 200
    kwargs = fake_stripe.checkout_create.call_args.kwargs
    assert kwargs["metadata"] == {"user_id": str(user_id), "package": "plus", "frequency": frequency}
    assert kwargs["subscription_data"] == {"metadata": kwargs["metadata"]}

    # Stripe delivers, then retries the same event.
    for _ in range(2):
        resp = await _deliver(client, _completed(kwargs))
        assert resp.status_code == 200, resp.text
    assert await _credits(db_session, user_id) == start + expected
    txns = (await db_session.execute(select(CreditTransaction).where(
        CreditTransaction.reference_id == "cs_fake_123"))).scalars().all()
    assert [(t.user_id, t.amount, t.transaction_type) for t in txns] == [(user_id, expected, "top_up")]

    # The subscription's first invoice is the checkout payment: nothing more.
    sub_metadata = kwargs["subscription_data"]["metadata"]
    await _deliver(client, _invoice(sub_metadata, "in_fake_first", "subscription_create"))
    assert await _credits(db_session, user_id) == start + expected

    # A renewal grants another period, once.
    for _ in range(2):
        await _deliver(client, _invoice(sub_metadata, "in_fake_renewal", "subscription_cycle"))
    assert await _credits(db_session, user_id) == start + 2 * expected


@pytest.mark.asyncio
async def test_unsigned_checkout_event_grants_nothing_in_production(client, db_session, test_data, env, fake_stripe):
    env("production", True)
    await client.post(CHECKOUT, json={"package": "pro", "frequency": "monthly"},
                      headers=test_data["get_headers"]("editor"))
    before = await _ledger(db_session)
    payload, headers = _signed(_completed(fake_stripe.checkout_create.call_args.kwargs))
    headers["stripe-signature"] = "t=1,v1=forged"
    assert (await client.post(WEBHOOK, content=payload, headers=headers)).status_code == 400
    assert await _ledger(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [{"user_id": "PLACEHOLDER", "package": "gold"},
                                      {"user_id": "PLACEHOLDER", "package": "plus", "frequency": "weekly"},
                                      {"package": "plus"}])
async def test_bad_metadata_grants_nothing(client, db_session, test_data, env, metadata):
    env("production", False)
    metadata = {k: str(test_data["users"]["editor"].id) if v == "PLACEHOLDER" else v for k, v in metadata.items()}
    before = await _ledger(db_session)
    resp = await _deliver(client, _completed({"client_reference_id": None, "metadata": metadata}))
    assert resp.status_code == 200
    assert await _ledger(db_session) == before


@pytest.mark.asyncio
async def test_unpaid_checkout_grants_nothing(client, db_session, test_data, env):
    env("production", False)
    event = _completed({"client_reference_id": None, "metadata": {
        "user_id": str(test_data["users"]["editor"].id), "package": "pro", "frequency": "monthly"}})
    event["data"]["object"]["payment_status"] = "unpaid"
    before = await _ledger(db_session)
    assert (await _deliver(client, event)).status_code == 200
    assert await _ledger(db_session) == before


# ========================== Stripe errors =========================

SECRET_IN_ERROR = "Invalid API Key provided: sk_live_fake_for_tests_only"


@pytest.mark.asyncio
@pytest.mark.parametrize("url,call", [(CHECKOUT, "checkout_create"), (PORTAL, "portal_create"),
                                      (CHECKOUT, "customer_list")])
@pytest.mark.parametrize("error", [stripe.error.AuthenticationError, stripe.error.APIConnectionError,
                                   stripe.error.InvalidRequestError, stripe.error.RateLimitError])
async def test_stripe_error_is_a_clean_502(client, db_session, test_data, env, fake_stripe, caplog, url, call, error):
    env("production", False)
    fake_stripe.customers.append(SimpleNamespace(id="cus_fake_1"))
    exc = error(SECRET_IN_ERROR, "param") if error is stripe.error.InvalidRequestError else error(SECRET_IN_ERROR)
    getattr(fake_stripe, call).side_effect = exc
    before = await _ledger(db_session)
    with caplog.at_level(logging.DEBUG):
        resp = await client.post(url, json={"package": "plus", "frequency": "monthly"},
                                 headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 502
    assert resp.json() == {"detail": PAYMENT_PROVIDER_ERROR}
    assert FAKE_SECRET_KEY not in resp.text and FAKE_SECRET_KEY not in caplog.text
    assert error.__name__ in caplog.text
    assert await _ledger(db_session) == before


# ========================== Portal ================================

@pytest.mark.asyncio
@pytest.mark.parametrize("mock_mode", [True, False])
async def test_portal_in_production_uses_real_stripe_for_own_customer(client, test_data, env, fake_stripe, mock_mode):
    env("production", mock_mode)
    fake_stripe.customers.append(SimpleNamespace(id="cus_fake_1"))
    resp = await client.post(PORTAL, headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 200
    assert resp.json() == {"portal_url": "https://billing.stripe.com/p/session/fake", "mock": False}
    fake_stripe.customer_list.assert_called_once_with(email=test_data["users"]["editor"].email, limit=1)
    assert fake_stripe.portal_create.call_args.kwargs["customer"] == "cus_fake_1"
    assert fake_stripe.keys == [FAKE_SECRET_KEY, FAKE_SECRET_KEY]


@pytest.mark.asyncio
async def test_portal_without_customer_is_404(client, test_data, env, fake_stripe):
    env("production", False)
    resp = await client.post(PORTAL, headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 404
    fake_stripe.portal_create.assert_not_called()


@pytest.mark.asyncio
async def test_portal_mock_outside_production(client, test_data, env, fake_stripe):
    env("development", True)
    resp = await client.post(PORTAL, headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 200 and resp.json()["mock"] is True
    assert fake_stripe.keys == []


# ========================== Auth ==================================

@pytest.mark.asyncio
@pytest.mark.parametrize("url", [CHECKOUT, PORTAL])
@pytest.mark.parametrize("app_env", ["production", "development"])
async def test_unauthenticated_is_401(client, env, fake_stripe, url, app_env):
    env(app_env, False)
    resp = await client.post(url, json={"package": "plus", "frequency": "monthly"})
    assert resp.status_code == 401
    assert fake_stripe.keys == []
