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

router = APIRouter(prefix="/api/v1/tiers", tags=["Quality Tiers"])


@router.get("")
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


@router.get("/{tier}")
async def get_tier(
    tier: str,
    current_user: User = Depends(get_current_user),
):
    """Get info for a specific quality tier."""
    normalized = normalize_quality_mode(tier)
    return get_tier_info(normalized)


@router.post("/normalize")
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


@router.get("/{tier}/dispatch-config")
async def get_tier_dispatch_config(
    tier: str,
    current_user: User = Depends(get_current_user),
):
    """Get dispatch configuration for a quality tier."""
    return get_dispatch_config(tier)
