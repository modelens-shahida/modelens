import json
import asyncio
from typing import Dict, Set
from fastapi import WebSocket
import logging

logger = logging.getLogger("modelens.websocket")


class ConnectionManager:
    """
    Manages active WebSocket connections scoped by brand_id and user_id.
    Ensures users only receive events for their authorized brand workspaces.
    """

    def __init__(self):
        # brand_id -> set of WebSocket connections
        self._brand_connections: Dict[int, Set[WebSocket]] = {}
        # websocket -> (brand_id, user_id) mapping
        self._connection_meta: Dict[WebSocket, tuple] = {}

    async def connect(self, websocket: WebSocket, brand_id: int, user_id: int):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        if brand_id not in self._brand_connections:
            self._brand_connections[brand_id] = set()
        self._brand_connections[brand_id].add(websocket)
        self._connection_meta[websocket] = (brand_id, user_id)
        logger.info(f"[WS] User {user_id} connected to brand {brand_id} channel.")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        meta = self._connection_meta.pop(websocket, None)
        if meta:
            brand_id, user_id = meta
            if brand_id in self._brand_connections:
                self._brand_connections[brand_id].discard(websocket)
                if not self._brand_connections[brand_id]:
                    del self._brand_connections[brand_id]
            logger.info(f"[WS] User {user_id} disconnected from brand {brand_id} channel.")

    async def broadcast_to_brand(self, brand_id: int, message: dict):
        """Broadcast a message to all active connections for a brand."""
        connections = self._brand_connections.get(brand_id, set()).copy()
        if not connections:
            return
        payload = json.dumps(message)
        disconnected = set()
        for websocket in connections:
            try:
                await websocket.send_text(payload)
            except Exception as e:
                logger.warning(f"[WS] Failed to send to connection: {e}")
                disconnected.add(websocket)
        for ws in disconnected:
            self.disconnect(ws)

    def get_brand_connection_count(self, brand_id: int) -> int:
        return len(self._brand_connections.get(brand_id, set()))


# Singleton instance
manager = ConnectionManager()
