from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from app.models.db import get_db, User, Brand, BrandMember
from app.middleware.auth import get_current_user
from app.services.admin_stats_service import (
    get_summary_stats,
    get_daily_jobs,
    get_user_growth,
    get_credit_usage,
)

router = APIRouter(
    prefix="/api/v1/admin/stats",
    tags=["Admin Stats"],
)


async def _require_admin_or_owner(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency to ensure only admin or owner users can access admin stats."""
    from sqlalchemy import select
    from app.middleware.auth import ROLE_HIERARCHY

    # Check if user is a platform-level admin
    if current_user.role in ("admin", "owner"):
        return current_user

    # Check if user is owner or admin of any brand
    owned = await db.execute(
        select(Brand).where(Brand.owner_id == current_user.id)
    )
    if owned.scalars().first():
        return current_user

    member = await db.execute(
        select(BrandMember).where(
            BrandMember.user_id == current_user.id,
            BrandMember.role.in_(["admin", "owner"])
        )
    )
    if member.scalars().first():
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin or Owner role required to access admin stats."
    )


@router.get("/summary")
async def get_stats_summary(
    _caller: User = Depends(_require_admin_or_owner),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns platform-wide summary statistics.
    Requires Admin or Owner role.
    """
    return await get_summary_stats(db)


@router.get("/jobs/daily")
async def get_daily_jobs_stats(
    _caller: User = Depends(_require_admin_or_owner),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Returns jobs created per day for the last 30 days.
    Requires Admin or Owner role.
    """
    return await get_daily_jobs(db)


@router.get("/users/growth")
async def get_user_growth_stats(
    _caller: User = Depends(_require_admin_or_owner),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Returns new user registrations per day for the last 30 days.
    Requires Admin or Owner role.
    """
    return await get_user_growth(db)


@router.get("/credits/usage")
async def get_credit_usage_stats(
    _caller: User = Depends(_require_admin_or_owner),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Returns credit consumption per day for the last 30 days.
    Requires Admin or Owner role.
    """
    return await get_credit_usage(db)
