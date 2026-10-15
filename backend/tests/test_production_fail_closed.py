"""Production fails closed.

* Stripe webhook: wherever production rules apply (APP_ENV production, or
  missing/unknown outside tests) STRIPE_MOCK_MODE is ignored and the
  Stripe-Signature is always verified; unsigned or forged events get 400 and
  grant nothing, and the repository-default webhook secret gives 503.
* Internal callbacks (/api/v1/internal/generations/*, /api/v1/fashn/webhook):
  the repository-default INTERNAL_CALLBACK_SECRET gives 503 where production
  rules apply; otherwise the X-Internal-Secret header must match (403).
* Startup: with APP_ENV=production a critical misconfiguration stops the
  boot, naming the variables but never their values; elsewhere it only warns.

Every secret here is a fake test value.
"""
import hashlib
import hmac
import json
import logging
import time

import pytest
from sqlalchemy import select

from app.config import (
    DEFAULT_INTERNAL_CALLBACK_SECRET, DEFAULT_SECRET_KEY, DEFAULT_STRIPE_SECRET_KEY, DEFAULT_STRIPE_WEBHOOK_SECRET,
    settings,
)
from app.config_production import ProductionConfigError, check_config, run_startup_checks, validate_production_config
from app.models.db import Brand, CreditTransaction, User
from app.routers import generation_credits
from app.services import internal_auth

WEBHOOK = "/api/v1/stripe/webhook"
FAKE_WEBHOOK_SECRET = "whsec_fake_for_tests_only"
FAKE_INTERNAL_SECRET = "fake-internal-secret-for-tests-0123456789"
GOOD_CONFIG = {
    "STRIPE_MOCK_MODE": False,
    "STRIPE_SECRET_KEY": "sk_live_fake_for_tests_only",
    "STRIPE_WEBHOOK_SECRET": FAKE_WEBHOOK_SECRET,
    "INTERNAL_CALLBACK_SECRET": FAKE_INTERNAL_SECRET,
    "SECRET_KEY": "fake-jwt-signing-key-for-tests-0123456789abcdef",
    "GEMINI_API_KEY": "fake-gemini-key-for-tests-only",
    "TESTING": False,
}


@pytest.fixture
def env(monkeypatch):
    """env(app_env, testing=False, **settings overrides)."""
    def set_env(app_env, testing=False, **overrides):
        monkeypatch.setattr(settings, "APP_ENV", app_env)
        monkeypatch.setattr(settings, "TESTING", testing)
        for name, value in overrides.items():
            monkeypatch.setattr(settings, name, value)
    return set_env


async def _ledger(db_session):
    """Every user and brand balance and every ledger row."""
    users = (await db_session.execute(select(User.id, User.credits).order_by(User.id)
                                      .execution_options(populate_existing=True))).all()
    brands = (await db_session.execute(select(Brand.id, Brand.credits).order_by(Brand.id)
                                       .execution_options(populate_existing=True))).all()
    txns = (await db_session.execute(select(
        CreditTransaction.id, CreditTransaction.reference_id, CreditTransaction.transaction_type,
        CreditTransaction.status, CreditTransaction.amount).order_by(CreditTransaction.id)
        .execution_options(populate_existing=True))).all()
    return users, brands, txns


# ========================== Stripe webhook ========================

def _checkout_event(user_id: int) -> bytes:
    return json.dumps({"id": "evt_fake", "object": "event", "type": "checkout.session.completed",
                       "data": {"object": {"metadata": {"user_id": str(user_id), "package": "pro"}}}}).encode()


def _stripe_signature(payload: bytes, secret: str) -> str:
    timestamp = int(time.time())
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


async def _post_event(client, payload, signature=None):
    headers = {"content-type": "application/json"}
    if signature:
        headers["stripe-signature"] = signature
    return await client.post(WEBHOOK, content=payload, headers=headers)


@pytest.mark.asyncio
@pytest.mark.parametrize("app_env", ["production", "prod", None, "", "qa"])
@pytest.mark.parametrize("signature", [None, "t=1,v1=deadbeef", "forged"])
async def test_unsigned_or_forged_webhook_rejected_where_production_rules_apply(
        client, db_session, test_data, env, app_env, signature):
    env(app_env, STRIPE_MOCK_MODE=True, STRIPE_WEBHOOK_SECRET=FAKE_WEBHOOK_SECRET)
    before = await _ledger(db_session)
    resp = await _post_event(client, _checkout_event(test_data["users"]["editor"].id), signature)
    assert resp.status_code == 400, resp.text
    assert await _ledger(db_session) == before


@pytest.mark.asyncio
async def test_signature_made_with_another_secret_is_rejected(client, db_session, test_data, env):
    env("production", STRIPE_MOCK_MODE=True, STRIPE_WEBHOOK_SECRET=FAKE_WEBHOOK_SECRET)
    payload = _checkout_event(test_data["users"]["editor"].id)
    before = await _ledger(db_session)
    resp = await _post_event(client, payload, _stripe_signature(payload, DEFAULT_STRIPE_WEBHOOK_SECRET))
    assert resp.status_code == 400
    assert await _ledger(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("mock_mode", [True, False])
async def test_signed_webhook_still_grants_credits_in_production(client, db_session, test_data, env, mock_mode):
    env("production", STRIPE_MOCK_MODE=mock_mode, STRIPE_WEBHOOK_SECRET=FAKE_WEBHOOK_SECRET)
    editor = test_data["users"]["editor"]
    before = editor.credits
    payload = _checkout_event(editor.id)
    resp = await _post_event(client, payload, _stripe_signature(payload, FAKE_WEBHOOK_SECRET))
    assert resp.status_code == 200, resp.text
    await db_session.refresh(editor)
    assert editor.credits == before + 1000


@pytest.mark.asyncio
@pytest.mark.parametrize("secret", [DEFAULT_STRIPE_WEBHOOK_SECRET, ""])
async def test_default_webhook_secret_in_production_is_503(client, db_session, test_data, env, secret):
    env("production", STRIPE_MOCK_MODE=False, STRIPE_WEBHOOK_SECRET=secret)
    payload = _checkout_event(test_data["users"]["editor"].id)
    before = await _ledger(db_session)
    # Even a signature made with the (public) default secret is refused.
    resp = await _post_event(client, payload, _stripe_signature(payload, DEFAULT_STRIPE_WEBHOOK_SECRET))
    assert (resp.status_code, resp.json()["detail"]) == (503, "Stripe webhooks are not configured.")
    assert await _ledger(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("app_env,testing", [("development", False), ("staging", False), ("local", False),
                                             (None, True)])
async def test_mock_webhook_still_works_outside_production(client, db_session, test_data, env, app_env, testing):
    env(app_env, testing=testing, STRIPE_MOCK_MODE=True, STRIPE_WEBHOOK_SECRET=DEFAULT_STRIPE_WEBHOOK_SECRET)
    editor = test_data["users"]["editor"]
    before = editor.credits
    resp = await _post_event(client, _checkout_event(editor.id))
    assert resp.status_code == 200, resp.text
    await db_session.refresh(editor)
    assert editor.credits == before + 1000


# ========================== Internal secret =======================

async def _pending_reservation(db_session, test_data, generation_id="gen-fail-closed"):
    db_session.add(CreditTransaction(brand_id=test_data["brand"].id, user_id=test_data["users"]["owner"].id,
                                     amount=-8, transaction_type="reserved", status="pending",
                                     reference_id=generation_id))
    await db_session.commit()
    return generation_id


def _internal_calls(gen_id):
    return [
        (f"/api/v1/internal/generations/{gen_id}/complete", {"generation_id": gen_id}),
        (f"/api/v1/internal/generations/{gen_id}/fail", {"generation_id": gen_id, "reason": "x"}),
        ("/api/v1/fashn/webhook", {"job_id": gen_id, "status": "failed", "error": "x"}),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("app_env", ["production", None, "qa"])
@pytest.mark.parametrize("secret", [DEFAULT_INTERNAL_CALLBACK_SECRET, ""])
async def test_default_internal_secret_is_refused_where_production_rules_apply(
        client, db_session, test_data, env, app_env, secret):
    env(app_env, INTERNAL_CALLBACK_SECRET=secret)
    gen_id = await _pending_reservation(db_session, test_data)
    before = await _ledger(db_session)
    for url, body in _internal_calls(gen_id):
        resp = await client.post(url, json=body, headers={"x-internal-secret": DEFAULT_INTERNAL_CALLBACK_SECRET})
        assert (resp.status_code, resp.json()["detail"]) == (503, "Internal callbacks are not configured."), url
    assert await _ledger(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("header", [None, "", "wrong", DEFAULT_INTERNAL_CALLBACK_SECRET, FAKE_INTERNAL_SECRET + "x",
                                    FAKE_INTERNAL_SECRET.upper()])
async def test_custom_secret_rejects_wrong_header_in_production(client, db_session, test_data, env, header):
    env("production", INTERNAL_CALLBACK_SECRET=FAKE_INTERNAL_SECRET)
    gen_id = await _pending_reservation(db_session, test_data)
    before = await _ledger(db_session)
    headers = {} if header is None else {"x-internal-secret": header}
    for url, body in _internal_calls(gen_id):
        resp = await client.post(url, json=body, headers=headers)
        assert resp.status_code == 403, (url, resp.text)
    assert await _ledger(db_session) == before


@pytest.mark.asyncio
async def test_custom_secret_with_correct_header_works_in_production(client, db_session, test_data, env):
    env("production", INTERNAL_CALLBACK_SECRET=FAKE_INTERNAL_SECRET)
    headers = {"x-internal-secret": FAKE_INTERNAL_SECRET}
    complete_id = await _pending_reservation(db_session, test_data, "gen-complete")
    fail_id = await _pending_reservation(db_session, test_data, "gen-fail")

    resp = await client.post(f"/api/v1/internal/generations/{complete_id}/complete",
                             json={"generation_id": complete_id}, headers=headers)
    assert resp.json() == {"status": "completed", "generation_id": complete_id}
    resp = await client.post(f"/api/v1/internal/generations/{fail_id}/fail",
                             json={"generation_id": fail_id, "reason": "x"}, headers=headers)
    assert resp.status_code == 200, resp.text
    resp = await client.post("/api/v1/fashn/webhook", json={"job_id": "fashn-1", "status": "processing"},
                             headers=headers)
    assert resp.json() == {"status": "acknowledged", "job_id": "fashn-1"}

    statuses = {ref: status for _, ref, kind, status, _ in (await _ledger(db_session))[2] if kind == "reserved"}
    assert statuses == {"gen-complete": "completed", "gen-fail": "refunded"}


@pytest.mark.asyncio
async def test_default_secret_still_works_outside_production(client, db_session, test_data, env):
    env("development", INTERNAL_CALLBACK_SECRET=DEFAULT_INTERNAL_CALLBACK_SECRET)
    gen_id = await _pending_reservation(db_session, test_data)
    resp = await client.post(f"/api/v1/internal/generations/{gen_id}/complete", json={"generation_id": gen_id},
                             headers={"x-internal-secret": DEFAULT_INTERNAL_CALLBACK_SECRET})
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("app_env,secret,header,expected", [
    ("production", DEFAULT_INTERNAL_CALLBACK_SECRET, DEFAULT_INTERNAL_CALLBACK_SECRET, 503),
    ("production", FAKE_INTERNAL_SECRET, "wrong", 403),
    ("production", FAKE_INTERNAL_SECRET, FAKE_INTERNAL_SECRET, None),
    ("development", DEFAULT_INTERNAL_CALLBACK_SECRET, DEFAULT_INTERNAL_CALLBACK_SECRET, None),
])
def test_generation_credits_copy_uses_the_same_check(env, app_env, secret, header, expected):
    """generation_credits.py also registers /internal/generations/*/complete and /fail (shadowed by
    internal_callbacks.py, which is included first); its dependency applies the same rule."""
    from fastapi import HTTPException
    env(app_env, INTERNAL_CALLBACK_SECRET=secret)
    if expected is None:
        assert generation_credits.verify_internal_secret(header) == header
    else:
        with pytest.raises(HTTPException) as err:
            generation_credits.verify_internal_secret(header)
        assert err.value.status_code == expected


def test_secret_is_compared_in_constant_time(env, monkeypatch):
    env("production", INTERNAL_CALLBACK_SECRET=FAKE_INTERNAL_SECRET)
    calls = []
    real = hmac.compare_digest
    monkeypatch.setattr(internal_auth.hmac, "compare_digest", lambda a, b: calls.append((a, b)) or real(a, b))
    internal_auth.check_internal_secret(FAKE_INTERNAL_SECRET, "nope")
    assert calls == [(FAKE_INTERNAL_SECRET.encode(), FAKE_INTERNAL_SECRET.encode())]


# ========================== Startup checklist =====================

@pytest.fixture
def good_production(env):
    env("production", **{k: v for k, v in GOOD_CONFIG.items() if k != "TESTING"})


def test_good_production_config_boots(good_production, caplog):
    with caplog.at_level(logging.WARNING):
        run_startup_checks()
    assert validate_production_config()[0] is True
    assert not [i for i in check_config() if i.fatal]


@pytest.mark.parametrize("name,bad", [
    ("STRIPE_MOCK_MODE", True),
    ("STRIPE_SECRET_KEY", DEFAULT_STRIPE_SECRET_KEY),
    ("STRIPE_SECRET_KEY", ""),
    ("STRIPE_WEBHOOK_SECRET", DEFAULT_STRIPE_WEBHOOK_SECRET),
    ("STRIPE_WEBHOOK_SECRET", ""),
    ("INTERNAL_CALLBACK_SECRET", DEFAULT_INTERNAL_CALLBACK_SECRET),
    ("INTERNAL_CALLBACK_SECRET", ""),
    ("SECRET_KEY", DEFAULT_SECRET_KEY),
    ("SECRET_KEY", "your-secret-key"),
    ("TESTING", True),
])
def test_bad_production_config_refuses_to_boot(good_production, monkeypatch, caplog, name, bad):
    monkeypatch.setattr(settings, name, bad)
    with caplog.at_level(logging.WARNING), pytest.raises(ProductionConfigError) as err:
        run_startup_checks()
    assert name in str(err.value)
    assert name in caplog.text and "Refusing to start" in caplog.text
    for value in GOOD_CONFIG.values():  # no secret value is ever logged
        if isinstance(value, str):
            assert value not in caplog.text and value not in str(err.value)
    if isinstance(bad, str) and bad:
        assert bad not in caplog.text


def test_every_fatal_issue_is_listed(env, caplog):
    env("production", STRIPE_MOCK_MODE=True, STRIPE_SECRET_KEY=DEFAULT_STRIPE_SECRET_KEY,
        STRIPE_WEBHOOK_SECRET=DEFAULT_STRIPE_WEBHOOK_SECRET, INTERNAL_CALLBACK_SECRET=DEFAULT_INTERNAL_CALLBACK_SECRET,
        SECRET_KEY=DEFAULT_SECRET_KEY)
    with caplog.at_level(logging.CRITICAL), pytest.raises(ProductionConfigError):
        run_startup_checks()
    for name in ("STRIPE_MOCK_MODE", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "INTERNAL_CALLBACK_SECRET",
                 "SECRET_KEY"):
        assert name in caplog.text
    for value in (DEFAULT_STRIPE_SECRET_KEY, DEFAULT_STRIPE_WEBHOOK_SECRET, DEFAULT_INTERNAL_CALLBACK_SECRET,
                  DEFAULT_SECRET_KEY):
        assert value not in caplog.text


@pytest.mark.parametrize("name,value", [
    ("COMFYUI_MOCK_MODE", True),
    ("STORAGE_BACKEND", "local"),
    ("SSO_MOCK_MODE", True),
    ("OPENAI_API_KEY", "sk.mock"),
    ("ALLOWED_ORIGINS", ["*"]),
    ("SECRET_KEY", "short-fake-key"),
    ("STRIPE_SECRET_KEY", "sk_test_fake_for_tests_only"),
])
def test_warnings_do_not_stop_production_boot(good_production, monkeypatch, caplog, name, value):
    monkeypatch.setattr(settings, name, value)
    with caplog.at_level(logging.WARNING):
        run_startup_checks()
    assert f"Production config warning: {name}" in caplog.text


def test_missing_optional_services_only_warn_in_production(good_production, monkeypatch, caplog):
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_S3_BUCKET", "SENDGRID_API_KEY", "CDN_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", None)
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", None)
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", None)
    with caplog.at_level(logging.WARNING):
        run_startup_checks()
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_S3_BUCKET", "SENDGRID_API_KEY", "CDN_BASE_URL"):
        assert f"Production config warning: {name}: is unset" in caplog.text


@pytest.mark.parametrize("app_env,testing", [("development", False), ("staging", False), (None, True),
                                             (None, False), ("qa", False)])
def test_non_production_only_warns(env, caplog, app_env, testing):
    env(app_env, testing=testing, STRIPE_MOCK_MODE=True, STRIPE_SECRET_KEY=DEFAULT_STRIPE_SECRET_KEY,
        STRIPE_WEBHOOK_SECRET=DEFAULT_STRIPE_WEBHOOK_SECRET, INTERNAL_CALLBACK_SECRET=DEFAULT_INTERNAL_CALLBACK_SECRET,
        SECRET_KEY=DEFAULT_SECRET_KEY)
    with caplog.at_level(logging.WARNING):
        run_startup_checks()
    assert "Production checklist not enforced" in caplog.text
    assert "INTERNAL_CALLBACK_SECRET" in caplog.text
    assert DEFAULT_INTERNAL_CALLBACK_SECRET not in caplog.text
    request_guards_warned = "refused as in production" in caplog.text
    assert request_guards_warned is (app_env in (None, "qa") and not testing)


@pytest.mark.asyncio
async def test_app_lifespan_refuses_to_start_in_production_with_bad_config(env):
    from app.main import app, lifespan
    env("production", **{**{k: v for k, v in GOOD_CONFIG.items() if k != "TESTING"},
                         "INTERNAL_CALLBACK_SECRET": DEFAULT_INTERNAL_CALLBACK_SECRET})
    with pytest.raises(ProductionConfigError, match="INTERNAL_CALLBACK_SECRET"):
        async with lifespan(app):
            pass
