import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import AIJob, CreditTransaction, User


@pytest.mark.asyncio
async def test_summary_auth_required(client: AsyncClient):
    """Summary endpoint should require authentication."""
    res = await client.get("/api/v1/admin/stats/summary")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_summary_viewer_forbidden(client: AsyncClient, test_data: dict):
    """Viewer should not be able to access admin stats."""
    viewer_headers = test_data["get_headers"]("viewer")
    res = await client.get("/api/v1/admin/stats/summary", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_summary_editor_forbidden(client: AsyncClient, test_data: dict):
    """Editor should not be able to access admin stats."""
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/admin/stats/summary", headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_summary_owner_success(client: AsyncClient, test_data: dict):
    """Owner should be able to access summary stats."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/admin/stats/summary", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "total_users" in data
    assert "total_assets" in data
    assert "total_jobs" in data
    assert "total_credits_consumed" in data
    assert "total_revenue" in data


@pytest.mark.asyncio
async def test_summary_admin_success(client: AsyncClient, test_data: dict):
    """Admin should be able to access summary stats."""
    admin_headers = test_data["get_headers"]("admin")
    res = await client.get("/api/v1/admin/stats/summary", headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_summary_counts_correctly(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    """Summary should return correct counts."""
    brand = test_data["brand"]
    editor_user = test_data["users"]["editor"]
    owner_headers = test_data["get_headers"]("owner")

    # Add a job
    job = AIJob(
        user_id=editor_user.id,
        brand_id=brand.id,
        status="completed",
        job_type="generation",
        inputs={},
        outputs={},
    )
    db_session.add(job)

    # Add a spend transaction
    txn = CreditTransaction(
        user_id=editor_user.id,
        amount=-1,
        transaction_type="spend",
        reference_type="job",
        balance_after=99,
    )
    db_session.add(txn)
    await db_session.commit()

    res = await client.get("/api/v1/admin/stats/summary", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_jobs"] >= 1
    assert data["total_credits_consumed"] >= 1


@pytest.mark.asyncio
async def test_daily_jobs_auth_required(client: AsyncClient):
    """Daily jobs endpoint should require authentication."""
    res = await client.get("/api/v1/admin/stats/jobs/daily")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_daily_jobs_owner_success(client: AsyncClient, test_data: dict):
    """Owner should be able to access daily jobs stats."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/admin/stats/jobs/daily", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_user_growth_auth_required(client: AsyncClient):
    """User growth endpoint should require authentication."""
    res = await client.get("/api/v1/admin/stats/users/growth")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_user_growth_owner_success(client: AsyncClient, test_data: dict):
    """Owner should be able to access user growth stats."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/admin/stats/users/growth", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_credit_usage_auth_required(client: AsyncClient):
    """Credit usage endpoint should require authentication."""
    res = await client.get("/api/v1/admin/stats/credits/usage")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_credit_usage_owner_success(client: AsyncClient, test_data: dict):
    """Owner should be able to access credit usage stats."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/admin/stats/credits/usage", headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_credit_usage_viewer_forbidden(client: AsyncClient, test_data: dict):
    """Viewer should not be able to access credit usage stats."""
    viewer_headers = test_data["get_headers"]("viewer")
    res = await client.get("/api/v1/admin/stats/credits/usage", headers=viewer_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN
