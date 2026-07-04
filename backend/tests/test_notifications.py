import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import Notification, User


# ========================== Auth Tests ===========================

@pytest.mark.asyncio
async def test_list_notifications_auth_required(client: AsyncClient):
    res = await client.get("/api/v1/notifications")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_preferences_auth_required(client: AsyncClient):
    res = await client.get("/api/v1/notifications/preferences")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ========================== List Tests ===========================

@pytest.mark.asyncio
async def test_list_notifications_empty(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/notifications", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_list_notifications_only_own(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """User should only see their own notifications."""
    editor_user = test_data["users"]["editor"]
    owner_user = test_data["users"]["owner"]
    editor_headers = test_data["get_headers"]("editor")

    # Create notification for editor
    notif = Notification(
        user_id=editor_user.id,
        type="job_completed",
        title="Job Done",
        message="Your job is done",
        is_read=False,
    )
    db_session.add(notif)

    # Create notification for owner
    other_notif = Notification(
        user_id=owner_user.id,
        type="job_completed",
        title="Other Job Done",
        message="Owner job done",
        is_read=False,
    )
    db_session.add(other_notif)
    await db_session.commit()

    res = await client.get("/api/v1/notifications", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert all(n["user_id"] == editor_user.id for n in data)


@pytest.mark.asyncio
async def test_list_notifications_unread_only(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """unread_only=true should filter out read notifications."""
    editor_user = test_data["users"]["editor"]
    editor_headers = test_data["get_headers"]("editor")

    db_session.add(Notification(user_id=editor_user.id, type="job_completed", title="Read", message="Read notif", is_read=True))
    db_session.add(Notification(user_id=editor_user.id, type="low_credit", title="Unread", message="Unread notif", is_read=False))
    await db_session.commit()

    res = await client.get("/api/v1/notifications?unread_only=true", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert all(n["is_read"] == False for n in data)


# ========================== Mark Read Tests ======================

@pytest.mark.asyncio
async def test_mark_as_read(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_user = test_data["users"]["editor"]
    editor_headers = test_data["get_headers"]("editor")

    notif = Notification(user_id=editor_user.id, type="job_completed", title="Test", message="Test", is_read=False)
    db_session.add(notif)
    await db_session.commit()
    await db_session.refresh(notif)

    res = await client.put(f"/api/v1/notifications/{notif.id}/read", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["is_read"] is True


@pytest.mark.asyncio
async def test_mark_read_other_user_forbidden(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Cannot mark another user's notification as read."""
    owner_user = test_data["users"]["owner"]
    editor_headers = test_data["get_headers"]("editor")

    notif = Notification(user_id=owner_user.id, type="job_completed", title="Test", message="Test", is_read=False)
    db_session.add(notif)
    await db_session.commit()
    await db_session.refresh(notif)

    res = await client.put(f"/api/v1/notifications/{notif.id}/read", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_mark_all_as_read(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_user = test_data["users"]["editor"]
    editor_headers = test_data["get_headers"]("editor")

    for i in range(3):
        db_session.add(Notification(user_id=editor_user.id, type="job_completed", title=f"Notif {i}", message="msg", is_read=False))
    await db_session.commit()

    res = await client.put("/api/v1/notifications/read-all", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK


# ========================== Delete Tests =========================

@pytest.mark.asyncio
async def test_delete_notification(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_user = test_data["users"]["editor"]
    editor_headers = test_data["get_headers"]("editor")

    notif = Notification(user_id=editor_user.id, type="low_credit", title="Delete me", message="msg", is_read=False)
    db_session.add(notif)
    await db_session.commit()
    await db_session.refresh(notif)

    res = await client.delete(f"/api/v1/notifications/{notif.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_204_NO_CONTENT

    result = await db_session.execute(select(Notification).where(Notification.id == notif.id))
    assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_delete_other_user_notification_forbidden(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    owner_user = test_data["users"]["owner"]
    editor_headers = test_data["get_headers"]("editor")

    notif = Notification(user_id=owner_user.id, type="job_completed", title="Test", message="msg", is_read=False)
    db_session.add(notif)
    await db_session.commit()
    await db_session.refresh(notif)

    res = await client.delete(f"/api/v1/notifications/{notif.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


# ========================== Preferences Tests ====================

@pytest.mark.asyncio
async def test_get_preferences(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/notifications/preferences", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "notify_on_job_complete" in data
    assert "notify_on_training_complete" in data


@pytest.mark.asyncio
async def test_update_preferences(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.put("/api/v1/notifications/preferences", json={
        "notify_on_job_complete": False,
        "notify_on_training_complete": True,
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["notify_on_job_complete"] is False
    assert data["notify_on_training_complete"] is True
