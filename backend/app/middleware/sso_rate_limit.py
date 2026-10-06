"""
Rate limits for POST /api/v1/auth/sso-login.

Two sliding windows:

* per client IP, checked before the provider credential is verified
  (SSO_RATE_LIMIT_REQUESTS per SSO_RATE_LIMIT_WINDOW_SECONDS);
* per account, keyed on the provider-verified email and checked after
  verification, before the user is looked up or a session is issued
  (SSO_RATE_LIMIT_ACCOUNT_REQUESTS per SSO_RATE_LIMIT_ACCOUNT_WINDOW_SECONDS).
  The request carries no email (it only ever comes from the provider), so the
  account is known only once the credential is verified.

Counters live in Redis (the client shared with app.middleware.rate_limit) so
the limits hold across workers. If Redis is unreachable each process falls
back to an in-memory window, so it also works with zero config. Only allowed
requests are recorded: a blocked client gets back in as soon as its oldest
request leaves the window, and Retry-After says when that is.

The client IP is the socket peer. X-Forwarded-For is read only when that peer
is in SSO_RATE_LIMIT_TRUSTED_PROXIES: it is walked right to left, skipping
trusted proxies, and the first untrusted address is the client.

Both limits answer with the same 429 body, so a response never tells whether
an account exists. Logs carry the IP or a hash + domain of the email, never
credentials or the request body.
"""
import hashlib
import ipaddress
import logging
import math
import time
import uuid
from collections import deque
from functools import lru_cache
from typing import Optional

from fastapi import HTTPException, Request, status

from app.config import settings
from app.middleware import rate_limit

logger = logging.getLogger("modelens.sso_rate_limit")

KEY_PREFIX = "sso_rate_limit"
LIMITED_DETAIL = "Too many sign-in attempts. Please wait and try again."

# Atomic sliding window: drop expired entries; if the window is full return
# the oldest entry's time (for Retry-After), else record this request.
_WINDOW_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', tonumber(ARGV[1]) - tonumber(ARGV[2]))
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  return {0, oldest[2]}
end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('PEXPIRE', KEYS[1], math.ceil(tonumber(ARGV[2]) * 1000))
return {1, '0'}
"""

_clock = time.time
_memory: dict[str, deque] = {}
_MEMORY_SWEEP_AT = 10_000
_redis_warned = False


def reset_memory() -> None:
    """Forget every in-memory window (tests)."""
    _memory.clear()


# ========================== Client IP =============================

@lru_cache(maxsize=8)
def _trusted_networks(raw: str) -> tuple:
    networks = []
    for entry in (e.strip() for e in raw.split(",")):
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            logger.error("Ignoring invalid SSO_RATE_LIMIT_TRUSTED_PROXIES entry: %r", entry)
    return tuple(networks)


def _is_trusted(address: str, networks: tuple) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in network for network in networks)


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    networks = _trusted_networks(settings.SSO_RATE_LIMIT_TRUSTED_PROXIES)
    if not networks or not _is_trusted(peer, networks):
        return peer
    hops = [hop.strip() for header in request.headers.getlist("x-forwarded-for")
            for hop in header.split(",") if hop.strip()]
    for hop in reversed(hops):
        if not _is_trusted(hop, networks):
            return hop
    return hops[0] if hops else peer


# ========================== Windows ===============================

def _memory_hit(key: str, limit: int, window: int, now: float) -> Optional[float]:
    if len(_memory) > _MEMORY_SWEEP_AT:
        for stale in [k for k, hits in _memory.items() if not hits or hits[-1] <= now - window]:
            del _memory[stale]
    hits = _memory.setdefault(key, deque())
    while hits and hits[0] <= now - window:
        hits.popleft()
    if len(hits) >= limit:
        return hits[0]
    hits.append(now)
    return None


async def _hit(key: str, limit: int, window: int) -> Optional[int]:
    """Record a request in the window. Returns None when allowed, else the
    seconds until a slot frees up."""
    global _redis_warned
    now = _clock()
    try:
        allowed, oldest = await rate_limit.redis_client.eval(
            _WINDOW_SCRIPT, 1, key, repr(now), window, limit, f"{now!r}:{uuid.uuid4().hex[:8]}")
        oldest = None if int(allowed) else float(oldest)
    except Exception as exc:
        if not _redis_warned:
            logger.warning("SSO rate limit: Redis unavailable (%s); using in-memory windows.", type(exc).__name__)
            _redis_warned = True
        oldest = _memory_hit(key, limit, window, now)
    if oldest is None:
        return None
    return max(1, math.ceil(oldest + window - now))


def _limited(limit: int, retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=LIMITED_DETAIL,
        headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0"},
    )


# ========================== Limits ================================

async def limit_sso_ip(request: Request) -> None:
    """FastAPI dependency: per-IP limit, before the credential is verified."""
    ip = client_ip(request)
    limit, window = settings.SSO_RATE_LIMIT_REQUESTS, settings.SSO_RATE_LIMIT_WINDOW_SECONDS
    retry_after = await _hit(f"{KEY_PREFIX}:ip:{ip}", limit, window)
    if retry_after is not None:
        logger.warning("SSO login rate limit hit: scope=ip client_ip=%s retry_after=%ss", ip, retry_after)
        raise _limited(limit, retry_after)


async def limit_sso_account(email: str) -> None:
    """Per-account limit on the provider-verified email, before the user is
    looked up, so the answer is the same whether or not the account exists."""
    normalized = email.strip().lower()
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    limit = settings.SSO_RATE_LIMIT_ACCOUNT_REQUESTS
    window = settings.SSO_RATE_LIMIT_ACCOUNT_WINDOW_SECONDS
    retry_after = await _hit(f"{KEY_PREFIX}:account:{digest}", limit, window)
    if retry_after is not None:
        logger.warning("SSO login rate limit hit: scope=account account=%s domain=%s retry_after=%ss",
                       digest[:12], normalized.rpartition("@")[2], retry_after)
        raise _limited(limit, retry_after)
