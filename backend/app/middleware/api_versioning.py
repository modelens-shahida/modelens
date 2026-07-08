import logging
from fastapi import Request, Response
from fastapi.routing import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

logger = logging.getLogger("modelens.versioning")

# V2 routes that have actual v2 implementations
V2_IMPLEMENTED_ROUTES = set()  # Add v2-specific routes here as implemented


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    API Version Middleware:
    - Supports path-based versioning (/api/v1/, /api/v2/)
    - Supports header-based versioning (Accept-Version: 2.0)
    - Falls back /api/v2/... requests to /api/v1/... if v2 not implemented
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        accept_version = request.headers.get("Accept-Version", "")

        # Header-based version detection
        if accept_version == "2.0" and not path.startswith("/api/v2/"):
            if path.startswith("/api/v1/"):
                v2_path = path.replace("/api/v1/", "/api/v2/", 1)
                logger.debug(f"[Versioning] Header redirect: {path} -> {v2_path}")
                # Rewrite path for v2 (will fall back if not implemented)
                scope = dict(request.scope)
                scope["path"] = v2_path
                request = Request(scope, request.receive, request._send)

        # v2 path fallback to v1
        if path.startswith("/api/v2/"):
            v2_sub = path[len("/api/v2"):]  # e.g. /brands
            if path not in V2_IMPLEMENTED_ROUTES:
                v1_path = f"/api/v1{v2_sub}"
                logger.info(f"[Versioning] v2 fallback: {path} -> {v1_path}")
                # Rewrite scope to redirect to v1
                scope = dict(request.scope)
                scope["path"] = v1_path
                request = Request(scope, request.receive, request._send)

        response = await call_next(request)

        # Add API version header to response
        response.headers["X-API-Version"] = "1.0"
        if path.startswith("/api/v2/"):
            response.headers["X-API-Version"] = "2.0"
            response.headers["X-API-Fallback"] = "v1"

        return response
