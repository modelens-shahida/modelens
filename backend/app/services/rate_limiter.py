"""
Redis Token-Bucket Rate Limiter per Brand Tier
Enforces concurrent job limits per brand workspace.
"""
import time
from typing import Optional, Tuple


# ========================== Tier Limits =========================

TIER_LIMITS = {
    "lite": {
        "concurrent_jobs": 2,
        "jobs_per_minute": 10,
        "batch_size_limit": 10,
    },
    "plus": {
        "concurrent_jobs": 5,
        "jobs_per_minute": 30,
        "batch_size_limit": 25,
    },
    "pro": {
        "concurrent_jobs": 10,
        "jobs_per_minute": 60,
        "batch_size_limit": 50,
    },
    "enterprise": {
        "concurrent_jobs": -1,  # unlimited
        "jobs_per_minute": -1,
        "batch_size_limit": -1,
    },
}


class RateLimiter:
    """Redis token-bucket rate limiter per brand tier."""

    def __init__(self, redis_client=None):
        self.redis = redis_client

    def get_tier_limits(self, tier: str) -> dict:
        return TIER_LIMITS.get(tier, TIER_LIMITS["lite"])

    async def check_concurrent_limit(
        self,
        brand_id: int,
        tier: str = "lite",
    ) -> Tuple[bool, int, int]:
        """
        Check if brand can submit another job.
        Returns (allowed, current_count, limit)
        """
        limits = self.get_tier_limits(tier)
        max_concurrent = limits["concurrent_jobs"]

        if max_concurrent == -1:
            return True, 0, -1

        if not self.redis:
            return True, 0, max_concurrent

        try:
            key = f"concurrent_jobs:brand:{brand_id}"
            current = await self.redis.get(key)
            current_count = int(current or 0)

            if current_count >= max_concurrent:
                return False, current_count, max_concurrent

            return True, current_count, max_concurrent
        except Exception as e:
            print(f"[RateLimit] Redis error: {e}")
            return True, 0, max_concurrent

    async def increment_concurrent(self, brand_id: int, ttl: int = 600):
        """Increment concurrent job counter."""
        if not self.redis:
            return
        try:
            key = f"concurrent_jobs:brand:{brand_id}"
            await self.redis.incr(key)
            await self.redis.expire(key, ttl)
        except Exception as e:
            print(f"[RateLimit] Increment failed: {e}")

    async def decrement_concurrent(self, brand_id: int):
        """Decrement concurrent job counter on completion."""
        if not self.redis:
            return
        try:
            key = f"concurrent_jobs:brand:{brand_id}"
            current = await self.redis.get(key)
            if current and int(current) > 0:
                await self.redis.decr(key)
        except Exception as e:
            print(f"[RateLimit] Decrement failed: {e}")

    async def check_rate_limit(
        self,
        brand_id: int,
        tier: str = "lite",
    ) -> Tuple[bool, int]:
        """
        Check jobs per minute rate limit.
        Returns (allowed, retry_after_seconds)
        """
        limits = self.get_tier_limits(tier)
        max_per_minute = limits["jobs_per_minute"]

        if max_per_minute == -1:
            return True, 0

        if not self.redis:
            return True, 0

        try:
            window = int(time.time() / 60)
            key = f"rate_limit:brand:{brand_id}:window:{window}"
            current = await self.redis.get(key)
            current_count = int(current or 0)

            if current_count >= max_per_minute:
                return False, 60 - int(time.time() % 60)

            await self.redis.incr(key)
            await self.redis.expire(key, 120)
            return True, 0

        except Exception as e:
            print(f"[RateLimit] Rate check failed: {e}")
            return True, 0


# Singleton
rate_limiter = RateLimiter()
