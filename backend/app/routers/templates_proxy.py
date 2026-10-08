from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db import get_db
import json
import uuid
from fastapi.responses import JSONResponse
from httpx import AsyncClient, ConnectError, TimeoutException
from app.middleware.auth import get_current_user
from app.models.db import User
from app.config import settings
from app.api_docs import error_responses

if TYPE_CHECKING:
    from app.models.db import CreditTransaction



# ========================== Credit Cost Estimation ===============

RESOLUTION_CREDIT_COST = {
    "1K": 1, "2K": 2, "4K": 5, "8K": 10, "14K": 20,
}

def estimate_credits(payload: dict) -> int:
    """Estimate credit cost based on outputCount and resolution."""
    output_count = payload.get("outputCount", payload.get("output_count", 1))
    resolution = payload.get("resolution", "2K").upper()
    cost_per_output = RESOLUTION_CREDIT_COST.get(resolution, 2)
    return max(1, int(output_count) * cost_per_output)


async def check_and_reserve_credits(
    db: AsyncSession,
    brand_id: int,
    user_id: int,
    credits_needed: int,
    generation_id: str,
) -> "CreditTransaction":
    """Check brand credits and create a pending reservation."""
    from sqlalchemy import select
    from app.models.db import Brand, CreditTransaction

    brand_result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = brand_result.scalars().first()

    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    if (brand.credits or 0) < credits_needed:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Need {credits_needed}, have {brand.credits or 0}."
        )

    # Reserve credits
    brand.credits = (brand.credits or 0) - credits_needed

    txn = CreditTransaction(
        user_id=user_id,
        brand_id=brand_id,
        transaction_type="reserved",
        amount=-credits_needed,
        description=f"Template generation reservation - {generation_id}",
        reference_id=generation_id,
        status="pending",
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn

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
):
    """Proxy all generation requests to NestJS templates service."""
    return await _proxy_request(request, f"v1/generations/{path}", current_user)


# ========================== Angle-Shots Proxy =====================

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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
)
async def proxy_angle_shots(
    request: Request,
    path: str = "",
    current_user: User = Depends(get_current_user),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
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
    responses=error_responses(401, 422, 500, 502, 504),
)
async def proxy_admin_angle_shots(
    request: Request,
    path: str = "",
    current_user: User = Depends(get_current_user),
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

@router.post(
    "/api/v1/template-generations",
    summary="Create a template generation",
    description=(
        "Intercept template generation POST to validate and reserve credits.\n"
        "\n"
        "Upstream status codes and bodies are passed through unchanged."
    ),
    response_description="Response forwarded from the templates service after credits were reserved.",
    operation_id="create_template_generation",
    responses=error_responses(400, 401, 402, 404, 500, 502, 504),
)
async def proxy_template_generations_with_credit_check(
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Intercept template generation POST to validate and reserve credits."""
    body = await request.body()
    try:
        payload = json.loads(body) if body else {}
    except Exception:
        payload = {}

    # Estimate credits
    credits_needed = estimate_credits(payload)
    generation_id = payload.get("generationId", str(uuid.uuid4()))

    # Get brand_id from payload or user context
    brand_id = payload.get("brandId") or payload.get("brand_id")
    if not brand_id:
        raise HTTPException(status_code=400, detail="brandId is required")

    # Check and reserve credits
    await check_and_reserve_credits(db, int(brand_id), current_user.id, credits_needed, generation_id)

    # Forward to NestJS
    return await _proxy_request(request, "v1/template-generations", current_user, body=body)

