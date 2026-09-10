"""
Dead-Letter Queue (DLQ) & Auto Credit Reconciliation Service
Handles unrecoverable job failures with automatic credit refunds.
"""
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class DLQService:
    """
    Dead-Letter Queue for unrecoverable GPU crashes.
    Automatically refunds credits and generates diagnostic dumps.
    """

    async def handle_failed_job(
        self,
        db,
        job_type: str,
        job_id: int,
        brand_id: int,
        user_id: int,
        error: str,
        credits_to_refund: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Handle unrecoverable job failure with credit refund."""
        from app.models.db import CreditTransaction

        print(f"[DLQ] Handling failed {job_type} job {job_id}: {error}")

        # Auto credit refund
        if credits_to_refund > 0:
            try:
                refund_txn = CreditTransaction(
                    user_id=user_id,
                    brand_id=brand_id,
                    transaction_type="refund",
                    amount=credits_to_refund,
                    description=f"Auto DLQ refund - {job_type} job {job_id} failed",
                    reference_id=f"dlq_{job_type}_{job_id}",
                    status="completed",
                )
                db.add(refund_txn)
                await db.flush()
                print(f"[DLQ] Refunded {credits_to_refund} credits for job {job_id}")
            except Exception as e:
                print(f"[DLQ] Credit refund failed: {e}")

        # Generate diagnostic dump
        diagnostic = {
            "job_type": job_type,
            "job_id": job_id,
            "brand_id": brand_id,
            "user_id": user_id,
            "error": error[:500],
            "credits_refunded": credits_to_refund,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        # Publish DLQ event
        await self._publish_dlq_event(brand_id, diagnostic)

        await db.commit()
        return diagnostic

    async def _publish_dlq_event(self, brand_id: int, diagnostic: dict):
        """Publish DLQ event to Redis for monitoring."""
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url("redis://localhost:6379")
            event = {
                "type": "job.dlq_failure",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": diagnostic,
            }
            await r.publish(f"brand:{brand_id}:events", json.dumps(event))
            await r.lpush("dlq:failed_jobs", json.dumps(diagnostic))
            await r.expire("dlq:failed_jobs", 86400 * 7)  # 7 days
            await r.aclose()
        except Exception as e:
            print(f"[DLQ] Event publish failed: {e}")

    async def get_dlq_jobs(self, limit: int = 50) -> list:
        """Get recent DLQ failed jobs."""
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url("redis://localhost:6379")
            jobs = await r.lrange("dlq:failed_jobs", 0, limit - 1)
            await r.aclose()
            return [json.loads(j) for j in jobs]
        except Exception:
            return []


# Singleton
dlq_service = DLQService()
