import pytest
from unittest.mock import patch, AsyncMock
from httpx import Response, ConnectError, TimeoutException
from fastapi import status

@pytest.mark.asyncio
async def test_proxy_unauthenticated(client):
    """Proxy endpoints must require a valid JWT token."""
    res = await client.get("/api/v1/templates/list")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    res2 = await client.post("/api/v1/generations/new")
    assert res2.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_proxy_templates_success(client, test_data):
    """Proxy templates request should successfully forward and inject headers."""
    owner_headers = test_data["get_headers"]("owner")
    
    mock_response = Response(
        status_code=200,
        content=b'{"templates": [{"id": "t1", "name": "Classic Tryon"}]}',
        headers={"content-type": "application/json"}
    )

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.request.return_value = mock_response

    with patch("app.routers.templates_proxy.AsyncClient", return_value=mock_client) as mock_class:
        res = await client.get("/api/v1/templates/list?active=true", headers=owner_headers)
        assert res.status_code == 200
        assert res.json() == {"templates": [{"id": "t1", "name": "Classic Tryon"}]}

        # Verify that internal request was called with expected arguments
        mock_client.request.assert_called_once()
        called_kwargs = mock_client.request.call_args[1]
        
        # Verify injected headers
        headers = called_kwargs["headers"]
        assert "X-User-Id" in headers
        assert "X-User-Email" in headers
        assert "X-User-Role" in headers
        assert called_kwargs["method"] == "GET"
        assert called_kwargs["url"].endswith("v1/templates/list?active=true")


@pytest.mark.asyncio
async def test_proxy_templates_connect_error(client, test_data):
    """Should return 502 Bad Gateway if NestJS service is offline."""
    owner_headers = test_data["get_headers"]("owner")

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.request.side_effect = ConnectError("Connection refused")

    with patch("app.routers.templates_proxy.AsyncClient", return_value=mock_client):
        res = await client.get("/api/v1/templates/list", headers=owner_headers)
        assert res.status_code == status.HTTP_502_BAD_GATEWAY
        assert "unavailable" in res.json()["detail"]


@pytest.mark.asyncio
async def test_proxy_templates_timeout(client, test_data):
    """Should return 504 Gateway Timeout if proxy request times out."""
    owner_headers = test_data["get_headers"]("owner")

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.request.side_effect = TimeoutException("Request timed out")

    with patch("app.routers.templates_proxy.AsyncClient", return_value=mock_client):
        res = await client.post("/api/v1/generations/create", json={"templateId": "1"}, headers=owner_headers)
        assert res.status_code == status.HTTP_504_GATEWAY_TIMEOUT
        assert "timed out" in res.json()["detail"]
