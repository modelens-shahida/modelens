"""JWT handling after the python-jose -> PyJWT migration.

Our tokens are HS256, signed with settings.SECRET_KEY. Every decode site must
accept only HS256: no "none", no asymmetric algorithms, no public key used as
an HMAC secret (algorithm confusion). Keys below are generated per test run.
"""
import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import status
from httpx import AsyncClient
from starlette.requests import Request

from app.config import settings
from app.middleware.auth import hash_password
from app.middleware.rate_limit import _resolve_identifier
from app.models.db import User
from app.routers.realtime_generation import _authenticate_ws
from app.routers.websockets import _authenticate_websocket

ME_URL = "/api/v1/auth/me"
REFRESH_URL = "/api/v1/auth/refresh"

# Issued by python-jose 3.5.0 (jwt.encode(..., algorithm="HS256")) before the
# migration, with a test-only secret. exp is 2100-01-01 / 2023-11-14.
LEGACY_SECRET = "test-only-legacy-jose-secret-0123456789abcdef"
LEGACY_EMAIL = "legacy@brand.com"
LEGACY_JOSE_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiJsZWdhY3lAYnJhbmQuY29tIiwiZXhwIjo0MTAyNDQ0ODAwfQ"
    ".KjxXlnKZ3p3r_OJPHn8_neKX35UgLvzEW-xG9jtKQYA"
)
LEGACY_JOSE_EXPIRED_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiJsZWdhY3lAYnJhbmQuY29tIiwiZXhwIjoxNzAwMDAwMDAwfQ"
    ".8XvqN4ce4Cn_8XN5hLgwiQF_a-KGZD_3aScG5ORR4fY"
)


# ========================== Helpers ===============================

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _segment(obj: dict) -> str:
    return _b64(json.dumps(obj, separators=(",", ":")).encode())


def none_alg_token(email: str) -> str:
    """Unsigned token: alg "none" and an empty signature."""
    return f"{_segment({'alg': 'none', 'typ': 'JWT'})}.{_segment({'sub': email, 'exp': int(time.time()) + 3600})}."


def hs256_token_signed_with(secret: bytes, email: str) -> str:
    """HS256 token signed by hand (PyJWT itself refuses a PEM key as an HMAC secret)."""
    signing_input = f"{_segment({'alg': 'HS256', 'typ': 'JWT'})}.{_segment({'sub': email, 'exp': int(time.time()) + 3600})}"
    signature = hmac.new(secret, signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"


@pytest.fixture(scope="module")
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_key, public_pem


def forged_tokens(rsa_keys, email: str) -> dict:
    private_key, public_pem = rsa_keys
    return {
        "none_alg": none_alg_token(email),
        "hs256_public_key_as_secret": hs256_token_signed_with(public_pem, email),
        "rs256": jwt.encode({"sub": email, "exp": int(time.time()) + 3600}, private_key, algorithm="RS256"),
        "hs256_wrong_secret": jwt.encode(
            {"sub": email, "exp": int(time.time()) + 3600},
            "test-only-some-other-secret-0123456789abcdef",
            algorithm="HS256",
        ),
    }


def valid_token(email: str, exp_offset: int = 3600) -> str:
    return jwt.encode({"sub": email, "exp": int(time.time()) + exp_offset}, settings.SECRET_KEY, algorithm="HS256")


def assert_bearer_401(res):
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["detail"] == "Could not validate credentials"
    assert res.headers["www-authenticate"] == "Bearer"


def bearer_request(token: str) -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
        "client": ("203.0.113.7", 1234),
    })


# ========================== Issued tokens =========================

@pytest.mark.asyncio
async def test_login_issues_hs256_tokens(client: AsyncClient, test_data: dict):
    res = await client.post("/api/v1/auth/login", json={"email": "owner@brand.com", "password": "password"})
    assert res.status_code == status.HTTP_200_OK
    for name in ("access_token", "refresh_token"):
        token = res.json()[name]
        assert jwt.get_unverified_header(token) == {"alg": "HS256", "typ": "JWT"}
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        assert set(claims) == {"sub", "exp"}
        assert claims["sub"] == "owner@brand.com"


@pytest.mark.asyncio
async def test_valid_token_accepted(client: AsyncClient, test_data: dict):
    res = await client.get(ME_URL, headers={"Authorization": f"Bearer {valid_token('owner@brand.com')}"})
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["email"] == "owner@brand.com"


# ========================== Rejected tokens =======================

@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["none_alg", "hs256_public_key_as_secret", "rs256", "hs256_wrong_secret"])
async def test_forged_token_rejected_by_api(client: AsyncClient, test_data: dict, rsa_keys, kind):
    token = forged_tokens(rsa_keys, "owner@brand.com")[kind]
    assert_bearer_401(await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"}))

    res = await client.post(REFRESH_URL, json={"refresh_token": token})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["detail"] == "Invalid refresh token"


@pytest.mark.asyncio
async def test_forged_token_rejected_in_cookie(client: AsyncClient, test_data: dict, rsa_keys):
    for token in forged_tokens(rsa_keys, "owner@brand.com").values():
        client.cookies.set("modelens_access_token", token)
        assert_bearer_401(await client.get(ME_URL))
    client.cookies.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticate", [_authenticate_websocket, _authenticate_ws], ids=["ws", "realtime"])
async def test_forged_token_rejected_by_websocket_auth(rsa_keys, authenticate):
    for kind, token in forged_tokens(rsa_keys, "1").items():
        user, error = await authenticate(token)
        assert user is None, kind
        assert "signature" in error.lower() or "alg" in error.lower(), (kind, error)


@pytest.mark.asyncio
async def test_forged_token_not_used_as_rate_limit_identity(test_data: dict, rsa_keys):
    owner_id = str(test_data["users"]["owner"].id)
    assert (await _resolve_identifier(bearer_request(valid_token("owner@brand.com"))))[:2] == ("user", owner_id)
    for token in forged_tokens(rsa_keys, "owner@brand.com").values():
        assert await _resolve_identifier(bearer_request(token)) == ("ip", "203.0.113.7", None)


@pytest.mark.asyncio
async def test_expired_token_401(client: AsyncClient, test_data: dict):
    token = valid_token("owner@brand.com", exp_offset=-10)
    assert_bearer_401(await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"}))

    res = await client.post(REFRESH_URL, json={"refresh_token": token})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["detail"] == "Invalid refresh token"


# ========================== Tokens issued by python-jose ==========

@pytest.fixture
def legacy_secret(monkeypatch):
    monkeypatch.setattr("app.middleware.auth.SECRET_KEY", LEGACY_SECRET)
    monkeypatch.setattr("app.routers.auth.SECRET_KEY", LEGACY_SECRET)


@pytest.mark.asyncio
async def test_jose_issued_token_still_accepted(client: AsyncClient, db_session, legacy_secret):
    db_session.add(User(email=LEGACY_EMAIL, hashed_password=hash_password("password"), full_name="Legacy", role="user"))
    await db_session.commit()

    res = await client.get(ME_URL, headers={"Authorization": f"Bearer {LEGACY_JOSE_TOKEN}"})
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["email"] == LEGACY_EMAIL

    res = await client.post(REFRESH_URL, json={"refresh_token": LEGACY_JOSE_TOKEN})
    assert res.status_code == status.HTTP_200_OK
    claims = jwt.decode(res.json()["access_token"], LEGACY_SECRET, algorithms=["HS256"])
    assert claims["sub"] == LEGACY_EMAIL


@pytest.mark.asyncio
async def test_jose_issued_expired_token_401(client: AsyncClient, db_session, legacy_secret):
    db_session.add(User(email=LEGACY_EMAIL, hashed_password=hash_password("password"), full_name="Legacy", role="user"))
    await db_session.commit()

    assert_bearer_401(await client.get(ME_URL, headers={"Authorization": f"Bearer {LEGACY_JOSE_EXPIRED_TOKEN}"}))
