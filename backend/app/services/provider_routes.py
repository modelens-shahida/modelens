"""
Provider routes: platform-admin lifecycle for ``provider_routes`` rows.

Production Dispatch only uses a route whose status is ACTIVE
(``production_dispatch._provider_routes``), and only after the product type's
capability pack is in PRODUCTION. Both are required: an enabled route with no
promoted pack, or a promoted pack with no enabled route, is still a 409 for
the customer.

Lifecycle: register -> DRAFT; DRAFT -> ACTIVE (enable); ACTIVE <-> DISABLED
(disable / enable); anything except RETIRED -> RETIRED (retire, final).
Rows written before this API may have a NULL or other status. Dispatch never
uses them; they can be disabled or retired, and enabled once disabled.

Route fields are fixed after register: to change a route, retire it and
register a new one. Every write (register, enable, disable, retire) adds an
``audit_logs`` entry in the same transaction: who (user id + email), which
route, from/to status, the reason, and when (``created_at``).
"""
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import CapabilityPack, ProviderRoute
from app.services.audit import write_audit_log

DRAFT = "DRAFT"
ACTIVE = "ACTIVE"
DISABLED = "DISABLED"
RETIRED = "RETIRED"
STATUSES = (DRAFT, ACTIVE, DISABLED, RETIRED)
TRANSITIONS: dict[str, frozenset[str]] = {
    DRAFT: frozenset({ACTIVE, RETIRED}),
    ACTIVE: frozenset({DISABLED, RETIRED}),
    DISABLED: frozenset({ACTIVE, RETIRED}),
    RETIRED: frozenset(),
}
# NULL or a status from before this API (e.g. INACTIVE): never used by dispatch.
LEGACY_TRANSITIONS = frozenset({DISABLED, RETIRED})
PACK_LIVE_STATUS = "PRODUCTION"


class RouteNotFound(Exception):
    pass


class RouteConflict(Exception):
    pass


class RouteInvalid(Exception):
    pass


async def _first(db: AsyncSession, stmt):
    return (await db.execute(stmt)).scalars().first()


def allowed_next(route: ProviderRoute) -> frozenset[str]:
    return TRANSITIONS.get(route.status, LEGACY_TRANSITIONS)


def _move(route: ProviderRoute, new_status: str) -> None:
    allowed = allowed_next(route)
    if new_status not in allowed:
        next_steps = ", ".join(sorted(allowed)) or "none (final)"
        raise RouteConflict(f"Route {route.route_id} is {route.status or 'unset'} and cannot move to {new_status}. "
                            f"Allowed next statuses: {next_steps}.")
    route.status = new_status


async def _audit(db: AsyncSession, action: str, route: ProviderRoute, actor: Optional[str],
                 actor_user_id: Optional[int], from_status: Optional[str], **extra: Any) -> None:
    """One audit_logs entry, flushed with the change it describes (the caller commits)."""
    await write_audit_log(db, action, user_id=actor_user_id, details={
        "actor_email": actor,
        "route_id": route.route_id,
        "workflow_id": route.workflow_id,
        "quality_mode": route.quality_mode,
        "provider_id": route.provider_id,
        "from_status": from_status,
        "to_status": route.status,
        **extra,
    })


# ========================== Reads =================================

async def get_route(db: AsyncSession, route_id: str) -> ProviderRoute:
    route = await _first(db, select(ProviderRoute).where(ProviderRoute.route_id == route_id))
    if route is None:
        raise RouteNotFound(f"Route {route_id} not found.")
    return route


async def list_routes(db: AsyncSession, workflow_id: Optional[str] = None, status: Optional[str] = None,
                      quality_mode: Optional[str] = None) -> list[ProviderRoute]:
    stmt = select(ProviderRoute).order_by(ProviderRoute.workflow_id, ProviderRoute.priority, ProviderRoute.id)
    if workflow_id:
        stmt = stmt.where(ProviderRoute.workflow_id == workflow_id)
    if status:
        stmt = stmt.where(ProviderRoute.status == status)
    if quality_mode:
        stmt = stmt.where(ProviderRoute.quality_mode == quality_mode)
    return list((await db.execute(stmt)).scalars().all())


async def live_workflows(db: AsyncSession) -> set[str]:
    """Workflow ids used by a PRODUCTION capability pack (the other half of what dispatch requires)."""
    rows = (await db.execute(select(CapabilityPack.workflow_route).where(
        CapabilityPack.status == PACK_LIVE_STATUS, CapabilityPack.workflow_route.is_not(None)))).scalars().all()
    return set(rows)


# ========================== Writes ================================

async def register(db: AsyncSession, *, route_id: str, workflow_id: str, quality_mode: str, provider_id: str,
                   model_id: Optional[str] = None, priority: int = 1, fallback_route_id: Optional[str] = None,
                   meta: Optional[dict] = None, registered_by: Optional[str] = None,
                   actor_user_id: Optional[int] = None) -> ProviderRoute:
    if await _first(db, select(ProviderRoute.id).where(ProviderRoute.route_id == route_id)):
        raise RouteConflict(f"Route {route_id} is already registered.")
    if fallback_route_id is not None:
        if fallback_route_id == route_id:
            raise RouteInvalid("fallback_route_id cannot be the route itself.")
        if not await _first(db, select(ProviderRoute.id).where(ProviderRoute.route_id == fallback_route_id)):
            raise RouteInvalid(f"fallback_route_id {fallback_route_id} is not a registered route.")
    route = ProviderRoute(route_id=route_id, workflow_id=workflow_id, quality_mode=quality_mode,
                          provider_id=provider_id, model_id=model_id, priority=priority, status=DRAFT,
                          fallback_route_id=fallback_route_id, meta=meta)
    db.add(route)
    try:
        await db.flush()
    except IntegrityError:  # registered concurrently
        await db.rollback()
        raise RouteConflict(f"Route {route_id} is already registered.")
    await _audit(db, "provider_route_registered", route, registered_by, actor_user_id, None)
    await db.commit()
    await db.refresh(route)
    return route


async def _transition(db: AsyncSession, route: ProviderRoute, new_status: str, action: str, reason: str,
                      actor: Optional[str], actor_user_id: Optional[int]) -> ProviderRoute:
    if not (reason or "").strip():
        raise RouteInvalid("A reason is required.")
    from_status = route.status
    _move(route, new_status)
    await _audit(db, action, route, actor, actor_user_id, from_status, reason=reason.strip())
    await db.commit()
    await db.refresh(route)
    return route


async def enable(db: AsyncSession, route: ProviderRoute, reason: str, actor: Optional[str] = None,
                 actor_user_id: Optional[int] = None) -> ProviderRoute:
    return await _transition(db, route, ACTIVE, "provider_route_enabled", reason, actor, actor_user_id)


async def disable(db: AsyncSession, route: ProviderRoute, reason: str, actor: Optional[str] = None,
                  actor_user_id: Optional[int] = None) -> ProviderRoute:
    return await _transition(db, route, DISABLED, "provider_route_disabled", reason, actor, actor_user_id)


async def retire(db: AsyncSession, route: ProviderRoute, reason: str, actor: Optional[str] = None,
                 actor_user_id: Optional[int] = None) -> ProviderRoute:
    return await _transition(db, route, RETIRED, "provider_route_retired", reason, actor, actor_user_id)
