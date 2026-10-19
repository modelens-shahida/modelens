"""Rosanne Studio is off in production unless ROSANNE_JOBS_ENABLED is on.

POST /api/v1/rosanne/generate reserved brand credits and then "ran" the job
with a mock ComfyUI call: the job was marked completed and the reservation
finalized, so the brand paid for images that were never generated. Until a
real Rosanne pipeline exists:

* while the flag is off and production rules apply, POST
  /api/v1/rosanne/generate answers 503 with ROSANNE_DISABLED before the body is
  used, so nothing is reserved, written or dispatched; platform admins
  included. The read-only Rosanne routes (config, presets, scene prompt,
  estimate, check, job status) keep working;
* a Rosanne job the dispatcher picks up meanwhile is failed with
  ROSANNE_DISABLED and its reservation refunded once (job_refunds);
* in production the dispatcher never marks a mock output completed, flag on or
  off: it fails the job with ROSANNE_GENERATION_FAILED and refunds it once.

Outside production (and in tests) Rosanne works as before, mock included.
"""
from app.config import settings
from app.services.studio_availability import blocked_in_production, require_available, unavailable_response

ROSANNE_DISABLED = "Rosanne Studio is undergoing scheduled pipeline upgrades. Please check back shortly."
ROSANNE_GENERATION_FAILED = "The Rosanne images could not be generated. The reserved credits were refunded."
ROSANNE_DISABLED_RESPONSE = unavailable_response(
    "Rosanne Studio is disabled in production (ROSANNE_JOBS_ENABLED is off); nothing was charged, created or "
    "queued.",
    ROSANNE_DISABLED,
)


def rosanne_jobs_blocked() -> bool:
    return blocked_in_production(settings.ROSANNE_JOBS_ENABLED)


def rosanne_pipeline_configured() -> bool:
    """Whether the Rosanne dispatcher can generate real images. It cannot yet: it only has a mock
    ComfyUI run (rosanne_pipeline._dispatch_rosanne_workflow), whatever COMFYUI_* say."""
    return False


# 503 while Rosanne is disabled. Runs after login and before the body is used.
require_rosanne_jobs_enabled = require_available(lambda: rosanne_jobs_blocked(), ROSANNE_DISABLED)
