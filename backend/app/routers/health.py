import asyncio
import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
import redis.asyncio as aioredis
from sqlalchemy import text

from app.config import settings
from app.models.db import async_session_maker

logger = logging.getLogger("modelens.health")

router = APIRouter(
    prefix="/api/v1/health",
    tags=["Health"],
)

# Per-dependency budget, so a hung DB or Redis still answers within a 5s probe timeout.
CHECK_TIMEOUT_SECONDS = 2.0


async def _check_database():
    async with async_session_maker() as db:
        await db.execute(text("SELECT 1"))


async def _check_redis():
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await redis.ping()
    finally:
        await redis.aclose()


async def _probe(name: str, check) -> bool:
    try:
        await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_SECONDS)
        return True
    except Exception:
        # Details stay in the server log; the response only names the component.
        logger.warning("Readiness check failed: %s", name, exc_info=True)
        return False


@router.get(
    "/live",
    summary="Liveness check",
    description=(
        "Returns 200 while the API process is running. Checks no dependencies (DB, Redis, Celery), "
        "so a dependency outage never restarts the container. Use for liveness probes and container "
        "healthchecks.\n"
        "\n"
        "No authentication required; not rate limited."
    ),
    response_description="The API process is up.",
    operation_id="get_health_liveness",
)
async def liveness():
    return {"status": "alive"}


@router.get(
    "",
    summary="Readiness check",
    description=(
        "Checks the database and Redis. Returns 200 when both respond, 503 when either is down, with "
        "the failing components listed in `failing`. Use for readiness probes and load-balancer "
        "health checks, not liveness: a DB or Redis outage should take the instance out of rotation, "
        "not restart it.\n"
        "\n"
        "No authentication required; not rate limited."
    ),
    response_description="All dependencies are healthy.",
    operation_id="get_health_readiness",
    responses={
        503: {
            "description": "At least one dependency is down.",
            "content": {"application/json": {"example": {
                "status": "unhealthy",
                "services": {"database": "healthy", "redis": "unhealthy"},
                "failing": ["redis"],
            }}},
        },
    },
)
async def health_check():
    results = {
        "database": await _probe("database", _check_database),
        "redis": await _probe("redis", _check_redis),
    }
    services = {name: "healthy" if ok else "unhealthy" for name, ok in results.items()}
    failing = [name for name, ok in results.items() if not ok]

    if failing:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "services": services, "failing": failing},
        )
    return {"status": "healthy", "services": services}
