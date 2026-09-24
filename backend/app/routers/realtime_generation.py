from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import asyncio
import logging

from app.models.db import get_db, User, Brand, BrandMember, async_session_maker
from app.middleware.auth import get_current_user
from app.services.generation_events import generation_events, GenerationEvent, GENERATION_STEPS

logger = logging.getLogger("modelens.realtime")

router = APIRouter(prefix="/api/v1", tags=["Realtime Generation Events"])


# ========================== Auth Helpers =========================

async def _authenticate_ws(token: str):
    """Authenticate WebSocket connection via JWT."""
    try:
        from jose import jwt
        from app.config import settings
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None, "Invalid token"

        async with async_session_maker() as db:
            result = await db.execute(select(User).where(User.id == int(user_id)))
            user = result.scalars().first()
            if not user:
                return None, "User not found"
            return user, None
    except Exception as e:
        return None, str(e)


async def _verify_brand_access(user_id: int, brand_id: int) -> bool:
    """Verify user has access to brand channel."""
    async with async_session_maker() as db:
        # Check owner
        owner = await db.execute(
            select(Brand).where(Brand.id == brand_id, Brand.owner_id == user_id)
        )
        if owner.scalars().first():
            return True

        # Check member
        member = await db.execute(
            select(BrandMember).where(
                BrandMember.brand_id == brand_id,
                BrandMember.user_id == user_id,
            )
        )
        return member.scalars().first() is not None


# ========================== WebSocket Endpoints ==================

@router.websocket("/ws/generation/{job_id}/progress")
async def generation_progress_ws(
    job_id: str,
    websocket: WebSocket,
    token: str = Query(...),
    brand_id: int = Query(...),
):
    """
    WebSocket endpoint for real-time generation progress.
    Channel isolated per brand for multi-tenant security.
    """
    # Authenticate
    user, error = await _authenticate_ws(token)
    if error:
        await websocket.close(code=4001, reason=error)
        return

    # Verify brand access
    has_access = await _verify_brand_access(user.id, brand_id)
    if not has_access:
        await websocket.close(code=4003, reason="No access to this brand workspace")
        return

    await websocket.accept()

    # Send connection confirmed
    await websocket.send_json({
        "event": "connection.established",
        "job_id": job_id,
        "brand_id": brand_id,
        "user_id": user.id,
        "message": "Connected to generation progress stream",
    })

    try:
        # Subscribe to Redis PubSub channel
        redis = await generation_events._get_redis()

        if redis:
            channel = generation_events._channel(brand_id, job_id)
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)

            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        data = json.loads(message["data"])
                        await websocket.send_json(data)

                        # Close on terminal events
                        if data.get("event") in [
                            GenerationEvent.COMPLETED.value,
                            GenerationEvent.FAILED.value,
                        ]:
                            break
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
        else:
            # Fallback: poll job status
            from app.models.db import CatalogJob
            while True:
                async with async_session_maker() as db:
                    result = await db.execute(
                        select(CatalogJob).where(CatalogJob.job_id == job_id)
                    )
                    job = result.scalars().first()

                    if job:
                        await websocket.send_json({
                            "event": "generation.progress",
                            "job_id": job_id,
                            "status": job.status,
                            "completed": job.completed_skus or 0,
                            "total": job.total_skus or 1,
                            "percent": int((job.completed_skus or 0) / max(job.total_skus or 1, 1) * 100),
                        })

                        if job.status in ["completed", "failed", "partial"]:
                            await websocket.send_json({
                                "event": f"generation.{job.status}",
                                "job_id": job_id,
                                "status": job.status,
                            })
                            break

                await asyncio.sleep(2)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from job {job_id} progress stream")


@router.websocket("/ws/brand/{brand_id}/events")
async def brand_events_ws(
    brand_id: int,
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    Brand-level WebSocket for all generation events.
    Multi-tenant isolated per brand_id.
    """
    user, error = await _authenticate_ws(token)
    if error:
        await websocket.close(code=4001, reason=error)
        return

    has_access = await _verify_brand_access(user.id, brand_id)
    if not has_access:
        await websocket.close(code=4003, reason="No access to this brand workspace")
        return

    await websocket.accept()

    await websocket.send_json({
        "event": "connection.established",
        "brand_id": brand_id,
        "user_id": user.id,
        "message": "Connected to brand event stream",
    })

    try:
        redis = await generation_events._get_redis()

        if redis:
            channel = generation_events._brand_channel(brand_id)
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)

            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        await websocket.send_json(json.loads(message["data"]))
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
        else:
            # Keep alive fallback
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"event": "ping", "brand_id": brand_id})

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from brand {brand_id} event stream")


# ========================== REST Endpoints =======================

@router.get("/generation/{job_id}/steps")
async def get_generation_steps(
    job_id: str,
    workflow: str = "catalog",
    current_user: User = Depends(get_current_user),
):
    """Get generation step taxonomy for a workflow."""
    steps = GENERATION_STEPS.get(workflow, GENERATION_STEPS["catalog"])
    return {
        "job_id": job_id,
        "workflow": workflow,
        "steps": steps,
        "total_steps": len(steps),
    }


@router.post("/generation/{job_id}/emit")
async def emit_generation_event(
    job_id: str,
    event: str,
    brand_id: int,
    step: Optional[str] = None,
    percent: Optional[int] = None,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Emit a generation event manually (internal/admin use)."""
    has_access = await _verify_brand_access(current_user.id, brand_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this brand.")

    await generation_events.publish(
        brand_id=brand_id,
        job_id=job_id,
        event=GenerationEvent(event),
        data={
            "step": step,
            "percent": percent or 0,
            "reason": reason,
        }
    )
    return {"status": "published", "event": event, "job_id": job_id}
