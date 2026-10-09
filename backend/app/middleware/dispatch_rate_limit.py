"""
Rate limits for POST /api/v1/productions/dispatch.

Two sliding windows, both checked once the request has been resolved (so the
charged brand is known) and after the Idempotency-Key lookup, so a replayed
key never counts:

* per user, across brands: DISPATCH_RATE_LIMIT_USER_REQUESTS per
  DISPATCH_RATE_LIMIT_USER_WINDOW_SECONDS. Checked first, so one member who
  keeps retrying is stopped before using up the brand's budget.
* per brand (the brand whose credits are charged): the admin
  orchestrator_rate_limit setting, in dispatches per minute. Admins change it
  with POST /api/v1/admin/settings (stored in Redis as
  settings:orchestrator_rate_limit); without a stored value it is
  ORCHESTRATOR_RATE_LIMIT.

Same approach as app.middleware.sso_rate_limit: counters live in Redis (the
client shared with app.middleware.rate_limit) so the limits hold across
workers, with an in-memory window per process when Redis is unreachable.
Only allowed requests are recorded, and a user slot is given back when the
brand limit then rejects the request, so a rejected dispatch counts nowhere.
Logs carry the brand and user ids, never the request body.
"""
import logging
import math
import time
import uuid
from collections import deque
from typing import Optional

from app.config import settings
from app.middleware import rate_limit
from app.middleware.sso_rate_limit import _WINDOW_SCRIPT

logger = logging.getLogger("modelens.dispatch_rate_limit")

KEY_PREFIX = "dispatch_rate_limit"
BRAND_LIMIT_SETTING = "settings:orchestrator_rate_limit"
BRAND_WINDOW_SECONDS = 60  # orchestrator_rate_limit is per minute

_clock = time.time
_memory: dict[str, deque] = {}
_MEMORY_SWEEP_AT = 10_000
_redis_warned = False


class DispatchRateLimited(Exception):
    """Too many dispatches for this brand or user (HTTP 429)."""

    def __init__(self, scope: str, limit: int, window: int, retry_after: int):
        self.scope, self.limit, self.window, self.retry_after = scope, limit, window, retry_after
        who = "your brand" if scope == "brand" else "you"
        super().__init__(
            f"Too many productions dispatched: {who} can start {limit} per {window} seconds. "
            f"Please try again in {retry_after} seconds. Nothing was charged.")


def reset_memory() -> None:
    """Forget every in-memory window (tests)."""
    _memory.clear()


# ========================== Windows ===============================

def _memory_hit(key: str, member: str, limit: int, window: int, now: float) -> Optional[float]:
    if len(_memory) > _MEMORY_SWEEP_AT:
        for stale in [k for k, hits in _memory.items() if not hits or hits[-1][0] <= now - window]:
            del _memory[stale]
    hits = _memory.setdefault(key, deque())
    while hits and hits[0][0] <= now - window:
        hits.popleft()
    if len(hits) >= limit:
        return hits[0][0]
    hits.append((now, member))
    return None


def _redis_unavailable(exc: Exception) -> None:
    global _redis_warned
    if not _redis_warned:
        logger.warning("Dispatch rate limit: Redis unavailable (%s); using in-memory windows.", type(exc).__name__)
        _redis_warned = True


async def _hit(key: str, limit: int, window: int) -> tuple[Optional[int], str]:
    """Record a dispatch in the window. Returns (None, member) when allowed,
    else (seconds until a slot frees up, member)."""
    now = _clock()
    member = f"{now!r}:{uuid.uuid4().hex[:8]}"
    try:
        allowed, oldest = await rate_limit.redis_client.eval(_WINDOW_SCRIPT, 1, key, repr(now), window, limit, member)
        oldest = None if int(allowed) else float(oldest)
    except Exception as exc:
        _redis_unavailable(exc)
        oldest = _memory_hit(key, member, limit, window, now)
    if oldest is None:
        return None, member
    return max(1, math.ceil(oldest + window - now)), member


async def _release(key: str, member: str) -> None:
    """Give back a slot recorded by _hit."""
    try:
        await rate_limit.redis_client.zrem(key, member)
    except Exception:
        pass
    hits = _memory.get(key)
    if hits:
        for entry in hits:
            if entry[1] == member:
                hits.remove(entry)
                break


# ========================== Limits ================================

async def brand_limit() -> int:
    """The admin orchestrator_rate_limit setting (dispatches per minute per brand)."""
    try:
        stored = await rate_limit.redis_client.get(BRAND_LIMIT_SETTING)
        if stored is not None and int(stored) >= 1:
            return int(stored)
    except Exception as exc:
        _redis_unavailable(exc)
    return settings.ORCHESTRATOR_RATE_LIMIT


async def check_dispatch(brand_id: int, user_id: int) -> None:
    """Count one dispatch for the user and the brand, or raise DispatchRateLimited."""
    user_key = f"{KEY_PREFIX}:user:{user_id}"
    user_limit = settings.DISPATCH_RATE_LIMIT_USER_REQUESTS
    user_window = settings.DISPATCH_RATE_LIMIT_USER_WINDOW_SECONDS
    retry_after, user_member = await _hit(user_key, user_limit, user_window)
    if retry_after is not None:
        logger.warning("Dispatch rate limit hit: scope=user brand_id=%s user_id=%s limit=%s/%ss retry_after=%ss",
                       brand_id, user_id, user_limit, user_window, retry_after)
        raise DispatchRateLimited("user", user_limit, user_window, retry_after)

    limit = await brand_limit()
    retry_after, _ = await _hit(f"{KEY_PREFIX}:brand:{brand_id}", limit, BRAND_WINDOW_SECONDS)
    if retry_after is not None:
        await _release(user_key, user_member)
        logger.warning("Dispatch rate limit hit: scope=brand brand_id=%s user_id=%s limit=%s/%ss retry_after=%ss",
                       brand_id, user_id, limit, BRAND_WINDOW_SECONDS, retry_after)
        raise DispatchRateLimited("brand", limit, BRAND_WINDOW_SECONDS, retry_after)
