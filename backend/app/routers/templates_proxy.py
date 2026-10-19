from fastapi import APIRouter, HTTPException, Depends, Request, Response
import re
from fastapi.responses import JSONResponse
from httpx import AsyncClient, ConnectError, TimeoutException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import get_current_user, require_platform_admin
from app.models.db import CreditTransaction, User, get_db
from app.services.job_access import require_brand_writable
from app.config import settings
from app.api_docs import ErrorResponse, error_responses

router = APIRouter(tags=["Templates Proxy"])

TIMEOUT = 30.0


# Headers the templates service trusts as identity. Whatever the client sent
# under these names is dropped (case-insensitively, every copy); only the
# values from the authenticated user are attached, once each.
TRUSTED_HEADER_PREFIXES = ("x-user-", "x-brand-", "x-org-", "x-internal-")
# Recomputed by the HTTP client for the forwarded request.
HOP_HEADERS = ("host", "content-length")


def forwarded_headers(request: Request, current_user: User) -> dict[str, str]:
    """The client's headers minus identity/trust headers, plus the verified user context."""
    headers = {}
    for name, value in request.headers.items():
        key = name.lower()
        if key in HOP_HEADERS or key.startswith(TRUSTED_HEADER_PREFIXES) or key in headers:
            continue
        headers[key] = value
    headers["X-User-Id"] = str(current_user.id)
    headers["X-User-Email"] = current_user.email or ""
    headers["X-User-Role"] = getattr(current_user, "role", "user")
    return headers


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

    headers = forwarded_headers(request, current_user)

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

@router.get(
    "/api/v1/templates/{path:path}",
    summary="Proxy GET templates request",
    description=(
        "Proxy all template requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_templates_get",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.post(
    "/api/v1/templates/{path:path}",
    summary="Proxy POST templates request",
    description=(
        "Proxy all template requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_templates_post",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.patch(
    "/api/v1/templates/{path:path}",
    summary="Proxy PATCH templates request",
    description=(
        "Proxy all template requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_templates_patch",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.put(
    "/api/v1/templates/{path:path}",
    summary="Proxy PUT templates request",
    description=(
        "Proxy all template requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_templates_put",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.delete(
    "/api/v1/templates/{path:path}",
    summary="Proxy DELETE templates request",
    description=(
        "Proxy all template requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_templates_delete",
    responses=error_responses(401, 422, 500, 502, 504),
)
async def proxy_templates(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Proxy all template requests to NestJS templates service."""
    return await _proxy_request(request, f"v1/templates/{path}", current_user)


# ========================== Generations Proxy ====================

@router.get(
    "/api/v1/generations/{path:path}",
    summary="Proxy GET generations request",
    description=(
        "Proxy all generation requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_generations_get",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.post(
    "/api/v1/generations/{path:path}",
    summary="Proxy POST generations request",
    description=(
        "Proxy all generation requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_generations_post",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.patch(
    "/api/v1/generations/{path:path}",
    summary="Proxy PATCH generations request",
    description=(
        "Proxy all generation requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_generations_patch",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.put(
    "/api/v1/generations/{path:path}",
    summary="Proxy PUT generations request",
    description=(
        "Proxy all generation requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_generations_put",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.delete(
    "/api/v1/generations/{path:path}",
    summary="Proxy DELETE generations request",
    description=(
        "Proxy all generation requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_generations_delete",
    responses=error_responses(401, 422, 500, 502, 504),
)
async def proxy_generations(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Proxy all generation requests to NestJS templates service."""
    cancel = GENERATION_CANCEL.fullmatch(path.strip("/"))
    if request.method == "POST" and cancel:
        await _check_generation_cancel(db, current_user, cancel.group(1))
    return await _proxy_request(request, f"v1/generations/{path}", current_user)


# POST /api/v1/generations/{id}/cancel: checked here before it reaches NestJS.
GENERATION_CANCEL = re.compile(r"([^/]+)/cancel")
GENERATION_NOT_FOUND = "Generation not found."


async def _check_generation_cancel(db: AsyncSession, user: User, generation_id: str) -> None:
    """Editors and above of the generation's brand (platform admins: any) may cancel it.

    The brand is that of the generation's credit reservation (credit_transactions,
    reference_id = generation id), the ledger row NestJS settles through the internal
    complete/fail callbacks. A generation without one, or of a brand the caller is not in,
    gets the same 404 and is never forwarded; a member below editor gets 403."""
    reservation = (await db.execute(
        select(CreditTransaction.brand_id).where(
            CreditTransaction.reference_id == generation_id,
            CreditTransaction.transaction_type == "reserved",
        ).order_by(CreditTransaction.id).limit(1)
    )).scalar()
    await require_brand_writable(db, user, reservation, GENERATION_NOT_FOUND)


# ========================== Angle-Shots Proxy =====================

# Angle shots are a shared catalog: only platform admins may change them.
# Reads, plus the two POSTs that only check a payload, stay open to every
# logged-in user.
READ_ONLY_ANGLE_SHOT_POSTS = re.compile(r"validate|[^/]+/compatibility-check")


async def _angle_shots_user(request: Request, path: str = "",
                            current_user: User = Depends(get_current_user)) -> User:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return current_user
    if request.method == "POST" and READ_ONLY_ANGLE_SHOT_POSTS.fullmatch(path.strip("/")):
        return current_user
    return await require_platform_admin(current_user)


async def _admin_angle_shots_user(request: Request,
                                  current_user: User = Depends(get_current_user)) -> User:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return current_user
    return await require_platform_admin(current_user)


@router.get(
    "/api/v1/angle-shots",
    summary="Proxy GET angle-shots request (collection)",
    description=(
        "Proxy all angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_angle_shots_collection_get",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.get(
    "/api/v1/angle-shots/{path:path}",
    summary="Proxy GET angle-shots request",
    description=(
        "Proxy all angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_angle_shots_get",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.post(
    "/api/v1/angle-shots",
    summary="Proxy POST angle-shots request (collection)",
    description=(
        "Proxy all angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_angle_shots_collection_post",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.post(
    "/api/v1/angle-shots/{path:path}",
    summary="Proxy POST angle-shots request",
    description=(
        "Proxy all angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_angle_shots_post",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.patch(
    "/api/v1/angle-shots",
    summary="Proxy PATCH angle-shots request (collection)",
    description=(
        "Proxy all angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_angle_shots_collection_patch",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.patch(
    "/api/v1/angle-shots/{path:path}",
    summary="Proxy PATCH angle-shots request",
    description=(
        "Proxy all angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_angle_shots_patch",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.put(
    "/api/v1/angle-shots",
    summary="Proxy PUT angle-shots request (collection)",
    description=(
        "Proxy all angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_angle_shots_collection_put",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.put(
    "/api/v1/angle-shots/{path:path}",
    summary="Proxy PUT angle-shots request",
    description=(
        "Proxy all angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_angle_shots_put",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.delete(
    "/api/v1/angle-shots",
    summary="Proxy DELETE angle-shots request (collection)",
    description=(
        "Proxy all angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_angle_shots_collection_delete",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.delete(
    "/api/v1/angle-shots/{path:path}",
    summary="Proxy DELETE angle-shots request",
    description=(
        "Proxy all angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_angle_shots_delete",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
async def proxy_angle_shots(
    request: Request,
    path: str = "",
    current_user: User = Depends(_angle_shots_user),
):
    """Proxy all angle-shots requests to NestJS templates service."""
    target_path = f"v1/angle-shots/{path}" if path else "v1/angle-shots"
    return await _proxy_request(request, target_path, current_user)


@router.get(
    "/api/v1/admin/angle-shots",
    summary="Proxy GET admin-angle-shots request (collection)",
    description=(
        "Proxy all admin angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_admin_angle_shots_collection_get",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.get(
    "/api/v1/admin/angle-shots/{path:path}",
    summary="Proxy GET admin-angle-shots request",
    description=(
        "Proxy all admin angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_admin_angle_shots_get",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.post(
    "/api/v1/admin/angle-shots",
    summary="Proxy POST admin-angle-shots request (collection)",
    description=(
        "Proxy all admin angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_admin_angle_shots_collection_post",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.post(
    "/api/v1/admin/angle-shots/{path:path}",
    summary="Proxy POST admin-angle-shots request",
    description=(
        "Proxy all admin angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_admin_angle_shots_post",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.patch(
    "/api/v1/admin/angle-shots",
    summary="Proxy PATCH admin-angle-shots request (collection)",
    description=(
        "Proxy all admin angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_admin_angle_shots_collection_patch",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.patch(
    "/api/v1/admin/angle-shots/{path:path}",
    summary="Proxy PATCH admin-angle-shots request",
    description=(
        "Proxy all admin angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_admin_angle_shots_patch",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.put(
    "/api/v1/admin/angle-shots",
    summary="Proxy PUT admin-angle-shots request (collection)",
    description=(
        "Proxy all admin angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_admin_angle_shots_collection_put",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.put(
    "/api/v1/admin/angle-shots/{path:path}",
    summary="Proxy PUT admin-angle-shots request",
    description=(
        "Proxy all admin angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_admin_angle_shots_put",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.delete(
    "/api/v1/admin/angle-shots",
    summary="Proxy DELETE admin-angle-shots request (collection)",
    description=(
        "Proxy all admin angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_admin_angle_shots_collection_delete",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
@router.delete(
    "/api/v1/admin/angle-shots/{path:path}",
    summary="Proxy DELETE admin-angle-shots request",
    description=(
        "Proxy all admin angle-shots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_admin_angle_shots_delete",
    responses=error_responses(401, 403, 422, 500, 502, 504),
)
async def proxy_admin_angle_shots(
    request: Request,
    path: str = "",
    current_user: User = Depends(_admin_angle_shots_user),
):
    """Proxy all admin angle-shots requests to NestJS templates service."""
    target_path = f"v1/admin/angle-shots/{path}" if path else "v1/admin/angle-shots"
    return await _proxy_request(request, target_path, current_user)


# ========================== Shoots Proxy =========================

@router.get(
    "/api/v1/shoots/{path:path}",
    summary="Proxy GET shoots request",
    description=(
        "Proxy all shoots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_shoots_get",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.post(
    "/api/v1/shoots/{path:path}",
    summary="Proxy POST shoots request",
    description=(
        "Proxy all shoots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_shoots_post",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.patch(
    "/api/v1/shoots/{path:path}",
    summary="Proxy PATCH shoots request",
    description=(
        "Proxy all shoots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_shoots_patch",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.put(
    "/api/v1/shoots/{path:path}",
    summary="Proxy PUT shoots request",
    description=(
        "Proxy all shoots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_shoots_put",
    responses=error_responses(401, 422, 500, 502, 504),
)
@router.delete(
    "/api/v1/shoots/{path:path}",
    summary="Proxy DELETE shoots request",
    description=(
        "Proxy all shoots requests to NestJS templates service.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded unchanged from the templates service.",
    operation_id="proxy_shoots_delete",
    responses=error_responses(401, 422, 500, 502, 504),
)
async def proxy_shoots(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Proxy all shoots requests to NestJS templates service."""
    return await _proxy_request(request, f"v1/shoots/{path}", current_user)

TEMPLATE_GENERATIONS_DISABLED = (
    "Template generations are disabled: POST /api/v1/template-generations is not available. "
    "Use POST /api/v1/productions/dispatch instead."
)


@router.post(
    "/api/v1/template-generations",
    status_code=501,
    summary="Create a template generation (disabled)",
    description=(
        "Disabled: always answers 501 Not Implemented, before any credit reservation or database write.\n"
        "\n"
        "It used to reserve credits from any brand named in the body without checking membership, then "
        "fail before forwarding, leaving the credits reserved. Use `POST /api/v1/productions/dispatch`."
    ),
    response_description="Never returned: the endpoint is disabled.",
    operation_id="create_template_generation",
    responses={
        **error_responses(401),
        501: {"model": ErrorResponse, "description": "Template generations are disabled; nothing was charged."},
    },
)
async def template_generations_disabled(current_user: User = Depends(get_current_user)):
    """Disabled; see TEMPLATE_GENERATIONS_DISABLED."""
    raise HTTPException(status_code=501, detail=TEMPLATE_GENERATIONS_DISABLED)

