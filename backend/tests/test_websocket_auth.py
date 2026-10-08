"""Websocket login: tokens carry the user's email in `sub`, like the HTTP auth.

Covers /api/v1/ws/events (routers/websockets.py, closes with 1008) and the
realtime endpoints in routers/realtime_generation.py (close with 4001 + reason).
Keys and secrets are test-only.
"""
import base64
import json
import time
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.main import app
from app.middleware.auth import hash_password
from app.models.db import User

pytestmark = pytest.mark.integration

WS_POLICY_VIOLATION = 1008
REALTIME_AUTH_FAILED = 4001


# ========================== Helpers ===============================

def token_for(email, exp_offset: int = 3600, secret: str = None) -> str:
    return jwt.encode(
        {"sub": email, "exp": int(time.time()) + exp_offset},
        secret or settings.SECRET_KEY,
        algorithm="HS256",
    )


def none_alg_token(email: str) -> str:
    def seg(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()
    return f"{seg({'alg': 'none', 'typ': 'JWT'})}.{seg({'sub': email, 'exp': int(time.time()) + 3600})}."


def bad_tokens(email: str) -> dict:
    return {
        "expired": token_for(email, exp_offset=-10),
        "none_alg": none_alg_token(email),
        "wrong_secret": token_for(email, secret="test-only-some-other-secret-0123456789abcdef"),
        "garbage": "not-a-jwt",
    }


class FakePubSub:
    """One terminal event, so the progress stream ends on its own."""

    async def subscribe(self, channel):
        pass

    async def unsubscribe(self, channel):
        pass

    async def close(self):
        pass

    async def listen(self):
        yield {"type": "message", "data": json.dumps({"event": "generation.completed"})}


class FakeRedis:
    def pubsub(self):
        return FakePubSub()


async def _fake_get_redis():
    return FakeRedis()


@pytest.fixture
def tc():
    with patch("app.routers.realtime_generation.generation_events._get_redis", _fake_get_redis):
        with TestClient(app) as client:
            yield client


def events_url(token, brand_id):
    return f"/api/v1/ws/events?token={token}&brand_id={brand_id}"


def progress_url(token, brand_id):
    return f"/api/v1/ws/generation/JOB-1/progress?token={token}&brand_id={brand_id}"


def assert_rejected(tc, url, code, reason=None):
    with pytest.raises(WebSocketDisconnect) as exc:
        with tc.websocket_connect(url):
            pass
    assert exc.value.code == code
    if reason is not None:
        assert exc.value.reason == reason
    return exc.value


# ========================== Valid token ===========================

@pytest.mark.asyncio
async def test_events_ws_valid_token_binds_user(tc, test_data):
    owner, brand = test_data["users"]["owner"], test_data["brand"]
    with tc.websocket_connect(events_url(token_for(owner.email), brand.id)) as ws:
        msg = json.loads(ws.receive_text())
    assert msg["type"] == "connected"
    assert msg["user_id"] == owner.id
    assert msg["brand_id"] == brand.id


@pytest.mark.asyncio
async def test_events_ws_member_bound_to_own_user(tc, test_data):
    editor, brand = test_data["users"]["editor"], test_data["brand"]
    with tc.websocket_connect(events_url(token_for(editor.email), brand.id)) as ws:
        assert json.loads(ws.receive_text())["user_id"] == editor.id


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["generation/JOB-1/progress", "brand/{brand_id}/events"])
async def test_realtime_ws_valid_token_binds_user(tc, test_data, path):
    owner, brand = test_data["users"]["owner"], test_data["brand"]
    url = f"/api/v1/ws/{path.format(brand_id=brand.id)}?token={token_for(owner.email)}&brand_id={brand.id}"
    with tc.websocket_connect(url) as ws:
        msg = ws.receive_json()
    assert msg["event"] == "connection.established"
    assert msg["user_id"] == owner.id
    assert msg["brand_id"] == brand.id


@pytest.mark.asyncio
async def test_valid_token_without_brand_access_still_denied(tc, test_data):
    nonmember, brand = test_data["users"]["nonmember"], test_data["brand"]
    assert_rejected(tc, events_url(token_for(nonmember.email), brand.id), WS_POLICY_VIOLATION)
    assert_rejected(tc, progress_url(token_for(nonmember.email), brand.id), 4003,
                    "No access to this brand workspace")


# ========================== Rejected tokens =======================

@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["expired", "none_alg", "wrong_secret", "garbage"])
async def test_bad_token_rejected(tc, test_data, kind):
    owner, brand = test_data["users"]["owner"], test_data["brand"]
    token = bad_tokens(owner.email)[kind]
    assert_rejected(tc, events_url(token, brand.id), WS_POLICY_VIOLATION)
    assert_rejected(tc, progress_url(token, brand.id), REALTIME_AUTH_FAILED)


@pytest.mark.asyncio
async def test_expired_token_keeps_realtime_reason(tc, test_data):
    owner, brand = test_data["users"]["owner"], test_data["brand"]
    token = bad_tokens(owner.email)["expired"]
    assert_rejected(tc, progress_url(token, brand.id), REALTIME_AUTH_FAILED, "Signature has expired")


@pytest.mark.asyncio
async def test_unknown_user_rejected_without_revealing_it(tc, test_data):
    brand = test_data["brand"]
    token = token_for("nobody@brand.com")
    assert_rejected(tc, events_url(token, brand.id), WS_POLICY_VIOLATION)
    unknown = assert_rejected(tc, progress_url(token, brand.id), REALTIME_AUTH_FAILED)
    # Same reason as a token with no subject at all.
    no_subject = jwt.encode({"exp": int(time.time()) + 3600}, settings.SECRET_KEY, algorithm="HS256")
    no_sub = assert_rejected(tc, progress_url(no_subject, brand.id), REALTIME_AUTH_FAILED)
    assert unknown.reason == no_sub.reason == "Invalid token"


@pytest.mark.asyncio
async def test_deleted_user_rejected(tc, test_data, db_session):
    brand = test_data["brand"]
    user = User(email="gone@brand.com", hashed_password=hash_password("password"), full_name="Gone", role="user")
    db_session.add(user)
    await db_session.commit()
    brand.owner_id = user.id
    await db_session.commit()
    token = token_for(user.email)

    with tc.websocket_connect(events_url(token, brand.id)) as ws:
        assert json.loads(ws.receive_text())["user_id"] == user.id

    await db_session.execute(delete(User).where(User.id == user.id))
    await db_session.commit()

    assert_rejected(tc, events_url(token, brand.id), WS_POLICY_VIOLATION)
    assert_rejected(tc, progress_url(token, brand.id), REALTIME_AUTH_FAILED, "Invalid token")


@pytest.mark.asyncio
async def test_numeric_sub_no_longer_resolves_by_id(tc, test_data):
    """The old helpers looked up int(sub) as a user id; an id in sub must not log anyone in."""
    owner, brand = test_data["users"]["owner"], test_data["brand"]
    token = token_for(str(owner.id))
    assert_rejected(tc, events_url(token, brand.id), WS_POLICY_VIOLATION)
    assert_rejected(tc, progress_url(token, brand.id), REALTIME_AUTH_FAILED, "Invalid token")
