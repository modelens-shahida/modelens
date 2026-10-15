"""Sketch Studio is off in production until the Sketch multimodal pipeline lands.

While SKETCH_JOBS_ENABLED is off and production rules apply, every route that
starts Sketch work answers 503 with SKETCH_DISABLED before reading the body,
so nothing is charged, written, uploaded or queued; platform admins included.
Reading existing Sketch jobs keeps working. A Sketch job already queued is
failed and refunded by the worker without calling Gemini.
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
