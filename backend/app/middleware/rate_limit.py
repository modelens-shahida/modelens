import time
import hashlib
import logging
from fastapi import HTTPException, status, Request, Response
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger("modelens.rate_limit")

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

# ========================== Tier Definitions =====================

TIER_LIMITS = {
    "free":       {"rpm": 20,  "rpd": 100,   "monthly_credits": 100},
    "growth":     {"rpm": 60,  "rpd": 1000,  "monthly_credits": 500},
    "enterprise": {"rpm": 200, "rpd": 10000, "monthly_credits": 2000},
}

CREDIT_CONSUMING_PATHS = [
    "/api/v1/jobs/generate",
    "/api/v1/jobs/workflow",
    "/api/v1/characters/",
]

BRAND_TIER_CACHE_TTL = 300  # 5 minutes


async def _get_brand_tier_cached(brand_id: int) -> dict:
    """Get brand tier from Redis cache or DB."""
    cache_key = f"brand_tier:{brand_id}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            import json
            return json.loads(cached)
    except Exception:
        pass

    # Fetch from DB
    try:
        from sqlalchemy import select
        from app.models.db import async_session_maker, Brand
        async with async_session_maker() as db:
            result = await db.execute(select(Brand).where(Brand.id == brand_id))
            brand = result.scalars().first()
            if brand:
                tier_data = {
                    "tier": brand.tier,
                    "monthly_credit_quota": brand.monthly_credit_quota,
                    "credits_used_this_month": brand.credits_used_this_month,
                }
                try:
                    import json
                    await redis_client.setex(cache_key, BRAND_TIER_CACHE_TTL, json.dumps(tier_data))
                except Exception:
                    pass
                return tier_data
    except Exception as e:
        logger.warning(f"Failed to fetch brand tier: {e}")

    return {"tier": "free", "monthly_credit_quota": 100, "credits_used_this_month": 0}


async def invalidate_brand_tier_cache(brand_id: int):
    """Invalidate brand tier cache when tier is updated."""
    try:
        await redis_client.delete(f"brand_tier:{brand_id}")
    except Exception as e:
        logger.warning(f"Failed to invalidate brand tier cache: {e}")


async def _resolve_identifier(request: Request) -> tuple[str, str, int | None]:
    """
    Resolve rate limit identifier and brand_id from request.
    Returns (identifier_type, identifier_value, brand_id)
    """
    # Check X-API-Key
    api_key = request.headers.get("x-api-key")
    if api_key:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        # Try to get brand_id from API key
        try:
            from sqlalchemy import select
            from app.models.db import async_session_maker, APIKey, BrandMember
            from app.middleware.auth import hash_api_key
            async with async_session_maker() as db:
                result = await db.execute(select(APIKey).where(APIKey.key_hash == hash_api_key(api_key)))
                api_key_obj = result.scalars().first()
                if api_key_obj:
                    member = await db.execute(
                        select(BrandMember).where(BrandMember.user_id == api_key_obj.user_id)
                    )
                    m = member.scalars().first()
                    brand_id = m.brand_id if m else None
                    return "apikey", key_hash, brand_id
        except Exception:
            pass
        return "apikey", key_hash, None

    # Check Bearer token
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            from jose import jwt
            from app.config import settings as cfg
            from sqlalchemy import select
            from app.models.db import async_session_maker, User, BrandMember
            payload = jwt.decode(token, cfg.SECRET_KEY, algorithms=[cfg.ALGORITHM])
            user_email = payload.get("sub")
            if user_email:
                async with async_session_maker() as db:
                    result = await db.execute(select(User).where(User.email == user_email))
                    user = result.scalars().first()
                    if user:
                        member = await db.execute(
                            select(BrandMember).where(BrandMember.user_id == user.id)
                        )
                        m = member.scalars().first()
                        brand_id = m.brand_id if m else None
                        return "user", str(user.id), brand_id
        except Exception:
            pass

    # Fallback to IP
    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    return "ip", client_ip, None


class RateLimiter:
    """
    Enhanced sliding window rate limiter with per-brand tier quotas.
    Enforces RPM/RPD limits and monthly credit quotas.
    Returns standard rate limit headers.
    """
    def __init__(
        self,
        requests_limit: int = 20,
        window_seconds: int = 60,
        api_key_limit: int = None,
        check_credit_quota: bool = False,
        ignore_tier: bool = False,
    ):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.api_key_limit = api_key_limit or requests_limit
        self.check_credit_quota = check_credit_quota
        self.ignore_tier = ignore_tier

    async def __call__(self, request: Request):
        id_type, id_value, brand_id = await _resolve_identifier(request)

        # Get tier limits if brand_id known
        tier_limits = TIER_LIMITS["free"]
        if brand_id:
            tier_data = await _get_brand_tier_cached(brand_id)
            tier = tier_data.get("tier", "free")
            tier_limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])

            # Check credit quota for credit-consuming endpoints
            if self.check_credit_quota:
                is_credit_endpoint = any(
                    request.url.path.startswith(p) for p in CREDIT_CONSUMING_PATHS
                )
                if is_credit_endpoint:
                    used = tier_data.get("credits_used_this_month", 0)
                    quota = tier_data.get("monthly_credit_quota", 100)
                    if used >= quota:
                        raise HTTPException(
                            status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            detail=f"Monthly credit quota exhausted ({used}/{quota}). Please upgrade your plan.",
                            headers={"X-Credit-Quota": str(quota), "X-Credits-Used": str(used)},
                        )

        # Apply tier-based limits
        if self.ignore_tier:
            effective_limit = self.requests_limit
            # Check dynamic rate limit from Redis if it's the orchestrator path
            is_orchestrator_path = (
                "/api/v1/campaigns/" in request.url.path 
                and request.url.path.endswith("/generate")
            )
            if is_orchestrator_path:
                try:
                    dynamic_limit = await redis_client.get("settings:orchestrator_rate_limit")
                    if dynamic_limit is not None:
                        effective_limit = int(dynamic_limit)
                except Exception as e:
                    logger.warning(f"Failed to fetch dynamic orchestrator limit: {e}")
        elif id_type == "apikey":
            effective_limit = tier_limits["rpm"] * 3  # API keys get 3x rpm
        elif brand_id:
            effective_limit = tier_limits["rpm"]
        else:
            effective_limit = self.requests_limit

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
            logger.warning(f"Redis rate limiter failed: {e}. Bypassing.")
            return

        remaining = max(0, effective_limit - count)

        if count > effective_limit:
            logger.warning(f"Rate limit exceeded for {id_type}:{id_value} on {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={
                    "X-RateLimit-Limit": str(effective_limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(self.window_seconds),
                },
            )
