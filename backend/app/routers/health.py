from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
import redis.asyncio as aioredis
from sqlalchemy import text

from app.config import settings
from app.models.db import async_session_maker

router = APIRouter(
    prefix="/api/v1/health",
    tags=["Health"],
)


@router.get("")
async def health_check():
    """
    Detailed health check endpoint.
    Returns 200 if all services are healthy, 503 if any service is down.
    """
    health = {
        "status": "healthy",
        "services": {
            "database": "unknown",
            "redis": "unknown",
        }
    }
    is_healthy = True

    # Check database
    try:
        async with async_session_maker() as db:
            await db.execute(text("SELECT 1"))
        health["services"]["database"] = "healthy"
    except Exception as e:
        health["services"]["database"] = f"unhealthy: {str(e)[:100]}"
        is_healthy = False

    # Check Redis
    try:
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis.ping()
        await redis.aclose()
        health["services"]["redis"] = "healthy"
    except Exception as e:
        health["services"]["redis"] = f"unhealthy: {str(e)[:100]}"
        is_healthy = False

    if not is_healthy:
        health["status"] = "unhealthy"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health,
        )

    return health
