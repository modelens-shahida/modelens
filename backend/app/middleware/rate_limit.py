import time
import hashlib
import logging
from fastapi import HTTPException, status, Request
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger("modelens.rate_limit")

# Configure async Redis connection
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def _resolve_identifier(request: Request) -> tuple[str, str]:
    """
    Resolve the rate limit identifier and type from the request.
    Returns (identifier_key_prefix, identifier_value).

    Priority:
    1. X-API-Key header → hash of the key
    2. Authorization Bearer token → user_id from DB lookup
    3. Fallback → client IP address
    """
    # 1. Check for X-API-Key header
    api_key = request.headers.get("x-api-key")
    if api_key:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return "apikey", key_hash

    # 2. Check for Bearer token (authenticated user session)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            from sqlalchemy.ext.asyncio import AsyncSession
            from sqlalchemy import select
            from app.models.db import async_session_maker, User
            from jose import jwt
            from app.config import settings as cfg

            payload = jwt.decode(token, cfg.SECRET_KEY, algorithms=[cfg.ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                return "user", str(user_id)
        except Exception:
            pass

    # 3. Fallback to client IP
    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    return "ip", client_ip


class RateLimiter:
    """
    Enhanced sliding window rate limiter using Redis sorted sets.
    Supports tiered identification: API key > authenticated user > client IP.
    """
    def __init__(
        self,
        requests_limit: int,
        window_seconds: int,
        api_key_limit: int = None,
    ):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        # API key clients get higher limit if specified, else same as default
        self.api_key_limit = api_key_limit or requests_limit

    async def __call__(self, request: Request):
        id_type, id_value = await _resolve_identifier(request)

        # Apply tiered limits
        if id_type == "apikey":
            effective_limit = self.api_key_limit
        else:
            effective_limit = self.requests_limit

        # Build Redis key based on identification type
        # rate_limit:apikey:{key_hash}:{endpoint}
        # rate_limit:user:{user_id}:{endpoint}
        # rate_limit:ip:{client_ip}:{endpoint}
        key = f"rate_limit:{id_type}:{id_value}:{request.url.path}"

        now = time.time()
        clear_before = now - self.window_seconds

        try:
            async with redis_client.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, clear_before)
                pipe.zcard(key)
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, self.window_seconds + 5)
                _, count, _, _ = await pipe.execute()
        except Exception as e:
            logger.warning(
                f"Redis rate limiter connection failed: {str(e)}. "
                "Bypassing rate limiter check."
            )
            return

        if count > effective_limit:
            logger.warning(
                f"Rate limit exceeded for {id_type}:{id_value} on {request.url.path}. "
                f"Limit: {effective_limit} req/{self.window_seconds}s. Count: {count}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )
