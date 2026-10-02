from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any

from app.models.db import User
from app.config import settings
from app.services.metrics import campaigns_total, campaigns_success, campaigns_failed, campaigns_retries
from app.routers.admin_stats import _require_admin_or_owner
from app.api_docs import error_responses

router = APIRouter(
    prefix="/api/v1/admin/settings",
    tags=["Admin Settings"],
)

class UpdateSettingsRequest(BaseModel):
    orchestrator_rate_limit: int = Field(..., ge=1, le=1000)

@router.get(
    "",
    summary="Get admin runtime settings",
    description=(
        "Get dynamic rate limit settings and Prometheus metrics.\n"
        "\n"
        "Requires a platform admin/owner, or the admin/owner of at least one brand."
    ),
    response_description="Current dynamic settings and selected Prometheus metrics.",
    operation_id="get_admin_settings",
    responses=error_responses(401, 403),
)
async def get_admin_settings(
    _caller: User = Depends(_require_admin_or_owner),
) -> Dict[str, Any]:
    """Get dynamic rate limit settings and Prometheus metrics."""
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
