"""
/api/v1/auth/sso-login must only trust identities vouched for by Google/GitHub.
Provider HTTP calls are served by an httpx.MockTransport; no live keys needed.
"""
import logging
import time
from datetime import datetime, timedelta, UTC

import httpx
import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db import Brand, BrandMember, Invitation, User
from app.services import sso_verification

GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
SSO_URL = "/api/v1/auth/sso-login"


@pytest.fixture(autouse=True)
def sso_settings(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", GOOGLE_CLIENT_ID)
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "gh-client-id")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", "gh-client-secret")
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setattr(settings, "SSO_MOCK_MODE", False)
    monkeypatch.setattr(settings, "APP_ENV", None)


class FakeProviders:
    """Routes provider URLs to canned responses and records every request."""

    def __init__(self):
        self.routes = {}
        self.requests = []

    def on(self, url, response):
        # response: httpx.Response, or an exception instance to raise
        self.routes[url] = response

    def handler(self, request: httpx.Request):
        self.requests.append(request)
        url = str(request.url.copy_with(query=None))
        response = self.routes.get(url)
        if response is None:
            return httpx.Response(404)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def providers(monkeypatch):
    fake = FakeProviders()
    monkeypatch.setattr(
        sso_verification,
        "_make_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake.handler), timeout=sso_verification.HTTP_TIMEOUT),
    )
    return fake


def google_claims(**overrides):
    claims = {
        "aud": GOOGLE_CLIENT_ID,
        "iss": "https://accounts.google.com",
        "exp": str(int(time.time()) + 3600),
        "email": "alice@sso-company.com",
        "email_verified": "true",
        "name": "Alice Google",
    }
    claims.update(overrides)
    return claims


def github_setup(providers, emails, profile=None):
    providers.on(sso_verification.GITHUB_USER_URL, httpx.Response(200, json=profile or {"login": "octo", "name": "Octo Cat"}))
    providers.on(sso_verification.GITHUB_EMAILS_URL, httpx.Response(200, json=emails))


async def get_user(db_session, email):
    res = await db_session.execute(select(User).where(User.email == email))
    return res.scalars().first()


def assert_rejected(res):
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    # No provider details leak to the client
    assert res.json() == {"detail": "SSO verification failed"}


# ========================== Google ==========================

@pytest.mark.asyncio
async def test_google_valid_id_token_logs_in_and_registers(client: AsyncClient, db_session: AsyncSession, providers):
    providers.on(sso_verification.GOOGLE_TOKENINFO_URL, httpx.Response(200, json=google_claims()))

    res = await client.post(SSO_URL, json={"provider": "google", "id_token": "real.google.jwt"})

    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["access_token"] and data["refresh_token"] and data["token_type"] == "bearer"
    assert providers.requests[0].url.params["id_token"] == "real.google.jwt"
    user = await get_user(db_session, "alice@sso-company.com")
    assert user is not None and user.full_name == "Alice Google"


@pytest.mark.asyncio
async def test_google_accepts_bare_issuer(client: AsyncClient, providers):
    providers.on(sso_verification.GOOGLE_TOKENINFO_URL, httpx.Response(200, json=google_claims(iss="accounts.google.com")))
    res = await client.post(SSO_URL, json={"provider": "google", "id_token": "t"})
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tokeninfo_response",
    [
        pytest.param(httpx.Response(400, json={"error": "invalid_token"}), id="invalid-or-forged"),
        pytest.param(httpx.Response(200, json=google_claims(exp=str(int(time.time()) - 10))), id="expired"),
        pytest.param(httpx.Response(200, json=google_claims(exp=None)), id="missing-exp"),
        pytest.param(httpx.Response(200, json=google_claims(aud="someone-elses-app.apps.googleusercontent.com")), id="wrong-audience"),
        pytest.param(httpx.Response(200, json=google_claims(iss="https://evil.example.com")), id="wrong-issuer"),
        pytest.param(httpx.Response(200, json=google_claims(email_verified="false")), id="unverified-email"),
        pytest.param(httpx.Response(200, json=google_claims(email=None)), id="missing-email"),
        pytest.param(httpx.Response(200, content=b"<html>oops</html>"), id="non-json"),
        pytest.param(httpx.Response(500), id="provider-500"),
        pytest.param(httpx.ConnectTimeout("timed out"), id="timeout"),
    ],
)
async def test_google_rejections(client: AsyncClient, db_session: AsyncSession, providers, tokeninfo_response):
    providers.on(sso_verification.GOOGLE_TOKENINFO_URL, tokeninfo_response)

    res = await client.post(SSO_URL, json={"provider": "google", "id_token": "bad.token"})

    assert_rejected(res)
    assert await get_user(db_session, "alice@sso-company.com") is None


@pytest.mark.asyncio
async def test_google_rejected_when_client_id_not_configured(client: AsyncClient, providers, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", None)
    providers.on(sso_verification.GOOGLE_TOKENINFO_URL, httpx.Response(200, json=google_claims()))

    res = await client.post(SSO_URL, json={"provider": "google", "id_token": "t"})

    assert_rejected(res)
    assert providers.requests == []


# ========================== GitHub ==========================

@pytest.mark.asyncio
async def test_github_access_token_uses_primary_verified_email(client: AsyncClient, db_session: AsyncSession, providers):
    github_setup(providers, [
        {"email": "unverified-primary@nope.com", "primary": False, "verified": False},
        {"email": "secondary@verified.com", "primary": False, "verified": True},
        {"email": "octo@sso-company.com", "primary": True, "verified": True},
    ])

    res = await client.post(SSO_URL, json={"provider": "github", "access_token": "gho_real"})

    assert res.status_code == status.HTTP_200_OK
    assert all(r.headers["Authorization"] == "Bearer gho_real" for r in providers.requests)
    user = await get_user(db_session, "octo@sso-company.com")
    assert user is not None and user.full_name == "Octo Cat"
    assert await get_user(db_session, "secondary@verified.com") is None


@pytest.mark.asyncio
async def test_github_code_is_exchanged_server_side(client: AsyncClient, db_session: AsyncSession, providers):
    providers.on(sso_verification.GITHUB_TOKEN_URL, httpx.Response(200, json={"access_token": "gho_from_code", "token_type": "bearer"}))
    github_setup(providers, [{"email": "coder@sso-company.com", "primary": True, "verified": True}], profile={"login": "coder", "name": None})

    res = await client.post(SSO_URL, json={"provider": "github", "code": "oauth-code-123"})

    assert res.status_code == status.HTTP_200_OK
    exchange = providers.requests[0]
    assert exchange.method == "POST"
    form = dict(httpx.QueryParams(exchange.content.decode()))
    assert form == {"client_id": "gh-client-id", "client_secret": "gh-client-secret", "code": "oauth-code-123"}
    assert providers.requests[1].headers["Authorization"] == "Bearer gho_from_code"
    user = await get_user(db_session, "coder@sso-company.com")
    assert user is not None and user.full_name == "coder"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "emails",
    [
        pytest.param([{"email": "octo@sso-company.com", "primary": True, "verified": False}], id="primary-unverified"),
        pytest.param([{"email": "octo@sso-company.com", "primary": False, "verified": True}], id="verified-not-primary"),
        pytest.param([], id="no-emails"),
    ],
)
async def test_github_rejects_without_primary_verified_email(client: AsyncClient, db_session: AsyncSession, providers, emails):
    github_setup(providers, emails)
    res = await client.post(SSO_URL, json={"provider": "github", "access_token": "gho_real"})
    assert_rejected(res)
    assert await get_user(db_session, "octo@sso-company.com") is None


@pytest.mark.asyncio
async def test_github_invalid_access_token(client: AsyncClient, providers):
    providers.on(sso_verification.GITHUB_USER_URL, httpx.Response(401, json={"message": "Bad credentials"}))
    res = await client.post(SSO_URL, json={"provider": "github", "access_token": "gho_forged"})
    assert_rejected(res)


@pytest.mark.asyncio
async def test_github_bad_code(client: AsyncClient, providers):
    # GitHub reports bad/expired codes as 200 + error
    providers.on(sso_verification.GITHUB_TOKEN_URL, httpx.Response(200, json={"error": "bad_verification_code"}))
    res = await client.post(SSO_URL, json={"provider": "github", "code": "expired-code"})
    assert_rejected(res)
    assert len(providers.requests) == 1


@pytest.mark.asyncio
async def test_github_code_rejected_without_client_secret(client: AsyncClient, providers, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", None)
    res = await client.post(SSO_URL, json={"provider": "github", "code": "oauth-code-123"})
    assert_rejected(res)
    assert providers.requests == []


@pytest.mark.asyncio
async def test_github_timeout(client: AsyncClient, providers):
    providers.on(sso_verification.GITHUB_USER_URL, httpx.ReadTimeout("timed out"))
    res = await client.post(SSO_URL, json={"provider": "github", "access_token": "gho_real"})
    assert_rejected(res)


def test_provider_calls_have_timeouts():
    client = sso_verification._make_client()
    assert client.timeout.read is not None and client.timeout.connect is not None


# ========================== Request shape ==========================

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"email": "victim@brand.com", "full_name": "x", "provider": "google"}, id="legacy-email-only"),
        pytest.param({"provider": "google", "id_token": "t", "email": "victim@brand.com"}, id="email-alongside-token"),
        pytest.param({"provider": "google"}, id="google-no-credential"),
        pytest.param({"provider": "google", "access_token": "t"}, id="google-wrong-credential"),
        pytest.param({"provider": "github"}, id="github-no-credential"),
        pytest.param({"provider": "github", "access_token": "a", "code": "c"}, id="github-both-credentials"),
        pytest.param({"provider": "sso", "id_token": "t"}, id="unknown-provider"),
    ],
)
async def test_malformed_requests_rejected(client: AsyncClient, db_session: AsyncSession, providers, body):
    res = await client.post(SSO_URL, json=body)
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert providers.requests == []
    assert await get_user(db_session, "victim@brand.com") is None


@pytest.mark.asyncio
async def test_email_only_request_cannot_log_into_existing_account(client: AsyncClient, test_data: dict):
    res = await client.post(SSO_URL, json={"email": "owner@brand.com", "full_name": "Owner", "provider": "google"})
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "access_token" not in res.text


# ========================== Mock mode ==========================

@pytest.mark.asyncio
async def test_mock_credentials_rejected_by_default(client: AsyncClient, providers):
    res = await client.post(SSO_URL, json={"provider": "google", "id_token": "mock:alice@example.com"})
    assert_rejected(res)
    assert providers.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,field", [("google", "id_token"), ("github", "access_token"), ("github", "code")])
async def test_mock_mode_with_testing_flag(client: AsyncClient, db_session: AsyncSession, providers, monkeypatch, provider, field):
    monkeypatch.setattr(settings, "TESTING", True)
    res = await client.post(SSO_URL, json={"provider": provider, field: "mock:mocked@example.com"})
    assert res.status_code == status.HTTP_200_OK
    assert providers.requests == []
    assert await get_user(db_session, "mocked@example.com") is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("app_env", ["production", "PRODUCTION", " prod "])
@pytest.mark.parametrize("flag", ["TESTING", "SSO_MOCK_MODE"])
async def test_mock_mode_rejected_in_production(client: AsyncClient, db_session: AsyncSession, providers, monkeypatch, app_env, flag):
    monkeypatch.setattr(settings, "APP_ENV", app_env)
    monkeypatch.setattr(settings, flag, True)

    res = await client.post(SSO_URL, json={"provider": "google", "id_token": "mock:admin@brand.com"})

    assert_rejected(res)
    assert providers.requests == []
    assert sso_verification.mock_mode_enabled() is False


@pytest.mark.asyncio
async def test_sso_mock_mode_needs_explicit_local_env(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "SSO_MOCK_MODE", True)
    body = {"provider": "google", "id_token": "mock:dev@example.com"}

    for env in (None, "staging"):
        monkeypatch.setattr(settings, "APP_ENV", env)
        assert_rejected(await client.post(SSO_URL, json=body))

    for env in ("development", "local"):
        monkeypatch.setattr(settings, "APP_ENV", env)
        assert (await client.post(SSO_URL, json=body)).status_code == status.HTTP_200_OK


def test_startup_log_warns_when_mock_mode_on(monkeypatch, caplog):
    monkeypatch.setattr(settings, "TESTING", True)
    with caplog.at_level(logging.WARNING, logger="modelens.sso"):
        sso_verification.log_mock_mode_status()
    assert any(r.levelno == logging.WARNING and "SSO MOCK MODE IS ON" in r.getMessage() for r in caplog.records)


def test_startup_log_errors_when_mock_requested_in_production(monkeypatch, caplog):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SSO_MOCK_MODE", True)
    with caplog.at_level(logging.WARNING, logger="modelens.sso"):
        sso_verification.log_mock_mode_status()
    assert any(r.levelno == logging.ERROR and "REJECTED" in r.getMessage() for r in caplog.records)


def test_startup_log_silent_when_mock_mode_off(caplog):
    with caplog.at_level(logging.WARNING, logger="modelens.sso"):
        sso_verification.log_mock_mode_status()
    assert caplog.records == []


# ========================== Provisioning ==========================

@pytest.mark.asyncio
async def test_verified_new_user_auto_provisioned_by_domain_whitelist(client: AsyncClient, db_session: AsyncSession, test_data: dict, providers):
    brand = (await db_session.execute(select(Brand).where(Brand.id == test_data["brand"].id))).scalars().first()
    brand.domain_whitelist = ["sso-company.com"]
    await db_session.commit()
    providers.on(sso_verification.GOOGLE_TOKENINFO_URL, httpx.Response(200, json=google_claims()))

    res = await client.post(SSO_URL, json={"provider": "google", "id_token": "t"})

    assert res.status_code == status.HTTP_200_OK
    user = await get_user(db_session, "alice@sso-company.com")
    member = (await db_session.execute(
        select(BrandMember).where(BrandMember.brand_id == brand.id, BrandMember.user_id == user.id)
    )).scalars().first()
    assert member is not None and member.role == "viewer"


@pytest.mark.asyncio
async def test_verified_email_auto_accepts_pending_invitation(client: AsyncClient, db_session: AsyncSession, test_data: dict, providers):
    brand = test_data["brand"]
    db_session.add(Invitation(
        brand_id=brand.id,
        email="invitee@partner.com",
        role="editor",
        token="sso_verify_invite_1",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    ))
    await db_session.commit()
    github_setup(providers, [{"email": "invitee@partner.com", "primary": True, "verified": True}])

    res = await client.post(SSO_URL, json={"provider": "github", "access_token": "gho_real"})

    assert res.status_code == status.HTTP_200_OK
    user = await get_user(db_session, "invitee@partner.com")
    member = (await db_session.execute(
        select(BrandMember).where(BrandMember.brand_id == brand.id, BrandMember.user_id == user.id)
    )).scalars().first()
    assert member is not None and member.role == "editor"
    invite = (await db_session.execute(select(Invitation).where(Invitation.token == "sso_verify_invite_1"))).scalars().first()
    await db_session.refresh(invite)
    assert invite.accepted_at is not None


@pytest.mark.asyncio
async def test_invitation_for_unverified_secondary_email_not_accepted(client: AsyncClient, db_session: AsyncSession, test_data: dict, providers):
    """Only the primary verified GitHub email is used, so an invite to another address stays pending."""
    brand = test_data["brand"]
    db_session.add(Invitation(
        brand_id=brand.id,
        email="invitee@partner.com",
        role="admin",
        token="sso_verify_invite_2",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    ))
    await db_session.commit()
    github_setup(providers, [
        {"email": "invitee@partner.com", "primary": False, "verified": False},
        {"email": "someone@elsewhere.com", "primary": True, "verified": True},
    ])

    res = await client.post(SSO_URL, json={"provider": "github", "access_token": "gho_real"})

    assert res.status_code == status.HTTP_200_OK
    assert await get_user(db_session, "invitee@partner.com") is None
    invite = (await db_session.execute(select(Invitation).where(Invitation.token == "sso_verify_invite_2"))).scalars().first()
    assert invite.accepted_at is None


@pytest.mark.asyncio
async def test_existing_user_logs_in_without_duplicate(client: AsyncClient, db_session: AsyncSession, test_data: dict, providers):
    providers.on(sso_verification.GOOGLE_TOKENINFO_URL, httpx.Response(200, json=google_claims(email="owner@brand.com", name="Someone Else")))

    res = await client.post(SSO_URL, json={"provider": "google", "id_token": "t"})

    assert res.status_code == status.HTTP_200_OK
    users = (await db_session.execute(select(User).where(User.email == "owner@brand.com"))).scalars().all()
    assert len(users) == 1 and users[0].full_name == "Owner User"
