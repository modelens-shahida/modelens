from fastapi import APIRouter, Depends
from typing import Optional, Dict, Any
from app.models.db import User
from app.middleware.auth import get_current_user
from app.services.provider_names import (
    QUALITY_TIERS,
    LEGACY_TO_TIER,
    normalize_quality_mode,
    get_tier_info,
    get_credit_rate,
    get_dispatch_config,
    sanitize_api_response,
)
from app.api_docs import error_responses

router = APIRouter(prefix="/api/v1/tiers", tags=["Quality Tiers"])


@router.get(
    "",
    summary="List quality tiers",
    description="List all available quality tiers.",
    response_description="All available quality tiers.",
    operation_id="list_quality_tiers",
    responses=error_responses(401),
)
async def list_quality_tiers(
    current_user: User = Depends(get_current_user),
):
    """List all available quality tiers."""
    return {
        "tiers": [
            {"tier": k, **v}
            for k, v in QUALITY_TIERS.items()
        ]
    }


@router.get(
    "/{tier}",
    summary="Get a quality tier",
    description="Get info for a specific quality tier.",
    response_description="Details of the requested quality tier.",
    operation_id="get_quality_tier",
    responses=error_responses(401, 422),
)
async def get_tier(
    tier: str,
    current_user: User = Depends(get_current_user),
):
    """Get info for a specific quality tier."""
    normalized = normalize_quality_mode(tier)
    return get_tier_info(normalized)


@router.post(
    "/normalize",
    summary="Normalize a legacy quality mode",
    description="Normalize a legacy quality mode to standardized tier.",
    response_description="The standardized tier for the legacy mode.",
    operation_id="normalize_quality_tier",
    responses=error_responses(401, 422),
)
async def normalize_tier(
    quality_mode: str,
    current_user: User = Depends(get_current_user),
):
    """Normalize a legacy quality mode to standardized tier."""
    normalized = normalize_quality_mode(quality_mode)
    return {
        "input": quality_mode,
        "normalized": normalized,
        "tier_info": QUALITY_TIERS.get(normalized, {}),
    }


@router.get(
    "/{tier}/dispatch-config",
    summary="Get tier dispatch configuration",
    description="Get dispatch configuration for a quality tier.",
    response_description="Dispatch configuration for the quality tier.",
    operation_id="get_tier_dispatch_config",
    responses=error_responses(401, 422),
)
async def get_tier_dispatch_config(
    tier: str,
    current_user: User = Depends(get_current_user),
):
    """Get dispatch configuration for a quality tier."""
    return get_dispatch_config(tier)
