import pytest
import json
from unittest.mock import patch
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import Asset, AIJob
from app.worker import is_safe_url, dispatch_webhook
from app.main import app
from app.middleware.rate_limit import RateLimiter

def test_is_safe_url_validation():
    # Safe public URLs should return True
    # Note: socket lookup on 'google.com' might fail offline. Let's mock socket.getaddrinfo for these.
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("8.8.8.8", 80))]):
        assert is_safe_url("http://google.com") is True
        assert is_safe_url("https://dns.google") is True

    # Unsafe URLs should return False
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 80))]):
        assert is_safe_url("http://127.0.0.1") is False
        assert is_safe_url("http://localhost") is False

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("169.254.169.254", 80))]):
        assert is_safe_url("http://169.254.169.254/latest/meta-data") is False

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("10.0.0.1", 80))]):
        assert is_safe_url("http://10.0.0.1") is False

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("192.168.1.1", 80))]):
        assert is_safe_url("http://192.168.1.1/admin") is False

    # Invalid schemes or strings
    assert is_safe_url("ftp://google.com") is False
    assert is_safe_url("just-a-string") is False


def test_dispatch_webhook_ssrf_aborted():
    # Triggering dispatch_webhook with private URL should raise ValueError
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 80))]):
        with pytest.raises(ValueError) as exc:
            dispatch_webhook("http://127.0.0.1/callback", {"test": "data"})
        assert "SSRF warning: Unsafe webhook URL" in str(exc.value)


@pytest.mark.asyncio
async def test_assets_pagination(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    # Create 5 test assets
    for i in range(5):
        asset = Asset(
            brand_id=brand.id,
            name=f"Asset {i}",
            filename=f"file_{i}.png",
            storage_path=f"/uploads/file_{i}.png",
            asset_type="image",
            meta={}
        )
        db_session.add(asset)
    await db_session.commit()

    # Query with limit 2, offset 0
    res = await client.get(f"/api/v1/assets?brand_id={brand.id}&limit=2&offset=0", headers=editor_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["name"] == "Asset 0"
    assert data[1]["name"] == "Asset 1"

    # Query with limit 2, offset 2
    res = await client.get(f"/api/v1/assets?brand_id={brand.id}&limit=2&offset=2", headers=editor_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["name"] == "Asset 2"
    assert data[1]["name"] == "Asset 3"

    # Query with limit 2, offset 4
    res = await client.get(f"/api/v1/assets?brand_id={brand.id}&limit=2&offset=4", headers=editor_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "Asset 4"


@pytest.mark.asyncio
async def test_jobs_pagination(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_user = test_data["users"]["editor"]
    editor_headers = test_data["get_headers"]("editor")

    # Create 5 jobs
    for i in range(5):
        job = AIJob(
            user_id=editor_user.id,
            brand_id=brand.id,
            workflow_template_id=workflow.id,
            status="pending",
            job_type="generation",
            inputs={},
            outputs={}
        )
        db_session.add(job)
    await db_session.commit()

    # Query with limit 3, offset 0
    # Note: list_jobs returns jobs ordered by created_at desc.
    # Let's verify we get 3 jobs
    res = await client.get(f"/api/v1/jobs?brand_id={brand.id}&limit=3&offset=0", headers=editor_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 3

    # Query with limit 3, offset 3
    res = await client.get(f"/api/v1/jobs?brand_id={brand.id}&limit=3&offset=3", headers=editor_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2


def test_rate_limiting_dependencies():
    # Verify that RateLimiter dependencies are present on the new routes
    generate_route = None
    search_route = None
    similar_route = None

    for route in app.routes:
        if route.path == "/api/v1/jobs/generate" and "POST" in route.methods:
            generate_route = route
        elif route.path == "/api/v1/assets/search" and "GET" in route.methods:
            search_route = route
        elif route.path == "/api/v1/assets/search/similar" and "POST" in route.methods:
            similar_route = route

    assert generate_route is not None
    assert search_route is not None
    assert similar_route is not None

    # Check for RateLimiter in dependencies
    def has_rate_limiter(route):
        for dep in route.dependencies:
            # Check dependency type or name
            if isinstance(dep.dependency, RateLimiter):
                return True
        return False

    assert has_rate_limiter(generate_route), "Generate route is missing RateLimiter dependency"
    assert has_rate_limiter(search_route), "Search route is missing RateLimiter dependency"
    assert has_rate_limiter(similar_route), "Search similar route is missing RateLimiter dependency"
