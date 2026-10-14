"""users.stripe_customer_id and the unique credit_transactions.stripe_reference.

* Migration stripe_customer_ledger_001 upgrades and downgrades on SQLite,
  backfills Stripe grants recorded in reference_id, and stops (deleting
  nothing) when two rows share a Stripe id.
* The checkout webhook saves the Stripe customer on the user; checkout and the
  billing portal use it, so the portal keeps working after an email change.
* Each checkout session / invoice grants credits once, enforced by the
  database: a concurrent second insert hits the unique index, is rolled back
  and Stripe still gets 200.

The stripe library is patched; nothing reaches the network. Fake keys only.
"""
import hashlib
import hmac
import importlib.util
import json
import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
import stripe
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models.db import CreditTransaction, User

CHECKOUT = "/api/v1/billing/checkout-session"
PORTAL = "/api/v1/billing/portal-session"
WEBHOOK = "/api/v1/stripe/webhook"
FAKE_SECRET_KEY = "sk_live_fake_for_tests_only"
FAKE_WEBHOOK_SECRET = "whsec_fake_for_tests_only"
MIGRATION = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "alembic", "versions", "stripe_customer_ledger_001.py")


# ========================== Migration =============================

def _load_migration():
    spec = importlib.util.spec_from_file_location("stripe_customer_ledger_001", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PRE_MIGRATION = """
CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) UNIQUE, credits INTEGER);
CREATE TABLE credit_transactions (
    id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER, transaction_type VARCHAR(50),
    reference_type VARCHAR(50), reference_id VARCHAR(255), balance_after INTEGER
);
INSERT INTO users VALUES (1, 'a@example.com', 100), (2, 'b@example.com', 100);
INSERT INTO credit_transactions VALUES
    (1, 1, 250, 'top_up', 'purchase_invoice', 'cs_fake_old', 350),
    (2, 1, 250, 'top_up', 'purchase_invoice', 'in_fake_renewal', 600),
    (3, 1, 50, 'top_up', 'purchase_invoice', NULL, 650),
    (4, 2, -1, 'deduction', 'job', '17', 99),
    (5, 2, 1, 'refund', 'job', '17', 100);
"""


@pytest.fixture
def migration_db(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as conn:
        for statement in PRE_MIGRATION.split(";"):
            if statement.strip():
                conn.exec_driver_sql(statement)
    yield engine
    engine.dispose()


def _run(engine, step):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(_load_migration(), step)()


def _state(engine):
    with engine.connect() as conn:
        inspector = sa.inspect(conn)
        columns = {t: {c["name"] for c in inspector.get_columns(t)} for t in ("users", "credit_transactions")}
        indexes = {t: {i["name"]: bool(i["unique"]) for i in inspector.get_indexes(t)}
                   for t in ("users", "credit_transactions")}
        rows = conn.exec_driver_sql("SELECT * FROM credit_transactions ORDER BY id").all()
    return columns, indexes, rows


def test_migration_revises_the_previous_head():
    module = _load_migration()
    assert (module.revision, module.down_revision) == ("stripe_customer_ledger_001", "presets_registry_001")


def test_upgrade_adds_columns_unique_indexes_and_backfills(migration_db):
    _run(migration_db, "upgrade")
    columns, indexes, _ = _state(migration_db)
    assert "stripe_customer_id" in columns["users"] and "stripe_reference" in columns["credit_transactions"]
    assert indexes["users"]["ix_users_stripe_customer_id"] is True
    assert indexes["credit_transactions"]["ix_credit_transactions_stripe_reference"] is True
    with migration_db.connect() as conn:
        refs = conn.exec_driver_sql("SELECT id, stripe_reference FROM credit_transactions ORDER BY id").all()
    # Stripe grants backfilled; the mock purchase (NULL id) and job rows stay NULL.
    assert refs == [(1, "cs_fake_old"), (2, "in_fake_renewal"), (3, None), (4, None), (5, None)]


def test_unique_index_blocks_a_second_grant_but_allows_many_nulls(migration_db):
    _run(migration_db, "upgrade")
    with pytest.raises(IntegrityError):
        with migration_db.begin() as conn:
            conn.exec_driver_sql("INSERT INTO credit_transactions (user_id, amount, stripe_reference) "
                                 "VALUES (1, 250, 'cs_fake_old')")
    with migration_db.begin() as conn:
        conn.exec_driver_sql("INSERT INTO credit_transactions (user_id, amount) VALUES (2, 5), (2, 6)")
        conn.exec_driver_sql("UPDATE users SET stripe_customer_id = 'cus_fake_1' WHERE id = 1")
    with pytest.raises(IntegrityError):
        with migration_db.begin() as conn:
            conn.exec_driver_sql("UPDATE users SET stripe_customer_id = 'cus_fake_1' WHERE id = 2")


def test_upgrade_twice_is_a_no_op(migration_db):
    _run(migration_db, "upgrade")
    once = _state(migration_db)
    _run(migration_db, "upgrade")
    assert _state(migration_db) == once


def test_downgrade_restores_the_schema_and_keeps_rows(migration_db):
    before = _state(migration_db)
    _run(migration_db, "upgrade")
    _run(migration_db, "downgrade")
    assert _state(migration_db) == before
    _run(migration_db, "upgrade")  # and can go up again
    assert "stripe_reference" in _state(migration_db)[0]["credit_transactions"]


def test_duplicate_stripe_references_stop_the_upgrade_without_deleting(migration_db):
    with migration_db.begin() as conn:
        conn.exec_driver_sql("INSERT INTO credit_transactions VALUES "
                             "(6, 1, 250, 'top_up', 'purchase_invoice', 'cs_fake_old', 900)")
    before = _state(migration_db)
    with pytest.raises(RuntimeError, match=r"cs_fake_old \(2 rows\).*nothing was deleted"):
        _run(migration_db, "upgrade")
    # Stopped before any change: no column, no index, every row still there.
    assert _state(migration_db) == before


# ========================== Stripe flow ===========================

@pytest.fixture
def production(monkeypatch):
    for name, value in {"APP_ENV": "production", "TESTING": False, "STRIPE_MOCK_MODE": False,
                        "STRIPE_SECRET_KEY": FAKE_SECRET_KEY, "STRIPE_WEBHOOK_SECRET": FAKE_WEBHOOK_SECRET,
                        "STRIPE_PRICE_PLUS_MONTHLY": "price_fake_plus_monthly"}.items():
        monkeypatch.setattr(settings, name, value)


@pytest.fixture
def fake_stripe(monkeypatch):
    calls = SimpleNamespace(customers=[])
    calls.customer_list = MagicMock(side_effect=lambda **kw: SimpleNamespace(data=list(calls.customers)))
    calls.checkout_create = MagicMock(return_value=SimpleNamespace(id="cs_fake_new", url="https://checkout.test/x"))
    calls.portal_create = MagicMock(return_value=SimpleNamespace(url="https://portal.test/x"))
    monkeypatch.setattr(stripe.Customer, "list", calls.customer_list)
    monkeypatch.setattr(stripe.checkout.Session, "create", calls.checkout_create)
    monkeypatch.setattr(stripe.billing_portal.Session, "create", calls.portal_create)
    return calls


def _signed(event):
    payload = json.dumps(event).encode()
    ts = int(time.time())
    digest = hmac.new(FAKE_WEBHOOK_SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return payload, {"content-type": "application/json", "stripe-signature": f"t={ts},v1={digest}"}


async def _deliver(client, event):
    payload, headers = _signed(event)
    resp = await client.post(WEBHOOK, content=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp


def _completed(user_id, session_id="cs_fake_new", customer="cus_fake_new"):
    return {"id": f"evt_{session_id}", "object": "event", "type": "checkout.session.completed",
            "data": {"object": {"id": session_id, "object": "checkout.session", "payment_status": "paid",
                                "customer": customer,
                                "metadata": {"user_id": str(user_id), "package": "plus", "frequency": "monthly"}}}}


def _renewal(user_id, invoice_id):
    metadata = {"user_id": str(user_id), "package": "plus", "frequency": "monthly"}
    return {"id": f"evt_{invoice_id}", "object": "event", "type": "invoice.payment_succeeded",
            "data": {"object": {"id": invoice_id, "object": "invoice", "billing_reason": "subscription_cycle",
                                "parent": {"subscription_details": {"metadata": metadata}}}}}


async def _user(db_session, user_id):
    return (await db_session.execute(select(User).where(User.id == user_id)
                                     .execution_options(populate_existing=True))).scalar_one()


async def _stripe_rows(db_session, user_id):
    return (await db_session.execute(select(CreditTransaction.stripe_reference, CreditTransaction.amount)
                                     .where(CreditTransaction.user_id == user_id,
                                            CreditTransaction.stripe_reference.is_not(None))
                                     .order_by(CreditTransaction.id))).all()


@pytest.mark.asyncio
async def test_first_checkout_saves_customer_and_later_checkouts_reuse_it(
        client, db_session, test_data, production, fake_stripe):
    user_id = test_data["users"]["editor"].id
    headers = test_data["get_headers"]("editor")
    assert (await client.post(CHECKOUT, json={"package": "plus", "frequency": "monthly"},
                              headers=headers)).status_code == 200
    assert "customer_email" in fake_stripe.checkout_create.call_args.kwargs  # no customer yet

    await _deliver(client, _completed(user_id))
    assert (await _user(db_session, user_id)).stripe_customer_id == "cus_fake_new"

    fake_stripe.customer_list.reset_mock()
    await client.post(CHECKOUT, json={"package": "plus", "frequency": "monthly"}, headers=headers)
    assert fake_stripe.checkout_create.call_args.kwargs["customer"] == "cus_fake_new"
    fake_stripe.customer_list.assert_not_called()


@pytest.mark.asyncio
async def test_customer_found_by_email_is_saved(client, db_session, test_data, production, fake_stripe):
    user_id = test_data["users"]["editor"].id
    fake_stripe.customers.append(SimpleNamespace(id="cus_fake_legacy"))
    resp = await client.post(CHECKOUT, json={"package": "plus", "frequency": "monthly"},
                             headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 200
    assert fake_stripe.checkout_create.call_args.kwargs["customer"] == "cus_fake_legacy"
    assert (await _user(db_session, user_id)).stripe_customer_id == "cus_fake_legacy"


@pytest.mark.asyncio
async def test_portal_works_after_email_change(client, db_session, test_data, production, fake_stripe):
    user_id = test_data["users"]["editor"].id
    await _deliver(client, _completed(user_id))
    user = await _user(db_session, user_id)
    user.email = "renamed-editor@brand.com"
    await db_session.commit()

    from app.middleware.auth import create_access_token
    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'renamed-editor@brand.com'})}"}
    resp = await client.post(PORTAL, headers=headers)
    assert resp.status_code == 200, resp.text
    assert fake_stripe.portal_create.call_args.kwargs["customer"] == "cus_fake_new"
    fake_stripe.customer_list.assert_not_called()


@pytest.mark.asyncio
async def test_portal_falls_back_to_email_once_then_404_without_customer(
        client, db_session, test_data, production, fake_stripe):
    headers = test_data["get_headers"]("viewer")
    assert (await client.post(PORTAL, headers=headers)).status_code == 404
    fake_stripe.customers.append(SimpleNamespace(id="cus_fake_viewer"))
    assert (await client.post(PORTAL, headers=headers)).status_code == 200
    assert (await _user(db_session, test_data["users"]["viewer"].id)).stripe_customer_id == "cus_fake_viewer"


@pytest.mark.asyncio
async def test_existing_different_customer_is_not_overwritten(client, db_session, test_data, production):
    user_id = test_data["users"]["editor"].id
    user = await _user(db_session, user_id)
    user.stripe_customer_id = "cus_fake_original"
    await db_session.commit()
    await _deliver(client, _completed(user_id, customer="cus_fake_other"))
    assert (await _user(db_session, user_id)).stripe_customer_id == "cus_fake_original"


@pytest.mark.asyncio
async def test_customer_already_linked_to_another_user_is_not_linked_again(client, db_session, test_data, production):
    other = await _user(db_session, test_data["users"]["viewer"].id)
    other.stripe_customer_id = "cus_fake_shared"
    await db_session.commit()
    editor_id = test_data["users"]["editor"].id
    await _deliver(client, _completed(editor_id, customer="cus_fake_shared"))
    assert (await _user(db_session, editor_id)).stripe_customer_id is None
    assert await _stripe_rows(db_session, editor_id) == [("cs_fake_new", 250)]  # credits still granted


@pytest.mark.asyncio
async def test_duplicate_delivery_grants_once(client, db_session, test_data, production):
    user_id = test_data["users"]["editor"].id
    start = (await _user(db_session, user_id)).credits
    for _ in range(3):
        await _deliver(client, _completed(user_id))
    assert (await _user(db_session, user_id)).credits == start + 250
    assert await _stripe_rows(db_session, user_id) == [("cs_fake_new", 250)]


@pytest.mark.asyncio
async def test_concurrent_grant_hits_unique_index_and_is_ignored(
        client, db_session, test_data, production, monkeypatch):
    """The pre-check misses a row a concurrent delivery is inserting; the unique index catches it."""
    user_id = test_data["users"]["editor"].id
    start = (await _user(db_session, user_id)).credits
    await _deliver(client, _completed(user_id))

    from app.routers import stripe_webhooks
    original_select = stripe_webhooks.select

    def select_that_misses_the_ledger(*entities):
        query = original_select(*entities)
        if entities and entities[0] is CreditTransaction.id:
            return query.where(sa.false())  # as if the other delivery had not committed yet
        return query

    monkeypatch.setattr(stripe_webhooks, "select", select_that_misses_the_ledger)
    sent = MagicMock()
    monkeypatch.setattr("app.routers.credits.send_low_credit_warning_email", sent)
    resp = await _deliver(client, _completed(user_id))
    assert resp.json()["status"] == "ok"
    assert (await _user(db_session, user_id)).credits == start + 250
    assert await _stripe_rows(db_session, user_id) == [("cs_fake_new", 250)]
    sent.delay.assert_not_called()


@pytest.mark.asyncio
async def test_renewals_grant_once_each(client, db_session, test_data, production):
    user_id = test_data["users"]["editor"].id
    start = (await _user(db_session, user_id)).credits
    await _deliver(client, _completed(user_id))
    for invoice in ("in_fake_1", "in_fake_1", "in_fake_2", "in_fake_2"):
        await _deliver(client, _renewal(user_id, invoice))
    assert (await _user(db_session, user_id)).credits == start + 3 * 250
    assert await _stripe_rows(db_session, user_id) == [("cs_fake_new", 250), ("in_fake_1", 250), ("in_fake_2", 250)]


@pytest.mark.asyncio
async def test_non_stripe_ledger_rows_are_unaffected(client, db_session, test_data, production):
    user_id = test_data["users"]["editor"].id
    for amount in (-1, -1, 5):
        db_session.add(CreditTransaction(user_id=user_id, amount=amount, transaction_type="deduction",
                                         reference_type="job", reference_id="42", balance_after=0))
    db_session.add(CreditTransaction(user_id=user_id, amount=50, transaction_type="top_up",
                                     reference_type="purchase_invoice", balance_after=0))  # mock purchase
    await db_session.commit()  # many NULL stripe_reference rows are fine
    await _deliver(client, _completed(user_id))
    rows = (await db_session.execute(select(CreditTransaction.reference_type, CreditTransaction.stripe_reference)
                                     .where(CreditTransaction.user_id == user_id)
                                     .order_by(CreditTransaction.id))).all()
    assert rows == [("job", None), ("job", None), ("job", None), ("purchase_invoice", None),
                    ("purchase_invoice", "cs_fake_new")]
