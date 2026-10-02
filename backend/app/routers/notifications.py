from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, Notification, User
from app.middleware.auth import get_current_user
from app.api_docs import error_responses, limit_query, offset_query

router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"],
)

# ========================== Schemas ==============================

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class PreferencesResponse(BaseModel):
    notify_on_job_complete: bool
    notify_on_training_complete: bool

class PreferencesUpdate(BaseModel):
    notify_on_job_complete: Optional[bool] = None
    notify_on_training_complete: Optional[bool] = None

# ========================== Endpoints ============================

@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="List notifications",
    description="List current user's notifications, newest first.",
    response_description="A page of the caller's notifications, newest first.",
    operation_id="list_notifications",
    responses=error_responses(401, 422),
)
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = limit_query(20, le=100),
    offset: int = offset_query(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's notifications, newest first."""
    query = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    if unread_only:
        query = query.where(Notification.is_read == False)
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.put(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark a notification as read",
    description="Mark a specific notification as read.",
    response_description="The updated notification.",
    operation_id="mark_notification_read",
    responses=error_responses(401, 403, 404, 422),
)
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a specific notification as read."""
    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalars().first()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another user's notification.")

    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification


@router.put(
    "/read-all",
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    description="Mark all notifications as read for current user.",
    response_description="Number of notifications marked as read.",
    operation_id="mark_all_notifications_read",
    responses=error_responses(401),
)
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read for current user."""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        )
    )
    notifications = result.scalars().all()
    for n in notifications:
        n.is_read = True
    await db.commit()
    return {"message": f"Marked {len(notifications)} notifications as read."}


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a notification",
    description="Delete a specific notification.",
    response_description="Notification deleted; no content returned.",
    operation_id="delete_notification",
    responses=error_responses(401, 403, 404, 422),
)
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific notification."""
    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalars().first()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another user's notification.")

    await db.delete(notification)
    await db.commit()


@router.get(
    "/preferences",
    response_model=PreferencesResponse,
    summary="Get notification preferences",
    description="Get current user's notification preferences.",
    response_description="The caller's notification preferences.",
    operation_id="get_notification_preferences",
    responses=error_responses(401),
)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's notification preferences."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalars().first()
    return PreferencesResponse(
        notify_on_job_complete=user.notify_on_job_complete,
        notify_on_training_complete=user.notify_on_training_complete,
    )


@router.put(
    "/preferences",
    response_model=PreferencesResponse,
    summary="Update notification preferences",
    description="Update current user's notification preferences.",
    response_description="The updated notification preferences.",
    operation_id="update_notification_preferences",
    responses=error_responses(401, 422),
)
async def update_preferences(
    payload: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's notification preferences."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalars().first()

    if payload.notify_on_job_complete is not None:
        user.notify_on_job_complete = payload.notify_on_job_complete
    if payload.notify_on_training_complete is not None:
        user.notify_on_training_complete = payload.notify_on_training_complete

    await db.commit()
    await db.refresh(user)
    return PreferencesResponse(
        notify_on_job_complete=user.notify_on_job_complete,
        notify_on_training_complete=user.notify_on_training_complete,
    )
