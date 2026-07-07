import csv
import io
import json
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta

from app.models.db import (
    WebhookDeliveryLog, WebhookSubscription,
    AIJob, CreditTransaction, Brand
)


async def get_brand_analytics(db: AsyncSession, brand_id: int) -> Dict[str, Any]:
    """Aggregate all analytics data for a brand."""

    # 1. Webhook delivery stats
    webhook_result = await db.execute(
        select(
            WebhookDeliveryLog.status,
            func.count(WebhookDeliveryLog.id).label("count"),
            func.avg(WebhookDeliveryLog.execution_time_ms).label("avg_latency"),
            func.max(WebhookDeliveryLog.execution_time_ms).label("max_latency"),
            func.min(WebhookDeliveryLog.execution_time_ms).label("min_latency"),
        )
        .join(WebhookSubscription, WebhookSubscription.id == WebhookDeliveryLog.subscription_id)
        .where(WebhookSubscription.brand_id == brand_id)
        .group_by(WebhookDeliveryLog.status)
    )
    webhook_rows = webhook_result.all()

    webhook_stats = {
        "success_count": 0,
        "failed_count": 0,
        "retrying_count": 0,
        "dead_count": 0,
        "avg_latency_ms": 0.0,
        "max_latency_ms": 0,
        "min_latency_ms": 0,
    }
    latencies = []
    for row in webhook_rows:
        if row.status == "success":
            webhook_stats["success_count"] = row.count
        elif row.status == "failed":
            webhook_stats["failed_count"] = row.count
        elif row.status == "retrying":
            webhook_stats["retrying_count"] = row.count
        elif row.status == "dead":
            webhook_stats["dead_count"] = row.count
        if row.avg_latency:
            latencies.append((row.count, float(row.avg_latency), row.max_latency or 0, row.min_latency or 0))

    if latencies:
        total_count = sum(l[0] for l in latencies)
        webhook_stats["avg_latency_ms"] = round(sum(l[0] * l[1] for l in latencies) / total_count, 2)
        webhook_stats["max_latency_ms"] = max(l[2] for l in latencies)
        webhook_stats["min_latency_ms"] = min(l[3] for l in latencies)

    # 2. Job stats
    job_result = await db.execute(
        select(
            AIJob.status,
            func.count(AIJob.id).label("count"),
        )
        .where(AIJob.brand_id == brand_id)
        .group_by(AIJob.status)
    )
    job_rows = job_result.all()
    job_stats = {row.status: row.count for row in job_rows}

    # 3. Quota usage history (last 30 days credit transactions)
    since = datetime.utcnow() - timedelta(days=30)
    quota_result = await db.execute(
        select(
            CreditTransaction.transaction_type,
            func.count(CreditTransaction.id).label("count"),
            func.sum(func.abs(CreditTransaction.amount)).label("total_amount"),
        )
        .where(
            CreditTransaction.created_at >= since,
        )
        .group_by(CreditTransaction.transaction_type)
    )
    quota_rows = quota_result.all()
    quota_stats = {
        row.transaction_type: {
            "count": row.count,
            "total_amount": int(row.total_amount or 0)
        }
        for row in quota_rows
    }

    # 4. Brand info
    brand_result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = brand_result.scalars().first()

    return {
        "brand_id": brand_id,
        "brand_name": brand.name if brand else "Unknown",
        "tier": brand.tier if brand else "free",
        "monthly_credit_quota": brand.monthly_credit_quota if brand else 0,
        "credits_used_this_month": brand.credits_used_this_month if brand else 0,
        "exported_at": datetime.utcnow().isoformat(),
        "webhook_delivery_stats": webhook_stats,
        "job_stats": job_stats,
        "quota_usage_last_30_days": quota_stats,
    }


def export_as_json(data: Dict[str, Any]) -> str:
    """Serialize analytics data as JSON string."""
    return json.dumps(data, indent=2, default=str)


def export_as_csv(data: Dict[str, Any]) -> str:
    """Serialize analytics data as CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["Section", "Metric", "Value"])

    # Brand info
    writer.writerow(["Brand", "brand_id", data["brand_id"]])
    writer.writerow(["Brand", "brand_name", data["brand_name"]])
    writer.writerow(["Brand", "tier", data["tier"]])
    writer.writerow(["Brand", "monthly_credit_quota", data["monthly_credit_quota"]])
    writer.writerow(["Brand", "credits_used_this_month", data["credits_used_this_month"]])
    writer.writerow(["Brand", "exported_at", data["exported_at"]])

    # Webhook stats
    for key, val in data["webhook_delivery_stats"].items():
        writer.writerow(["Webhook Delivery", key, val])

    # Job stats
    writer.writerow(["Jobs", "total_jobs", sum(data["job_stats"].values())])
    for status, count in data["job_stats"].items():
        writer.writerow(["Jobs", f"status_{status}", count])

    # Quota usage
    writer.writerow(["Quota Usage (30d)", "total_transactions", sum(stats["count"] for stats in data["quota_usage_last_30_days"].values())])
    for txn_type, stats in data["quota_usage_last_30_days"].items():
        writer.writerow(["Quota Usage (30d)", f"{txn_type}_count", stats["count"]])
        writer.writerow(["Quota Usage (30d)", f"{txn_type}_total_amount", stats["total_amount"]])

    return output.getvalue()
