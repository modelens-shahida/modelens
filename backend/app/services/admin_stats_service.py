from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.models.db import User, Asset, AIJob, CreditTransaction


async def get_summary_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get platform-wide summary statistics."""

    # Total users
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0

    # Total assets
    total_assets_result = await db.execute(
        select(func.count(Asset.id)).where(Asset.deleted_at == None)
    )
    total_assets = total_assets_result.scalar() or 0

    # Total jobs
    total_jobs_result = await db.execute(select(func.count(AIJob.id)))
    total_jobs = total_jobs_result.scalar() or 0

    # Total credits consumed (sum of negative spend transactions)
    total_credits_result = await db.execute(
        select(func.sum(func.abs(CreditTransaction.amount)))
        .where(CreditTransaction.transaction_type == "spend")
    )
    total_credits_consumed = total_credits_result.scalar() or 0

    # Total revenue (sum of top_up transactions as proxy for revenue)
    total_revenue_result = await db.execute(
        select(func.sum(CreditTransaction.amount))
        .where(CreditTransaction.transaction_type == "top_up")
    )
    total_revenue = total_revenue_result.scalar() or 0

    return {
        "total_users": total_users,
        "total_assets": total_assets,
        "total_jobs": total_jobs,
        "total_credits_consumed": total_credits_consumed,
        "total_revenue": total_revenue,
    }


async def get_daily_jobs(db: AsyncSession, days: int = 30) -> List[Dict[str, Any]]:
    """Get jobs created per day for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            func.date(AIJob.created_at).label("date"),
            func.count(AIJob.id).label("count"),
        )
        .where(AIJob.created_at >= since)
        .group_by(func.date(AIJob.created_at))
        .order_by(func.date(AIJob.created_at))
    )
    rows = result.all()
    return [{"date": str(row.date), "count": row.count} for row in rows]


async def get_user_growth(db: AsyncSession, days: int = 30) -> List[Dict[str, Any]]:
    """Get new user registrations per day for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            func.date(User.created_at).label("date"),
            func.count(User.id).label("count"),
        )
        .where(User.created_at >= since)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
    )
    rows = result.all()
    return [{"date": str(row.date), "count": row.count} for row in rows]


async def get_credit_usage(db: AsyncSession, days: int = 30) -> List[Dict[str, Any]]:
    """Get credit consumption per day for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            func.date(CreditTransaction.created_at).label("date"),
            func.sum(func.abs(CreditTransaction.amount)).label("credits_used"),
        )
        .where(
            CreditTransaction.created_at >= since,
            CreditTransaction.transaction_type == "spend",
        )
        .group_by(func.date(CreditTransaction.created_at))
        .order_by(func.date(CreditTransaction.created_at))
    )
    rows = result.all()
    return [{"date": str(row.date), "credits_used": row.credits_used} for row in rows]
