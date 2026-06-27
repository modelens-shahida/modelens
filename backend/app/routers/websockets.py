import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import select
from app.models.db import async_session_maker, User, Brand, BrandMember
from app.services.connection_manager import manager

logger = logging.getLogger("modelens.websocket")

router = APIRouter(
    prefix="/api/v1/ws",
    tags=["WebSockets"],
)


async def _authenticate_websocket(token: str) -> tuple[User, None] | tuple[None, str]:
    """
    Validate JWT token and return the authenticated user.
    Returns (user, None) on success or (None, error_message) on failure.
    """
    try:
        from jose import jwt, JWTError
        from app.config import settings
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        if not email:
            return None, "Invalid token payload"

        async with async_session_maker() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            if not user:
                return None, "User not found"
            return user, None
    except Exception as e:
        return None, f"Authentication failed: {str(e)}"


async def _verify_brand_access(user_id: int, brand_id: int) -> bool:
    """Check if user has access to the brand workspace."""
    async with async_session_maker() as db:
        # Check owner
        owner = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.owner_id == user_id))
        if owner.scalars().first():
            return True
        # Check member
        member = await db.execute(select(BrandMember).where(
            BrandMember.brand_id == brand_id,
            BrandMember.user_id == user_id
        ))
        return member.scalars().first() is not None


@router.websocket("/events")
async def websocket_events(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication"),
    brand_id: int = Query(..., description="Brand workspace to subscribe to"),
):
    """
    Real-time event WebSocket endpoint.
    Connect with: ws://.../api/v1/ws/events?token=<jwt>&brand_id=<id>
    """
    # 1. Authenticate
    user, error = await _authenticate_websocket(token)
    if error:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning(f"[WS] Auth failed: {error}")
        return

    # 2. Verify brand access
    has_access = await _verify_brand_access(user.id, brand_id)
    if not has_access:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning(f"[WS] User {user.id} denied access to brand {brand_id}")
        return

    # 3. Connect
    await manager.connect(websocket, brand_id, user.id)

    try:
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "brand_id": brand_id,
            "user_id": user.id,
            "message": "Connected to Mode Lens real-time events"
        }))

        # 4. Ping/pong heartbeat loop
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send server-side ping
                await websocket.send_text(json.dumps({"type": "ping"}))
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"[WS] Error in connection loop: {e}")
                break

    finally:
        manager.disconnect(websocket)
