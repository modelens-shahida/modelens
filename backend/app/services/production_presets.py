"""
Production output settings: the allowed aspect ratios, image count, quality
tiers and resolutions for Production Dispatch.

Location, lighting and campaign presets are not here: they live in the
Presets Registry (``app.services.presets_registry``, table ``presets``) and
only PRODUCTION presets are accepted.
"""
from app.services.credits_sync_service import CREDIT_RATES

ASPECT_RATIOS = ("1:1", "3:4", "4:5", "2:3", "9:16", "16:9")
MIN_COUNT, MAX_COUNT = 1, 8

# Customer-facing quality tiers (app.services.provider_names) that have a
# credit rate. ultra_master has no CREDIT_RATES entry, so it is not offered.
QUALITY_TIERS = ("fast_preview", "high_fidelity")
DEFAULT_QUALITY = "high_fidelity"
RESOLUTIONS = ("1K", "2K", "4K")
DEFAULT_RESOLUTION = "2K"

assert all(res in CREDIT_RATES["STUDIO_QUALITY"] for res in RESOLUTIONS)
