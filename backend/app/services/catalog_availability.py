"""Catalog Studio is off in production unless CATALOG_JOBS_ENABLED is on.

Catalog generates with FASHN (app/services/fashn_catalog.py). Earlier the worker
never reached FASHN and saved mock outputs as charged successes, so Catalog stays
off in production until it has been tested with the real key:

* while the flag is off and production rules apply, POST /api/v1/catalog-jobs
  (JSON and multipart), /{job_id}/retry and /{job_id}/items/{item_id}/retry
  answer 503 with CATALOG_DISABLED before reading the body, so nothing is
  reserved, written, uploaded or queued; platform admins included. Reading
  jobs, exports and cancel keep working;
* a Catalog job or item the worker picks up meanwhile is failed with
  CATALOG_DISABLED and refunded once, without calling FASHN;
* in production the worker never saves a mock output, flag on or off: an item
  FASHN does not generate (no key, an error, no output) is failed with
  CATALOG_GENERATION_FAILED and refunded once.

Outside production (and in tests) Catalog works as before, mock included.
"""
from app.config import settings
from app.services.studio_availability import blocked_in_production, require_available, unavailable_response

CATALOG_DISABLED = (
    "Catalog Studio is undergoing scheduled try-on pipeline upgrades. Please check back shortly."
)
CATALOG_GENERATION_FAILED = "The catalog image could not be generated. The credits for this item were refunded."
CATALOG_DISABLED_RESPONSE = unavailable_response(
    "Catalog Studio is disabled in production (CATALOG_JOBS_ENABLED is off); nothing was charged, created or "
    "queued.",
    CATALOG_DISABLED,
)


def catalog_jobs_blocked() -> bool:
    return blocked_in_production(settings.CATALOG_JOBS_ENABLED)


# 503 while Catalog is disabled. Runs after login and before the body is read.
require_catalog_jobs_enabled = require_available(lambda: catalog_jobs_blocked(), CATALOG_DISABLED)
