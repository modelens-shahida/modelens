"""Sketch Studio is off in production unless SKETCH_JOBS_ENABLED is on.

While it is off and production rules apply, POST /api/v1/sketch-jobs and its
/retry answer 503 with SKETCH_DISABLED before reading the body, so nothing is
charged, written, uploaded or queued; platform admins included. Reading
existing Sketch jobs keeps working. A Sketch job already queued is failed and
refunded by the worker without calling Gemini. With the flag on, Sketch jobs
run through Gemini with their sketch and reference images.

POST /api/v1/sketch/jobs (the ComfyUI sketch-to-product placeholder) answers
503 in production whatever the flag says: its worker writes no image, so it
would charge for an empty asset.

Outside production (and in tests) Sketch works as before.
"""
from app.config import production_rules_apply, settings
from app.services.studio_availability import blocked_in_production, require_available, unavailable_response

SKETCH_DISABLED = (
    "Sketch Studio is undergoing scheduled multimodal pipeline upgrades. Please check back shortly."
)
SKETCH_DISABLED_RESPONSE = unavailable_response(
    "Sketch Studio is disabled in production (SKETCH_JOBS_ENABLED is off); nothing was charged, created or queued.",
    SKETCH_DISABLED,
)


def sketch_jobs_blocked() -> bool:
    return blocked_in_production(settings.SKETCH_JOBS_ENABLED)


# 503 while Sketch is disabled. Runs after login and before the body is read.
require_sketch_jobs_enabled = require_available(lambda: sketch_jobs_blocked(), SKETCH_DISABLED)

# 503 in production for the ComfyUI sketch-to-product placeholder, whatever SKETCH_JOBS_ENABLED says.
require_sketch_product_jobs_available = require_available(lambda: production_rules_apply(), SKETCH_DISABLED)
