from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, WebhookSubscription, Brand, BrandMember, User
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

class WebhookResponse(BaseModel):
    id: int
    brand_id: int
    url: str
    events: list
    is_active: bool
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

@router.post("", status_code=status.HTTP_201_CREATED, response_model=WebhookResponse)
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

    subscription = WebhookSubscription(
        brand_id=payload.brand_id,
        url=payload.url,
        events=payload.events,
        is_active=True,
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
