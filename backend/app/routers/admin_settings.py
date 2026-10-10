from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from app.models.db import Brand, BrandMember, User, get_db
from app.config import settings
from app.services.metrics import campaigns_total, campaigns_success, campaigns_failed, campaigns_retries
from app.services.production_metrics import production_metrics
from app.routers.admin_stats import _require_admin_or_owner
from app.api_docs import error_responses

router = APIRouter(
    prefix="/api/v1/admin/settings",
    tags=["Admin Settings"],
)

async def _metrics_brand_ids(user: User, db: AsyncSession) -> Optional[list[int]]:
    """Brands whose productions the caller may count: every brand (None) for a
    platform admin/owner, else the brands they own or administer."""
    if user.role in ("admin", "owner"):
        return None
    administered = select(BrandMember.brand_id).where(
        BrandMember.user_id == user.id, BrandMember.role.in_(["admin", "owner"]))
    result = await db.execute(select(Brand.id).where(or_(Brand.owner_id == user.id, Brand.id.in_(administered))))
    return list(result.scalars().all())


class UpdateSettingsRequest(BaseModel):
    orchestrator_rate_limit: int = Field(
        ..., ge=1, le=1000,
        description="Production dispatches allowed per brand per minute (POST /api/v1/productions/dispatch).")

@router.get(
    "",
    summary="Get admin runtime settings",
    description=(
        "Get dynamic rate limit settings and orchestrator metrics.\n"
        "\n"
        "`metrics.productions_*` count productions (POST /api/v1/productions/dispatch) by outcome: "
        "`productions_total` = success + failed (finished productions, so success / total is the success "
        "rate); cancelled and in-progress productions are reported separately and are not part of total; "
        "`productions_retries` is always 0 because productions are never retried. A platform admin/owner "
        "sees every brand, a brand admin/owner only the brands they own or administer. "
        "`metrics.campaigns_*` are the legacy Prometheus counters of the removed campaign generation route.\n"
        "\n"
        "Requires a platform admin/owner, or the admin/owner of at least one brand."
    ),
    response_description="Current dynamic settings and orchestrator metrics.",
    operation_id="get_admin_settings",
    responses=error_responses(401, 403),
)
async def get_admin_settings(
    caller: User = Depends(_require_admin_or_owner),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get dynamic rate limit settings and orchestrator metrics."""
    # 1. Fetch orchestrator rate limit
    from app.middleware.rate_limit import redis_client
    orchestrator_rate_limit = settings.ORCHESTRATOR_RATE_LIMIT
    try:
        val = await redis_client.get("settings:orchestrator_rate_limit")
        if val is not None:
            orchestrator_rate_limit = int(val)
    except Exception:
        pass

    # 2. Get current values of metrics
    metrics = {
        "campaigns_total": int(campaigns_total._value.get()),
        "campaigns_success": int(campaigns_success._value.get()),
        "campaigns_failed": int(campaigns_failed._value.get()),
        "campaigns_retries": int(campaigns_retries._value.get()),
        **await production_metrics(db, await _metrics_brand_ids(caller, db)),
    }

    return {
        "orchestrator_rate_limit": orchestrator_rate_limit,
        "metrics": metrics,
    }

@router.post(
    "",
    summary="Update admin runtime settings",
    description=(
        "Update dynamic settings in Redis.\n"
        "\n"
        "Requires a platform admin/owner, or the admin/owner of at least one brand."
    ),
    response_description="The updated dynamic settings.",
    operation_id="update_admin_settings",
    responses=error_responses(401, 403, 422, 500),
)
async def update_admin_settings(
    payload: UpdateSettingsRequest,
    _caller: User = Depends(_require_admin_or_owner),
) -> Dict[str, Any]:
    """Update dynamic settings in Redis."""
    from app.middleware.rate_limit import redis_client
    try:
        await redis_client.set("settings:orchestrator_rate_limit", str(payload.orchestrator_rate_limit))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings in Redis: {e}"
        )
    return {
        "status": "success",
        "orchestrator_rate_limit": payload.orchestrator_rate_limit,
    }
