import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import CreditTransaction, User, AIJob


@pytest.mark.asyncio
async def test_credit_history_auth_required(client: AsyncClient):
    res = await client.get("/api/v1/credits/history")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_credit_balance(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/credits/balance", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert "balance" in res.json()
    assert "low_credits" in res.json()


@pytest.mark.asyncio
async def test_low_credits_flag(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    user.credits = 5
    await db_session.commit()
    res = await client.get("/api/v1/credits/balance", headers=editor_headers)
    assert res.json()["low_credits"] is True


@pytest.mark.asyncio
async def test_credit_history_empty(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/credits/history", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_mock_purchase_starter(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    starting_credits = user.credits
    res = await client.post("/api/v1/credits/mock-purchase", json={"package": "starter"}, headers=editor_headers)
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["credits_added"] == 100
    assert res.json()["new_balance"] == starting_credits + 100


@pytest.mark.asyncio
async def test_mock_purchase_invalid_package(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/credits/mock-purchase", json={"package": "invalid"}, headers=editor_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_admin_adjust_unauthorized(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    res = await client.post("/api/v1/credits/admin-adjust", json={
        "target_user_id": editor_user.id, "amount": 100, "description": "Test"
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN
