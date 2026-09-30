"""
Server-side verification of SSO identity proofs.

The browser never tells us who the user is; it hands us a provider credential
(Google ID token, GitHub access token or OAuth code) and we ask the provider.
Any failure raises SSOVerificationError, which the router maps to a generic 401.
"""
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("modelens.sso")

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

HTTP_TIMEOUT = httpx.Timeout(5.0, connect=3.0)

MOCK_TOKEN_PREFIX = "mock:"
PRODUCTION_ENVS = {"production", "prod"}
LOCAL_DEV_ENVS = {"development", "dev", "local"}


class SSOVerificationError(Exception):
    """Identity proof could not be verified. The message is for server logs only."""


@dataclass
class VerifiedIdentity:
    email: str
    full_name: str
    provider: str


def _make_client() -> httpx.AsyncClient:
    # Tests replace this to inject an httpx.MockTransport.
    return httpx.AsyncClient(timeout=HTTP_TIMEOUT)


# --- Mock mode ---

def _app_env() -> str:
    return (settings.APP_ENV or "").strip().lower()


def is_production() -> bool:
    return _app_env() in PRODUCTION_ENVS


def mock_mode_requested() -> bool:
    return settings.TESTING or settings.SSO_MOCK_MODE


def mock_mode_enabled() -> bool:
    """Mock credentials are honored only in tests or explicit local dev, never in production."""
    if is_production():
        return False
    if settings.TESTING:
        return True
    return settings.SSO_MOCK_MODE and _app_env() in LOCAL_DEV_ENVS


def log_mock_mode_status() -> None:
    """Called once at startup so mock SSO is never on silently."""
    if not mock_mode_requested():
        return
    if is_production():
        logger.error(
            "SSO mock mode was requested (TESTING/SSO_MOCK_MODE) but APP_ENV=production; "
            "mock credentials will be REJECTED."
        )
    elif mock_mode_enabled():
        logger.warning(
            "SSO MOCK MODE IS ON (APP_ENV=%s, TESTING=%s): 'mock:<email>' credentials are accepted "
            "without provider verification. Never enable this outside tests/local development.",
            _app_env() or "unset", settings.TESTING,
        )
    else:
        logger.warning(
            "SSO_MOCK_MODE=true is ignored because APP_ENV=%s is not development/local.",
            _app_env() or "unset",
        )


def _verify_mock(credential: str, provider: str) -> VerifiedIdentity:
    if not mock_mode_enabled():
        if is_production():
            logger.error("Rejected mock SSO credential in production")
        raise SSOVerificationError("mock credential while mock mode is disabled")
    email = credential[len(MOCK_TOKEN_PREFIX):].strip()
    if "@" not in email:
        raise SSOVerificationError("malformed mock credential")
    return VerifiedIdentity(email=email, full_name=email.split("@")[0], provider=provider)


# --- Google ---

async def verify_google_id_token(id_token: str) -> VerifiedIdentity:
    if id_token.startswith(MOCK_TOKEN_PREFIX):
        return _verify_mock(id_token, "google")

    client_id = settings.GOOGLE_CLIENT_ID
    if not client_id:
        logger.error("GOOGLE_CLIENT_ID is not configured; cannot verify Google sign-in")
        raise SSOVerificationError("google not configured")

    async with _make_client() as client:
        res = await client.get(GOOGLE_TOKENINFO_URL, params={"id_token": id_token})
    if res.status_code != 200:
        raise SSOVerificationError(f"tokeninfo returned {res.status_code}")
    claims = res.json()
    if not isinstance(claims, dict):
        raise SSOVerificationError("tokeninfo returned non-object")

    if claims.get("aud") != client_id:
        raise SSOVerificationError("audience mismatch")
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise SSOVerificationError("issuer mismatch")
    try:
        exp = int(claims.get("exp"))
    except (TypeError, ValueError):
        raise SSOVerificationError("missing exp")
    if exp <= int(time.time()):
        raise SSOVerificationError("token expired")
    # tokeninfo returns booleans as strings
    if str(claims.get("email_verified")).lower() != "true":
        raise SSOVerificationError("email not verified")
    email = claims.get("email")
    if not isinstance(email, str) or "@" not in email:
        raise SSOVerificationError("missing email")

    name = claims.get("name")
    return VerifiedIdentity(
        email=email,
        full_name=name if isinstance(name, str) and name else email.split("@")[0],
        provider="google",
    )


# --- GitHub ---

async def _exchange_github_code(client: httpx.AsyncClient, code: str) -> str:
    client_id, client_secret = settings.GITHUB_CLIENT_ID, settings.GITHUB_CLIENT_SECRET
    if not client_id or not client_secret:
        logger.error("GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET not configured; cannot exchange GitHub code")
        raise SSOVerificationError("github not configured")
    res = await client.post(
        GITHUB_TOKEN_URL,
        data={"client_id": client_id, "client_secret": client_secret, "code": code},
        headers={"Accept": "application/json"},
    )
    if res.status_code != 200:
        raise SSOVerificationError(f"code exchange returned {res.status_code}")
    body = res.json()
    token = body.get("access_token") if isinstance(body, dict) else None
    if not isinstance(token, str) or not token:
        # GitHub reports bad/expired codes as 200 with an "error" field
        raise SSOVerificationError("code exchange failed")
    return token


async def verify_github(access_token: Optional[str] = None, code: Optional[str] = None) -> VerifiedIdentity:
    credential = access_token or code or ""
    if credential.startswith(MOCK_TOKEN_PREFIX):
        return _verify_mock(credential, "github")

    async with _make_client() as client:
        token = access_token or await _exchange_github_code(client, code)
        headers = {**GITHUB_HEADERS, "Authorization": f"Bearer {token}"}

        user_res = await client.get(GITHUB_USER_URL, headers=headers)
        if user_res.status_code != 200:
            raise SSOVerificationError(f"/user returned {user_res.status_code}")
        emails_res = await client.get(GITHUB_EMAILS_URL, headers=headers)
        if emails_res.status_code != 200:
            raise SSOVerificationError(f"/user/emails returned {emails_res.status_code}")

    profile = user_res.json()
    emails = emails_res.json()
    if not isinstance(profile, dict) or not isinstance(emails, list):
        raise SSOVerificationError("unexpected GitHub response shape")

    email = next(
        (
            e.get("email") for e in emails
            if isinstance(e, dict) and e.get("primary") is True and e.get("verified") is True
        ),
        None,
    )
    if not isinstance(email, str) or "@" not in email:
        raise SSOVerificationError("no primary verified email")

    name = profile.get("name") or profile.get("login")
    return VerifiedIdentity(
        email=email,
        full_name=name if isinstance(name, str) and name else email.split("@")[0],
        provider="github",
    )


async def verify_sso_identity(provider: str, *, id_token=None, access_token=None, code=None) -> VerifiedIdentity:
    """Verify a provider credential. Raises SSOVerificationError on any failure."""
    try:
        if provider == "google":
            return await verify_google_id_token(id_token)
        if provider == "github":
            return await verify_github(access_token=access_token, code=code)
        raise SSOVerificationError("unsupported provider")
    except SSOVerificationError as e:
        logger.info("SSO verification failed for provider=%s: %s", provider, e)
        raise
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError) as e:
        # Timeouts, connection errors, bad JSON: the provider couldn't vouch for the user
        logger.warning("SSO provider call failed for provider=%s: %s", provider, type(e).__name__)
        raise SSOVerificationError("provider error") from e
