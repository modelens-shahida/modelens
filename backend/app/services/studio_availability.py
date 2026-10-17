"""A studio that is switched off in production: one 503 gate shared by Sketch and Catalog.

``require_available(is_blocked, message)`` builds a route dependency that runs
after login and before the route reads its body: while ``is_blocked()`` is true
it answers 503 with ``message`` for every caller (platform admins included), so
nothing is charged, written, uploaded or queued. ``unavailable_response`` is
the matching OpenAPI entry.
"""
from typing import Callable

from fastapi import Depends, HTTPException, status

from app.api_docs import ErrorResponse
from app.config import production_rules_apply
from app.middleware.auth import get_current_user
from app.models.db import User


def blocked_in_production(enabled: bool) -> bool:
    """Production rules apply and the studio's flag is off."""
    return production_rules_apply() and not enabled


def unavailable_response(description: str, message: str) -> dict:
    return {
        503: {
            "model": ErrorResponse,
            "description": description,
            "content": {"application/json": {"example": {"detail": message}}},
        },
    }


def require_available(is_blocked: Callable[[], bool], message: str):
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if is_blocked():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=message)
        return current_user
    return dependency
