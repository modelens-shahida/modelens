from fastapi import APIRouter, HTTPException, Depends, Query, status, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.db import get_db, User, AuditLog
from app.middleware.auth import get_current_user
from app.services.audit_service import audit_service, AuditEventType

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Logs"])


# ========================== Schemas ==============================

class AuditLogResponse(BaseModel):
    id: int
    event_type: str
    actor_email: Optional[str]
    brand_id: Optional[int]
    resource_type: Optional[str]
    resource_id: Optional[int]
    metadata: Optional[dict]
    ip_address: Optional[str]
    severity: str
    created_at: str


# ========================== Endpoints ============================

@router.get("/logs")
async def list_audit_logs(
    brand_id: Optional[int] = Query(None),
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List audit logs with filters."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())

    if brand_id:
        query = query.where(AuditLog.brand_id == brand_id)
    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if severity:
        query = query.where(AuditLog.severity == severity)
    if user_email:
        query = query.where(AuditLog.actor_email.ilike(f"%{user_email}%"))

    result = await db.execute(query)
    all_logs = result.scalars().all()

    total = len(all_logs)
    offset = (page - 1) * limit
    logs = all_logs[offset:offset + limit]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "logs": [
            {
                "id": log.id,
                "event_type": log.event_type,
                "actor_email": log.actor_email,
                "brand_id": log.brand_id,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "metadata": log.metadata,
                "ip_address": log.ip_address,
                "severity": log.severity,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
    }


@router.get("/logs/{log_id}")
async def get_audit_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get single audit log entry."""
    result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
    log = result.scalars().first()
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found.")

    return {
        "id": log.id,
        "event_type": log.event_type,
        "actor_email": log.actor_email,
        "brand_id": log.brand_id,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "metadata": log.metadata,
        "ip_address": log.ip_address,
        "severity": log.severity,
        "created_at": log.created_at.isoformat(),
    }


@router.get("/event-types")
async def list_event_types(
    current_user: User = Depends(get_current_user),
):
    """List all available audit event types."""
    return {
        "event_types": [e.value for e in AuditEventType]
    }
