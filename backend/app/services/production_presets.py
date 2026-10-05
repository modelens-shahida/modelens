"""
Production presets: the allowed locations, campaign presets, aspect ratios,
quality tiers and resolutions for Production Dispatch.

Existing presets are reused, not copied: lighting comes from
``fluid_service.LIGHTING_PRESETS`` and camera focal lengths from
``fluid_service.FOCAL_LENGTHS``. Locations are the Create Production
environment presets (also served by ``GET /api/v1/environments``). Campaign
presets had no existing equivalent (``campaign_templates`` is free-form
omnichannel config without stable ids), so a small allowed list lives here.
"""
from app.services.credits_sync_service import CREDIT_RATES
from app.services.fluid_service import FOCAL_LENGTHS, LIGHTING_PRESETS

# Create Production background picker (formerly inline in generation_api).
ENVIRONMENT_PRESETS = (
    {"env_id": "ENV-STU-0001", "display_name": "White Seamless", "family": "STUDIO", "preview_url": None},
    {"env_id": "ENV-STU-0002", "display_name": "Warm Gray Studio", "family": "STUDIO", "preview_url": None},
    {"env_id": "ENV-STU-0003", "display_name": "Cream Studio", "family": "STUDIO", "preview_url": None},
    {"env_id": "ENV-STU-0004", "display_name": "Black Studio", "family": "STUDIO", "preview_url": None},
    {"env_id": "ENV-INT-0001", "display_name": "Minimal Interior", "family": "INTERIOR", "preview_url": None},
    {"env_id": "ENV-INT-0002", "display_name": "Luxury Hotel", "family": "INTERIOR", "preview_url": None},
    {"env_id": "ENV-BCH-0001", "display_name": "Beach Golden Hour", "family": "BEACH", "preview_url": None},
    {"env_id": "ENV-URB-0001", "display_name": "City Street", "family": "URBAN", "preview_url": None},
)
LOCATIONS = {env["env_id"]: env for env in ENVIRONMENT_PRESETS}
DEFAULT_LOCATION = "ENV-STU-0001"

# Campaign preset -> default lighting and focal length when the request
# does not choose them.
CAMPAIGN_PRESETS = {
    "ecommerce": {"label": "E-commerce", "lighting_id": "STUDIO_SOFT_DIFFUSE", "focal_length_mm": 85},
    "catalog": {"label": "Catalog", "lighting_id": "STUDIO_SOFT_DIFFUSE", "focal_length_mm": 85},
    "editorial": {"label": "Editorial", "lighting_id": "EDITORIAL_HARD_HIGH_KEY", "focal_length_mm": 50},
    "lookbook": {"label": "Lookbook", "lighting_id": "NATURAL_GOLDEN_HOUR", "focal_length_mm": 50},
    "social": {"label": "Social", "lighting_id": "NATURAL_GOLDEN_HOUR", "focal_length_mm": 35},
}
DEFAULT_CAMPAIGN_PRESET = "ecommerce"

ASPECT_RATIOS = ("1:1", "3:4", "4:5", "2:3", "9:16", "16:9")
MIN_COUNT, MAX_COUNT = 1, 8

# Customer-facing quality tiers (app.services.provider_names) that have a
# credit rate. ultra_master has no CREDIT_RATES entry, so it is not offered.
QUALITY_TIERS = ("fast_preview", "high_fidelity")
DEFAULT_QUALITY = "high_fidelity"
RESOLUTIONS = ("1K", "2K", "4K")
DEFAULT_RESOLUTION = "2K"

assert all(res in CREDIT_RATES["STUDIO_QUALITY"] for res in RESOLUTIONS)
assert all(p["lighting_id"] in LIGHTING_PRESETS and p["focal_length_mm"] in FOCAL_LENGTHS
           for p in CAMPAIGN_PRESETS.values())
