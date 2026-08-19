from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse
from httpx import AsyncClient, ConnectError, TimeoutException
from app.middleware.auth import get_current_user
from app.models.db import User
from app.config import settings

router = APIRouter(tags=["Templates Proxy"])

TIMEOUT = 30.0


async def _proxy_request(
    request: Request,
    path: str,
    current_user: User,
) -> Response:
    """Forward request to NestJS templates backend."""
    base_url = getattr(settings, "TEMPLATES_BACKEND_URL", "http://localhost:4000")
    target_url = f"{base_url}/{path}"

    # Build query string
    query_string = str(request.url.query)
    if query_string:
        target_url = f"{target_url}?{query_string}"

    # Forward headers
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    # Inject user context
    headers["X-User-Id"] = str(current_user.id)
    headers["X-User-Email"] = current_user.email or ""
    headers["X-User-Role"] = getattr(current_user, "role", "user")

    # Read body
    body = await request.body()

    try:
        async with AsyncClient(timeout=TIMEOUT) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )

        # Mirror response headers securely, popping transport-level headers
        resp_headers = dict(response.headers)
        resp_headers.pop("content-encoding", None)
        resp_headers.pop("transfer-encoding", None)
        resp_headers.pop("content-length", None)

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=resp_headers,
            media_type=response.headers.get("content-type", "application/json"),
        )

    except ConnectError:
        raise HTTPException(
            status_code=502,
            detail=f"Templates service unavailable at {base_url}",
        )
    except TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Templates service request timed out",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Proxy error: {str(e)}",
        )


# ========================== Templates Proxy =======================

@router.get("/api/v1/templates/{path:path}")
@router.post("/api/v1/templates/{path:path}")
@router.patch("/api/v1/templates/{path:path}")
@router.put("/api/v1/templates/{path:path}")
@router.delete("/api/v1/templates/{path:path}")
async def proxy_templates(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Proxy all template requests to NestJS templates service."""
    return await _proxy_request(request, f"v1/templates/{path}", current_user)


# ========================== Generations Proxy ====================

@router.get("/api/v1/generations/{path:path}")
@router.post("/api/v1/generations/{path:path}")
@router.patch("/api/v1/generations/{path:path}")
@router.put("/api/v1/generations/{path:path}")
@router.delete("/api/v1/generations/{path:path}")
async def proxy_generations(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Proxy all generation requests to NestJS templates service."""
    return await _proxy_request(request, f"v1/generations/{path}", current_user)


# ========================== Angle-Shots Proxy =====================

@router.get("/api/v1/angle-shots")
@router.get("/api/v1/angle-shots/{path:path}")
@router.post("/api/v1/angle-shots")
@router.post("/api/v1/angle-shots/{path:path}")
@router.patch("/api/v1/angle-shots")
@router.patch("/api/v1/angle-shots/{path:path}")
@router.put("/api/v1/angle-shots")
@router.put("/api/v1/angle-shots/{path:path}")
@router.delete("/api/v1/angle-shots")
@router.delete("/api/v1/angle-shots/{path:path}")
async def proxy_angle_shots(
    request: Request,
    path: str = "",
    current_user: User = Depends(get_current_user),
):
    """Proxy all angle-shots requests to NestJS templates service."""
    target_path = f"v1/angle-shots/{path}" if path else "v1/angle-shots"
    return await _proxy_request(request, target_path, current_user)


@router.get("/api/v1/admin/angle-shots")
@router.get("/api/v1/admin/angle-shots/{path:path}")
@router.post("/api/v1/admin/angle-shots")
@router.post("/api/v1/admin/angle-shots/{path:path}")
@router.patch("/api/v1/admin/angle-shots")
@router.patch("/api/v1/admin/angle-shots/{path:path}")
@router.put("/api/v1/admin/angle-shots")
@router.put("/api/v1/admin/angle-shots/{path:path}")
@router.delete("/api/v1/admin/angle-shots")
@router.delete("/api/v1/admin/angle-shots/{path:path}")
async def proxy_admin_angle_shots(
    request: Request,
    path: str = "",
    current_user: User = Depends(get_current_user),
):
    """Proxy all admin angle-shots requests to NestJS templates service."""
    target_path = f"v1/admin/angle-shots/{path}" if path else "v1/admin/angle-shots"
    return await _proxy_request(request, target_path, current_user)


# ========================== Shoots Proxy =========================

@router.get("/api/v1/shoots/{path:path}")
@router.post("/api/v1/shoots/{path:path}")
@router.patch("/api/v1/shoots/{path:path}")
@router.put("/api/v1/shoots/{path:path}")
@router.delete("/api/v1/shoots/{path:path}")
async def proxy_shoots(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Proxy all shoots requests to NestJS templates service."""
    return await _proxy_request(request, f"v1/shoots/{path}", current_user)

