from fastapi import APIRouter, HTTPException, Depends, status, Query, Request
import secrets
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, WebhookSubscription, Brand, BrandMember, User, WebhookLog, WebhookDeliveryLog
from app.middleware.auth import get_current_user
from app.services.audit import write_audit_log

router = APIRouter(
    prefix="/api/v1/webhooks",
    tags=["Webhooks"],
)

# ========================== Schemas ===============================

ALLOWED_EVENTS = [
    "job.completed",
    "job.failed",
    "asset.processed",
    "character.training.completed",
    "character.training.failed",
]

class WebhookCreateRequest(BaseModel):
    brand_id: int
    url: str = Field(..., max_length=1000)
    events: List[str] = Field(..., min_length=1)
    filter_rules: Optional[dict] = None
    payload_format: str = Field(default="verbose", pattern="^(verbose|summary)$")

class WebhookResponse(BaseModel):
    id: int
    brand_id: int
    url: str
    events: list
    is_active: bool
    filter_rules: Optional[dict]
    payload_format: str
    created_at: datetime
    model_config = {"from_attributes": True}

class WebhookCreateResponse(BaseModel):
    id: int
    brand_id: int
    url: str
    events: list
    is_active: bool
    secret_token: Optional[str]
    filter_rules: Optional[dict]
    payload_format: str
    created_at: datetime
    model_config = {"from_attributes": True}

# ========================== Helpers ==============================

async def get_user_role_in_brand(user_id: int, brand_id: int, db: AsyncSession) -> str:
    owner = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.owner_id == user_id))
    if owner.scalars().first():
        return "owner"
    member = await db.execute(select(BrandMember).where(
        BrandMember.brand_id == brand_id,
        BrandMember.user_id == user_id
    ))
    m = member.scalars().first()
    if m:
        return m.role
    return "none"

async def get_accessible_brand_ids(user_id: int, db: AsyncSession) -> set:
    owned = await db.execute(select(Brand.id).where(Brand.owner_id == user_id))
    ids = set(owned.scalars().all())
    members = await db.execute(select(BrandMember.brand_id).where(BrandMember.user_id == user_id))
    ids.update(members.scalars().all())
    return ids

# ========================== Endpoints ============================

@router.post("", status_code=status.HTTP_201_CREATED, response_model=WebhookCreateResponse)
async def register_webhook(
    payload: WebhookCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new webhook subscription. Requires Admin or Owner role."""
    role = await get_user_role_in_brand(current_user.id, payload.brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Admin or Owner role to register webhooks.")

    # Validate events
    invalid_events = [e for e in payload.events if e not in ALLOWED_EVENTS]
    if invalid_events:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid events: {invalid_events}. Allowed: {ALLOWED_EVENTS}"
        )

    secret_token = f"ml_sec_{secrets.token_hex(32)}"
    subscription = WebhookSubscription(
        brand_id=payload.brand_id,
        url=payload.url,
        events=payload.events,
        is_active=True,
        secret_token=secret_token,
        filter_rules=payload.filter_rules,
        payload_format=payload.payload_format,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)

    # Audit log
    await write_audit_log(db, action="webhook_created", user_id=current_user.id, brand_id=payload.brand_id, details={"webhook_id": subscription.id, "url": payload.url, "events": payload.events}, request=request)

    return subscription


@router.get("", response_model=List[WebhookResponse])
async def list_webhooks(
    brand_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List active webhooks for a brand. Requires Viewer role or higher."""
    role = await get_user_role_in_brand(current_user.id, brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")

    result = await db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.brand_id == brand_id,
            WebhookSubscription.is_active == True
        )
    )
    return list(result.scalars().all())


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook subscription. Requires Admin or Owner role."""
    result = await db.execute(
        select(WebhookSubscription).where(WebhookSubscription.id == webhook_id)
    )
    subscription = result.scalars().first()
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")

    role = await get_user_role_in_brand(current_user.id, subscription.brand_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Admin or Owner role to delete webhooks.")

    sub_id = subscription.id
    sub_brand_id = subscription.brand_id
    await db.delete(subscription)
    await db.commit()

    # Audit log
    await write_audit_log(db, action="webhook_deleted", user_id=current_user.id, brand_id=sub_brand_id, details={"webhook_id": sub_id}, request=request)


@router.get("/{subscription_id}/logs")
async def get_webhook_logs(
    subscription_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get delivery logs for a webhook subscription. Requires Admin or Owner role."""
    result = await db.execute(select(WebhookSubscription).where(WebhookSubscription.id == subscription_id))
    subscription = result.scalars().first()
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")

    role = await get_user_role_in_brand(current_user.id, subscription.brand_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Admin or Owner role to view webhook logs.")

    logs_result = await db.execute(
        select(WebhookLog)
        .where(WebhookLog.subscription_id == subscription_id)
        .order_by(WebhookLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = logs_result.scalars().all()

    return [
        {
            "id": log.id,
            "subscription_id": log.subscription_id,
            "event": log.event,
            "payload": log.payload,
            "status_code": log.status_code,
            "response_body": log.response_body,
            "attempt": log.attempt,
            "is_success": log.is_success,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.post("/{subscription_id}/rotate-secret")
async def rotate_webhook_secret(
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rotate the signing secret for a webhook subscription. Requires Admin or Owner role."""
    result = await db.execute(select(WebhookSubscription).where(WebhookSubscription.id == subscription_id))
    subscription = result.scalars().first()
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")

    role = await get_user_role_in_brand(current_user.id, subscription.brand_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Admin or Owner role to rotate webhook secret.")

    new_secret = f"ml_sec_{secrets.token_hex(32)}"
    subscription.secret_token = new_secret
    await db.commit()

    return {
        "message": "Webhook signing secret rotated successfully.",
        "subscription_id": subscription_id,
        "secret_token": new_secret,
    }


@router.get("/{subscription_id}/delivery-logs")
async def get_webhook_delivery_logs(
    subscription_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get delivery logs for a webhook subscription. Requires Admin or Owner role."""
    result = await db.execute(select(WebhookSubscription).where(WebhookSubscription.id == subscription_id))
    subscription = result.scalars().first()
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")

    role = await get_user_role_in_brand(current_user.id, subscription.brand_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Admin or Owner role.")

    logs_result = await db.execute(
        select(WebhookDeliveryLog)
        .where(WebhookDeliveryLog.subscription_id == subscription_id)
        .order_by(WebhookDeliveryLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = logs_result.scalars().all()

    return [
        {
            "id": log.id,
            "subscription_id": log.subscription_id,
            "event_type": log.event_type,
            "payload": log.payload,
            "response_status": log.response_status,
            "response_body": log.response_body,
            "execution_time_ms": log.execution_time_ms,
            "status": log.status,
            "attempt_number": log.attempt_number,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.post("/logs/{log_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_webhook_delivery(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually retry a failed or dead webhook delivery. Requires Admin or Owner role."""
    from app.worker import dispatch_webhook

    log_result = await db.execute(select(WebhookDeliveryLog).where(WebhookDeliveryLog.id == log_id))
    log = log_result.scalars().first()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery log not found.")

    sub_result = await db.execute(select(WebhookSubscription).where(WebhookSubscription.id == log.subscription_id))
    subscription = sub_result.scalars().first()
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")

    role = await get_user_role_in_brand(current_user.id, subscription.brand_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Admin or Owner role.")

    # Reset log status and queue fresh delivery
    log.status = "retrying"
    log.attempt_number = 1
    await db.commit()

    dispatch_webhook.delay(subscription.url, log.payload, subscription_id=subscription.id)

    return {"message": "Webhook delivery queued for retry.", "log_id": log_id}


@router.get("/{subscription_id}/metrics")
async def get_webhook_metrics(
    subscription_id: int,
    time_range: str = Query("7d", pattern="^(24h|7d|30d)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get delivery metrics for a webhook subscription. Requires Admin or Owner role."""
    from app.services.webhook_metrics_service import get_subscription_metrics

    result = await db.execute(select(WebhookSubscription).where(WebhookSubscription.id == subscription_id))
    subscription = result.scalars().first()
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")

    role = await get_user_role_in_brand(current_user.id, subscription.brand_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Admin or Owner role.")

    return await get_subscription_metrics(db, subscription_id, time_range, start_date, end_date)


@router.get("/admin/metrics")
async def get_admin_webhook_metrics(
    time_range: str = Query("7d", pattern="^(24h|7d|30d)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get platform-wide webhook delivery metrics. Requires Admin or Owner role."""
    from app.services.webhook_metrics_service import get_admin_metrics
    from app.models.db import Brand, BrandMember
    from sqlalchemy import select as _select

    # Check admin/owner of any brand
    owned = await db.execute(_select(Brand).where(Brand.owner_id == current_user.id))
    if not owned.scalars().first():
        member = await db.execute(
            _select(BrandMember).where(
                BrandMember.user_id == current_user.id,
                BrandMember.role.in_(["admin", "owner"])
            )
        )
        if not member.scalars().first():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Admin or Owner role.")

    return await get_admin_metrics(db, time_range, start_date, end_date)
