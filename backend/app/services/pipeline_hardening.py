"""
Generation Pipeline Hardening Service
Job lifecycle state machine, timeouts, retry resilience, DLQ routing.
"""
import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger("modelens.pipeline")


# ========================== Job Status State Machine =============

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DLQ = "dlq"


# Valid state transitions
VALID_TRANSITIONS = {
    JobStatus.QUEUED: [JobStatus.PROCESSING, JobStatus.CANCELLED],
    JobStatus.PROCESSING: [JobStatus.STREAMING, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED],
    JobStatus.STREAMING: [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED],
    JobStatus.COMPLETED: [],
    JobStatus.FAILED: [JobStatus.DLQ],
    JobStatus.CANCELLED: [],
    JobStatus.DLQ: [],
}

TERMINAL_STATES = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.DLQ}


# ========================== Provider Timeouts ====================

PROVIDER_TIMEOUTS = {
    "fashn": {
        "standard": 120,
        "2k": 120,
        "4k": 180,
        "default": 120,
    },
    "comfyui": {
        "standard": 180,
        "2k": 180,
        "4k": 300,
        "default": 180,
    },
    "dalle": {
        "standard": 60,
        "2k": 90,
        "4k": 120,
        "default": 60,
    },
    "ghost": {
        "standard": 90,
        "2k": 90,
        "4k": 150,
        "default": 90,
    },
    "default": {
        "standard": 120,
        "2k": 120,
        "4k": 180,
        "default": 120,
    },
}

# Retry configuration
RETRY_CONFIG = {
    "max_retries": 3,
    "base_delay": 2.0,
    "max_delay": 30.0,
    "backoff_factor": 2.0,
    "retryable_errors": [
        "timeout",
        "connection_error",
        "rate_limit",
        "502",
        "503",
        "504",
    ],
    "non_retryable_errors": [
        "invalid_input",
        "unauthorized",
        "insufficient_credits",
        "cancelled",
    ],
}


def get_provider_timeout(provider: str, resolution: str = "standard") -> int:
    """Get timeout in seconds for a provider/resolution combination."""
    timeouts = PROVIDER_TIMEOUTS.get(provider.lower(), PROVIDER_TIMEOUTS["default"])
    return timeouts.get(resolution.lower(), timeouts["default"])


def calculate_backoff(attempt: int) -> float:
    """Calculate exponential backoff delay."""
    delay = RETRY_CONFIG["base_delay"] * (RETRY_CONFIG["backoff_factor"] ** attempt)
    return min(delay, RETRY_CONFIG["max_delay"])


def is_retryable_error(error: str) -> bool:
    """Check if an error is retryable."""
    error_lower = error.lower()
    for non_retryable in RETRY_CONFIG["non_retryable_errors"]:
        if non_retryable in error_lower:
            return False
    for retryable in RETRY_CONFIG["retryable_errors"]:
        if retryable in error_lower:
            return True
    return False


def validate_transition(current: str, new: str) -> bool:
    """Validate a job status transition."""
    try:
        current_status = JobStatus(current)
        new_status = JobStatus(new)
        return new_status in VALID_TRANSITIONS.get(current_status, [])
    except ValueError:
        return False


class PipelineHardeningService:
    """Manages job lifecycle, timeouts and retry resilience."""

    async def transition_job_status(
        self,
        job,
        new_status: str,
        db,
        reason: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Transition job to new status with validation."""
        current = job.status
        if not validate_transition(current, new_status):
            logger.warning(f"Invalid transition: {current} -> {new_status} for job {job.job_id}")
            return False

        job.status = new_status
        if not job.meta:
            job.meta = {}

        job.meta["status_history"] = job.meta.get("status_history", [])
        job.meta["status_history"].append({
            "from": current,
            "to": new_status,
            "at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        })

        if metadata:
            job.meta.update(metadata)

        await db.commit()
        logger.info(f"Job {job.job_id}: {current} -> {new_status}")
        return True

    async def cancel_job(
        self,
        job,
        brand_id: int,
        user_id: int,
        db,
        reason: str = "User cancelled",
    ) -> Dict[str, Any]:
        """Cancel a job and refund credits."""
        if job.status in [s.value for s in TERMINAL_STATES]:
            return {
                "cancelled": False,
                "reason": f"Job already in terminal state: {job.status}",
                "credits_refunded": 0,
            }

        # Transition to cancelled
        success = await self.transition_job_status(
            job, JobStatus.CANCELLED, db, reason=reason
        )

        credits_refunded = 0
        if success:
            # Refund credits
            try:
                from app.services.credits_sync_service import credits_sync_service
                result = await credits_sync_service.refund_credits(
                    generation_id=job.job_id,
                    reason=f"Job cancelled: {reason}",
                    db=db,
                )
                credits_refunded = result.get("credits_refunded", 0)
            except Exception as e:
                logger.warning(f"Credit refund failed for cancelled job {job.job_id}: {e}")

            # Emit cancelled event
            try:
                from app.services.generation_events import generation_events, GenerationEvent
                await generation_events.publish(
                    brand_id=brand_id,
                    job_id=job.job_id,
                    event=GenerationEvent.FAILED,
                    data={
                        "reason": f"Job cancelled: {reason}",
                        "credits_refunded": credits_refunded,
                        "cancelled_by": str(user_id),
                    }
                )
            except Exception:
                pass

        return {
            "cancelled": success,
            "job_id": job.job_id,
            "reason": reason,
            "credits_refunded": credits_refunded,
        }

    async def route_to_dlq(
        self,
        job,
        error: str,
        db,
        brand_id: int,
    ) -> Dict[str, Any]:
        """Route unrecoverable job to Dead Letter Queue."""
        await self.transition_job_status(
            job, JobStatus.DLQ, db,
            reason=f"Unrecoverable error: {error}",
            metadata={"dlq_error": error, "dlq_at": datetime.now(timezone.utc).isoformat()}
        )

        # Refund credits for DLQ jobs
        credits_refunded = 0
        try:
            from app.services.credits_sync_service import credits_sync_service
            result = await credits_sync_service.refund_credits(
                generation_id=job.job_id,
                reason=f"DLQ: {error}",
                db=db,
            )
            credits_refunded = result.get("credits_refunded", 0)
        except Exception as e:
            logger.warning(f"DLQ credit refund failed: {e}")

        logger.error(f"Job {job.job_id} routed to DLQ: {error}")

        return {
            "job_id": job.job_id,
            "dlq": True,
            "error": error,
            "credits_refunded": credits_refunded,
        }

    async def execute_with_timeout(
        self,
        coro,
        provider: str,
        resolution: str = "standard",
        job_id: str = "",
    ) -> Any:
        """Execute a coroutine with provider-specific timeout."""
        timeout = get_provider_timeout(provider, resolution)
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Provider {provider} timed out after {timeout}s for job {job_id}")

    async def execute_with_retry(
        self,
        coro_factory,
        provider: str,
        resolution: str = "standard",
        job_id: str = "",
        max_retries: Optional[int] = None,
    ):
        """Execute with exponential backoff retry on transient errors."""
        max_attempts = max_retries or RETRY_CONFIG["max_retries"]
        last_error = None

        for attempt in range(max_attempts + 1):
            try:
                coro = coro_factory()
                return await self.execute_with_timeout(coro, provider, resolution, job_id)
            except TimeoutError as e:
                last_error = str(e)
                if attempt < max_attempts:
                    delay = calculate_backoff(attempt)
                    logger.warning(f"Timeout attempt {attempt + 1}/{max_attempts + 1} for job {job_id}. Retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    raise
            except Exception as e:
                last_error = str(e)
                if is_retryable_error(str(e)) and attempt < max_attempts:
                    delay = calculate_backoff(attempt)
                    logger.warning(f"Retryable error attempt {attempt + 1}/{max_attempts + 1} for job {job_id}: {e}. Retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    raise

        raise Exception(f"Max retries exceeded for job {job_id}: {last_error}")


# Singleton
pipeline_hardening = PipelineHardeningService()
