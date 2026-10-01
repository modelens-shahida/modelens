import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import select

from app.models.db import WebhookSubscription
from app.services.webhook_security import (
    REPLAY_WINDOW_SECONDS,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    build_webhook_headers,
    compute_signature,
    generate_signature,
    generate_webhook_secret,
    require_webhook_signature,
    serialize_payload,
    verify_signature,
)


SECRET = "whsec_test_secret_key_modelens"
PAYLOAD = '{"event":"job.completed","job_id":123}'


class MockSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# ========================== Signature Calculation ================

def test_header_names():
    assert SIGNATURE_HEADER == "X-Modelens-Signature-256"
    assert TIMESTAMP_HEADER == "X-Modelens-Timestamp"


def test_signature_matches_reference_hmac():
    """Signature is HMAC-SHA256(secret, timestamp + "." + payload)."""
    ts = 1_700_000_000
    expected = hmac.new(SECRET.encode(), f"{ts}.{PAYLOAD}".encode(), hashlib.sha256).hexdigest()
    sig, out_ts = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    assert out_ts == ts
    assert sig == f"sha256={expected}"


def test_signature_same_for_bytes_and_str():
    ts = int(time.time())
    assert compute_signature(SECRET, ts, PAYLOAD) == compute_signature(SECRET, ts, PAYLOAD.encode())


def test_signature_differs_by_secret_payload_and_timestamp():
    ts = int(time.time())
    base = compute_signature(SECRET, ts, PAYLOAD)
    assert compute_signature("whsec_other", ts, PAYLOAD) != base
    assert compute_signature(SECRET, ts, PAYLOAD + " ") != base
    assert compute_signature(SECRET, ts + 1, PAYLOAD) != base


def test_generate_webhook_secret_format_and_uniqueness():
    s1, s2 = generate_webhook_secret(), generate_webhook_secret()
    assert s1.startswith("whsec_") and s2.startswith("whsec_")
    assert len(s1) >= len("whsec_") + 43  # token_urlsafe(32) -> 43 chars
    assert s1 != s2


def test_serialize_payload_is_stable_bytes():
    body = serialize_payload({"type": "job.completed", "job_id": 1})
    assert isinstance(body, bytes)
    assert json.loads(body) == {"type": "job.completed", "job_id": 1}


# ========================== Verification =========================

def test_verify_valid_signature():
    ts = int(time.time())
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    assert verify_signature(SECRET, PAYLOAD, sig, str(ts)) == (True, "Valid")


def test_verify_uses_compare_digest():
    ts = int(time.time())
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    with patch("app.services.webhook_security.hmac.compare_digest", wraps=hmac.compare_digest) as cd:
        assert verify_signature(SECRET, PAYLOAD, sig, str(ts))[0] is True
        cd.assert_called_once()


def test_verify_wrong_secret_rejected():
    ts = int(time.time())
    sig, _ = generate_signature("whsec_wrong", PAYLOAD, timestamp=ts)
    ok, reason = verify_signature(SECRET, PAYLOAD, sig, str(ts))
    assert ok is False
    assert "mismatch" in reason.lower()


def test_verify_tampered_signature_rejected():
    ts = int(time.time())
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    last = sig[-1]
    tampered = sig[:-1] + ("0" if last != "0" else "1")
    ok, reason = verify_signature(SECRET, PAYLOAD, tampered, str(ts))
    assert ok is False
    assert "mismatch" in reason.lower()


def test_verify_tampered_body_rejected():
    ts = int(time.time())
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    ok, _ = verify_signature(SECRET, PAYLOAD.replace("123", "124"), sig, str(ts))
    assert ok is False


def test_verify_whitespace_reserialized_body_rejected():
    """Re-serializing JSON changes bytes, so the signature must not verify."""
    ts = int(time.time())
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    reserialized = json.dumps(json.loads(PAYLOAD))  # adds spaces
    assert verify_signature(SECRET, reserialized, sig, str(ts))[0] is False


def test_verify_tampered_timestamp_rejected():
    ts = int(time.time())
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    ok, reason = verify_signature(SECRET, PAYLOAD, sig, str(ts - 1))
    assert ok is False
    assert "mismatch" in reason.lower()


@pytest.mark.parametrize("bad_sig", [
    "invalidsignature",
    "sha1=" + "a" * 64,
    "sha256=",
    "sha256=" + "a" * 63,
    "sha256=" + "z" * 64,
])
def test_verify_malformed_signature_rejected(bad_sig):
    ts = int(time.time())
    ok, reason = verify_signature(SECRET, PAYLOAD, bad_sig, str(ts))
    assert ok is False
    assert "format" in reason.lower()


@pytest.mark.parametrize("bad_ts", ["not-a-number", "1.5", "-5", "+5", "1e9", " ", "١٢٣"])
def test_verify_malformed_timestamp_rejected(bad_ts):
    sig, _ = generate_signature(SECRET, PAYLOAD)
    ok, reason = verify_signature(SECRET, PAYLOAD, sig, bad_ts)
    assert ok is False
    assert "timestamp" in reason.lower()


def test_verify_missing_signature_header_rejected():
    ts = str(int(time.time()))
    for missing in (None, ""):
        ok, reason = verify_signature(SECRET, PAYLOAD, missing, ts)
        assert ok is False
        assert "missing signature" in reason.lower()


def test_verify_missing_timestamp_header_rejected():
    sig, _ = generate_signature(SECRET, PAYLOAD)
    for missing in (None, ""):
        ok, reason = verify_signature(SECRET, PAYLOAD, sig, missing)
        assert ok is False
        assert "missing timestamp" in reason.lower()


def test_verify_empty_secret_rejected():
    ts = int(time.time())
    sig, _ = generate_signature("", PAYLOAD, timestamp=ts)
    assert verify_signature("", PAYLOAD, sig, str(ts))[0] is False


# ========================== Replay Protection ====================

def test_expired_timestamp_rejected():
    old_ts = int(time.time()) - REPLAY_WINDOW_SECONDS - 10
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=old_ts)
    ok, reason = verify_signature(SECRET, PAYLOAD, sig, str(old_ts))
    assert ok is False
    assert "expired" in reason.lower()


def test_future_timestamp_rejected():
    future_ts = int(time.time()) + REPLAY_WINDOW_SECONDS + 10
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=future_ts)
    ok, reason = verify_signature(SECRET, PAYLOAD, sig, str(future_ts))
    assert ok is False
    assert "future" in reason.lower()


def test_replay_window_boundaries():
    now = 1_700_000_000
    for ts, expected in [
        (now - REPLAY_WINDOW_SECONDS, True),
        (now - REPLAY_WINDOW_SECONDS - 1, False),
        (now + REPLAY_WINDOW_SECONDS, True),
        (now + REPLAY_WINDOW_SECONDS + 1, False),
    ]:
        sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
        assert verify_signature(SECRET, PAYLOAD, sig, str(ts), now=now)[0] is expected, ts


def test_replay_protection_can_be_disabled_explicitly():
    old_ts = int(time.time()) - 9999
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=old_ts)
    assert verify_signature(SECRET, PAYLOAD, sig, str(old_ts), enforce_replay_protection=False)[0] is True


# ========================== Outgoing Headers =====================

def test_build_webhook_headers_verifiable():
    body = serialize_payload({"type": "job.completed", "job_id": 7})
    headers = build_webhook_headers(SECRET, body)
    assert headers[TIMESTAMP_HEADER].isdigit()
    assert abs(int(headers[TIMESTAMP_HEADER]) - int(time.time())) <= 2
    assert "ModelLens" in headers["User-Agent"]
    assert verify_signature(SECRET, body, headers[SIGNATURE_HEADER], headers[TIMESTAMP_HEADER]) == (True, "Valid")


# ========================== Incoming Verification Dependency =====

def _make_receiver(secret_resolver):
    app = FastAPI()

    @app.post("/inbound")
    async def inbound(raw: bytes = Depends(require_webhook_signature(secret_resolver))):
        return {"received": json.loads(raw)}

    return TestClient(app)


def test_dependency_accepts_valid_request():
    client = _make_receiver(lambda request: SECRET)
    body = serialize_payload({"type": "job.completed"})
    res = client.post("/inbound", content=body, headers=build_webhook_headers(SECRET, body))
    assert res.status_code == 200
    assert res.json() == {"received": {"type": "job.completed"}}


def test_dependency_supports_async_resolver():
    async def resolver(request):
        return SECRET

    client = _make_receiver(resolver)
    body = b'{"a":1}'
    assert client.post("/inbound", content=body, headers=build_webhook_headers(SECRET, body)).status_code == 200


def test_dependency_rejects_tampered_body():
    client = _make_receiver(lambda request: SECRET)
    body = b'{"amount":1}'
    headers = build_webhook_headers(SECRET, body)
    res = client.post("/inbound", content=b'{"amount":1000}', headers=headers)
    assert res.status_code == 401


def test_dependency_rejects_missing_headers():
    client = _make_receiver(lambda request: SECRET)
    res = client.post("/inbound", content=b"{}", headers={"Content-Type": "application/json"})
    assert res.status_code == 401
    assert "Missing" in res.json()["detail"]


def test_dependency_rejects_replayed_request():
    client = _make_receiver(lambda request: SECRET)
    body = b'{"a":1}'
    headers = build_webhook_headers(SECRET, body, timestamp=int(time.time()) - REPLAY_WINDOW_SECONDS - 60)
    res = client.post("/inbound", content=body, headers=headers)
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_dependency_rejects_when_no_secret():
    client = _make_receiver(lambda request: None)
    body = b'{"a":1}'
    assert client.post("/inbound", content=body, headers=build_webhook_headers(SECRET, body)).status_code == 401


# ========================== Secret Management API ================

async def _create_webhook(client: AsyncClient, test_data: dict, role: str = "owner") -> dict:
    res = await client.post("/api/v1/webhooks", json={
        "brand_id": test_data["brand"].id,
        "url": "https://example.com/secure-hook",
        "events": ["job.completed"],
    }, headers=test_data["get_headers"](role))
    assert res.status_code == status.HTTP_201_CREATED, res.text
    return res.json()


@pytest.mark.asyncio
async def test_create_returns_whsec_secret(client: AsyncClient, test_data: dict):
    data = await _create_webhook(client, test_data)
    assert data["secret_token"].startswith("whsec_")


@pytest.mark.asyncio
async def test_list_never_returns_secret(client: AsyncClient, test_data: dict):
    created = await _create_webhook(client, test_data)
    res = await client.get(
        f"/api/v1/webhooks?brand_id={test_data['brand'].id}",
        headers=test_data["get_headers"]("owner"),
    )
    assert res.status_code == 200
    assert res.json()
    for item in res.json():
        assert "secret_token" not in item
    assert created["secret_token"] not in res.text


@pytest.mark.asyncio
async def test_rotation_lifecycle(client: AsyncClient, db_session, test_data: dict):
    created = await _create_webhook(client, test_data)
    old_secret = created["secret_token"]

    res = await client.post(
        f"/api/v1/webhooks/{created['id']}/rotate-secret",
        headers=test_data["get_headers"]("owner"),
    )
    assert res.status_code == 200
    new_secret = res.json()["secret_token"]
    assert new_secret.startswith("whsec_")
    assert new_secret != old_secret

    # Stored secret is the new one
    db_session.expire_all()
    sub = (await db_session.execute(
        select(WebhookSubscription).where(WebhookSubscription.id == created["id"])
    )).scalars().first()
    assert sub.secret_token == new_secret

    # A delivery signed after rotation verifies with the new secret only
    body = serialize_payload({"type": "job.completed", "job_id": 1})
    headers = build_webhook_headers(sub.secret_token, body)
    assert verify_signature(new_secret, body, headers[SIGNATURE_HEADER], headers[TIMESTAMP_HEADER])[0] is True
    assert verify_signature(old_secret, body, headers[SIGNATURE_HEADER], headers[TIMESTAMP_HEADER])[0] is False

    # Something signed with the old secret is no longer accepted by the new one
    old_headers = build_webhook_headers(old_secret, body)
    assert verify_signature(new_secret, body, old_headers[SIGNATURE_HEADER], old_headers[TIMESTAMP_HEADER])[0] is False


@pytest.mark.asyncio
async def test_brand_admin_can_rotate(client: AsyncClient, test_data: dict):
    created = await _create_webhook(client, test_data)
    res = await client.post(
        f"/api/v1/webhooks/{created['id']}/rotate-secret",
        headers=test_data["get_headers"]("admin"),
    )
    assert res.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["viewer", "editor"])
async def test_low_privilege_member_cannot_rotate(client: AsyncClient, db_session, test_data: dict, role: str):
    created = await _create_webhook(client, test_data)
    res = await client.post(
        f"/api/v1/webhooks/{created['id']}/rotate-secret",
        headers=test_data["get_headers"](role),
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "secret_token" not in res.text

    db_session.expire_all()
    sub = (await db_session.execute(
        select(WebhookSubscription).where(WebhookSubscription.id == created["id"])
    )).scalars().first()
    assert sub.secret_token == created["secret_token"]


@pytest.mark.asyncio
async def test_other_brand_user_cannot_rotate(client: AsyncClient, db_session, test_data: dict):
    created = await _create_webhook(client, test_data)
    res = await client.post(
        f"/api/v1/webhooks/{created['id']}/rotate-secret",
        headers=test_data["get_headers"]("nonmember"),
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND

    db_session.expire_all()
    sub = (await db_session.execute(
        select(WebhookSubscription).where(WebhookSubscription.id == created["id"])
    )).scalars().first()
    assert sub.secret_token == created["secret_token"]


@pytest.mark.asyncio
async def test_rotate_requires_auth(client: AsyncClient, test_data: dict):
    created = await _create_webhook(client, test_data)
    res = await client.post(f"/api/v1/webhooks/{created['id']}/rotate-secret")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ========================== Outgoing Delivery (worker) ===========

def _run_dispatch(db_session, url, payload, subscription_id):
    captured = {}
    mock_response = MagicMock(status_code=200, text="OK")

    def mock_post(url, content=None, headers=None, timeout=None, **kwargs):
        assert not kwargs, f"unexpected kwargs (e.g. json=) would re-serialize: {kwargs}"
        captured["url"] = url
        captured["content"] = content
        captured["headers"] = dict(headers or {})
        return mock_response

    with patch("httpx.Client") as mock_client, \
         patch("app.worker.is_safe_url", return_value=True), \
         patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)):
        mock_client.return_value.__enter__.return_value.post.side_effect = mock_post
        from app.worker import dispatch_webhook
        dispatch_webhook(url, payload, subscription_id=subscription_id)
    return captured


@pytest.mark.asyncio
async def test_delivery_signs_exact_bytes_sent(db_session, test_data: dict):
    secret = generate_webhook_secret()
    sub = WebhookSubscription(
        brand_id=test_data["brand"].id, url="https://example.com/h",
        events=["job.completed"], is_active=True, secret_token=secret,
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    payload = {"type": "job.completed", "job_id": 42, "note": "naïve – ünicode"}
    sent = _run_dispatch(db_session, sub.url, payload, sub.id)

    assert isinstance(sent["content"], bytes)
    assert json.loads(sent["content"]) == payload
    h = sent["headers"]
    assert h[SIGNATURE_HEADER].startswith("sha256=")
    assert h[TIMESTAMP_HEADER].isdigit()
    assert verify_signature(secret, sent["content"], h[SIGNATURE_HEADER], h[TIMESTAMP_HEADER]) == (True, "Valid")


@pytest.mark.asyncio
async def test_legacy_subscription_without_secret_gets_one_and_is_signed(db_session, test_data: dict, capsys):
    sub = WebhookSubscription(
        brand_id=test_data["brand"].id, url="https://example.com/legacy",
        events=["job.completed"], is_active=True, secret_token=None,
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    sub_id = sub.id

    sent = _run_dispatch(db_session, "https://example.com/legacy", {"type": "job.completed"}, sub_id)

    db_session.expire_all()
    stored = (await db_session.execute(
        select(WebhookSubscription).where(WebhookSubscription.id == sub_id)
    )).scalars().first()
    assert stored.secret_token and stored.secret_token.startswith("whsec_")

    h = sent["headers"]
    assert SIGNATURE_HEADER in h and TIMESTAMP_HEADER in h
    assert verify_signature(stored.secret_token, sent["content"], h[SIGNATURE_HEADER], h[TIMESTAMP_HEADER])[0] is True

    # The generated secret is never logged
    assert stored.secret_token not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_delivery_for_missing_subscription_is_not_sent(db_session, test_data: dict):
    sent = _run_dispatch(db_session, "https://example.com/gone", {"type": "job.completed"}, 999999)
    assert sent == {}
