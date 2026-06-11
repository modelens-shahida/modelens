import time
import logging
from fastapi import HTTPException, status, Request
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger("modelens.rate_limit")

# Configure async Redis connection using the REDIS_URL setting
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

class RateLimiter:
    """
    Sliding window rate limiter using Redis sorted sets.
    Tracks exact request counts in a rolling window.
    """
    def __init__(self, requests_limit: int, window_seconds: int):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds

    async def __call__(self, request: Request):
        # Resolve the client IP (supporting X-Forwarded-For if behind a reverse proxy like NGINX)
        client_ip = request.client.host if request.client else "127.0.0.1"
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
            
        key = f"rate_limit:{request.url.path}:{client_ip}"
        now = time.time()
        clear_before = now - self.window_seconds
        
        try:
            # Multi-command atomic pipeline
            async with redis_client.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, clear_before)
                pipe.zcard(key)
                pipe.zadd(key, {str(now): now})
                # Add expiry buffer to clean up empty keys from Redis memory
                pipe.expire(key, self.window_seconds + 5)
                _, count, _, _ = await pipe.execute()
        except Exception as e:
            # Graceful fallback: Allow request to proceed if Redis connection fails (e.g. offline tests or local run)
            logger.warning(
                f"Redis rate limiter connection failed: {str(e)}. "
                "Bypassing rate limiter check."
            )
            return
            
        if count > self.requests_limit:
            logger.warning(
                f"Rate limit exceeded for client {client_ip} on {request.url.path}. "
                f"Limit: {self.requests_limit} req/{self.window_seconds}s. Count: {count}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )
