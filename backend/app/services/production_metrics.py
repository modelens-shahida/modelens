"""
Production metrics for the admin settings page (GET /api/v1/admin/settings).

Counted from the database (productions joined to their ai_jobs row), not
from in-process Prometheus counters, so the numbers survive restarts and
include work finished by the Celery worker.

Each production is in exactly one bucket, by its ai_jobs.status:

* success: completed
* failed: failed or timeout, or the ai_jobs row is gone (the customer sees
  these productions as failed too)
* cancelled: cancelled (stopped on purpose, so not a failure)
* in progress: any other status (queued, pending, processing and the
  pipeline stages in between)

productions_total = success + failed: finished productions with an outcome,
so productions_success / productions_total is the success rate. Cancelled
and in-progress productions are reported but not part of total.

productions_retries is always 0: production jobs are never retried (the
Celery task runs with max_retries=0, generation runs once, and an
Idempotency-Key replay returns the original production instead of running
again). A customer dispatching again after a failure creates a new,
unrelated production.
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import AIJob, Production

SUCCESS_STATUSES = ("completed",)
FAILED_STATUSES = ("failed", "timeout")
CANCELLED_STATUSES = ("cancelled",)


async def production_metrics(db: AsyncSession, brand_ids: Optional[list[int]] = None) -> dict[str, int]:
    """Production counts, for every brand (None) or only ``brand_ids``."""
    stmt = (select(AIJob.status, func.count(Production.id))
            .select_from(Production)
            .outerjoin(AIJob, AIJob.id == Production.ai_job_id)
            .group_by(AIJob.status))
    if brand_ids is not None:
        stmt = stmt.where(Production.brand_id.in_(brand_ids))

    success = failed = cancelled = in_progress = 0
    for status, count in (await db.execute(stmt)).all():
        if status in SUCCESS_STATUSES:
            success += count
        elif status is None or status in FAILED_STATUSES:
            failed += count
        elif status in CANCELLED_STATUSES:
            cancelled += count
        else:
            in_progress += count

    return {
        "productions_total": success + failed,
        "productions_success": success,
        "productions_failed": failed,
        "productions_retries": 0,
        "productions_in_progress": in_progress,
        "productions_cancelled": cancelled,
    }
