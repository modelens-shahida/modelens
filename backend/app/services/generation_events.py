"""
Real-Time Generation Progress Events
Broadcasts generation lifecycle events via Redis PubSub + WebSocket.
"""
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger("modelens.generation_events")


# ========================== Event Types ==========================

class GenerationEvent(str, Enum):
    STARTED = "generation.started"
    PROGRESS = "generation.progress"
    STEP = "generation.step"
    COMPLETED = "generation.completed"
    FAILED = "generation.failed"
    REFUNDED = "generation.refunded"


# ========================== Step Taxonomy ========================

GENERATION_STEPS = {
    "catalog": [
        {"step": "pre-processing", "label": "Pre-processing inputs", "percent": 5},
        {"step": "character-resolve", "label": "Resolving character profile", "percent": 10},
        {"step": "reference-load", "label": "Loading reference assets", "percent": 20},
        {"step": "prompt-resolve", "label": "Building generation parameters", "percent": 30},
        {"step": "dispatch", "label": "Dispatching to generation engine", "percent": 35},
        {"step": "render", "label": "Rendering", "percent": 75},
        {"step": "qa-check", "label": "Running QA checks", "percent": 90},
        {"step": "post-processing", "label": "Post-processing output", "percent": 95},
        {"step": "complete", "label": "Complete", "percent": 100},
    ],
    "ghost": [
        {"step": "pre-processing", "label": "Pre-processing garment", "percent": 5},
        {"step": "segmentation", "label": "Segmenting garment", "percent": 20},
        {"step": "dispatch", "label": "Dispatching to Ghost engine", "percent": 35},
        {"step": "render", "label": "Rendering Ghost output", "percent": 75},
        {"step": "alpha-mask", "label": "Applying transparency mask", "percent": 90},
        {"step": "post-processing", "label": "Post-processing output", "percent": 95},
        {"step": "complete", "label": "Complete", "percent": 100},
    ],
    "fashn": [
        {"step": "pre-processing", "label": "Pre-processing inputs", "percent": 5},
        {"step": "credit-reserve", "label": "Reserving credits", "percent": 10},
        {"step": "fashn-dispatch", "label": "Dispatching to FASHN API", "percent": 25},
        {"step": "fashn-processing", "label": "FASHN processing try-on", "percent": 65},
        {"step": "render", "label": "Rendering output", "percent": 85},
        {"step": "post-processing", "label": "Post-processing output", "percent": 95},
        {"step": "complete", "label": "Complete", "percent": 100},
    ],
    "batch": [
        {"step": "pre-processing", "label": "Pre-processing batch", "percent": 5},
        {"step": "credit-reserve", "label": "Reserving credits", "percent": 10},
        {"step": "dispatch", "label": "Dispatching angle tiles", "percent": 20},
        {"step": "render", "label": "Rendering angles", "percent": 80},
        {"step": "qa-check", "label": "Running QA checks", "percent": 90},
        {"step": "post-processing", "label": "Post-processing", "percent": 95},
        {"step": "complete", "label": "Complete", "percent": 100},
    ],
}


class GenerationEventsService:
    """Broadcasts generation progress events via Redis PubSub."""

    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        """Get Redis connection lazily."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                from app.config import settings
                redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
                self._redis = aioredis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                logger.warning(f"Redis unavailable: {e}")
                return None
        return self._redis

    def _channel(self, brand_id: int, job_id: str) -> str:
        """Get brand-isolated channel name."""
        return f"brand:{brand_id}:generation:{job_id}"

    def _brand_channel(self, brand_id: int) -> str:
        """Get brand-level channel for all events."""
        return f"brand:{brand_id}:events"

    async def publish(
        self,
        brand_id: int,
        job_id: str,
        event: GenerationEvent,
        data: Dict[str, Any],
    ) -> bool:
        """Publish generation event to Redis PubSub."""
        payload = {
            "event": event.value,
            "job_id": job_id,
            "brand_id": brand_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }

        try:
            redis = await self._get_redis()
            if redis:
                channel = self._channel(brand_id, job_id)
                brand_channel = self._brand_channel(brand_id)
                message = json.dumps(payload)
                await redis.publish(channel, message)
                await redis.publish(brand_channel, message)
                logger.info(f"Published {event.value} for job {job_id} to brand {brand_id}")
                return True
        except Exception as e:
            logger.warning(f"Redis publish failed: {e}")

        # Fallback: log event
        logger.info(f"[EVENT] {event.value} | job={job_id} | brand={brand_id} | data={data}")
        return False

    async def emit_started(
        self,
        brand_id: int,
        job_id: str,
        workflow: str,
        total_items: int = 1,
        credits_reserved: int = 0,
        character_id: Optional[str] = None,
        product_id: Optional[str] = None,
    ):
        """Emit generation.started event."""
        steps = GENERATION_STEPS.get(workflow, GENERATION_STEPS["catalog"])
        await self.publish(brand_id, job_id, GenerationEvent.STARTED, {
            "workflow": workflow,
            "total_items": total_items,
            "credits_reserved": credits_reserved,
            "character_id": character_id,
            "product_id": product_id,
            "steps": steps,
            "current_step": steps[0]["step"],
            "current_step_label": steps[0]["label"],
            "percent": 0,
        })

    async def emit_progress(
        self,
        brand_id: int,
        job_id: str,
        step: str,
        percent: int,
        step_label: str = "",
        completed_items: int = 0,
        total_items: int = 1,
        angle_code: Optional[str] = None,
        extra: Optional[Dict] = None,
    ):
        """Emit generation.progress event."""
        await self.publish(brand_id, job_id, GenerationEvent.PROGRESS, {
            "step": step,
            "step_label": step_label,
            "percent": percent,
            "completed_items": completed_items,
            "total_items": total_items,
            "angle_code": angle_code,
            **(extra or {}),
        })

    async def emit_step(
        self,
        brand_id: int,
        job_id: str,
        step: str,
        step_label: str,
        percent: int,
    ):
        """Emit generation.step event."""
        await self.publish(brand_id, job_id, GenerationEvent.STEP, {
            "step": step,
            "step_label": step_label,
            "percent": percent,
        })

    async def emit_completed(
        self,
        brand_id: int,
        job_id: str,
        workflow: str,
        total_items: int = 1,
        output_urls: Optional[list] = None,
        credits_used: int = 0,
        qa_score: Optional[float] = None,
    ):
        """Emit generation.completed event."""
        await self.publish(brand_id, job_id, GenerationEvent.COMPLETED, {
            "workflow": workflow,
            "total_items": total_items,
            "output_urls": output_urls or [],
            "credits_used": credits_used,
            "qa_score": qa_score,
            "percent": 100,
        })

    async def emit_failed(
        self,
        brand_id: int,
        job_id: str,
        workflow: str,
        reason: str,
        credits_refunded: int = 0,
    ):
        """Emit generation.failed event."""
        await self.publish(brand_id, job_id, GenerationEvent.FAILED, {
            "workflow": workflow,
            "reason": reason,
            "credits_refunded": credits_refunded,
            "percent": 0,
        })

    async def simulate_progress(
        self,
        brand_id: int,
        job_id: str,
        workflow: str = "catalog",
        total_items: int = 1,
    ):
        """Simulate step-by-step progress for demo/testing."""
        steps = GENERATION_STEPS.get(workflow, GENERATION_STEPS["catalog"])
        for step_data in steps[:-1]:
            await self.emit_step(
                brand_id=brand_id,
                job_id=job_id,
                step=step_data["step"],
                step_label=step_data["label"],
                percent=step_data["percent"],
            )
            await asyncio.sleep(1.5)


# Singleton
generation_events = GenerationEventsService()
