"""Rate limits on POST /api/v1/productions/dispatch.

Per brand: the admin orchestrator_rate_limit setting (dispatches per minute).
Per user: DISPATCH_RATE_LIMIT_USER_REQUESTS per DISPATCH_RATE_LIMIT_USER_WINDOW_SECONDS.
The conftest Redis mock has no EVAL, so the windows run in memory here (as
they do locally without Redis); test_redis_window_is_used_when_available
covers the Redis path.
"""
import logging

import pytest
from sqlalchemy import select

from app.config import settings
from app.middleware import dispatch_rate_limit, rate_limit
from app.models.db import AIJob, Brand, CreditTransaction, Production

from test_production_dispatch import DISPATCH, _body, _count, _credits, queue, world  # noqa: F401 (fixtures)

ADMIN_SETTINGS = "/api/v1/admin/settings"


@pytest.fixture
def clock(monkeypatch):
    now = [1_000_000.0]
    monkeypatch.setattr(dispatch_rate_limit, "_clock", lambda: now[0])
    return now


@pytest.fixture
def user_limit(monkeypatch):
    def set_limit(requests: int, window: int = 60):
        monkeypatch.setattr(settings, "DISPATCH_RATE_LIMIT_USER_REQUESTS", requests)
        monkeypatch.setattr(settings, "DISPATCH_RATE_LIMIT_USER_WINDOW_SECONDS", window)
    set_limit(100)  # out of the way unless a test sets it
    return set_limit


async def _set_brand_limit(client, world, limit: int):
    resp = await client.post(ADMIN_SETTINGS, json={"orchestrator_rate_limit": limit}, headers=world["h"]["owner"])
    assert resp.status_code == 200, resp.text


async def _dispatch(client, world, user="owner", key=None, **overrides):
    headers = dict(world["h"][user])
    if key:
        headers["Idempotency-Key"] = key
    return await client.post(DISPATCH, json=_body(world, count=1, **overrides), headers=headers)


def _assert_limited(resp, scope: str, limit: int, retry_after: int = None):
    assert resp.status_code == 429, resp.text
    detail = resp.json()["detail"]
    assert (detail["error"], detail["scope"], detail["limit"]) == ("rate_limited", scope, limit)
    assert "Nothing was charged" in detail["message"]
    assert int(resp.headers["Retry-After"]) == detail["retry_after"] >= 1
    if retry_after is not None:
        assert detail["retry_after"] == retry_after
    assert resp.headers["X-RateLimit-Limit"] == str(limit)
    assert resp.headers["X-RateLimit-Remaining"] == "0"


async def _totals(db_session, world):
    return (await _count(db_session, Production), await _count(db_session, AIJob),
            await _count(db_session, CreditTransaction), await _credits(db_session, world["brand"]))


# ========================== Ported orchestrator throttling tests ==

@pytest.mark.asyncio
async def test_orchestrator_throttling(client, db_session, world, queue, user_limit, clock):
    """Over the orchestrator limit, dispatch returns 429 and creates or charges nothing."""
    await _set_brand_limit(client, world, 2)
    for _ in range(2):
        assert (await _dispatch(client, world)).status_code == 202
    before = await _totals(db_session, world)
    assert before == (2, 2, 2, 100 - 2 * 4)

    _assert_limited(await _dispatch(client, world), "brand", 2, retry_after=60)
    assert await _totals(db_session, world) == before
    assert len(queue) == 2


@pytest.mark.asyncio
async def test_dynamic_rate_limit_enforced(client, db_session, world, queue, user_limit, clock):
    """The brand limit is read from settings:orchestrator_rate_limit on every dispatch."""
    await rate_limit.redis_client.set("settings:orchestrator_rate_limit", "5")
    for _ in range(5):
        assert (await _dispatch(client, world)).status_code == 202
    _assert_limited(await _dispatch(client, world), "brand", 5)

    await _set_brand_limit(client, world, 6)  # takes effect immediately, no restart
    assert (await _dispatch(client, world)).status_code == 202
    _assert_limited(await _dispatch(client, world), "brand", 6)
    assert await _count(db_session, Production) == 6


@pytest.mark.asyncio
async def test_default_brand_limit_without_admin_setting(client, world, queue, user_limit, clock, monkeypatch):
    monkeypatch.setattr(settings, "ORCHESTRATOR_RATE_LIMIT", 1)
    assert await dispatch_rate_limit.brand_limit() == 1
    assert (await _dispatch(client, world)).status_code == 202
    _assert_limited(await _dispatch(client, world), "brand", 1)


# ========================== Scope =================================

@pytest.mark.asyncio
async def test_brand_limit_is_shared_by_members_but_not_across_brands(client, db_session, world, queue, user_limit,
                                                                       clock):
    await _set_brand_limit(client, world, 1)
    assert (await _dispatch(client, world, "owner")).status_code == 202
    _assert_limited(await _dispatch(client, world, "editor"), "brand", 1)  # same brand, other member

    rival_asset = f"asset:{world['assets']['rival'].id}"
    resp = await _dispatch(client, world, "other", product_asset_url=rival_asset)
    assert resp.status_code == 202, resp.text  # another brand has its own window
    rival_production = (await db_session.execute(
        select(Production).where(Production.brand_id == world["rival"].id))).scalars().one()
    assert rival_production.production_id == resp.json()["production_id"]


@pytest.mark.asyncio
async def test_user_limit(client, db_session, world, queue, user_limit, clock):
    user_limit(2)
    for _ in range(2):
        assert (await _dispatch(client, world, "owner")).status_code == 202
    before = await _totals(db_session, world)
    _assert_limited(await _dispatch(client, world, "owner"), "user", 2, retry_after=60)
    assert await _totals(db_session, world) == before
    assert (await _dispatch(client, world, "editor")).status_code == 202  # same brand, own user window


@pytest.mark.asyncio
async def test_brand_rejection_does_not_use_up_the_users_window(client, world, queue, user_limit, clock):
    user_limit(2)
    await _set_brand_limit(client, world, 1)
    assert (await _dispatch(client, world, "owner")).status_code == 202
    _assert_limited(await _dispatch(client, world, "editor"), "brand", 1)

    await _set_brand_limit(client, world, 10)
    for _ in range(2):  # the rejected attempt above did not count for the editor
        assert (await _dispatch(client, world, "editor")).status_code == 202
    _assert_limited(await _dispatch(client, world, "editor"), "user", 2)


# ========================== Window ================================

@pytest.mark.asyncio
async def test_window_reset_allows_again(client, world, queue, user_limit, clock):
    await _set_brand_limit(client, world, 1)
    assert (await _dispatch(client, world)).status_code == 202
    clock[0] += 20
    _assert_limited(await _dispatch(client, world), "brand", 1, retry_after=40)
    clock[0] += 39
    _assert_limited(await _dispatch(client, world), "brand", 1, retry_after=1)
    clock[0] += 1.5
    assert (await _dispatch(client, world)).status_code == 202


@pytest.mark.asyncio
async def test_user_window_follows_settings(client, world, queue, user_limit, clock):
    user_limit(1, window=300)
    assert (await _dispatch(client, world)).status_code == 202
    clock[0] += 100
    _assert_limited(await _dispatch(client, world), "user", 1, retry_after=200)
    clock[0] += 200.5
    assert (await _dispatch(client, world)).status_code == 202


# ========================== Idempotency ===========================

@pytest.mark.asyncio
async def test_idempotent_replay_does_not_consume_the_limit(client, db_session, world, queue, user_limit, clock):
    await _set_brand_limit(client, world, 2)
    first = await _dispatch(client, world, key="click-1")
    assert first.status_code == 202
    for _ in range(3):
        replay = await _dispatch(client, world, key="click-1")
        assert replay.status_code == 202
        assert replay.headers.get("Idempotent-Replayed") == "true"
        assert replay.json() == first.json()

    assert (await _dispatch(client, world, key="click-2")).status_code == 202  # 2nd real dispatch
    _assert_limited(await _dispatch(client, world, key="click-3"), "brand", 2)
    # Replays still answer while the brand is over its limit.
    replay = await _dispatch(client, world, key="click-1")
    assert replay.status_code == 202 and replay.json() == first.json()
    assert await _totals(db_session, world) == (2, 2, 2, 100 - 2 * 4)


@pytest.mark.asyncio
async def test_limited_key_can_be_retried_later(client, db_session, world, queue, user_limit, clock):
    """A 429 stores nothing under the key, so the same key works once the window frees up."""
    await _set_brand_limit(client, world, 1)
    assert (await _dispatch(client, world, key="click-1")).status_code == 202
    _assert_limited(await _dispatch(client, world, key="click-2"), "brand", 1)
    clock[0] += 61
    resp = await _dispatch(client, world, key="click-2")
    assert resp.status_code == 202 and "Idempotent-Replayed" not in resp.headers
    assert await _count(db_session, Production) == 2


# ========================== Other errors first ====================

@pytest.mark.asyncio
async def test_validation_and_credit_errors_do_not_count(client, db_session, world, queue, user_limit, clock):
    await _set_brand_limit(client, world, 1)
    assert (await _dispatch(client, world, pose_id="no-such-pose")).status_code == 422
    assert (await _dispatch(client, world, product_type="shoes", pose_id=None)).status_code == 409
    brand = await db_session.get(Brand, world["brand"])
    brand.credits = 0
    await db_session.commit()
    assert (await _dispatch(client, world)).status_code == 402
    brand.credits = 100
    await db_session.commit()
    assert (await _dispatch(client, world)).status_code == 202


# ========================== Logging and Redis =====================

@pytest.mark.asyncio
async def test_limit_hits_are_logged_without_payload(client, world, queue, user_limit, clock, caplog):
    await _set_brand_limit(client, world, 1)
    assert (await _dispatch(client, world)).status_code == 202
    with caplog.at_level(logging.WARNING, logger="modelens.dispatch_rate_limit"):
        assert (await _dispatch(client, world)).status_code == 429
    (record,) = [r for r in caplog.records if r.name == "modelens.dispatch_rate_limit"]
    message = record.getMessage()
    assert "scope=brand" in message
    assert f"brand_id={world['brand']} " in message
    assert f"user_id={world['users']['owner'].id} " in message
    for leaked in ("EE-F-002", "asset:", "garment", "walking", "ENV-STU", "Bearer", "owner@brand.com"):
        assert leaked not in message


class FakeRedisWindows:
    """Redis with the EVAL window script, recording the keys it sees."""

    def __init__(self, limit_setting=None):
        self.windows: dict[str, list] = {}
        self.limit_setting = limit_setting

    async def get(self, key):
        return self.limit_setting if key == dispatch_rate_limit.BRAND_LIMIT_SETTING else None

    async def eval(self, script, numkeys, key, now, window, limit, member):
        now = float(now)
        hits = [h for h in self.windows.get(key, []) if h[0] > now - window]
        if len(hits) >= limit:
            self.windows[key] = hits
            return [0, str(hits[0][0])]
        self.windows[key] = hits + [(now, member)]
        return [1, "0"]

    async def zrem(self, key, member):
        self.windows[key] = [h for h in self.windows.get(key, []) if h[1] != member]


@pytest.mark.asyncio
async def test_redis_window_is_used_when_available(client, world, queue, user_limit, clock, monkeypatch):
    fake = FakeRedisWindows(limit_setting="1")
    monkeypatch.setattr(rate_limit, "redis_client", fake)
    owner_id = world["users"]["owner"].id
    editor_id = world["users"]["editor"].id

    assert (await _dispatch(client, world)).status_code == 202
    _assert_limited(await _dispatch(client, world, "editor"), "brand", 1)
    assert len(fake.windows[f"dispatch_rate_limit:brand:{world['brand']}"]) == 1
    assert len(fake.windows[f"dispatch_rate_limit:user:{owner_id}"]) == 1
    assert fake.windows[f"dispatch_rate_limit:user:{editor_id}"] == []  # given back on the brand rejection
    assert dispatch_rate_limit._memory == {}
