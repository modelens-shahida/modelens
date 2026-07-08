import json
import logging
import redis.asyncio as aioredis
from typing import Optional, Any, Callable
from app.config import settings

logger = logging.getLogger("modelens.cache")

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

# ========================== Cache Keys ===========================

def brand_memory_cache_key(brand_id: int) -> str:
    return f"cache:brand_memory:{brand_id}"

def admin_stats_cache_key() -> str:
    return "cache:admin_stats:summary"


# ========================== Cache Operations =====================

async def get_cached(key: str) -> Optional[Any]:
    """Get value from Redis cache. Returns None on miss or error."""
    try:
        value = await redis_client.get(key)
        if value:
            logger.debug(f"[Cache] HIT: {key}")
            return json.loads(value)
        logger.debug(f"[Cache] MISS: {key}")
        return None
    except Exception as e:
        logger.warning(f"[Cache] Redis error on GET {key}: {e}. Falling back to DB.")
        return None


async def set_cached(key: str, value: Any, ttl: int) -> bool:
    """Set value in Redis cache with TTL. Returns False on error."""
    try:
        await redis_client.setex(key, ttl, json.dumps(value, default=str))
        logger.debug(f"[Cache] SET: {key} (TTL: {ttl}s)")
        return True
    except Exception as e:
        logger.warning(f"[Cache] Redis error on SET {key}: {e}")
        return False


async def invalidate_cache(key: str) -> bool:
    """Delete a cache key. Returns False on error."""
    try:
        await redis_client.delete(key)
        logger.debug(f"[Cache] INVALIDATED: {key}")
        return True
    except Exception as e:
        logger.warning(f"[Cache] Redis error on DELETE {key}: {e}")
        return False


async def invalidate_brand_memory_cache(brand_id: int):
    """Invalidate brand memory cache on asset changes."""
    await invalidate_cache(brand_memory_cache_key(brand_id))


async def invalidate_admin_stats_cache():
    """Invalidate admin stats cache on job/user/brand changes."""
    await invalidate_cache(admin_stats_cache_key())


async def get_or_set(key: str, ttl: int, fetch_fn: Callable) -> Any:
    """
    Cache-aside pattern: return cached value or fetch from DB and cache it.
    Gracefully falls back to DB on Redis errors.
    """
    cached = await get_cached(key)
    if cached is not None:
        return cached

    value = await fetch_fn()
    await set_cached(key, value, ttl)
    return value
