from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from app.models.db import WebhookDeliveryLog


def _get_time_range(time_range: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]):
    """Resolve time range from parameters."""
    if start_date and end_date:
        return start_date, end_date
    now = datetime.utcnow()
    if time_range == "24h":
        return now - timedelta(hours=24), now
    elif time_range == "7d":
        return now - timedelta(days=7), now
    elif time_range == "30d":
        return now - timedelta(days=30), now
    else:
        return now - timedelta(days=7), now  # Default 7 days


async def get_subscription_metrics(
    db: AsyncSession,
    subscription_id: int,
    time_range: Optional[str] = "7d",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Get delivery metrics for a specific webhook subscription."""
    since, until = _get_time_range(time_range, start_date, end_date)

    base_filter = and_(
        WebhookDeliveryLog.subscription_id == subscription_id,
        WebhookDeliveryLog.created_at >= since,
        WebhookDeliveryLog.created_at <= until,
    )

    # Total count
    total_result = await db.execute(
        select(func.count(WebhookDeliveryLog.id)).where(base_filter)
    )
    total = total_result.scalar() or 0

    # Status breakdown
    status_result = await db.execute(
        select(WebhookDeliveryLog.status, func.count(WebhookDeliveryLog.id))
        .where(base_filter)
        .group_by(WebhookDeliveryLog.status)
    )
    status_counts = {row[0]: row[1] for row in status_result.all()}

    success_count = status_counts.get("success", 0)
    failed_count = status_counts.get("failed", 0)
    retrying_count = status_counts.get("retrying", 0)
    dead_count = status_counts.get("dead", 0)

    success_rate = round((success_count / total * 100), 2) if total > 0 else 0.0
    failure_rate = round(((failed_count + dead_count) / total * 100), 2) if total > 0 else 0.0

    # Average latency
    latency_result = await db.execute(
        select(func.avg(WebhookDeliveryLog.execution_time_ms)).where(base_filter)
    )
    avg_latency = latency_result.scalar()
    avg_latency_ms = round(float(avg_latency), 2) if avg_latency else 0.0

    # HTTP status code distribution
    status_code_result = await db.execute(
        select(WebhookDeliveryLog.response_status, func.count(WebhookDeliveryLog.id))
        .where(base_filter)
        .where(WebhookDeliveryLog.response_status != None)
        .group_by(WebhookDeliveryLog.response_status)
    )
    status_code_distribution = {str(row[0]): row[1] for row in status_code_result.all()}

    return {
        "subscription_id": subscription_id,
        "time_range": time_range or "custom",
        "period_start": since.isoformat(),
        "period_end": until.isoformat(),
        "total_deliveries": total,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "avg_latency_ms": avg_latency_ms,
        "status_breakdown": {
            "success": success_count,
            "failed": failed_count,
            "retrying": retrying_count,
            "dead": dead_count,
        },
        "queue_health": {
            "retrying": retrying_count,
            "dead_letter_queue": dead_count,
        },
        "status_code_distribution": status_code_distribution,
    }


async def get_admin_metrics(
    db: AsyncSession,
    time_range: Optional[str] = "7d",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Get platform-wide webhook delivery metrics for admin dashboard."""
    since, until = _get_time_range(time_range, start_date, end_date)

    base_filter = and_(
        WebhookDeliveryLog.created_at >= since,
        WebhookDeliveryLog.created_at <= until,
    )

    # Total count
    total_result = await db.execute(
        select(func.count(WebhookDeliveryLog.id)).where(base_filter)
    )
    total = total_result.scalar() or 0

    # Status breakdown
    status_result = await db.execute(
        select(WebhookDeliveryLog.status, func.count(WebhookDeliveryLog.id))
        .where(base_filter)
        .group_by(WebhookDeliveryLog.status)
    )
    status_counts = {row[0]: row[1] for row in status_result.all()}

    success_count = status_counts.get("success", 0)
    failed_count = status_counts.get("failed", 0)
    retrying_count = status_counts.get("retrying", 0)
    dead_count = status_counts.get("dead", 0)

    success_rate = round((success_count / total * 100), 2) if total > 0 else 0.0
    failure_rate = round(((failed_count + dead_count) / total * 100), 2) if total > 0 else 0.0

    # Average latency
    latency_result = await db.execute(
        select(func.avg(WebhookDeliveryLog.execution_time_ms)).where(base_filter)
    )
    avg_latency = latency_result.scalar()
    avg_latency_ms = round(float(avg_latency), 2) if avg_latency else 0.0

    # HTTP status code distribution
    status_code_result = await db.execute(
        select(WebhookDeliveryLog.response_status, func.count(WebhookDeliveryLog.id))
        .where(base_filter)
        .where(WebhookDeliveryLog.response_status != None)
        .group_by(WebhookDeliveryLog.response_status)
    )
    status_code_distribution = {str(row[0]): row[1] for row in status_code_result.all()}

    return {
        "time_range": time_range or "custom",
        "period_start": since.isoformat(),
        "period_end": until.isoformat(),
        "total_deliveries": total,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "avg_latency_ms": avg_latency_ms,
        "status_breakdown": {
            "success": success_count,
            "failed": failed_count,
            "retrying": retrying_count,
            "dead": dead_count,
        },
        "queue_health": {
            "retrying": retrying_count,
            "dead_letter_queue": dead_count,
        },
        "status_code_distribution": status_code_distribution,
    }
