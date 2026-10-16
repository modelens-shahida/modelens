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
from fastapi import Depends, HTTPException, status

from app.api_docs import ErrorResponse
from app.config import production_rules_apply, settings
from app.middleware.auth import get_current_user
from app.models.db import User

SKETCH_DISABLED = (
    "Sketch Studio is undergoing scheduled multimodal pipeline upgrades. Please check back shortly."
)
SKETCH_DISABLED_RESPONSE = {
    503: {
        "model": ErrorResponse,
        "description": "Sketch Studio is disabled in production (SKETCH_JOBS_ENABLED is off); "
                       "nothing was charged, created or queued.",
        "content": {"application/json": {"example": {"detail": SKETCH_DISABLED}}},
    },
}


def sketch_jobs_blocked() -> bool:
    return production_rules_apply() and not settings.SKETCH_JOBS_ENABLED


async def require_sketch_jobs_enabled(current_user: User = Depends(get_current_user)) -> User:
    """503 while Sketch is disabled. Runs after login and before the body is read."""
    if sketch_jobs_blocked():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=SKETCH_DISABLED)
    return current_user


async def require_sketch_product_jobs_available(current_user: User = Depends(get_current_user)) -> User:
    """503 in production for the ComfyUI sketch-to-product placeholder, whatever SKETCH_JOBS_ENABLED says."""
    if production_rules_apply():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=SKETCH_DISABLED)
    return current_user
