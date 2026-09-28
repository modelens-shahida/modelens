"""
Provider Names Cleanup & Standardization
Maps legacy internal provider names to standardized tier identifiers.
Ensures no internal provider names leak into external-facing API responses.
"""

# ========================== Tier Taxonomy =======================

# Customer-facing quality tiers (external API)
QUALITY_TIERS = {
    "fast_preview": {
        "label": "Fast Preview",
        "description": "Quick previews for testing ideas",
        "estimated_time": "~15 sec",
        "credit_multiplier": 0.5,
    },
    "high_fidelity": {
        "label": "High Fidelity",
        "description": "Production-quality output for ecommerce and catalog",
        "estimated_time": "~30 sec",
        "credit_multiplier": 1.0,
    },
    "ultra_master": {
        "label": "Ultra Master",
        "description": "Maximum detail for campaign and hero imagery",
        "estimated_time": "~60 sec",
        "credit_multiplier": 2.0,
    },
}

# ========================== Legacy Alias Mapping =================

# Maps legacy/internal names → standardized tier
LEGACY_TO_TIER = {
    # Old quality mode names
    "FAST_DRAFT": "fast_preview",
    "fast_draft": "fast_preview",
    "DRAFT": "fast_preview",
    "draft": "fast_preview",
    "preview": "fast_preview",
    "PREVIEW": "fast_preview",
    "standard": "fast_preview",
    "STANDARD": "fast_preview",

    # Old studio quality names
    "STUDIO_QUALITY": "high_fidelity",
    "studio_quality": "high_fidelity",
    "quality": "high_fidelity",
    "QUALITY": "high_fidelity",
    "HIGH": "high_fidelity",
    "high": "high_fidelity",
    "hd": "high_fidelity",
    "HD": "high_fidelity",

    # Old max/ultra names
    "max": "ultra_master",
    "MAX": "ultra_master",
    "ultra": "ultra_master",
    "ULTRA": "ultra_master",
    "master": "ultra_master",
    "MASTER": "ultra_master",
    "4k": "ultra_master",
    "4K": "ultra_master",
}

# Reverse mapping: tier → legacy names (for backward compat)
TIER_TO_LEGACY = {
    "fast_preview": "FAST_DRAFT",
    "high_fidelity": "STUDIO_QUALITY",
    "ultra_master": "ULTRA_MASTER",
}


# ========================== Helper Functions ====================

def normalize_quality_mode(quality_mode: str) -> str:
    """Normalize any legacy/internal quality mode to standardized tier."""
    if not quality_mode:
        return "high_fidelity"
    normalized = LEGACY_TO_TIER.get(quality_mode, quality_mode)
    if normalized not in QUALITY_TIERS:
        return "high_fidelity"
    return normalized


def tier_to_legacy(tier: str) -> str:
    """Convert standardized tier to legacy name for internal workers."""
    return TIER_TO_LEGACY.get(tier, "STUDIO_QUALITY")


def get_tier_info(quality_mode: str) -> dict:
    """Get full tier info for a quality mode (normalizes first)."""
    tier = normalize_quality_mode(quality_mode)
    return {
        "tier": tier,
        **QUALITY_TIERS.get(tier, QUALITY_TIERS["high_fidelity"]),
    }


def sanitize_api_response(response: dict) -> dict:
    """
    Remove internal provider names from API response.
    Replaces quality_mode with standardized tier.
    """
    sanitized = response.copy()

    # Normalize quality_mode
    if "quality_mode" in sanitized:
        sanitized["quality_mode"] = normalize_quality_mode(sanitized["quality_mode"])

    # Remove internal provider fields
    internal_fields = [
        "provider_id",
        "provider_model",
        "provider_version",
        "provider_route",
        "comfyui_workflow_id",
        "fashn_model_name",
        "dalle_model",
        "internal_route",
        "worker_queue",
        "celery_task_id",
    ]
    for field in internal_fields:
        sanitized.pop(field, None)

    return sanitized


def get_credit_rate(quality_mode: str, base_rate: int = 4) -> int:
    """Get credit rate based on quality tier."""
    tier = normalize_quality_mode(quality_mode)
    multiplier = QUALITY_TIERS[tier]["credit_multiplier"]
    return max(1, int(base_rate * multiplier))


# ========================== Dispatcher Lookup ===================

WORKFLOW_DISPATCH_MAP = {
    "fast_preview": {
        "priority": "low",
        "timeout_multiplier": 0.5,
        "retry_budget": 1,
        "reference_density": "reduced",
        "qa_level": "standard",
    },
    "high_fidelity": {
        "priority": "normal",
        "timeout_multiplier": 1.0,
        "retry_budget": 3,
        "reference_density": "full",
        "qa_level": "production",
    },
    "ultra_master": {
        "priority": "high",
        "timeout_multiplier": 2.0,
        "retry_budget": 3,
        "reference_density": "full",
        "qa_level": "master",
    },
}


def get_dispatch_config(quality_mode: str) -> dict:
    """Get dispatch configuration for a quality tier."""
    tier = normalize_quality_mode(quality_mode)
    config = WORKFLOW_DISPATCH_MAP.get(tier, WORKFLOW_DISPATCH_MAP["high_fidelity"])
    return {"tier": tier, **config}
