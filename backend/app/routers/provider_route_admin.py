"""
Provider route admin API (platform admins only).

Register, list, get, enable, disable and retire ``provider_routes`` rows. The
lifecycle rules live in ``app/services/provider_routes.py``; a step the
lifecycle does not allow is a 409 that names the current status and the
allowed next ones. A route is registered as DRAFT and is never live until a
platform admin enables it.

Production Dispatch needs both an ACTIVE route and a PRODUCTION capability
pack whose ``workflow_route`` is the route's ``workflow_id``. Enabling a route
does not require the pack; ``pack_live`` shows whether that half is in place.
Every write adds an ``audit_logs`` entry (who, which route, from/to status,
reason, when).

These responses are admin-only and include provider and workflow ids.
Customer routes are unchanged and never read this API.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_docs import error_responses
from app.middleware.auth import require_platform_admin
from app.models.db import ProviderRoute, User, get_db
from app.services import provider_routes as svc

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$"
RouteStatus = Literal["DRAFT", "ACTIVE", "DISABLED", "RETIRED"]
# The tier names and their legacy equivalents; dispatch matches a route on either.
QualityMode = Literal["fast_preview", "high_fidelity", "ultra_master", "FAST_DRAFT", "STUDIO_QUALITY", "ULTRA_MASTER"]

router = APIRouter(
    prefix="/api/v1/admin/provider-routes",
    tags=["Provider Routes"],
    dependencies=[Depends(require_platform_admin)],
)


async def _run(db: AsyncSession, coro):
    """Translate service errors into HTTP errors; nothing half-done is kept."""
    try:
        return await coro
    except svc.RouteNotFound as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except svc.RouteConflict as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except svc.RouteInvalid as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ========================== Schemas ===============================

class AdminProviderRoute(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    route_id: str = Field(..., examples=["RT-GARMENT-01"])
    workflow_id: str = Field(..., examples=["WF-GARMENT-TRYON"])
    quality_mode: str = Field(..., examples=["STUDIO_QUALITY"])
    provider_id: str = Field(..., examples=["PRV-COMFYUI"])
    model_id: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = Field(None, examples=["DRAFT"],
                                  description="NULL or a non-lifecycle value for rows written before this API.")
    fallback_route_id: Optional[str] = None
    avg_latency_ms: Optional[int] = None
    avg_qa_score: Optional[float] = None
    meta: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    allowed_next_statuses: list[str]
    pack_live: bool = Field(..., description="A PRODUCTION capability pack uses this workflow. Dispatch needs this "
                                             "and an ACTIVE route.")


class AdminProviderRouteList(BaseModel):
    routes: list[AdminProviderRoute]
    total: int


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: str = Field(..., pattern=ID_PATTERN, examples=["RT-GARMENT-01"])
    workflow_id: str = Field(..., pattern=ID_PATTERN, examples=["WF-GARMENT-TRYON"])
    quality_mode: QualityMode
    provider_id: str = Field(..., pattern=ID_PATTERN, examples=["PRV-COMFYUI"])
    model_id: Optional[str] = Field(None, pattern=ID_PATTERN)
    priority: int = Field(1, ge=1, le=1000)
    fallback_route_id: Optional[str] = Field(None, pattern=ID_PATTERN)
    meta: Optional[dict[str, Any]] = None


class ReasonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=1000, examples=["Staging run passed QA."])


def _out(route: ProviderRoute, live: set[str]) -> AdminProviderRoute:
    return AdminProviderRoute.model_validate({
        **{c.name: getattr(route, c.name) for c in ProviderRoute.__table__.columns},
        "allowed_next_statuses": sorted(svc.allowed_next(route)),
        "pack_live": route.workflow_id in live,
    })


RouteId = Path(..., pattern=ID_PATTERN, examples=["RT-GARMENT-01"])
ADMIN_ERRORS = error_responses(400, 401, 403, 404, 409, 422)


async def _transition(db: AsyncSession, route_id: str, action, payload: ReasonRequest, admin: User):
    route = await _run(db, svc.get_route(db, route_id))
    route = await _run(db, action(db, route, payload.reason, admin.email, admin.id))
    return _out(route, await svc.live_workflows(db))


# ========================== Endpoints =============================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminProviderRoute,
    summary="Register a provider route",
    description="Registers a route (workflow + quality mode -> provider). It starts DRAFT and dispatch never uses "
                "it until it is enabled. 409 when the route id is already registered; 400 when the fallback route "
                "is unknown or is the route itself. Route fields are fixed once registered.",
    response_description="The registered route.",
    operation_id="register_provider_route",
    responses=ADMIN_ERRORS,
)
async def register_route(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    route = await _run(db, svc.register(db, registered_by=admin.email, actor_user_id=admin.id,
                                        **payload.model_dump()))
    return _out(route, await svc.live_workflows(db))


@router.get(
    "",
    response_model=AdminProviderRouteList,
    summary="List provider routes",
    description="Every provider route, in every status. Filter by `workflow_id`, `status` and `quality_mode`.",
    response_description="The provider routes.",
    operation_id="list_provider_routes",
    responses=error_responses(401, 403, 422),
)
async def list_routes(
    workflow_id: Optional[str] = Query(None, pattern=ID_PATTERN),
    route_status: Optional[RouteStatus] = Query(None, alias="status"),
    quality_mode: Optional[QualityMode] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    routes = await svc.list_routes(db, workflow_id, route_status, quality_mode)
    live = await svc.live_workflows(db)
    return AdminProviderRouteList(routes=[_out(r, live) for r in routes], total=len(routes))


@router.get(
    "/{route_id}",
    response_model=AdminProviderRoute,
    summary="Get a provider route",
    description="One route, with its allowed next statuses and whether a PRODUCTION pack uses its workflow.",
    response_description="The route.",
    operation_id="get_provider_route",
    responses=error_responses(401, 403, 404, 422),
)
async def get_route(route_id: str = RouteId, db: AsyncSession = Depends(get_db)):
    route = await _run(db, svc.get_route(db, route_id))
    return _out(route, await svc.live_workflows(db))


@router.post(
    "/{route_id}/enable",
    response_model=AdminProviderRoute,
    summary="Enable a provider route",
    description="DRAFT or DISABLED -> ACTIVE; 409 from any other status. Dispatch uses the route only when a "
                "PRODUCTION capability pack also uses its workflow (`pack_live`).",
    response_description="The route, now ACTIVE.",
    operation_id="enable_provider_route",
    responses=ADMIN_ERRORS,
)
async def enable_route(
    payload: ReasonRequest,
    route_id: str = RouteId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    return await _transition(db, route_id, svc.enable, payload, admin)


@router.post(
    "/{route_id}/disable",
    response_model=AdminProviderRoute,
    summary="Disable a provider route",
    description="ACTIVE (or a status from before this API) -> DISABLED; 409 otherwise. Dispatch stops using the "
                "route at once.",
    response_description="The route, now DISABLED.",
    operation_id="disable_provider_route",
    responses=ADMIN_ERRORS,
)
async def disable_route(
    payload: ReasonRequest,
    route_id: str = RouteId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    return await _transition(db, route_id, svc.disable, payload, admin)


@router.post(
    "/{route_id}/retire",
    response_model=AdminProviderRoute,
    summary="Retire a provider route",
    description="Retires a route from any status except RETIRED (409). Retired routes are kept, never deleted, "
                "and cannot be enabled again.",
    response_description="The route, now RETIRED.",
    operation_id="retire_provider_route",
    responses=ADMIN_ERRORS,
)
async def retire_route(
    payload: ReasonRequest,
    route_id: str = RouteId,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    return await _transition(db, route_id, svc.retire, payload, admin)
