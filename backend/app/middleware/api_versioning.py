import logging
from fastapi import Request, Response
from fastapi.routing import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

logger = logging.getLogger("modelens.versioning")

# V2 routes that have actual v2 implementations
V2_IMPLEMENTED_ROUTES = set()  # Add v2-specific routes here as implemented


class APIVersionMiddleware:
    """
    API Version Middleware:
    - Supports path-based versioning (/api/v1/, /api/v2/)
    - Supports header-based versioning (Accept-Version: 2.0)
    - Falls back /api/v2/... requests to /api/v1/... if v2 not implemented
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        headers = scope.get("headers", [])
        
        accept_version = ""
        for name, value in headers:
            if name.lower() == b"accept-version":
                accept_version = value.decode("utf-8")
                break

        original_path = path
        is_v2 = path.startswith("/api/v2/")
        fallback_used = False

        # Header-based version detection
        if accept_version == "2.0" and not is_v2:
            if path.startswith("/api/v1/"):
                v2_path = path.replace("/api/v1/", "/api/v2/", 1)
                logger.debug(f"[Versioning] Header redirect: {path} -> {v2_path}")
                path = v2_path
                is_v2 = True

        # v2 path fallback to v1
        if is_v2:
            v2_sub = path[len("/api/v2"):]  # e.g. /brands
            if path not in V2_IMPLEMENTED_ROUTES:
                v1_path = f"/api/v1{v2_sub}"
                logger.info(f"[Versioning] v2 fallback: {path} -> {v1_path}")
                path = v1_path
                fallback_used = True

        # Write modified path back to scope
        if path != original_path:
            scope["path"] = path
            scope["raw_path"] = path.encode("utf-8")

        # To add headers to response, we intercept the send call
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                
                version_val = "2.0" if is_v2 else "1.0"
                response_headers.append((b"x-api-version", version_val.encode("utf-8")))
                if fallback_used:
                    response_headers.append((b"x-api-fallback", b"v1"))
                
                message["headers"] = response_headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
