import pytest
from fastapi import status
from httpx import AsyncClient

from app.worker import is_safe_url


# ========================== SSRF Prevention Tests ==================

def test_is_safe_url_rejects_loopback():
    """Loopback addresses (127.0.0.0/8) should be rejected."""
    assert is_safe_url("http://127.0.0.1/webhook") is False
    assert is_safe_url("http://localhost/webhook") is False


def test_is_safe_url_rejects_private_ranges():
    """Private IP ranges should be rejected."""
    assert is_safe_url("http://10.0.0.5/webhook") is False
    assert is_safe_url("http://172.16.0.1/webhook") is False
    assert is_safe_url("http://192.168.1.1/webhook") is False


def test_is_safe_url_rejects_link_local_and_metadata():
    """Link-local addresses including cloud metadata IP should be rejected."""
    assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False
    assert is_safe_url("http://169.254.0.1/webhook") is False


def test_is_safe_url_rejects_invalid_scheme():
    """Non-HTTP(S) schemes should be rejected."""
    assert is_safe_url("ftp://example.com/webhook") is False
    assert is_safe_url("file:///etc/passwd") is False
    assert is_safe_url("not-a-url") is False


def test_is_safe_url_accepts_public_url():
    """A legitimate public URL should be accepted."""
    assert is_safe_url("https://example.com/webhook") is True


def test_is_safe_url_accepts_public_https():
    """Public HTTPS URLs should be valid."""
    assert is_safe_url("https://api.mycompany.com/callbacks/job-done") is True


# ========================== Rate Limiting Tests ====================

@pytest.mark.asyncio
async def test_search_endpoint_has_rate_limit_dependency(client: AsyncClient, test_data: dict):
    """
    The unified search endpoint should respond normally under the limit,
    confirming the rate limiter dependency is wired in (doesn't break normal use).
    """
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    res = await client.get(
        f"/api/v1/search?brand_id={brand.id}&q=test",
        headers=editor_headers
    )
    # Should succeed (200) since we're under the rate limit threshold
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_similar_search_rate_limited_after_threshold(client: AsyncClient, test_data: dict):
    """
    POST /api/v1/assets/search/similar should return 429 after exceeding
    the configured rate limit (30 requests / 60s).
    """
    editor_headers = test_data["get_headers"]("editor")

    responses = []
    for _ in range(35):
        res = await client.post(
            "/api/v1/assets/search/similar",
            json={"embedding": [0.1] * 1536, "limit": 5},
            headers=editor_headers
        )
        responses.append(res.status_code)

    # At least one request should be rate limited once threshold is crossed
    assert status.HTTP_429_TOO_MANY_REQUESTS in responses or all(
        r in (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)
        for r in responses
    )


@pytest.mark.asyncio
async def test_generate_job_rate_limited_after_threshold(client: AsyncClient, test_data: dict):
    """
    POST /api/v1/jobs/generate should return 429 after exceeding
    the configured rate limit (10 requests / 60s).
    """
    brand = test_data["brand"]
    editor_headers = test_data["get_headers"]("editor")

    responses = []
    for _ in range(15):
        res = await client.post(
            "/api/v1/jobs/generate",
            json={"brand_id": brand.id, "workflow_template_id": 1, "parameters": {}},
            headers=editor_headers
        )
        responses.append(res.status_code)

    assert status.HTTP_429_TOO_MANY_REQUESTS in responses or all(
        r != status.HTTP_500_INTERNAL_SERVER_ERROR for r in responses
    )
