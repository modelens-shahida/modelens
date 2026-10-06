"""Rate limits on POST /api/v1/auth/sso-login: per client IP and per verified account."""
import logging

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import settings
from app.main import app
from app.middleware import rate_limit, sso_rate_limit
from app.models.db import User

SSO_URL = "/api/v1/auth/sso-login"
PEER = "203.0.113.5"


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def sso_env(monkeypatch):
    # Mock credentials ("mock:<email>") stand in for provider-verified identities.
    monkeypatch.setattr(settings, "TESTING", True)
    monkeypatch.setattr(settings, "APP_ENV", None)
    for name, value in (("SSO_RATE_LIMIT_REQUESTS", 10), ("SSO_RATE_LIMIT_WINDOW_SECONDS", 60),
                        ("SSO_RATE_LIMIT_ACCOUNT_REQUESTS", 5), ("SSO_RATE_LIMIT_ACCOUNT_WINDOW_SECONDS", 300),
                        ("SSO_RATE_LIMIT_TRUSTED_PROXIES", "")):
        monkeypatch.setattr(settings, name, value)


@pytest.fixture
def clock(monkeypatch):
    fake = Clock()
    monkeypatch.setattr(sso_rate_limit, "_clock", fake)
    return fake


@pytest_asyncio.fixture
async def connect():
    """Clients whose TCP peer address is the given IP."""
    opened = []

    def _connect(ip=PEER):
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=(ip, 40000)), base_url="http://test")
        opened.append(client)
        return client

    yield _connect
    for client in opened:
        await client.aclose()


async def _login(client, email, headers=None):
    return await client.post(SSO_URL, json={"provider": "google", "id_token": f"mock:{email}"}, headers=headers)


def _assert_limited(resp, limit):
    assert resp.status_code == 429, resp.text
    assert resp.json() == {"detail": sso_rate_limit.LIMITED_DETAIL}
    assert int(resp.headers["Retry-After"]) >= 1
    assert resp.headers["X-RateLimit-Limit"] == str(limit)
    assert resp.headers["X-RateLimit-Remaining"] == "0"


# ========================== Under the limit =======================

@pytest.mark.asyncio
async def test_under_limit_logs_in_normally(connect, clock):
    resp = await _login(connect(), "alice@example.com")
    assert resp.status_code == 200, resp.text
    assert resp.json()["token_type"] == "bearer" and resp.json()["access_token"]


# ========================== Per IP ================================

@pytest.mark.asyncio
async def test_over_ip_limit_is_429_with_retry_after(connect, clock):
    client = connect()
    for i in range(10):
        assert (await _login(client, f"user{i}@example.com")).status_code == 200
    resp = await _login(client, "user10@example.com")
    _assert_limited(resp, 10)
    assert resp.headers["Retry-After"] == "60"
    # Another IP is unaffected.
    assert (await _login(connect("198.51.100.9"), "user11@example.com")).status_code == 200


@pytest.mark.asyncio
async def test_failed_verifications_count_toward_ip_limit(connect, clock):
    client = connect()
    for _ in range(10):
        resp = await client.post(SSO_URL, json={"provider": "google", "id_token": "not-a-valid-token"})
        assert resp.status_code == 401
    _assert_limited(await _login(client, "alice@example.com"), 10)


@pytest.mark.asyncio
async def test_retry_after_counts_down_to_the_oldest_request(connect, clock):
    client = connect()
    for i in range(10):
        await _login(client, f"user{i}@example.com")
        clock.now += 1
    resp = await _login(client, "late@example.com")
    # Oldest request was 10 s ago in a 60 s window.
    assert resp.headers["Retry-After"] == "50"


@pytest.mark.asyncio
async def test_ip_limit_follows_settings(connect, clock, monkeypatch):
    monkeypatch.setattr(settings, "SSO_RATE_LIMIT_REQUESTS", 2)
    monkeypatch.setattr(settings, "SSO_RATE_LIMIT_WINDOW_SECONDS", 30)
    client = connect()
    for i in range(2):
        assert (await _login(client, f"user{i}@example.com")).status_code == 200
    resp = await _login(client, "user2@example.com")
    _assert_limited(resp, 2)
    assert resp.headers["Retry-After"] == "30"


# ========================== Per account ===========================

@pytest.mark.asyncio
async def test_over_account_limit_is_429_from_any_ip(connect, clock):
    for i in range(5):
        assert (await _login(connect(f"198.51.100.{i}"), "victim@example.com")).status_code == 200
    resp = await _login(connect("198.51.100.200"), "Victim@Example.com")
    _assert_limited(resp, 5)
    assert resp.headers["Retry-After"] == "300"
    # Other accounts from the same IP still work.
    assert (await _login(connect("198.51.100.200"), "other@example.com")).status_code == 200


@pytest.mark.asyncio
async def test_account_limit_does_not_reveal_whether_account_exists(connect, clock, db_session):
    for i in range(5):
        assert (await _login(connect(f"198.51.100.{i}"), "existing@example.com")).status_code == 200
    # Exhaust a never-seen account without creating it: pre-fill its window.
    for _ in range(5):
        await sso_rate_limit.limit_sso_account("ghost@example.com")

    existing = await _login(connect("198.51.100.50"), "existing@example.com")
    ghost = await _login(connect("198.51.100.51"), "ghost@example.com")
    for resp in (existing, ghost):
        _assert_limited(resp, 5)
    assert existing.json() == ghost.json()
    assert existing.headers["Retry-After"] == ghost.headers["Retry-After"]
    # A blocked login never creates the account.
    found = (await db_session.execute(select(User).where(User.email == "ghost@example.com"))).scalars().first()
    assert found is None


# ========================== Window reset ==========================

@pytest.mark.asyncio
async def test_ip_window_reset_allows_again(connect, clock):
    client = connect()
    for i in range(10):
        await _login(client, f"user{i}@example.com")
    _assert_limited(await _login(client, "next@example.com"), 10)
    clock.now += 59
    _assert_limited(await _login(client, "next@example.com"), 10)
    clock.now += 2
    assert (await _login(client, "next@example.com")).status_code == 200


@pytest.mark.asyncio
async def test_account_window_reset_allows_again(connect, clock):
    for i in range(5):
        await _login(connect(f"198.51.100.{i}"), "victim@example.com")
    _assert_limited(await _login(connect("198.51.100.99"), "victim@example.com"), 5)
    clock.now += 301
    assert (await _login(connect("198.51.100.99"), "victim@example.com")).status_code == 200


# ========================== Client IP / X-Forwarded-For ===========

@pytest.mark.asyncio
async def test_spoofed_forwarded_for_without_trusted_proxies_is_ignored(connect, clock):
    client = connect()
    for i in range(10):
        resp = await _login(client, f"user{i}@example.com", headers={"X-Forwarded-For": f"192.0.2.{i}"})
        assert resp.status_code == 200
    _assert_limited(await _login(client, "x@example.com", headers={"X-Forwarded-For": "192.0.2.250"}), 10)


@pytest.mark.asyncio
async def test_spoofed_forwarded_for_from_untrusted_peer_is_ignored(connect, clock, monkeypatch):
    monkeypatch.setattr(settings, "SSO_RATE_LIMIT_TRUSTED_PROXIES", "10.0.0.0/8")
    client = connect(PEER)  # not a trusted proxy
    for i in range(10):
        await _login(client, f"user{i}@example.com", headers={"X-Forwarded-For": f"192.0.2.{i}"})
    _assert_limited(await _login(client, "x@example.com", headers={"X-Forwarded-For": "192.0.2.250"}), 10)


@pytest.mark.asyncio
async def test_trusted_proxy_forwards_the_real_client_ip(connect, clock, monkeypatch):
    monkeypatch.setattr(settings, "SSO_RATE_LIMIT_TRUSTED_PROXIES", "10.0.0.0/8, 172.16.0.1")
    proxy = connect("10.0.0.2")
    for i in range(10):
        assert (await _login(proxy, f"a{i}@example.com", headers={"X-Forwarded-For": "198.51.100.1"})).status_code == 200
    _assert_limited(await _login(proxy, "a10@example.com", headers={"X-Forwarded-For": "198.51.100.1"}), 10)
    # A different real client behind the same proxy has its own window.
    assert (await _login(proxy, "b@example.com", headers={"X-Forwarded-For": "198.51.100.2"})).status_code == 200


@pytest.mark.asyncio
async def test_client_cannot_bypass_via_leftmost_forwarded_for_behind_trusted_proxy(connect, clock, monkeypatch):
    monkeypatch.setattr(settings, "SSO_RATE_LIMIT_TRUSTED_PROXIES", "10.0.0.0/8")
    proxy = connect("10.0.0.2")
    # The client sends its own X-Forwarded-For; the proxy appends the real address (and a second hop).
    for i in range(10):
        resp = await _login(proxy, f"a{i}@example.com",
                            headers={"X-Forwarded-For": f"192.0.2.{i}, 198.51.100.7, 10.0.0.3"})
        assert resp.status_code == 200
    _assert_limited(await _login(proxy, "a10@example.com",
                                 headers={"X-Forwarded-For": "192.0.2.99, 198.51.100.7, 10.0.0.3"}), 10)


# ========================== Redis =================================

class FakeRedis:
    """Answers the limiter's EVAL like Redis would; records the calls."""

    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    async def eval(self, script, numkeys, *args):
        self.calls.append(args)
        return self.reply


@pytest.mark.asyncio
async def test_redis_window_is_used_when_available(connect, clock, monkeypatch):
    allow = FakeRedis([1, "0"])
    monkeypatch.setattr(rate_limit, "redis_client", allow)
    assert (await _login(connect(), "alice@example.com")).status_code == 200
    keys = [call[0] for call in allow.calls]
    assert keys[0] == f"sso_rate_limit:ip:{PEER}"
    assert keys[1].startswith("sso_rate_limit:account:") and "alice" not in keys[1]

    deny = FakeRedis([0, repr(clock.now - 15)])
    monkeypatch.setattr(rate_limit, "redis_client", deny)
    resp = await _login(connect(), "alice@example.com")
    _assert_limited(resp, 10)
    assert resp.headers["Retry-After"] == "45"


# ========================== Logging ===============================

@pytest.mark.asyncio
async def test_rate_limit_hits_are_logged_without_credentials(connect, clock, caplog):
    caplog.set_level(logging.WARNING, logger="modelens.sso_rate_limit")
    for i in range(5):
        await _login(connect(f"198.51.100.{i}"), "victim@example.com")
    await _login(connect("198.51.100.99"), "victim@example.com")
    client = connect()
    for i in range(11):
        await _login(client, f"user{i}@example.com")

    hits = [r.getMessage() for r in caplog.records if "rate limit hit" in r.getMessage()]
    assert any("scope=account" in m and "domain=example.com" in m for m in hits)
    assert any(f"scope=ip client_ip={PEER}" in m for m in hits)
    for message in hits:
        assert "mock:" not in message and "id_token" not in message and "victim@" not in message


# ========================== Docs ==================================

def test_openapi_documents_the_429():
    operation = app.openapi()["paths"][SSO_URL]["post"]
    assert "429" in operation["responses"]
    assert "Retry-After" in operation["responses"]["429"]["headers"]
    assert "SSO_RATE_LIMIT_REQUESTS" in operation["description"]
