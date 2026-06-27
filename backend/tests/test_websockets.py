import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.services.connection_manager import ConnectionManager


@pytest.mark.asyncio
async def test_connection_manager_connect_disconnect():
    cm = ConnectionManager()
    mock_ws = AsyncMock()
    await cm.connect(mock_ws, brand_id=1, user_id=10)
    assert cm.get_brand_connection_count(1) == 1
    cm.disconnect(mock_ws)
    assert cm.get_brand_connection_count(1) == 0


@pytest.mark.asyncio
async def test_connection_manager_multitenant_isolation():
    cm = ConnectionManager()
    ws_a = AsyncMock()
    ws_b = AsyncMock()
    await cm.connect(ws_a, brand_id=1, user_id=1)
    await cm.connect(ws_b, brand_id=2, user_id=2)
    await cm.broadcast_to_brand(1, {"type": "asset.uploaded", "asset_id": 99})
    ws_a.send_text.assert_called_once()
    ws_b.send_text.assert_not_called()
    cm.disconnect(ws_a)
    cm.disconnect(ws_b)


@pytest.mark.asyncio
async def test_connection_manager_handles_dead_connection():
    cm = ConnectionManager()
    ws_dead = AsyncMock()
    ws_dead.send_text.side_effect = Exception("Connection closed")
    await cm.connect(ws_dead, brand_id=1, user_id=5)
    await cm.broadcast_to_brand(1, {"type": "ping"})
    assert cm.get_brand_connection_count(1) == 0


@pytest.mark.asyncio
async def test_connection_manager_broadcast_correct_payload():
    cm = ConnectionManager()
    ws = AsyncMock()
    await cm.connect(ws, brand_id=1, user_id=1)
    await cm.broadcast_to_brand(1, {"type": "job.completed", "job_id": 1, "brand_id": 1})
    ws.send_text.assert_called_once()
    sent = json.loads(ws.send_text.call_args[0][0])
    assert sent["type"] == "job.completed"
    cm.disconnect(ws)


class MockSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_websocket_rejects_invalid_token(test_data: dict, db_session):
    from app.main import app
    brand = test_data["brand"]
    with patch("app.routers.websockets.async_session_maker", return_value=MockSessionContext(db_session)):
        with TestClient(app) as tc:
            with pytest.raises(Exception):
                with tc.websocket_connect(f"/api/v1/ws/events?token=invalid_token&brand_id={brand.id}"):
                    pass


@pytest.mark.asyncio
async def test_websocket_successful_auth_and_welcome(test_data: dict, db_session):
    from app.main import app
    from app.middleware.auth import create_access_token
    brand = test_data["brand"]
    editor = test_data["users"]["editor"]
    token = create_access_token({"sub": editor.email})
    
    with patch("app.routers.websockets.async_session_maker", return_value=MockSessionContext(db_session)):
        with TestClient(app) as tc:
            with tc.websocket_connect(f"/api/v1/ws/events?token={token}&brand_id={brand.id}") as websocket:
                data = websocket.receive_text()
                welcome_msg = json.loads(data)
                assert welcome_msg["type"] == "connected"
                assert welcome_msg["brand_id"] == brand.id
                assert welcome_msg["user_id"] == editor.id

